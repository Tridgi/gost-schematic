"""Actual independent MCP client: model-based connection targets + real SVG/PNG.

These are read-only tool calls to a new stdio server, not mocked Python functions.
"""
import asyncio
import base64
import hashlib
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "3c99dccf-80be-4d6e-a962-59359b947cc8"
FOREIGN = "a98aff4c-fb39-4b04-9de8-4abdfd21bbf3"
KEY = "1957b691-3ca3-4830-9745-24747db2d974"


def _env(workspace, enabled=True, allowed=PID):
    result = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    if enabled:
        result["GSE_P11_READONLY_ENABLED"] = "1"
    result["GSE_P11_WORKSPACE"] = str(workspace)
    result["GSE_P11_ALLOWED_PROJECT_IDS"] = allowed
    return result


def _rpc_env(env):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "gost_schematic.mcp_server"], env=env,
    )


def _result(result):
    assert not result.isError, result
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    text = [item.text for item in result.content if isinstance(item, TextContent)]
    assert text, result
    return json.loads(text[0])


def _rejection(result, code):
    assert result.isError
    assert not any(isinstance(entry, ImageContent) for entry in result.content)
    assert code in " ".join(
        entry.text for entry in result.content if isinstance(entry, TextContent)
    )


def test_mcp_client_real_saved_targets_and_diagnostic_svg_no_mutation(tmp_path):
    workspace = tmp_path / "trusted-store"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    direct = ProjectService.for_workspace(workspace)
    revision = snap.project.revision
    baseline = direct.get_connection_targets(PID, revision)
    assert baseline["target_count"] > 32
    head = workspace / "projects" / PID / "HEAD.json"
    blob = workspace / "projects" / PID / "revisions" / (revision + ".gseproj")
    before_head, before_blob = head.read_bytes(), blob.read_bytes()

    async def exercise():
        async with stdio_client(_rpc_env(_env(workspace))) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert "schematic_get_connection_targets" in names
                assert {"schematic_open_project", "schematic_validate_project",
                        "schematic_render_project"} <= names
                assert not any(name in names for name in (
                    "schematic_add_component", "schematic_connect_pins",
                    "schematic_commit_transaction", "schematic_validate_transaction",
                ))
                tool = next(tool for tool in tools.tools
                            if tool.name == "schematic_get_connection_targets")
                assert tool.annotations is not None
                assert tool.annotations.readOnlyHint is True
                assert tool.annotations.destructiveHint is False

                opened = _result(await client.call_tool(
                    "schematic_open_project", {"project_id": PID, "revision": revision},
                ))
                assert opened["project_revision"] == revision
                via_mcp = _result(await client.call_tool(
                    "schematic_get_connection_targets",
                    {"project_id": PID, "revision": revision},
                ))
                assert via_mcp == baseline
                assert len([x for x in via_mcp["targets"]
                            if x["kind"] == "wire_endpoint"]) == 32
                c3_plus = next(x for x in via_mcp["targets"]
                               if x["kind"] == "physical_pin"
                               and x["pin_ref"] == {"reference": "C3", "number": "1"})
                c3_minus = next(x for x in via_mcp["targets"]
                                if x["kind"] == "physical_pin"
                                and x["pin_ref"] == {"reference": "C3", "number": "2"})
                assert c3_plus["world_um"] == [91000, 80000]
                assert c3_minus["world_um"] == [109000, 80000]
                assert c3_plus["net_identity"]["id"] != c3_minus["net_identity"]["id"]

                with_source = _result(await client.call_tool(
                    "schematic_get_connection_targets", {
                        "project_id": PID, "revision": revision,
                        "source_target_id": c3_plus["target_id"],
                    },
                ))
                target = next(x for x in with_source["targets"]
                              if x["target_id"] == c3_minus["target_id"])
                assert target["reason_code"] == "NET_MERGE_DENIED"
                assert target["preview_candidate_allowed"] is False
                assert target["connection_allowed"] is False
                assert with_source["hover_creates_net"] is False

                diagnostic = _result(await client.call_tool(
                    "schematic_validate_project", {
                        "project_id": PID, "revision": revision,
                    },
                ))
                assert diagnostic["wire_segment_count"] == 16
                assert diagnostic["junction_count"] == 3
                assert not any(d["severity"] == "error"
                               for d in diagnostic["diagnostics"])
                diagnostic_image = await client.call_tool(
                    "schematic_render_project", {
                        "project_id": PID, "revision": revision,
                        "mode": "diagnostic", "reference": "C3",
                        "target_dpi": 250, "include_svg": True,
                    },
                )
                assert not diagnostic_image.isError
                images = [x for x in diagnostic_image.content
                          if isinstance(x, ImageContent)]
                texts = [x for x in diagnostic_image.content
                         if isinstance(x, TextContent)]
                assert len(images) == 1 and len(texts) == 2
                png = base64.b64decode(images[0].data, validate=True)
                metadata = json.loads(texts[0].text)
                assert png.startswith(b"\x89PNG\r\n\x1a\n")
                assert metadata["project_revision"] == revision
                assert hashlib.sha256(png).hexdigest() == metadata["png_sha256"]
                assert hashlib.sha256(texts[1].text.encode()).hexdigest() == (
                    metadata["view_svg_sha256"]
                )
                # Debug rendering is a diagnostic sheet, NOT an interactive editor.
                assert 'data-layer="editor-connection-targets"' not in texts[1].text
                assert "interactive" not in metadata["source"]

                _rejection(await client.call_tool(
                    "schematic_get_connection_targets",
                    {"project_id": FOREIGN, "revision": revision},
                ), "PROJECT_ACCESS_DENIED")
                _rejection(await client.call_tool(
                    "schematic_get_connection_targets",
                    {"project_id": "../../escape", "revision": revision},
                ), "PROJECT_ACCESS_DENIED")
                _rejection(await client.call_tool(
                    "schematic_get_connection_targets",
                    {"project_id": PID, "revision": "f" * 64},
                ), "REVISION_NOT_FOUND")
    asyncio.run(exercise())
    assert head.read_bytes() == before_head
    assert blob.read_bytes() == before_blob
    assert not (workspace / "artifacts").exists()


def test_mcp_client_default_deny_and_no_project_disclosure(tmp_path):
    workspace = tmp_path / "trusted-store"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)

    async def exercise():
        for env in (_env(workspace, enabled=False),
                    _env(workspace, enabled=True, allowed=FOREIGN)):
            async with stdio_client(_rpc_env(env)) as (read, write):  # noqa: SIM117
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    _rejection(await client.call_tool(
                        "schematic_get_connection_targets",
                        {"project_id": PID, "revision": snap.project.revision},
                    ), "PROJECT_ACCESS_DENIED")
    asyncio.run(exercise())
