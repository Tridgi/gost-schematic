"""Issue #107–#110 ESKD source-scoped normative regression.

No production catalog/rendering imports, no fake 1:1 official-source approval.
The owner's actual catalogue JSON and exact blob SHAs are frozen as evidence;
our gallery is a project-vector reproduction, not an official figure copy.
"""
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/standards"
SOURCE = D / "issue107-ugo-source-snapshots.json"
MATRIX = D / "issue107-ugo-normative-matrix.json"
REPORT = D / "issue107-tl494-normative-review.md"
EVIDENCE = D / "evidence"
SVG = "{http://www.w3.org/2000/svg}"


def _source():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def _matrix():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _cards():
    return {x["id"]: x for x in _matrix()["cards"]}


def _source_symbols():
    return {x["id"]: x for x in _source()["cards"]}


def _rotate90(pt):
    return [-pt[1], pt[0]]


def test_baseline_and_read_only_reference_pins_are_pinned():
    a, b = _source(), _matrix()
    assert a["baseline"] == b["base_sha"] == (
        "afd359cf2c63337471e746e5ff7f399b76394612"
    )
    assert a["reference_head"] == b["reference_head"] == (
        "e695c415fdced164b0e0c39c5249d030795a0aa6"
    )
    assert b["reference_manifest_blob"] == (
        "b2375feb43ad18b8a8e5a515bfc007d169b26908"
    )
    assert b["approved"] == 0


def test_twelve_source_project_objects_have_genuine_frozen_git_blob_shas():
    objects = _source_symbols()
    assert len(objects) == 12
    for symbol in objects.values():
        assert len(symbol["owner_blob_sha"]) == 40
        assert symbol["owner_file"].startswith(
            "src/gost_schematic/catalog/"
        )
        if symbol["geometry"]:
            assert symbol["pins"]
        else:
            assert symbol["coil_profile"]
        assert symbol["owner_stroke_mm"] > 0


def test_all_normative_cards_have_original_pdf_figure_and_negative_test():
    entries = _matrix()["cards"]
    assert len(entries) == 21
    assert len({x["id"] for x in entries}) == 21
    for item in entries:
        assert item["source"]["url"].startswith("https://")
        assert "#page=" in item["source_figure_url"]
        assert item["source_clauses"] and item["positive_test"]
        assert item["negative_test"] and item["approval"] == "DRAFT"
        assert not item["real_part_certificate"]
        assert item["status_full_1to1"] == "BLOCKED"
    assert _matrix()["figure_policy"].startswith("Link primary original")


def test_schottky_exact_original_owner_hooks_are_asymmetric_and_cathode_only():
    c = _cards()["diode.schottky"]
    s = _source_symbols()["diode.schottky"]
    assert c["owner_blob_sha"] == (
        "38cf0cd20b111719cb2b9b3147397346e455b231"
    )
    points = c["signature_mm"]
    assert points["cathode_x"] == 2.5
    assert points["anode_mm"] == [-10, 0]
    assert points["cathode_pin_mm"] == [10, 0]
    assert points["upper_hook"] == [
        [2.5, -3.3], [4.2, -3.3], [4.2, -1.8]
    ]
    assert points["lower_hook"] == [
        [2.5, 3.3], [0.8, 3.3], [0.8, 4.8]
    ]
    # The hook's horizontal bends have different direction from the stem.
    assert points["upper_hook"][1][0] > points["cathode_x"]
    assert points["lower_hook"][1][0] < points["cathode_x"]
    assert [p["label"] for p in s["pins"]] == ["A", "K"]
    assert s["owner_stroke_mm"] == 0.3


def test_schottky_r90_true_preserves_top_anode_bottom_cathode_and_chirality():
    d = _cards()["diode.schottky"]["signature_mm"]
    r = d["R90_clockwise_screen"]
    assert _rotate90(d["anode_mm"]) == r["A"] == [0, -10]
    assert _rotate90(d["cathode_pin_mm"]) == r["K"] == [0, 10]
    assert [_rotate90(p) for p in d["upper_hook"]] == r["upper_hook"]
    assert [_rotate90(p) for p in d["lower_hook"]] == r["lower_hook"]
    assert r["upper_hook"][0][0] > 0
    assert r["lower_hook"][0][0] < 0


def test_schottky_d4_svg_uses_one_actual_owner_blob_and_four_exact_poses():
    root = ET.fromstring((EVIDENCE /
        "issue107-schottky-d4-owner-1to1.svg").read_text(
            encoding="utf-8"
        ))
    assert root.get("width") == "238mm"
    assert root.get("viewBox") == "0 0 238 125"
    assert root.get("data-evidence") == (
        "ACTUAL_OWNER_JSON_MM_NOT_CALIBRATED_NORMATIVE_OVERLAY"
    )
    groups = [
        g for g in root.findall(".//" + SVG + "g")
        if g.get("data-symbol") == "diode.schottky"
    ]
    assert len(groups) == 4
    assert {g.get("data-orientation") for g in groups} == {
        "0", "90", "180", "270"
    }
    sha = _cards()["diode.schottky"]["owner_blob_sha"]
    assert all(g.get("data-source-blob") == sha for g in groups)
    all_lines = len(
        _source_symbols()["diode.schottky"]["geometry"]["lines"]
    )
    for g in groups:
        assert len(g.findall(".//" + SVG + "path")) == all_lines
        assert len([
            p for p in g.findall(".//" + SVG + "circle")
            if p.get("data-pin") is not None
        ]) == 2


def test_capacitor_two_separate_valid_ugo_families_and_photo_selection():
    cs = _cards()
    thin = cs["capacitor.polarized"]
    thick = cs["capacitor.electrolytic"]
    assert "position 1 note" in thin["source_clauses"]
    assert "position 2а" in thick["source_clauses"]
    assert thin["status_source_shape"] == "PASS"
    assert thick["status_source_shape"] == "PASS"
    assert thin["photo_instances"] == ["C1", "C2", "C3", "C5", "C6"]
    assert thick["selected_for_TL494_reference"] is False
    assert thin["polarity_electrical_gate"].startswith("BLOCKED")
    assert cs["capacitor.fixed"]["status_source_shape"] == "PASS"


@pytest.mark.parametrize("device", ["inductor.ferromagnetic", "choke.ferromagnetic"])
def test_ferromagnetic_core_profiles_not_air_or_dashed(device):
    target = _cards()[device]
    assert "ferromagnetic" in target["id"]
    assert target["owner_profile"]["core"] == "ferromagnetic"
    assert target["owner_profile"]["turns"] == 4
    assert target["owner_profile"]["radius_mm"] == "2"
    assert target["status_full_1to1"] == "BLOCKED"


def test_magnetodielectric_and_ferromagnetic_profiles_are_not_interchangeable():
    a = _cards()["inductor.ferromagnetic"]["owner_profile"]
    b = _cards()["inductor.magnetodielectric"]["owner_profile"]
    assert a["core"] == "ferromagnetic"
    assert b["core"] == "magnetodielectric"


def test_ground_type_markers_are_not_physical_parts_or_shorting_nets():
    d = _cards()
    ids = [
        "net-marker.common", "net-marker.earth",
        "net-marker.protective_earth",
        "net-marker.chassis", "net-marker.equipotential"
    ]
    for id_ in ids:
        item = d[id_]
        assert item["requires_existing_net"]
        assert item["marker_may_create_physical_part"] is False
        assert item["owner_source_path"] is None
    assert d["net-marker.common"]["status_source_shape"] == "BLOCKED"
    assert "protection" not in d["net-marker.common"]["positive_test"].lower()
    assert "PE" in d["net-marker.protective_earth"]["positive_test"]


def test_sheet_continuation_standard_2701_has_different_arrow_policy():
    c = _cards()
    a = c["net-continuation.other-sheet"]
    b = c["net-continuation.same-sheet"]
    assert a["source_clauses"].startswith("ГОСТ 2.701 §5.5.3")
    assert b["source_clauses"].startswith("ГОСТ 2.701 §5.5.4")
    assert "no arrow" in a["positive_test"]
    assert "arrow" in b["positive_test"]
    assert "sheet,zone" in a["positive_test"]


def test_print_dimensions_exact_and_recommendation_are_different_fields():
    c = _cards()["drc.clearances"]
    h = c["hard_mm"]
    r = c["recommendation_mm"]
    assert h == {
        "adjacent_ugo_line_gap": 1,
        "distinct_ugo_gap": 2,
        "parallel_interconnect_gap": 3,
        "wire_stroke_min": 0.2,
        "wire_stroke_max": 1,
    }
    assert r == {"wire_stroke_min": 0.3, "wire_stroke_max": 0.4}
    # For two 0.3-mm identical lines, stroke-edge gap 3mm needs c-c 3.3.
    assert math.isclose(
        h["parallel_interconnect_gap"] + r["wire_stroke_min"],
        3.3,
        abs_tol=1e-12,
    )
    assert c["tl494_wire_drc_real_run"].startswith("BLOCKED")


def test_pwm_bottom_to_top_is_minus90_in_svg_screen_space_and_is_draft():
    c = _cards()["ic.TL494CN"]
    f = c["function_text_bottom_to_top"]
    assert f["svg_local_angle_degrees"] == -90
    assert f["svg_matrix"] == "matrix(0,-1,1,0,0,0)"
    assert f["gost_approval"] == "BLOCKED"
    assert c["max_display_characters"] == 6
    assert c["maximum_rule"] == "EDITORIAL_NOT_GOST"
    assert c["aliases"] == {
        "3": {"manufacturer": "FEEDBACK", "display": "FB"},
        "13": {"manufacturer": "OUTPUT CTRL", "display": "OC"},
    }


def test_all_candidate_glyphs_in_original_svg_gallery_are_source_pinned():
    root = ET.fromstring((EVIDENCE /
        "issue107-catalog-12-draft-source-gallery.svg").read_text(
            encoding="utf-8"
        ))
    assert root.get("width") == "320mm"
    ids = {g.get("data-symbol") for g in root.findall(
        ".//" + SVG + "g") if g.get("data-symbol")
    }
    assert ids == set(_source_symbols())
    ind = [g for g in root.findall(".//" + SVG + "g")
           if g.get("data-vector-provenance") is not None]
    assert len(ind) == 3
    assert all(g.get("data-vector-provenance") ==
               "EDITORIAL_PROFILE_ONLY_NOT_OWNER_RENDERER_OUTPUT"
               for g in ind)


def test_report_explicitly_denies_unsigned_rotations_and_auto_pe_bonds():
    text = REPORT.read_text(encoding="utf-8")
    for tok in [
        "R90_screen_clockwise", "Schottky", "body", "PE",
        "ГОСТ 2.701", "5.5.3", "5.5.4", "FB", "OC",
        "DRAFT", "BLOCKED", "300DPI", "2.723-68",
        "2.728-74", "2.721-74", "2.730-73",
        "23", "15", "16", "91"
    ]:
        assert tok in text
