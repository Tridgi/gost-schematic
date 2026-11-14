"""Reproducible native MCP catalog/UGO and saved E3 print-subset diagnostic proof.

Trusted Python bootstraps a six-part E3 because a full physical TL494CN
device adapter is NOT in the P1.1 installed catalog. A real separate
MCP ClientSession then chooses the 12 exact TL494 UGO variants from
the installed catalog, requests genuine SVG/PNG examples, and invokes
immutable preflight diagnostics on the saved six-part project. This is
NOT a Codex model run, a TL494 circuit generation, or full print DRC.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent

from gost_schematic.agent_project.trusted_import import import_six_part


def decoded(response):
    if response.isError:
        raise AssertionError("MCP returned error: " + str(response.content))
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    texts = [x.text for x in response.content if isinstance(x, TextContent)]
    if not texts:
        raise AssertionError("Expected structured MCP tool response")
    return json.loads(texts[0])


async def run_native_client(workspace: Path, project_id: str, revision: str) -> dict:
    env = {key: val for key, val in os.environ.items() if not key.startswith("GSE_P11_")}
    env.update({
        "GSE_P11_READONLY_ENABLED": "1",
        "GSE_P11_WORKSPACE": str(workspace.resolve()),
        "GSE_P11_ALLOWED_PROJECT_IDS": project_id,
    })
    settings = StdioServerParameters(
        command=sys.executable, args=["-m", "gost_schematic.mcp_server"],
        env=env,
    )
    output = workspace / "client-evidence"
    if output.is_symlink() or (hasattr(output, "is_junction") and output.is_junction()):
        raise AssertionError("Unsafe client evidence path")
    output.mkdir(exist_ok=True)

    async with stdio_client(settings) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            required = {
                "schematic_catalog_search", "schematic_catalog_preview",
                "schematic_tl494_selection_profile", "schematic_tl494_pin_alias",
                "schematic_preflight_project", "schematic_render_project",
            }
            if not required <= tools.keys():
                raise AssertionError(f"Native MCP tools absent: {required - tools.keys()}")
            for name in required:
                if tools[name].annotations is None or tools[name].annotations.readOnlyHint is not True:
                    raise AssertionError("Wrong MCP read-only tool annotations: " + name)
            profile = decoded(await client.call_tool(
                "schematic_tl494_selection_profile", {},
            ))
            if len(profile["required_variants"]) != 12:
                raise AssertionError("Incomplete source-specific TL494 UGO matrix")
            if profile["tl494_device_catalog"] != "NOT_IN_INSTALLED_P11_CATALOG":
                raise AssertionError("Device provenance gate has changed; re-review")
            sampled = {}
            for part_id in sorted({
                row["required_part_id"] for row in profile["required_variants"]
            }):
                search = decoded(await client.call_tool(
                    "schematic_catalog_search", {"semantic_query": part_id},
                ))
                if [x["part_id"] for x in search["candidates"]] != [part_id]:
                    raise AssertionError("Unexpected exact symbol variant")
                reply = await client.call_tool(
                    "schematic_catalog_preview", {"part_id": part_id},
                )
                if reply.isError:
                    raise AssertionError("Failed genuine installed symbol preview")
                pictures = [x for x in reply.content if isinstance(x, ImageContent)]
                texts = [x for x in reply.content if isinstance(x, TextContent)]
                if len(pictures) != 1 or len(texts) != 2:
                    raise AssertionError("Missing native PNG/SVG for catalog glyph")
                meta = json.loads(texts[0].text)
                png = base64.b64decode(pictures[0].data, validate=True)
                svg = texts[1].text
                if (hashlib.sha256(png).hexdigest() != meta["png_sha256"]
                        or hashlib.sha256(svg.encode()).hexdigest() != meta["svg_sha256"]):
                    raise AssertionError("Ungrounded catalog preview image")
                (output / (part_id + ".svg")).write_text(svg, encoding="utf-8")
                (output / (part_id + ".png")).write_bytes(png)
                sampled[part_id] = {
                    "symbol_sha256": meta["symbol_sha256"],
                    "normative_status": meta["symbol_status"],
                    "svg_sha256": meta["svg_sha256"],
                    "png_sha256": meta["png_sha256"],
                    "physical_pin_count": len(meta["physical_pin_refs"]),
                    "normative_transforms_unapproved": (
                        meta["normative_transform_approval"] == "NOT_VERIFIED_PER_POSE"
                    ),
                }
            aliases = {}
            for original in ("FEEDBACK", "OUTPUT CTRL"):
                response = decoded(await client.call_tool(
                    "schematic_tl494_pin_alias", {"full_name": original},
                ))
                aliases[original] = response
            if aliases["FEEDBACK"]["display_alias"] != "FB":
                raise AssertionError("Unexpected full-name FEEDBACK truncation")
            if aliases["OUTPUT CTRL"]["display_alias"] != "OC":
                raise AssertionError("Unexpected OUTPUT CTRL abbreviation")
            before = decoded(await client.call_tool(
                "schematic_preflight_project", {
                    "project_id": project_id, "revision": revision, "profile": "none",
                },
            ))
            contrast = decoded(await client.call_tool(
                "schematic_preflight_project", {
                    "project_id": project_id, "revision": revision, "profile": "tl494",
                },
            ))
            if not any(
                d["code"] == "TL494_UGO_VARIANT_MISMATCH"
                for d in contrast["diagnostics"]
            ):
                raise AssertionError("TL494 mismatch was falsely accepted")
            if before["print_ready"] or contrast["print_ready"]:
                raise AssertionError("False full print/DRC acceptance")
            view = await client.call_tool("schematic_render_project", {
                "project_id": project_id, "revision": revision,
                "mode": "diagnostic", "reference": "C3",
                "target_dpi": 300, "include_svg": True,
            })
            images = [x for x in view.content if isinstance(x, ImageContent)]
            texts = [x for x in view.content if isinstance(x, TextContent)]
            if view.isError or len(images) != 1 or len(texts) != 2:
                raise AssertionError("Real project native diagnostic render unavailable")
            png = base64.b64decode(images[0].data, validate=True)
            meta = json.loads(texts[0].text)
            svg = texts[1].text
            if (hashlib.sha256(png).hexdigest() != meta["png_sha256"]
                    or hashlib.sha256(svg.encode()).hexdigest() != meta["view_svg_sha256"]):
                raise AssertionError("Stale diagnostics image mismatched project SHA")
            (output / "saved-c3-diagnostic.png").write_bytes(png)
            (output / "saved-c3-diagnostic.svg").write_text(svg, encoding="utf-8")
            return {
                "status": "READ_ONLY_PREVIEW_PARTIAL_PRINT_DRC",
                "transport": "real stdio MCP ClientSession",
                "python_bootstrap_not_mcp_write": True,
                "codex_cli_used": False,
                "project_revision": revision,
                "selected_physical_symbol_variants": sampled,
                "tl494_aliases": aliases,
                "tl494_profile": profile,
                "saved_sixpart_preflight": before,
                "misprofiled_sixpart_tl494_preflight": contrast,
                "project_diagnostic_svg_sha256": meta["view_svg_sha256"],
                "project_diagnostic_png_sha256": meta["png_sha256"],
                "no_physical_net_or_svg_mutation": True,
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--idempotency-key")
    arguments = parser.parse_args()
    project_id = arguments.project_id or str(uuid.uuid4())
    idempotency = arguments.idempotency_key or str(uuid.uuid4())
    snap = import_six_part(arguments.workspace, project_id=project_id,
                           idempotency_key=idempotency)
    head = arguments.workspace / "projects" / project_id / "HEAD.json"
    original_head = head.read_bytes()
    proof = asyncio.run(run_native_client(arguments.workspace, project_id,
                                          snap.project.revision))
    assert original_head == head.read_bytes(), "Read-only MCP modified original HEAD"
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
