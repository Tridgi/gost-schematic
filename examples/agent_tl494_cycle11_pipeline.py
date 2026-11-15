"""Cycle11 real frozen 23/15/62 → native MCP catalog → strict trusted CLI.

Exactly the user's immutable *physical source*, NOT a synthetic source or
newly routed TL494 sheet. This is an evidence-only deterministic pipeline.
Owner data paths are trusted CLI-only inputs, NOT MCP tools/permissions.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.design_assistant import (
    TL494_FROZEN_SOURCE_SHA,
    TL494_REQUIRED_PARTS,
)
from gost_schematic.agent_project.owner_api_locks import verify_pinned_owner_api_files
from gost_schematic.agent_project.owner_source_contract import (
    verify_cycle11_owner_bridge_surfaces,
    verify_frozen_owner_fixture,
    verify_owner_reversible_display,
    verify_pinned_owner_headers,
)


_REQUIRED_CATALOG_TOOLS = frozenset({
    "schematic_catalog_search", "schematic_catalog_select",
    "schematic_catalog_preview", "schematic_tl494_selection_profile",
    "schematic_tl494_pin_alias",
})
# Strict allowlist: a fake "readOnlyHint" on a new, innocuously named tool
# cannot extend agent authority. Any genuine new read tool needs code review.
_APPROVED_READONLY_TOOLS = frozenset({
    "schematic_render_overview",
    "schematic_inspect_region",
    "schematic_inspect_component",
    "schematic_inspect_connection",
    "schematic_get_diagnostics",
    "schematic_list_views",
    "schematic_list_projects",
    "schematic_open_project",
    "schematic_describe_project",
    "schematic_validate_project",
    "schematic_catalog_search",
    "schematic_catalog_preview",
    "schematic_catalog_select",
    "schematic_tl494_selection_profile",
    "schematic_tl494_pin_alias",
    "schematic_preflight_project",
    "schematic_preview_placement",
    "schematic_render_project",
})
_FORBIDDEN_WRITE_VERBS = (
    "commit", "connect_pins", "delete", "edit", "write",
    "transaction", "execute", "create", "move", "route",
    "apply", "update", "rename", "undo", "redo", "import",
)


def _assert_readonly_tool_registry(tools: dict) -> None:
    if not _REQUIRED_CATALOG_TOOLS <= set(tools):
        raise AssertionError("Missing mandatory native read-only catalog tools")
    if any(
        item.annotations is None
        or item.annotations.readOnlyHint is not True
        or item.annotations.destructiveHint is not False
        or item.annotations.openWorldHint is not False
        for item in tools.values()
    ):
        raise AssertionError("Unsafe MCP tool exposed in read-only agent server")
    if any(
        token in name.lower()
        for name in tools
        for token in _FORBIDDEN_WRITE_VERBS
    ):
        raise AssertionError("Agent write tool unexpectedly registered")
    if set(tools) - _APPROVED_READONLY_TOOLS:
        raise AssertionError("Agent write tool unexpectedly registered: unknown tool")


def _decoded(reply):
    if reply.isError:
        raise AssertionError("Real read-only MCP call returned an error")
    if isinstance(reply.structuredContent, dict):
        return reply.structuredContent
    return json.loads(next(x.text for x in reply.content if isinstance(x, TextContent)))


async def _native_mcp_catalog(output: Path, source: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gost_schematic.mcp_server"], env=env,
    )
    results = {}
    async with stdio_client(params) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            _assert_readonly_tool_registry(tools)
            profile = _decoded(await client.call_tool(
                "schematic_tl494_selection_profile", {"api_version": 1},
            ))
            model_refs = {row["reference"]: row["part_id"]
                          for row in source["source_components"]}
            for row in profile["required_variants"]:
                ref = row["reference"]
                if model_refs.get(ref) != row["required_part_id"]:
                    raise AssertionError("Original source UGO profile drifts")
            if len(profile["required_variants"]) != 13:
                raise AssertionError("Source-selected real catalog matrix incomplete")

            for part_id in sorted(set(TL494_REQUIRED_PARTS.values())):
                search = _decoded(await client.call_tool(
                    "schematic_catalog_search",
                    {"semantic_query": part_id, "api_version": 1},
                ))
                candidates = search["candidates"]
                if len(candidates) != 1 or candidates[0]["part_id"] != part_id:
                    raise AssertionError("Semantic query did not resolve exact UGO")
                item = candidates[0]
                lock = source["installed_part_locks"][
                    next(ref for ref, kind in TL494_REQUIRED_PARTS.items()
                         if kind == part_id)
                ]
                if (item["part_sha256"] != lock["part_sha256"]
                        or item["symbol_sha256"] != lock["symbol_sha256"]):
                    raise AssertionError("True source catalog SHA does not match MCP")
                selected = _decoded(await client.call_tool(
                    "schematic_catalog_select", {
                        "part_id": part_id, "part_sha256": item["part_sha256"],
                        "symbol_sha256": item["symbol_sha256"], "api_version": 1,
                    },
                ))
                if (selected["connection_authorized"]
                        or any(p["pin_ref"] is not None
                               for p in selected["physical_pin_templates"])):
                    raise AssertionError("Catalog template must NOT fake PinRefs")
                render = await client.call_tool(
                    "schematic_catalog_preview", {
                        "part_id": part_id, "part_sha256": item["part_sha256"],
                        "symbol_sha256": item["symbol_sha256"], "api_version": 1,
                    },
                )
                if render.isError:
                    raise AssertionError("MCP source-lock preview failed")
                texts = [x for x in render.content if isinstance(x, TextContent)]
                images = [x for x in render.content if isinstance(x, ImageContent)]
                if len(images) != 1 or len(texts) != 2:
                    raise AssertionError("Source preview must return real native SVG+PNG")
                data = json.loads(texts[0].text)
                svg = texts[1].text.encode("utf-8")
                png = base64.b64decode(images[0].data, validate=True)
                if (hashlib.sha256(svg).hexdigest() != data["svg_sha256"]
                        or hashlib.sha256(png).hexdigest() != data["png_sha256"]
                        or data["preview_lock_status"] != "EXACT_CATALOG_LOCK_MATCH"):
                    raise AssertionError("Real catalog SVG/PNG digest mismatch")
                (output / (part_id + ".svg")).write_bytes(svg)
                (output / (part_id + ".png")).write_bytes(png)
                results[part_id] = {
                    "part_sha256": item["part_sha256"],
                    "symbol_sha256": item["symbol_sha256"],
                    "real_svg_sha256": data["svg_sha256"],
                    "real_png_sha256": data["png_sha256"],
                    "physical_catalog_templates": len(selected["physical_pin_templates"]),
                    "normative_approval": False,
                }

            for full, short, number in (("FEEDBACK", "FB", "3"),
                                         ("OUTPUT CTRL", "OC", "13")):
                alias = _decoded(await client.call_tool(
                    "schematic_tl494_pin_alias",
                    {"full_name": full, "api_version": 1},
                ))
                if alias["display_alias"] != short or alias["physical_number"] != number:
                    raise AssertionError("Real physical TL494 editorial alias changed")
    return results


def _read_trusted(path: Path) -> bytes:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise AssertionError("Untrusted redirected source path")
    if not path.is_file() or path.stat().st_size > 256_000:
        raise AssertionError("Missing/bounded real pinned owner source")
    return path.read_bytes()


def _request(source: dict) -> dict:
    return {
        "schema_version": 1,
        "intent": "tl494_reconstruction",
        "source_sha": TL494_FROZEN_SOURCE_SHA,
        "project_id": None, "expected_revision": None,
        "expected_generation": None,
        "components": [
            {"reference": c["reference"],
             "source_part_id": c["part_id"], "nominal_si": c["nominal_si"],
             "part_id": c["part_id"]
             if c["reference"] in TL494_REQUIRED_PARTS else None,
             "part_sha256": (source["installed_part_locks"][c["reference"]]["part_sha256"]
                             if c["reference"] in TL494_REQUIRED_PARTS else None),
             "symbol_sha256": (source["installed_part_locks"][c["reference"]]["symbol_sha256"]
                               if c["reference"] in TL494_REQUIRED_PARTS else None)}
            for c in source["source_components"]
        ],
        "nets": [
            {"name": name,
             "members": [{"reference": p.rsplit(".", 1)[0],
                          "number": p.rsplit(".", 1)[1]} for p in contacts]}
            for name, contacts in source["source_nets"].items()
        ],
        "outputs": ["bom", "netlist", "drc", "svg_clean",
                    "svg_diagnostic", "png_300dpi"],
        "max_route_attempts": 3,
    }


def _cli(request: dict) -> tuple[int, dict]:
    r = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input=json.dumps(request, sort_keys=True).encode(),
        capture_output=True, check=False,
        env={key: val for key, val in os.environ.items()
             if not key.startswith("GSE_P11_")},
    )
    if r.stderr:
        raise AssertionError("Strict read-only CLI had unexpected stderr")
    return r.returncode, json.loads(r.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-fixture", type=Path, required=True)
    parser.add_argument("--ic-header", type=Path, required=True)
    parser.add_argument("--recon-header", type=Path, required=True)
    parser.add_argument("--ic-integration", type=Path, required=True)
    parser.add_argument("--recon-ti-bridge", type=Path, required=True)
    parser.add_argument("--recon-b-continuation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    catalog = CatalogResolver()
    owner_files = {
        "ic_frozen_fixture": _read_trusted(args.owner_fixture),
        "ic_tl494": _read_trusted(args.ic_header),
        "ic_integration": _read_trusted(args.ic_integration),
        "recon_native": _read_trusted(args.recon_header),
        "recon_ti_bridge": _read_trusted(args.recon_ti_bridge),
        "recon_b_continuation": _read_trusted(args.recon_b_continuation),
    }
    owner_locks = verify_pinned_owner_api_files(owner_files)
    source = verify_frozen_owner_fixture(owner_files["ic_frozen_fixture"], catalog)
    owner = verify_pinned_owner_headers(
        owner_files["ic_tl494"], owner_files["recon_native"],
    )
    display = verify_owner_reversible_display(source, owner)
    live_bridges = verify_cycle11_owner_bridge_surfaces(
        owner_files["ic_integration"],
        owner_files["recon_ti_bridge"],
        owner_files["recon_b_continuation"],
        source,
    )
    output = args.out
    if output.exists() and (
        output.is_symlink()
        or (hasattr(output, "is_junction") and output.is_junction())
    ):
        raise AssertionError("Redirected evidence directory is forbidden")
    output.mkdir(parents=True, exist_ok=True)
    samples = asyncio.run(_native_mcp_catalog(output, source))
    req = _request(source)
    code, report = _cli(req)
    if (code != 2 or report["status"] != "BLOCKED_SOURCE_NOT_IMPORTABLE"
            or report["submitted_pinref_count"] != 62
            or report["component_count"] != 23 or report["net_count"] != 15
            or report["source_membership_verified"]
            or not report["frozen_original_nominals_verified"]
            or not report["frozen_original_bom_part_ids_verified"]):
        raise AssertionError("Synthetic or incomplete TL494 falsely accepted")
    missing = json.loads(json.dumps(req))
    missing["nets"].pop()
    negative_code, negative = _cli(missing)
    if negative_code != 3 or negative["code"] != "SOURCE_NET_INVENTORY_INCOMPLETE":
        raise AssertionError("Missing real physical Net did not fail closed")
    output_request = output / "source-typed-request.json"
    output_request.write_text(
        json.dumps(req, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    artifact = {
        "status": "BLOCKED_15NET_NOT_ROUTED",
        "schema_version": 1, "autonomous_codex_model_run": False,
        "transport": "native real stdio MCP ClientSession and strict CLI subprocess",
        "mcp_write_tool_enabled": False, "real_source_23_15_62_verified": True,
        "source_git_sha": TL494_FROZEN_SOURCE_SHA,
        "source_fixture_git_blob_sha1": source["source_fixture_git_blob_sha1"],
        "source_typed_manifest_sha256": source["source_typed_manifest_sha256"],
        "source_components_count": source["component_count"],
        "source_nets_count": source["net_count"],
        "source_pinrefs_count": source["source_physical_pinref_memberships"],
        "da1_16_contacts": source["da1_all_16_physical_pins"],
        "physical_nominal_strings_preserved": source["source_nominals_preserved_as_literals"],
        "real_source_nets": source["source_nets"],
        "owner_part_id_bridge": owner,
        "owner_cycle11_bridge": live_bridges,
        "cycle12_exact_owner_api_locks": owner_locks,
        "reversible_net_display": display,
        "real_UGO_samples": samples,
        "typed_readiness_exit": code,
        "typed_readiness": report,
        "missing_net_reject_exit": negative_code,
        "missing_net_reject_code": negative["code"],
        "route_completed_nets": 0,
        "route_tool_called": False,
        "new_print_svg_generated": False,
        "new_print_png300dpi_generated": False,
        "print_ready": False,
        "blocks": [
            "SOURCE_BRIDGE_TI_PART_NOT_IN_P11",
            "OWNER_RECON_ALIAS_NOT_PERSISTED_P11",
            "15NET_NOT_ROUTED",
            "FULL_INK_DRC_NOT_VERIFIED",
            "MODEL_AGENT_EXEC_NOT_AUTHORIZED",
        ],
    }
    (output / "source-pipeline-report.json").write_text(
        json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
