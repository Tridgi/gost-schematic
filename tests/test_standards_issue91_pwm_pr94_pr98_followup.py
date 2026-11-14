"""Independent ESKD Issue #91 follow-on review (no production code).

Frozen normative evidence: #94 exact source JSON geometry and #98 two-sheet
asset metadata, checked against primary-source figure interpretations.
A passing test asserts the DRAFT report is self-consistent; it does not
constitute 1:1 GOST source-overlay approval.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs/standards"
DOC = DIR / "issue91-pwm-15ugo-netrefs-primary-review.md"
MATRIX = DIR / "issue91-pwm-pr94-pr98-acceptance.json"
SYMBOLS = DIR / "issue91-pr94-15-ugo-visual-metric-review.json"
GALLERY = DIR / "evidence/issue91-cycle7-pr94-15-ugo-1to1-project-geometry.svg"
NS = "{http://www.w3.org/2000/svg}"


def matrix():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def cases():
    return {x["id"]: x for x in matrix()["case_policies"]}


def symbols():
    return json.loads(SYMBOLS.read_text(encoding="utf-8"))


def test_merger_history_not_overwritten_and_new_exact_baseline_is_pinned():
    d = matrix()
    assert d["historical_merged_pr95_unchanged"] is True
    assert d["integration_base"] == "8bc768c72bad85b128f28311a316f25c8bb97807"
    assert d["owner_pins"] == {
        "pr94": "47b0589ffa048c0801b6b8604582efd62a63acc9",
        "pr98": "77463052796e315dfee4d4859695cdb00beeb74d",
    }
    assert d["zero_new_approved_symbols"] is True


def test_default_horizontal_pwm_pass_only_conditionally():
    d = cases()
    assert d["PWM-FIXED-VERTICAL-BODY-FUNCTION-0"]["status"] == (
        "PASS_CONDITIONAL"
    )
    assert d["PWM-FIXED-VERTICAL-BODY-FUNCTION-90"]["status"] == "BLOCKED"
    assert d["PWM-FIXED-VERTICAL-BODY-FUNCTION-270"]["status"] == "BLOCKED"
    assert "§2.1.6" in d["PWM-FIXED-VERTICAL-BODY-FUNCTION-90"]["clause"]


def test_fig3_whole_profile_only_and_fig4_requires_flow_arrows():
    d = cases()
    assert d["PWM-FIG3-TOP-BOTTOM-VERTICAL-PROFILE"]["status"] == (
        "PASS_CONDITIONAL"
    )
    fig4 = d["PWM-FIG4-REVERSED-FLOW"]
    assert fig4["status"] == "PASS_CONDITIONAL"
    assert any("directional arrows" in x for x in fig4["mandatory_dimensions"])
    assert any("function corresponds" in x for x in
               fig4["mandatory_dimensions"])


def test_pwm_unlisted_code_needs_explicit_sheet_explanation():
    item = cases()["PWM-UNLISTED-FUNCTION-NAME"]
    assert item["status"] == "BLOCKED"
    assert "§2.2.6" in item["clause"]
    assert any("explained" in x for x in item["mandatory_dimensions"])
    assert "PWM" in DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("angle", ["0", "90", "270"])
def test_angular_cases_never_claim_production_approved(angle):
    entry = cases()["PWM-FIXED-VERTICAL-BODY-FUNCTION-" + angle]
    assert not entry["physical_component_approved"]
    assert entry["source"]["standard"] == "ГОСТ 2.743-91"
    assert entry["positive"] and entry["negative"]
    assert isinstance(entry["mandatory_dimensions"], list)
    assert isinstance(entry["allowed_source_variants"], list)


def test_all_15_real_pr94_shape_ids_with_source_blobs_and_real_mm():
    proof = symbols()
    assert proof["count"] == len(proof["cards"]) == 15
    assert proof["pr94_head"] == matrix()["owner_pins"]["pr94"]
    ids = [c["id"] for c in proof["cards"]]
    assert len(set(ids)) == 15
    assert sum(name.startswith("resistor.") for name in ids) == 2
    assert "fuse.general" in ids
    assert sum(name.startswith("diode.") for name in ids) == 4
    assert sum(name.startswith("transistor.") for name in ids) == 8
    for entry in proof["cards"]:
        assert len(entry["blob_sha"]) == 40
        assert entry["observed_1to1_json"]["stroke_mm"] > 0
        assert len(entry["observed_1to1_json"]["pins"]) in (2, 3)
        assert entry["status"] == "DRAFT"
        assert entry["full_ugo_source_1to1"].startswith("BLOCKED")
        assert entry["physical_part_signoff"].startswith("BLOCKED")
        assert entry["figure"]


def test_all_fifteen_symbol_and_real_abstract_part_records_are_paired():
    proof = symbols()
    assert proof["paired_owner_parts_verified"] == 15
    for item in proof["cards"]:
        assert item["paired_part_symbol_id"] == item["id"]
        assert len(item["paired_part_blob_sha"]) == 40
        assert item["paired_part_file"].replace("/parts/", "/symbols/") == (
            item["path"]
        )
        graphic = item["observed_1to1_json"]["pins"]
        part = item["paired_part_pin_manifest"]
        assert len(graphic) == len(part)
        assert {p["number"]: p["label"] for p in graphic} == {
            p["number"]: p["name"] for p in part
        }
        assert all(p["electrical_type"] == "passive" for p in part)
        assert item["paired_part_number_to_graphic_role_verified"]
        assert "not an authenticated manufacturer pinout" in (
            item["paired_part_note"]
        )


def test_numpy_free_svg_1to1_mm_and_all_fifteen_frozen_owner_shapes():
    svg = ET.fromstring(GALLERY.read_text(encoding="utf-8"))
    assert svg.get("width") == "315mm"
    assert svg.get("height") == "267mm"
    assert svg.get("viewBox") == "0 0 315 267"
    assert svg.get("data-approval") == "BLOCKED_SOURCE_1_TO_1"
    groups = {g.get("data-id"): g for g in svg.findall(".//" + NS + "g")
              if g.get("data-id") is not None}
    manifest = symbols()
    assert set(groups) == {c["id"] for c in manifest["cards"]}
    for c in manifest["cards"]:
        group = groups[c["id"]]
        assert group.get("data-source-blob") == c["blob_sha"]
        assert float(group.get("data-line-width-mm")) == (
            c["observed_1to1_json"]["stroke_mm"]
        )
        pins = group.findall(NS + "circle")
        declared = len(c["observed_1to1_json"]["pins"])
        count_case = len(c["observed_1to1_json"]["circles"])
        assert len(pins) == declared + count_case
        assert sum(x.get("data-pin") is not None for x in pins) == declared


def test_original_npn_with_shield_is_not_generic_3pin():
    d = symbols()["cards"]
    for name in ("transistor.bjt_npn", "transistor.bjt_npn.with_case"):
        e = next(x for x in d if x["id"] == name)
        assert e["source_feature_status"] == "BLOCKED_DERIVED_NPN"
        assert "SHIELDED" in e["figure"]
        assert len(e["observed_1to1_json"]["pins"]) == 3


def test_case_variant_is_schematic_not_package_footprint():
    d = symbols()["cards"]
    circles = [x for x in d if x["observed_1to1_json"]["circles"]]
    assert len(circles) == 4
    for item in circles:
        assert item["id"].endswith(".with_case")
        assert len(item["observed_1to1_json"]["pins"]) == 3
    assert symbols()["implemented_real_connector_ugo"] == 0
    assert "connector.plug" in symbols()["missing"]
    assert "connector.socket" in symbols()["missing"]


def test_led_light_and_schottky_cathode_source_must_not_be_generic():
    d = {x["id"]: x for x in symbols()["cards"]}
    assert "Schottky" in d["diode.schottky"]["source_feature"]
    assert "outward" in d["diode.led"]["source_feature"]
    assert "inward" in d["diode.photodiode"]["source_feature"]
    assert "plate" in d["diode.varicap"]["source_feature"]


def test_gost_2721_arrowless_note3_is_explicit_and_not_deprecated():
    cases_map = cases()
    assert cases_map["NET-ARROW-BREAK-ITEM8"]["status"] == "PASS"
    note = cases_map["NET-BREAK-ARROWLESS-ITEM35-NOTE3"]
    assert note["status"] == "PASS"
    assert "прим.3" in note["clause"]
    assert "no arrow" in " ".join(note["allowed_source_variants"])
    assert "every break" in note["negative"]


def test_pr98_real_net_reciprocal_sheetzone_not_full_gost_attachment_address():
    d = cases()
    assert d["NET-PR98-TWO-SHEET"]["status"] == "PASS_EDITORIAL_ONLY"
    assert d["NET-RECIPROCAL-ELEMENT-ADDRESS"]["status"] == "BLOCKED"
    assert "1/D4" in " ".join(
        d["NET-RECIPROCAL-ELEMENT-ADDRESS"]["editorial_settings"]
    )
    assert "DD1.5" in d["NET-RECIPROCAL-ELEMENT-ADDRESS"]["positive"]
    assert not d["CONNECTOR-XP-XS-OUTSTANDING"]["physical_component_approved"]


def test_no_new_production_module_changes_are_implied_by_docs():
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "8bc768c72bad85b128f28311a316f25c8bb97807",
        "47b0589ffa048c0801b6b8604582efd62a63acc9",
        "77463052796e315dfee4d4859695cdb00beeb74d",
        "PWM", "0°", "90°", "270°", "BLOCKED",
        "ГОСТ 2.721-74", "ГОСТ 2.709-89", "DD1.5", "VT1.G",
    ):
        assert marker in text
    assert all(c["physical_component_approved"] is False
               for c in matrix()["case_policies"])
