"""Issue107 original-source UGO selection and narrowly audited print preflight."""
from pathlib import Path

import pytest

from gost_schematic.agent_project import ProjectError, ProjectService
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.design_assistant import (
    TL494_REQUIRED_PARTS,
    _measured_parallel_wire_gaps,
    catalog_card,
    catalog_preview,
    catalog_search,
    tl494_alias,
    tl494_profile,
)
from gost_schematic.agent_project.trusted_import import import_six_part
from gost_schematic.core.geometry import Line, Point
from gost_schematic.model.obstacles import WireObstacle

PID = "4b2d29a7-1970-48a4-9d72-08c1bccd2266"
KEY = "62622bc8-9854-4e15-8ad2-fcbd7fc593e5"


def test_curated_catalog_requires_explicit_selection_and_verifies_true_pins():
    catalog = CatalogResolver()
    options = catalog_search(catalog, "конденсатор")
    assert options["selection_required"]
    assert options["status"] == "OPTIONS_REQUIRE_EXPLICIT_PART_ID"
    assert {v["part_id"] for v in options["candidates"]} == {
        "capacitor.polarized", "capacitor.fixed", "capacitor.electrolytic",
    }
    exact = catalog_search(catalog, "полярный конденсатор")
    assert [x["part_id"] for x in exact["candidates"]] == ["capacitor.polarized"]
    card = exact["candidates"][0]
    assert card["symbol_status"] == "draft"
    assert card["physical_pins"][0]["number"] == "1"
    assert card["physical_pin_refs"][0]["symbol_anchor_um"] == [-8000, 0]
    assert card["physical_pin_refs"][0]["polarity"] == "positive"
    assert len(card["allowed_by_geometry_engine"]) == 8
    assert card["normative_transform_approval"] == "NOT_VERIFIED_PER_POSE"
    assert card["preview_tool"] == "schematic_catalog_preview"
    assert len(card["symbol_sha256"]) == 64
    assert len(card["part_sha256"]) == 64
    assert card["body_keepout_um"] != card["stroked_graphic_bounds_um"]


def test_ambiguous_coil_is_not_forced_to_ferromagnetic():
    catalog = CatalogResolver()
    options = catalog_search(catalog, "катушка с сердечником")
    choices = {row["part_id"] for row in options["candidates"]}
    assert "inductor.ferromagnetic" in choices
    assert "inductor.ferrite" in choices
    assert "inductor.air_core" not in choices
    assert "inductor.variable" not in choices
    assert len(choices) >= 3
    assert options["selection_required"]


@pytest.mark.parametrize(("word", "expected"), [
    ("ferromagnetic inductor", "inductor.ferromagnetic"),
    ("диод шоттки", "diode.schottky"),
    ("n channel enhancement mosfet", "transistor.mosfet_n_enh"),
    ("предохранитель", "fuse.general"),
])
def test_generic_mosfet_excludes_unrelated_bjt_shapes():
    options = catalog_search(CatalogResolver(), "mosfet")
    assert options["candidate_count"] >= 2
    assert all(row["part_id"].startswith("transistor.mosfet")
               for row in options["candidates"])


def test_explicit_phrase_only_returns_existing_part(word, expected):
    report = catalog_search(CatalogResolver(), word)
    assert [row["part_id"] for row in report["candidates"]] == [expected]
    assert report["candidates"][0]["physical_pin_refs"]


def test_source_matrix_all_physical_part_sha_and_no_false_approved_ic():
    cat = CatalogResolver()
    report = tl494_profile(cat)
    matrix = {row["reference"]: row for row in report["required_variants"]}
    assert set(matrix) == set(TL494_REQUIRED_PARTS)
    assert len(matrix) == 12
    for ref, wanted in TL494_REQUIRED_PARTS.items():
        assert matrix[ref]["required_part_id"] == wanted
        assert matrix[ref]["part_sha256"] == catalog_card(cat, wanted)["part_sha256"]
        assert matrix[ref]["symbol_status"] == "draft"
    assert report["not_normatively_approved"] is True
    assert report["tl494_device_catalog"] == "NOT_IN_INSTALLED_P11_CATALOG"
    assert report["unlisted_components"] == "REQUIRE_INDEPENDENT_EXACT_PART_SELECTION"
    assert {x["display_alias"] for x in report["aliases"]} == {"FB", "OC"}


def test_aliases_protect_full_name_and_physical_number():
    assert tl494_alias("FEEDBACK") == {
        "status": "EDITORIAL_DRAFT_VERIFIED_DICTIONARY",
        "full_name": "FEEDBACK", "display_alias": "FB",
        "physical_number": "3", "abbreviation_allowed": True,
        "original_name_unchanged": True,
    }
    assert tl494_alias("OUTPUT CTRL")["display_alias"] == "OC"
    assert tl494_alias("OUTPUT CTRL")["physical_number"] == "13"
    assert tl494_alias("VCC")["status"] == "ALIAS_UNVERIFIED"
    assert not tl494_alias("FEED BACK")["abbreviation_allowed"]


def test_real_installed_svg_png_preview_is_not_hand_painted():
    cat = CatalogResolver()
    for part_id in ("capacitor.polarized", "inductor.ferromagnetic",
                    "transistor.mosfet_n_enh", "diode.schottky"):
        svg, png, metadata = catalog_preview(cat, part_id)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert "<svg" in svg and part_id in svg
        assert metadata["part_id"] == part_id
        assert len(metadata["svg_sha256"]) == 64
        assert len(metadata["png_sha256"]) == 64
        assert metadata["not_a_printed_sheet"]


def test_source_backed_exact_gap_with_true_endpoint_ownership():
    a = WireObstacle("wire-R5", Line(Point(0, 0), Point(12000, 0)),
                     stroke_um=300, net_name="R5_NET")
    b = WireObstacle("wire-R6", Line(Point(1000, 500), Point(13000, 500)),
                     stroke_um=300, net_name="R6_NET")
    placed = {"R5": {"pins": {"2": Point(0, 0)}},
              "R6": {"pins": {"1": Point(1000, 500)}}}
    measured = _measured_parallel_wire_gaps((a, b), placed)
    assert len(measured) == 1
    assert measured[0]["code"] == "ESKD_PARALLEL_WIRE_CLEARANCE"
    assert measured[0]["wire_ids"] == ["wire-R5", "wire-R6"]
    assert measured[0]["wire_nets"] == ["R5_NET", "R6_NET"]
    assert measured[0]["printed_edge_gap_twice_um"] == 400
    assert measured[0]["required_edge_gap_twice_um"] == 6000
    assert measured[0]["nearby_true_pinrefs_at_endpoints"] == ["R5.2", "R6.1"]
    assert _measured_parallel_wire_gaps((
        a, WireObstacle("far", Line(Point(0, 4000), Point(12000, 4000)),
                        stroke_um=300, net_name="OTHER"),
    ), placed) == []


def test_existing_six_part_model_preflight_is_partial_not_falsely_print_ready(tmp_path: Path):
    workspace = tmp_path / "workspace"
    created = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    head = workspace / "projects" / PID / "HEAD.json"
    blob = workspace / "projects" / PID / "revisions" / (
        created.project.revision + ".gseproj"
    )
    hbytes, pbytes = head.read_bytes(), blob.read_bytes()
    report = service.preflight_design(PID, created.project.revision)
    assert report["project_id"] == PID
    assert report["project_revision"] == created.project.revision
    assert report["generation"] == 1
    assert report["component_count"] == 6
    assert len(report["nets"]) == 5
    assert report["route"]["authored_segment_count"] == 16
    assert report["route"]["explicit_junction_count"] == 3
    assert report["sheet_format"] == "NOT_PERSISTED_IN_P11"
    assert report["print_drc"] == "PARTIAL_ONLY_NOT_CERTIFIED"
    assert report["print_ready"] is False
    assert report["status"] == "BLOCKED_INCOMPLETE_PRINT_DRC"
    assert report["used_sheet_bbox_um"] is not None
    assert "multi-Net safe routing and automatic placement" in report[
        "not_implemented_checks"
    ]
    assert all("physical_pins" in c for c in report["components"])
    assert head.read_bytes() == hbytes and blob.read_bytes() == pbytes
    assert not (workspace / "artifacts").exists()


def test_wrong_tl494_ugo_yields_explicit_failure_no_silent_swap(tmp_path):
    workspace = tmp_path / "workspace"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    old = snap.project.to_record()
    report = service.preflight_design(PID, snap.project.revision, profile="tl494")
    codes = {item["code"] for item in report["diagnostics"]}
    assert "TL494_REQUIRED_COMPONENT_MISSING" in codes
    assert "TL494_UGO_VARIANT_MISMATCH" in codes
    assert report["functional_groups"]
    assert report["print_ready"] is False
    assert service.open_project(PID, snap.project.revision).project.to_record() == old


@pytest.mark.parametrize("bad", ("all", "tl494cn", "../", ""))
def test_unaccepted_profile_is_rejected_even_read_only(tmp_path, bad):
    service = ProjectService.for_workspace(tmp_path)
    with pytest.raises(ProjectError, match="REVISION_REQUIRED"):
        service.preflight_design(PID, "bad", profile=bad)


def test_semantic_unknown_never_guesses_part_or_alias():
    assert catalog_search(CatalogResolver(), "chip that looks like mosfet")[
        "status"
    ] == "NO_EXACT_CATALOG_MATCH"
    with pytest.raises(ProjectError, match="INVALID_SEMANTIC_QUERY"):
        catalog_search(CatalogResolver(), "../capacitor")
    with pytest.raises(ProjectError, match="CATALOG_PART_MISSING"):
        catalog_preview(CatalogResolver(), "transistor.anything")
