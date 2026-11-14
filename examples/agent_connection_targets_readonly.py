"""Real read-only MCP project/PinRef/wire-target/diagnostic-image experiment.

Usage:
  python -m examples.agent_connection_targets_readonly --workspace output/p12-targets

The initial six-part E3 circuit and 16 authored conductor segments are
created via trusted Python API ONLY.  A separate real MCP stdio server is
then asked to OPEN the immutable project, READ the typed physical endpoints,
DIAGNOSE the circuit, and RENDER SVG-derived PNG.  No code claims an agent
or Codex can issue write MCP commands; no green hotspots are printed.
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

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.trusted_import import import_six_part


def structured(result):
    if result.isError:
        raise AssertionError("Native read tool error: " + str(result.content))
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    values = [c.text for c in result.content if isinstance(c, TextContent)]
    if not values:
        raise AssertionError("No native MCP structured result")
    return json.loads(values[0])


async def query_real_mcp(workspace: Path, project_id: str, revision: str) -> dict:
    host_env = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    host_env.update({
        "GSE_P11_READONLY_ENABLED": "1",
        "GSE_P11_WORKSPACE": str(workspace.resolve()),
        "GSE_P11_ALLOWED_PROJECT_IDS": project_id,
    })
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "gost_schematic.mcp_server"], env=host_env,
    )
    async with stdio_client(server) as (read, write):  # noqa: SIM117
        async with ClientSession(read, write) as client:
            await client.initialize()
            offered = {tool.name: tool for tool in (await client.list_tools()).tools}
            required = {
                "schematic_open_project", "schematic_get_connection_targets",
                "schematic_validate_project", "schematic_render_project",
            }
            if not required <= offered.keys():
                raise AssertionError("Missing native MCP reader: "
                                     + str(required - offered.keys()))
            for name in required:
                annotated = offered[name].annotations
                if annotated is None or annotated.readOnlyHint is not True:
                    raise AssertionError("Tool lacks true read-only contract: " + name)
            opened = structured(await client.call_tool(
                "schematic_open_project", {"project_id": project_id, "revision": revision},
            ))
            data = structured(await client.call_tool(
                "schematic_get_connection_targets",
                {"project_id": project_id, "revision": revision},
            ))
            c3_plus = next(x for x in data["targets"] if
                           x["kind"] == "physical_pin"
                           and x["pin_ref"] == {"reference": "C3", "number": "1"})
            c3_minus = next(x for x in data["targets"] if
                            x["kind"] == "physical_pin"
                            and x["pin_ref"] == {"reference": "C3", "number": "2"})
            proposed = structured(await client.call_tool(
                "schematic_get_connection_targets", {
                    "project_id": project_id, "revision": revision,
                    "source_target_id": c3_plus["target_id"],
                },
            ))
            pair = next(x for x in proposed["targets"]
                        if x["target_id"] == c3_minus["target_id"])
            if pair["reason_code"] != "NET_MERGE_DENIED":
                raise AssertionError("Distinct physical Nets were not protected")
            if pair["preview_candidate_allowed"] or pair["connection_allowed"]:
                raise AssertionError("False same-Net or topology mutation admission")
            diagnostics = structured(await client.call_tool(
                "schematic_validate_project", {
                    "project_id": project_id, "revision": revision,
                },
            ))
            view = await client.call_tool(
                "schematic_render_project", {
                    "project_id": project_id, "revision": revision,
                    "reference": "C3", "mode": "diagnostic",
                    "target_dpi": 300, "include_svg": True,
                },
            )
            if view.isError:
                raise AssertionError("Real diagnostic render failed")
            images = [x for x in view.content if isinstance(x, ImageContent)]
            texts = [x for x in view.content if isinstance(x, TextContent)]
            if len(images) != 1 or len(texts) != 2:
                raise AssertionError("Expected binary PNG and exact SVG source")
            image = base64.b64decode(images[0].data, validate=True)
            meta = json.loads(texts[0].text)
            source_svg = texts[1].text
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise AssertionError("The MCP render was not a real PNG")
            if (hashlib.sha256(image).hexdigest() != meta["png_sha256"]
                    or hashlib.sha256(source_svg.encode()).hexdigest()
                    != meta["view_svg_sha256"]):
                raise AssertionError("SVG/PNG SHA mismatch")
            if "editor-connection-targets" in source_svg:
                raise AssertionError("Editor-only hotspot leaked into rendered sheet")
            return {
                "real_transport": "mcp.ClientSession + stdio_client",
                "project_id": project_id,
                "revision": revision,
                "generation": opened["generation"],
                "physical_targets": len([
                    x for x in data["targets"] if x["kind"] == "physical_pin"
                ]),
                "authored_wire_endpoints": len([
                    x for x in data["targets"] if x["kind"] == "wire_endpoint"
                ]),
                "authored_junctions": diagnostics["junction_count"],
                "net_count": diagnostics["net_count"],
                "c3_plus_um": c3_plus["world_um"],
                "c3_minus_um": c3_minus["world_um"],
                "forbidden_cross_net_reason": pair["reason_code"],
                "hover_creates_net": data["hover_creates_net"],
                "mcp_created_or_modified_project": False,
                "diagnostics": diagnostics,
                "png_sha256": meta["png_sha256"],
                "svg_sha256": meta["view_svg_sha256"],
                "clean_normative_hotspots": False,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--idempotency-key", default=None)
    args = parser.parse_args()
    project_id = args.project_id or str(uuid.uuid4())
    key = args.idempotency_key or str(uuid.uuid4())
    snapshot = import_six_part(args.workspace, project_id=project_id,
                               idempotency_key=key)
    old_record = snapshot.project.to_record()
    head = (args.workspace / "projects" / project_id / "HEAD.json")
    before = head.read_bytes()
    result = asyncio.run(query_real_mcp(args.workspace, project_id,
                                        snapshot.project.revision))
    assert before == head.read_bytes(), "Read-only MCP must never alter persisted HEAD"
    assert ProjectService.for_workspace(args.workspace).open_project(
        project_id, snapshot.project.revision,
    ).project.to_record() == old_record
    assert result["authored_wire_endpoints"] == 32
    assert result["authored_junctions"] == 3
    assert result["net_count"] == 5
    print(json.dumps({
        "schema_version": 1,
        "creation": "trusted Python initial import (not MCP write)",
        "codex_cli_used": False,
        "saved_e3_mcp": result,
    }, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
