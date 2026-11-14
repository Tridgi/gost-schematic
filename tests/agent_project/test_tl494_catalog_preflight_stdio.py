"""Actual independent MCP ClientSession for catalog queries and physical preflight."""
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

PID = "1509a5a6-1152-476e-af11-2971196d6cbf"
KEY = "c01a63e0-1393-4a8d-8537-7afc57263ce2"
FOREIGN = "7ea3c029-bea5-4bc2-9c5a-5028036c20a5"


def _env(workspace, *, grant=True, allowed=PID):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    if grant:
        env["GSE_P11_READONLY_ENABLED"] = "1"
    env["GSE_P11_WORKSPACE"] = str(workspace)
    env["GSE_P11_ALLOWED_PROJECT_IDS"] = allowed
    return env


def _stdio(env):
    return StdioServerParameters(
        command=sys.executable, args=["-m", "gost_schematic.mcp_server"], env=env,
    )


def _data(response):
    assert not response.isError, response.content
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    body = [c.text for c in response.content if isinstance(c, TextContent)]
    assert body
    return json.loads(body[0])


def _failed(response, code):
    assert response.isError
    assert code in " ".join(
        c.text for c in response.content if isinstance(c, TextContent)
    )


def test_real_mcp_client_curated_ugo_alias_preflight_and_exact_image(tmp_path):
    workspace = tmp_path / "trusted"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    svc = ProjectService.for_workspace(workspace)
    revision = snap.project.revision
    prior = svc.open_project(PID, revision).project.to_record()
    head = workspace / "projects" / PID / "HEAD.json"
    blob = workspace / "projects" / PID / "revisions" / (revision + ".gseproj")
    h, b = head.read_bytes(), blob.read_bytes()

    async def verify():
        async with stdio_client(_stdio(_env(workspace))) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {tool.name: tool for tool in (await client.list_tools()).tools}
                expected = {
                    "schematic_catalog_search", "schematic_catalog_preview",
                    "schematic_tl494_selection_profile", "schematic_tl494_pin_alias",
                    "schematic_preflight_project",
                }
                assert expected <= names.keys()
                assert {
                    "schematic_open_project", "schematic_render_project",
                    "schematic_validate_project",
                } <= names.keys()
                assert not {"schematic_connect_pins", "schematic_commit_transaction"} & names.keys()
                for name in expected:
                    assert names[name].annotations is not None
                    assert names[name].annotations.readOnlyHint is True
                    assert names[name].annotations.destructiveHint is False

                general = _data(await client.call_tool(
                    "schematic_catalog_search", {"semantic_query": "конденсатор"},
                ))
                assert general["candidate_count"] == 3
                exact = _data(await client.call_tool(
                    "schematic_catalog_search",
                    {"semantic_query": "ferromagnetic inductor"},
                ))
                assert [x["part_id"] for x in exact["candidates"]] == [
                    "inductor.ferromagnetic"
                ]
                matrix = _data(await client.call_tool(
                    "schematic_tl494_selection_profile", {},
                ))
                assert len(matrix["required_variants"]) == 12
                assert matrix["tl494_device_catalog"] == "NOT_IN_INSTALLED_P11_CATALOG"
                alias = _data(await client.call_tool(
                    "schematic_tl494_pin_alias", {"full_name": "FEEDBACK"},
                ))
                assert alias["display_alias"] == "FB"
                assert alias["physical_number"] == "3"
                unresolved = _data(await client.call_tool(
                    "schematic_tl494_pin_alias", {"full_name": "UNLISTED ALIAS"},
                ))
                assert unresolved["status"] == "ALIAS_UNVERIFIED"

                preview = await client.call_tool(
                    "schematic_catalog_preview", {"part_id": "diode.schottky"},
                )
                assert not preview.isError
                images = [x for x in preview.content if isinstance(x, ImageContent)]
                texts = [x for x in preview.content if isinstance(x, TextContent)]
                assert len(images) == 1 and len(texts) == 2
                assert images[0].mimeType == "image/png"
                png = base64.b64decode(images[0].data, validate=True)
                meta = json.loads(texts[0].text)
                svg = texts[1].text
                assert png.startswith(b"\x89PNG\r\n\x1a\n")
                assert 'diode.schottky' in svg
                assert meta["symbol_status"] == "draft"
                assert hashlib.sha256(png).hexdigest() == meta["png_sha256"]
                assert hashlib.sha256(svg.encode()).hexdigest() == meta["svg_sha256"]
                assert meta["physical_pin_refs"][1]["number"] == "2"

                preflight = _data(await client.call_tool(
                    "schematic_preflight_project", {
                        "project_id": PID, "revision": revision, "profile": "none",
                    },
                ))
                assert preflight == svc.preflight_design(PID, revision)
                assert preflight["project_revision"] == revision
                assert preflight["route"]["authored_segment_count"] == 16
                assert preflight["route"]["explicit_junction_count"] == 3
                assert preflight["sheet_format"] == "NOT_PERSISTED_IN_P11"
                assert preflight["print_ready"] is False
                wrong_tl = _data(await client.call_tool(
                    "schematic_preflight_project", {
                        "project_id": PID, "revision": revision, "profile": "tl494",
                    },
                ))
                assert any(d["code"] == "TL494_UGO_VARIANT_MISMATCH"
                           for d in wrong_tl["diagnostics"])
                render = await client.call_tool("schematic_render_project", {
                    "project_id": PID, "revision": revision,
                    "reference": "C3", "mode": "diagnostic",
                    "target_dpi": 300, "include_svg": True,
                })
                assert not render.isError
                pics = [x for x in render.content if isinstance(x, ImageContent)]
                rendered_text = [x for x in render.content if isinstance(x, TextContent)]
                assert len(pics) == 1 and len(rendered_text) == 2
                displayed = base64.b64decode(pics[0].data)
                info = json.loads(rendered_text[0].text)
                assert hashlib.sha256(displayed).hexdigest() == info["png_sha256"]
                assert hashlib.sha256(rendered_text[1].text.encode()).hexdigest() == (
                    info["view_svg_sha256"]
                )
                _failed(await client.call_tool(
                    "schematic_preflight_project", {
                        "project_id": FOREIGN, "revision": revision,
                    },
                ), "PROJECT_ACCESS_DENIED")
                _failed(await client.call_tool(
                    "schematic_preflight_project", {
                        "project_id": "../escape", "revision": revision,
                    },
                ), "PROJECT_ACCESS_DENIED")
                _failed(await client.call_tool(
                    "schematic_preflight_project", {
                        "project_id": PID, "revision": "f" * 64,
                    },
                ), "REVISION_NOT_FOUND")
                assert not (workspace / "artifacts").exists()
                return {
                    "project_revision": revision,
                    "catalog_preview_png_sha256": meta["png_sha256"],
                    "catalog_preview_svg_sha256": meta["svg_sha256"],
                    "project_diagnostic_png_sha256": info["png_sha256"],
                    "project_diagnostic_svg_sha256": info["view_svg_sha256"],
                    "run": "real native MCP stdio ClientSession",
                }
    return_value = asyncio.run(verify())
    assert return_value["run"] == "real native MCP stdio ClientSession"
    assert head.read_bytes() == h and blob.read_bytes() == b
    assert svc.open_project(PID, revision).project.to_record() == prior


def test_mcp_scope_denied_without_host_project_grant(tmp_path):
    workspace = tmp_path / "trusted"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)

    async def verify():
        for env in (_env(workspace, grant=False),
                    _env(workspace, allowed=FOREIGN)):
            async with stdio_client(_stdio(env)) as (read, write):  # noqa: SIM117
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    _failed(await client.call_tool(
                        "schematic_preflight_project", {
                            "project_id": PID, "revision": snap.project.revision,
                        },
                    ), "PROJECT_ACCESS_DENIED")
    asyncio.run(verify())
