"""Independent Cycle9 AI read-only physical part selection and placement guards."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.design_assistant import (
    TL494_BASELINE,
    TL494_FROZEN_SOURCE_SHA,
    catalog_search,
    tl494_profile,
)
from gost_schematic.agent_project.design_selection import (
    preview_placement,
    require_api_version,
    select_physical_part,
)
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "8d5edcd8-df55-41b0-a8b8-bc5d89be318b"
KEY = "14acb0f6-87fb-4bb8-9a7f-bc30305cb71e"
OTHER = "a824f2e7-70b6-4b4a-8520-4d6bd3d9a06b"


def _selected(catalog, name="capacitor.polarized"):
    lock = catalog.lock(name)
    return select_physical_part(
        catalog, name, part_sha256=lock["part_sha256"],
        symbol_sha256=lock["symbol_sha256"],
    )


def test_selection_returns_actual_physical_pins_but_not_fake_instance_pinref():
    cat = CatalogResolver()
    result = _selected(cat)
    assert result["selection_status"] == "EXACT_CATALOG_LOCK_MATCH"
    assert result["read_only"] and result["connection_authorized"] is False
    assert result["selected_part_id"] == "capacitor.polarized"
    assert result["symbol_status"] == "draft"
    assert result["normative_status"] == "NOT_APPROVED"
    assert result["placement_requires_real_project_component"]
    assert len(result["d4_geometric_transforms"]) == 8
    assert [r["number"] for r in result["physical_pin_templates"]] == ["1", "2"]
    assert all(r["pin_ref"] is None and not r["is_instantiated_pin_ref"]
               for r in result["physical_pin_templates"])
    assert result["physical_pin_templates"][0]["polarity"] == "positive"


@pytest.mark.parametrize(("part", "code"), [
    ("../capacitor.polarized", "INVALID_CATALOG_SELECTOR"),
    ("Capacitor.polarized", "INVALID_CATALOG_SELECTOR"),
    ("capacitor.polarized\n", "INVALID_CATALOG_SELECTOR"),
    ("capacitor..polarized", "INVALID_CATALOG_SELECTOR"),
    ("unknown.ugo", "CATALOG_PART_MISSING"),
])
def test_exact_part_selector_fail_closed(part, code):
    cat = CatalogResolver()
    lock = cat.lock("capacitor.polarized")
    with pytest.raises(ProjectError, match=code):
        select_physical_part(cat, part, part_sha256=lock["part_sha256"],
                             symbol_sha256=lock["symbol_sha256"])


@pytest.mark.parametrize("version", (0, 2, True, "1", 1.0, None))
def test_api_version_must_be_exact_int_one(version):
    with pytest.raises(ProjectError, match="API_VERSION_UNSUPPORTED"):
        require_api_version(version)


@pytest.mark.parametrize("sha", ("0"*64, "F"*64, "f"*63, "../", "", None))
def test_stale_invalid_sha_denied_without_catalog_mutation(sha):
    cat = CatalogResolver()
    lock = cat.lock("diode.schottky")
    with pytest.raises(ProjectError, match="CATALOG_REVISION_MISMATCH|INVALID_CATALOG_SHA"):
        select_physical_part(
            cat, "diode.schottky", part_sha256=sha,
            symbol_sha256=lock["symbol_sha256"],
        )
    assert cat.lock("diode.schottky") == lock


def test_correct_part_wrong_symbol_sha_is_rejected():
    cat = CatalogResolver()
    cap = cat.lock("capacitor.polarized")
    other = cat.lock("capacitor.fixed")
    with pytest.raises(ProjectError, match="CATALOG_REVISION_MISMATCH"):
        select_physical_part(cat, "capacitor.polarized",
                             part_sha256=cap["part_sha256"],
                             symbol_sha256=other["symbol_sha256"])


def test_exact_source_pin_and_authentic_3_terminal_wiper():
    catalog = CatalogResolver()
    profile = tl494_profile(catalog)
    assert profile["frozen_source_git_commit_sha"] == TL494_FROZEN_SOURCE_SHA
    assert profile["frozen_source_model_counts"] == TL494_BASELINE
    assert TL494_BASELINE == {
        "component_count": 23, "net_count": 15,
        "wire_segment_count": 91, "explicit_junction_count": 37,
        "da1_physical_contact_count": 16,
    }
    assert len(profile["required_variants"]) == 13
    r5 = next(p for p in profile["required_variants"] if p["reference"] == "R5")
    assert r5["required_part_id"] == "resistor.variable"
    contacts = _selected(catalog, "resistor.variable")["physical_pin_templates"]
    assert [c["name"] for c in contacts] == ["A", "B", "W"]
    assert [c["number"] for c in contacts] == ["1", "2", "3"]
    assert profile["not_normatively_approved"] is True


def test_malformed_semantic_input_no_injection_or_guessing():
    cat = CatalogResolver()
    inputs = (
        "../capacitor", "conDENsator../", "capacitor\nDROP TABLE",
        "polarized capacitor\x00", "диод шоттки; rm -rf /",
        " capacitor", "capacitor ", "c" * 10000,
        "<svg onload=alert(1)>", "🧨"*20,
    )
    for raw in inputs:
        with pytest.raises(ProjectError, match="INVALID_SEMANTIC_QUERY"):
            catalog_search(cat, raw)
    assert catalog_search(cat, "unknownphysicalcomponent")[
        "status"] == "NO_EXACT_CATALOG_MATCH"


def test_readonly_placement_keeps_true_pinrefs_and_blocks_connected_net(tmp_path):
    workspace = tmp_path / "trusted"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    project = snap.project
    c3 = next(c for c in project.circuit.components if c.reference == "C3")
    before = project.to_record()
    head_path = workspace / "projects" / PID / "HEAD.json"
    original_head = head_path.read_bytes()
    result = service.preview_placement(
        PID, project.revision, reference="C3",
        x_um=c3.origin.x + 10000, y_um=c3.origin.y,
    )
    assert result["project_revision"] == project.revision
    assert result["part_id"] == c3.part_id
    assert result["component_geometry_changed"] is True
    assert result["model_or_head_mutated"] is False
    assert result["connection_authorized"] is False
    assert result["commit_authorized"] is False
    assert result["print_ready"] is False
    assert result["candidate_render"] == "BLOCKED_UNTIL_VIEW_PLUS_ROUTING_CONTRACT"
    assert any(d["code"] == "CONNECTED_PIN_RELOCATION_BLOCKED"
               for d in result["diagnostics"])
    assert {p["pin_ref"]["number"] for p in result["original_pin_anchors_um"]} == {
        "1", "2",
    }
    assert result["original_net_membership"]
    assert project.to_record() == before
    assert head_path.read_bytes() == original_head
    assert service.open_project(PID, project.revision).project.to_record() == before


@pytest.mark.parametrize(("kwargs", "code"), [
    ({"reference": "MISSING"}, "UNKNOWN_COMPONENT"),
    ({"reference": "../C3"}, "INVALID_COMPONENT_REFERENCE"),
    ({"reference": "C3", "x_um": True}, "INVALID_COORDINATE"),
    ({"reference": "C3", "y_um": 1.5}, "INVALID_COORDINATE"),
    ({"reference": "C3", "x_um": 10**12}, "INVALID_COORDINATE"),
    ({"reference": "C3", "rotation": 45}, "INVALID_TRANSFORM"),
    ({"reference": "C3", "rotation": True}, "INVALID_TRANSFORM"),
    ({"reference": "C3", "mirror_x": 1}, "INVALID_TRANSFORM"),
    ({"reference": "C3", "api_version": 2}, "API_VERSION_UNSUPPORTED"),
])
def test_readonly_placement_bad_arguments_fail_before_any_model_write(tmp_path, kwargs, code):
    snap = import_six_part(tmp_path / "trusted", project_id=PID, idempotency_key=KEY)
    original = snap.project.to_record()
    args = {"reference": "C3", "x_um": 0, "y_um": 0}
    args.update(kwargs)
    with pytest.raises(ProjectError, match=code):
        preview_placement(snap.project, CatalogResolver(), **args)
    assert snap.project.to_record() == original


def _mcp_data(response):
    assert not response.isError, response.content
    if isinstance(response.structuredContent, dict):
        return response.structuredContent
    return json.loads(next(x.text for x in response.content if isinstance(x, TextContent)))


def _mcp_error(response, code):
    assert response.isError, response.content
    assert code in " ".join(x.text for x in response.content if isinstance(x, TextContent))


def test_native_stdio_selection_rbac_negative_version_and_no_writes(tmp_path: Path):
    workspace = tmp_path / "trusted"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    revision = snap.project.revision
    head = workspace / "projects" / PID / "HEAD.json"
    blob = workspace / "projects" / PID / "revisions" / (revision + ".gseproj")
    before_head, before_blob = head.read_bytes(), blob.read_bytes()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    env.update({
        "GSE_P11_READONLY_ENABLED": "1",
        "GSE_P11_WORKSPACE": str(workspace),
        "GSE_P11_ALLOWED_PROJECT_IDS": PID,
    })

    async def run():
        settings = StdioServerParameters(
            command=sys.executable, args=["-m", "gost_schematic.mcp_server"], env=env,
        )
        async with stdio_client(settings) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = {t.name: t for t in (await client.list_tools()).tools}
                for name in ("schematic_catalog_select", "schematic_preview_placement"):
                    assert tools[name].annotations.readOnlyHint is True
                    assert tools[name].annotations.destructiveHint is False
                assert not any("commit_transaction" in name or "connect_pins" in name
                               for name in tools)
                cat = _mcp_data(await client.call_tool(
                    "schematic_catalog_search", {"semantic_query": "resistor.variable"},
                ))
                card = cat["candidates"][0]
                selected = _mcp_data(await client.call_tool(
                    "schematic_catalog_select", {
                        "part_id": card["part_id"],
                        "part_sha256": card["part_sha256"],
                        "symbol_sha256": card["symbol_sha256"],
                    },
                ))
                assert selected["selected_part_id"] == "resistor.variable"
                assert len(selected["physical_pin_templates"]) == 3
                _mcp_error(await client.call_tool(
                    "schematic_catalog_select", {
                        "part_id": card["part_id"], "part_sha256": "f"*64,
                        "symbol_sha256": card["symbol_sha256"],
                    },
                ), "CATALOG_REVISION_MISMATCH")
                _mcp_error(await client.call_tool(
                    "schematic_catalog_search", {
                        "semantic_query": "capacitor", "api_version": 2,
                    },
                ), "API_VERSION_UNSUPPORTED")
                _mcp_error(await client.call_tool(
                    "schematic_tl494_selection_profile", {"api_version": 2},
                ), "API_VERSION_UNSUPPORTED")
                c3 = next(c for c in snap.project.circuit.components
                          if c.reference == "C3")
                good = _mcp_data(await client.call_tool(
                    "schematic_preview_placement", {
                        "project_id": PID, "revision": revision, "reference": "C3",
                        "x_um": c3.origin.x + 10000, "y_um": c3.origin.y,
                    },
                ))
                assert any(d["code"] == "CONNECTED_PIN_RELOCATION_BLOCKED"
                           for d in good["diagnostics"])
                assert not good["model_or_head_mutated"]
                _mcp_error(await client.call_tool(
                    "schematic_preview_placement", {
                        "project_id": OTHER, "revision": revision,
                        "reference": "C3", "x_um": 0, "y_um": 0,
                    },
                ), "PROJECT_ACCESS_DENIED")
                _mcp_error(await client.call_tool(
                    "schematic_preview_placement", {
                        "project_id": PID, "revision": "f"*64,
                        "reference": "C3", "x_um": 0, "y_um": 0,
                    },
                ), "REVISION_NOT_FOUND")
                _mcp_error(await client.call_tool(
                    "schematic_preview_placement", {
                        "project_id": PID, "revision": revision,
                        "reference": "C3", "x_um": 0, "y_um": 0,
                        "api_version": 2,
                    },
                ), "API_VERSION_UNSUPPORTED")
                return selected["part_sha256"]
    part_sha = asyncio.run(run())
    assert len(part_sha) == 64
    assert head.read_bytes() == before_head and blob.read_bytes() == before_blob
    assert not (workspace / "artifacts").exists()
