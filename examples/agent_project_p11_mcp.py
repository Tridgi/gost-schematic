"""Live stdio MCP agent demonstration over a genuine saved E3 project.

The physical project is authored through trusted Python APIs by
examples.agent_project_p11.run (NOT by a writable Codex MCP tool).
A genuine MCP ClientSession then discovers and invokes five read-only
ProjectService-backed tools plus an existing fixed-specimen MCP Vision view.

Run:
  python -m examples.agent_project_p11_mcp --workspace output/p11-agent-mcp

This is executable agent-style tool orchestration, NOT a claimed live Codex
CLI trace or proof of arbitrary 40/64-pin project generation.
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

from examples.agent_project_p11 import run

REQUIRED = {
    "schematic_list_projects", "schematic_open_project",
    "schematic_describe_project", "schematic_validate_project",
    "schematic_render_project", "schematic_render_overview",
}


def _json_result(value) -> dict:
    if value.isError:
        raise AssertionError(f"MCP tool failed: {value.content}")
    if isinstance(value.structuredContent, dict):
        return value.structuredContent
    candidates = [c.text for c in value.content if isinstance(c, TextContent)]
    if not candidates:
        raise AssertionError("MCP returned no structured read-only response")
    return json.loads(candidates[0])


async def check_mcp_reads(workspace: Path, source: dict) -> dict:
    project_id = source["project_id"]
    revision = source["revision_sha256"]
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GSE_P11_")}
    env.update({
        "GSE_P11_READONLY_ENABLED": "1",
        "GSE_P11_WORKSPACE": str(workspace.resolve()),
        "GSE_P11_ALLOWED_PROJECT_IDS": project_id,
    })
    settings = StdioServerParameters(
        command=sys.executable, args=["-m", "gost_schematic.mcp_server"], env=env,
    )
    async with stdio_client(settings) as (reader, writer):  # noqa: SIM117
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = await client.list_tools()
            names = {item.name for item in tools.tools}
            if not REQUIRED <= names:
                raise AssertionError(f"Missing native read tools: {REQUIRED - names}")
            for item in tools.tools:
                if item.name in REQUIRED and (
                    item.annotations is None
                    or item.annotations.readOnlyHint is not True
                ):
                    raise AssertionError(f"Native MCP read-only annotation absent: {item.name}")
            listed = _json_result(await client.call_tool("schematic_list_projects", {}))
            if (listed["count"] != 1
                    or listed["projects"][0]["project_id"] != project_id):
                raise AssertionError("MCP discovery ignored explicit project allowlist")
            opened = _json_result(await client.call_tool(
                "schematic_open_project",
                {"project_id": project_id, "revision": revision},
            ))
            if opened["project_revision"] != revision:
                raise AssertionError("MCP opened wrong persisted E3 revision")
            described = _json_result(await client.call_tool(
                "schematic_describe_project", {"project_id": project_id,
                                               "revision": revision},
            ))
            if described["model"] != source["source_model"]:
                raise AssertionError("MCP physical PinRef/Net/wire geometry mismatched Python")
            diagnostics = _json_result(await client.call_tool(
                "schematic_validate_project", {"project_id": project_id,
                                                "revision": revision},
            ))
            if diagnostics != source["cold_diagnostics"]:
                raise AssertionError("MCP ERC differs from independent cold-process ERC")
            view = await client.call_tool(
                "schematic_render_project", {
                    "project_id": project_id, "revision": revision,
                    "mode": "clean", "include_svg": True,
                },
            )
            if view.isError:
                raise AssertionError(f"Native MCP SVG/PNG failed: {view.content}")
            images = [item for item in view.content if isinstance(item, ImageContent)]
            texts = [item for item in view.content if isinstance(item, TextContent)]
            if len(images) != 1 or len(texts) != 2:
                raise AssertionError("Expected exact MCP image + metadata + true SVG")
            png_bytes = base64.b64decode(images[0].data, validate=True)
            metadata = json.loads(texts[0].text)
            svg_bytes = texts[1].text.encode("utf-8")
            if (metadata["project_revision"] != revision
                    or metadata["png_sha256"] != hashlib.sha256(png_bytes).hexdigest()
                    or metadata["view_svg_sha256"] != hashlib.sha256(svg_bytes).hexdigest()
                    or metadata["png_sha256"] != source["overview_image"]["png_sha256"]
                    or metadata["view_svg_sha256"]
                    != source["overview_image"]["view_svg_sha256"]):
                raise AssertionError("MCP native visual hashes differ from saved-revision API")
            # P0 Vision is still an independent fixed six-part reference, NOT
            # the newly constructed R1/R2/C1 agent project.
            legacy_vision = await client.call_tool(
                "schematic_render_overview", {"project_ref": "six-part"},
            )
            if legacy_vision.isError or not any(
                isinstance(item, ImageContent) for item in legacy_vision.content
            ):
                raise AssertionError("Existing P0 MCP Vision PNG unavailable")
            return {
                "transport": "real MCP stdio ClientSession",
                "read_tools_verified": sorted(REQUIRED),
                "project_id": project_id, "project_revision": revision,
                "generation": opened["generation"],
                "physical_model_matches_python_api": True,
                "diagnostics_match_cold_reopen": True,
                "project_mcp_png_sha256": metadata["png_sha256"],
                "project_mcp_svg_sha256": metadata["view_svg_sha256"],
                "legacy_mcp_vision_project_ref": "six-part",
                "mcp_mutations_exposed": sorted(
                    name for name in names if any(
                        token in name for token in (
                            "add_component", "connect_pins",
                            "commit_transaction", "attach_net_continuation",
                        )
                    )
                ),
            }


def run_experiment(workspace: Path, project_id: str,
                   idempotency_key: str) -> dict:
    physical = run(workspace, project_id, idempotency_key)
    agent_reads = asyncio.run(check_mcp_reads(workspace, physical))
    if agent_reads["mcp_mutations_exposed"]:
        raise AssertionError("Write tools exposed before MAIN 2 authorization")
    return {
        "schema_version": 1,
        "agent_construction": "trusted Python API, not Codex MCP write",
        "codex_cli_used": False,
        "physical_project": physical,
        "actual_mcp_client": agent_reads,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()
    result = run_experiment(
        args.workspace, args.project_id or str(uuid.uuid4()),
        args.idempotency_key or str(uuid.uuid4()),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
