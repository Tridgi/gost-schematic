"""Real MCP ClientSession/stdio acceptance for P1.1 persisted E3 project reads.

A clean-process MCP server is launched as a separate process. Neither images
nor netlists are mocked; the server reloads immutable .gseproj and catalog.
"""
import asyncio
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "cf26bf02-8bf1-43bf-86aa-5f6a84bbcc51"
OTHER = "32b46b40-8aaf-4ed6-a90f-a5cc1864b5e8"
KEY = "72f3a7e5-272e-4323-a77b-5cf1c66fe77d"
OTHER_KEY = "7e9f45eb-ab6c-43a4-8a23-3636c13f33ec"
TOOLS = {
    "schematic_list_projects", "schematic_open_project",
    "schematic_describe_project", "schematic_validate_project",
    "schematic_render_project",
}


def _env(workspace: Path, *, enabled: bool = True, allowed: str = PID) -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("GSE_P11_")
    }
    if enabled:
        env["GSE_P11_READONLY_ENABLED"] = "1"
    env["GSE_P11_WORKSPACE"] = str(workspace)
    env["GSE_P11_ALLOWED_PROJECT_IDS"] = allowed
    return env


def _object(response):
    assert not response.isError, response
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    texts = [entry.text for entry in response.content if isinstance(entry, TextContent)]
    assert texts
    return json.loads(texts[0])


def _error(response) -> str:
    assert response.isError, response
    assert not any(isinstance(c, ImageContent) for c in response.content)
    return " ".join(c.text for c in response.content if isinstance(c, TextContent))


def _stdio(env):
    return StdioServerParameters(
        command=sys.executable, args=["-m", "gost_schematic.mcp_server"],
        env=env,
    )


def test_actual_mcp_client_saved_six_part_pinrefs_svg_png_and_no_writes(tmp_path: Path):
    workspace = tmp_path / "allowed-workspace"
    source = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    import_six_part(workspace, project_id=OTHER, idempotency_key=OTHER_KEY)
    source_view = ProjectService.for_workspace(workspace).render_project(
        PID, source.head.revision, reference="C3", target_dpi=300,
    )
    primary_head = workspace / "projects" / PID / "HEAD.json"
    primary_blob = (
        workspace / "projects" / PID / "revisions"
        / (source.head.revision + ".gseproj")
    )
    head_before, blob_before = primary_head.read_bytes(), primary_blob.read_bytes()

    async def verify():
        async with stdio_client(_stdio(_env(workspace))) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as session:
                await session.initialize()
                announced = await session.list_tools()
                names = {tool.name for tool in announced.tools}
                assert TOOLS <= names
                assert {
                    "schematic_render_overview", "schematic_inspect_region",
                    "schematic_inspect_component", "schematic_inspect_connection",
                    "schematic_get_diagnostics", "schematic_list_views",
                } <= names
                assert not any(
                    name in names for name in (
                        "schematic_add_component", "schematic_connect_pins",
                        "schematic_attach_net_continuation",
                        "schematic_commit_transaction",
                    )
                )
                for tool in announced.tools:
                    if tool.name in TOOLS:
                        assert tool.annotations is not None
                        assert tool.annotations.readOnlyHint is True
                        assert tool.annotations.destructiveHint is False
                        assert tool.annotations.openWorldHint is False

                listed = _object(await session.call_tool("schematic_list_projects", {}))
                assert listed["count"] == 1
                assert [p["project_id"] for p in listed["projects"]] == [PID]
                assert listed["projects"][0]["project_revision"] == source.head.revision

                opening = _object(await session.call_tool(
                    "schematic_open_project", {"project_id": PID},
                ))
                assert opening["head_revision"] == source.head.revision
                assert opening["generation"] == 1
                assert [opening[key] for key in (
                    "component_count", "net_count", "wire_segment_count", "junction_count",
                )] == [6, 5, 16, 3]

                described = _object(await session.call_tool(
                    "schematic_describe_project",
                    {"project_id": PID, "revision": source.head.revision},
                ))
                model = described["model"]
                assert model["canonical_typed_project"] == source.project.to_record()
                assert model["component_count"] == 6
                assert model["wire_count"] == 16
                assert model["junction_count"] == 3
                c3 = next(x for x in model["resolved_physical_contacts"]
                          if x["component_reference"] == "C3")
                assert c3["part_id"] == "capacitor.electrolytic"
                assert {(p["number"], p["name"], tuple(p["world_um"]))
                        for p in c3["physical_pins"]} == {
                    ("1", "PLUS", (91000, 80000)),
                    ("2", "MINUS", (109000, 80000)),
                }

                diagnostics = _object(await session.call_tool(
                    "schematic_validate_project",
                    {"project_id": PID, "revision": source.head.revision},
                ))
                assert diagnostics["project_revision"] == source.head.revision
                assert diagnostics["wire_segment_count"] == 16
                assert diagnostics["junction_count"] == 3
                assert diagnostics["status"] == "WARN"
                assert not any(d["severity"] == "error"
                               for d in diagnostics["diagnostics"])

                rendered = await session.call_tool(
                    "schematic_render_project", {
                        "project_id": PID, "revision": source.head.revision,
                        "reference": "C3", "target_dpi": 300, "include_svg": True,
                    },
                )
                assert not rendered.isError
                image = [x for x in rendered.content if isinstance(x, ImageContent)]
                text = [x for x in rendered.content if isinstance(x, TextContent)]
                assert len(image) == 1 and len(text) == 2
                assert image[0].mimeType == "image/png"
                assert base64.b64decode(image[0].data) == source_view.png
                meta = json.loads(text[0].text)
                assert meta["project_revision"] == source.head.revision
                assert meta["diagnostics_revision"] == source.head.revision
                assert meta["png_sha256"] == hashlib.sha256(source_view.png).hexdigest()
                assert text[1].text == source_view.svg
                assert meta["view_svg_sha256"] == hashlib.sha256(
                    text[1].text.encode("utf-8")
                ).hexdigest()

                other_denied = await session.call_tool(
                    "schematic_open_project", {"project_id": OTHER},
                )
                assert "PROJECT_ACCESS_DENIED" in _error(other_denied)
                bad_path = await session.call_tool(
                    "schematic_describe_project", {"project_id": "../../outside"},
                )
                assert "PROJECT_ACCESS_DENIED" in _error(bad_path)
                bad_revision = await session.call_tool(
                    "schematic_render_project",
                    {"project_id": PID, "revision": "f" * 64},
                )
                assert "REVISION_NOT_FOUND" in _error(bad_revision)

                # Native six-part P0 stdio capability remains available.
                old = await session.call_tool(
                    "schematic_list_views", {"project_ref": "six-part"},
                )
                assert not old.isError
    asyncio.run(verify())
    assert primary_head.read_bytes() == head_before
    assert primary_blob.read_bytes() == blob_before
    assert not (workspace / "artifacts").exists()


def test_actual_mcp_client_permission_denied_when_not_explicitly_enabled(tmp_path):
    workspace = tmp_path / "authorized-store"
    import_six_part(workspace, project_id=PID, idempotency_key=KEY)

    async def verify():
        for env in (_env(workspace, enabled=False),
                    _env(workspace, allowed=""),
                    _env(workspace, allowed="../../outside")):
            async with stdio_client(_stdio(env)) as (read, write):  # noqa: SIM117
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("schematic_list_projects", {})
                    err = _error(result)
                    assert "PROJECT_ACCESS_DENIED" in err
                    assert str(workspace) not in err
                    result = await session.call_tool(
                        "schematic_open_project", {"project_id": PID},
                    )
                    err = _error(result)
                    assert "PROJECT_ACCESS_DENIED" in err
                    assert str(workspace) not in err
    asyncio.run(verify())


def test_actual_mcp_client_rejects_redirected_workspace(tmp_path):
    workspace = tmp_path / "safe"
    import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    other = tmp_path / "another"
    try:
        (tmp_path / "redirect").symlink_to(workspace, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("Symlink creation unavailable")

    async def verify():
        async with stdio_client(_stdio(_env(tmp_path / "redirect"))) as (
            read, write,
        ):  # noqa: SIM117
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("schematic_list_projects", {})
                assert "PROJECT_ACCESS_DENIED" in _error(result)
    asyncio.run(verify())
