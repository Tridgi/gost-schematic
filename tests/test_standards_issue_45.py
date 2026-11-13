"""Issue #45: independent evidence and existing C3 geometry regression.

These tests preserve source traceability. Passing does NOT approve a GOST
symbol or authorize silently changing a diagram's selected symbol.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "standards" / "issue-45-capacitor-comparison.json"
REPORT_PATH = ROOT / "docs" / "standards" / "issue-45-polarized-electrolytic-review.md"
CATALOG = ROOT / "src" / "gost_schematic" / "catalog"
SVG = ROOT / "tests" / "fixtures" / "electrical-cycle3" / "end-to-end-clean.svg"
NS = "{http://www.w3.org/2000/svg}"


def _evidence():
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def _source(name, kind):
    return json.loads(
        (CATALOG / kind / "capacitors" / f"{name}.json").read_text(encoding="utf-8")
    )


def _c3():
    root = ET.parse(SVG).getroot()
    matches = [
        element for element in root.iter(f"{NS}g")
        if element.attrib.get("data-reference") == "C3"
        and element.attrib.get("data-layer") == "symbols"
    ]
    assert len(matches) == 1
    return root, matches[0]


def _outline_extent(lines):
    endpoints = [
        (float(item.attrib[key1]), float(item.attrib[key2]))
        for item in lines
        for key1, key2 in (("x1", "y1"), ("x2", "y2"))
    ]
    xs, ys = zip(*endpoints, strict=True)
    return (min(xs), min(ys), max(xs), max(ys))


def test_issue45_source_is_active_and_draft_only():
    p = _evidence()
    assert p["issue"] == 45
    assert p["branch"] == "parallel/standards-review45"
    assert p["baseline_sha"] == "73bc6f88a814d7b92267326fc1dab8f127e92e77"
    assert p["status"] == "DRAFT_BLOCKED_GEOMETRY"
    assert p["reference"]["status"] == "Действует"
    assert p["reference"]["official_url"].startswith("https://protect.gost.ru/")
    assert p["reference"]["figure_pdf"].endswith("gost_2.728-74.pdf")
    assert p["reference"]["pages_1_based"] == {
        "table4": 7,
        "table5_and_paragraph7": 9,
        "table6_9_10": 10,
    }
    assert p["boundary"]["approved"] == 0
    assert "PR #38" in p["boundary"]["untouched"]


def test_nine_evidence_cards_keep_two_families_separate():
    records = {x["id"]: x for x in _evidence()["rules"]}
    assert len(records) == 9
    assert set(records) == {
        "R45-GENERIC-POLAR",
        "R45-EL-POLAR",
        "R45-EL-NONPOLAR",
        "R45-PLUS",
        "R45-GENERIC-DIMS",
        "R45-ELECTROLYTIC-DIMS",
        "R45-LINE-WEIGHT",
        "R45-PRINTING-EXCEPTION",
        "R45-DISPLAY-POLICY",
    }
    assert records["R45-GENERIC-POLAR"]["target"] == "capacitor.polarized"
    assert records["R45-EL-POLAR"]["target"] == "capacitor.electrolytic"
    assert records["R45-EL-NONPOLAR"]["target"] == "future_only"
    assert records["R45-DISPLAY-POLICY"]["classification"] == "editorial_policy"
    assert "2а" in records["R45-EL-POLAR"]["source"]
    assert "2б" in records["R45-EL-NONPOLAR"]["source"]


def test_proven_dimensions_are_not_relabelled_as_other_ugo_dimensions():
    cards = {x["id"]: x for x in _evidence()["rules"]}
    general = cards["R45-GENERIC-DIMS"]["dimensional_rule_mm"]
    special = cards["R45-ELECTROLYTIC-DIMS"]["dimensional_rule_mm"]
    assert general == {"plate_length": 8, "plate_centerline_separation": 1.5}
    assert special == {"left_outline_strip_width": 1.5, "right_outline_strip_width": 1.5}
    for invented in ("strip_height", "inner_gap", "lead_extent"):
        assert invented not in special
    assert cards["R45-ELECTROLYTIC-DIMS"]["classification"] == (
        "source_confirmed_limited"
    )


@pytest.mark.parametrize("name", ["polarized", "electrolytic"])
def test_existing_part_polarity_is_unchanged_and_not_the_symbol_style(name):
    symbol = _source(name, "symbols")
    part = _source(name, "parts")
    assert symbol["status"] == "draft"
    assert part["symbol_id"] == symbol["id"]
    assert part["voltage_orientation_rule"] == "positive_not_below_negative"
    assert [(x["number"], x["name"], x["polarity"]) for x in part["pins"]] == [
        ("1", "PLUS", "positive"),
        ("2", "MINUS", "negative"),
    ]
    assert symbol["conductor_topology"]["pin_groups"] == [["1"], ["2"]]


def test_two_outline_strips_are_unfilled_and_not_broken():
    symbol = _source("electrolytic", "symbols")
    assert symbol["geometry"]["rectangles"] == []
    assert len(symbol["geometry"]["lines"]) == 12
    assert symbol["conductor_topology"]["indices"] == list(range(10))
    assert symbol["conductor_topology"]["junctions_mm"] == [[-2.25, 0], [2.25, 0]]
    _, group = _c3()
    assert group.attrib["fill"] == "none"
    assert group.attrib["stroke-width"] == "0.3"
    lines = list(group.findall(f"{NS}line"))
    assert len(lines) == 12
    assert _outline_extent(lines[2:6]) == (97.75, 71.0, 99.25, 79.0)
    assert _outline_extent(lines[6:10]) == (100.75, 71.0, 102.25, 79.0)
    assert group.find(f"{NS}rect") is None


def test_rectangles_have_1_5_mm_width_but_unapproved_height_and_gap():
    _, group = _c3()
    lines = list(group.findall(f"{NS}line"))
    left = _outline_extent(lines[2:6])
    right = _outline_extent(lines[6:10])
    assert left[2] - left[0] == right[2] - right[0] == 1.5
    assert left[3] - left[1] == right[3] - right[1] == 8.0
    assert right[0] - left[2] == 1.5
    observed = _evidence()["observed"]["c3_svg"]
    assert observed["strip_width_mm"] == 1.5
    assert observed["strip_height_mm"] == 8
    assert observed["centerline_interior_gap_mm"] == 1.5
    assert "Нормативность общей высоты 8 мм специального УГО не доказана" in (
        _evidence()["unresolved"]
    )


def test_generic_polarized_has_single_plate_strokes_not_wide_outlines():
    symbol = _source("polarized", "symbols")
    lines = symbol["geometry"]["lines"]
    assert symbol["geometry"]["rectangles"] == []
    assert len(lines) == 6
    assert lines[2] == [[-0.75, -4], [-0.75, 4]]
    assert lines[3] == [[0.75, -4], [0.75, 4]]
    assert symbol["conductor_topology"]["indices"] == [0, 1, 2, 3]


def test_c3_plus_marker_and_real_pin_positions_are_explicit():
    _, group = _c3()
    lines = list(group.findall(f"{NS}line"))
    assert _outline_extent(lines[10:12]) == (96.0, 70.0, 97.0, 71.0)
    symbol = _source("electrolytic", "symbols")
    assert [(p["number"], p["label"], p["at_mm"]) for p in symbol["pins"]] == [
        ("1", "+", [-9, 0]),
        ("2", "", [9, 0]),
    ]
    assert _evidence()["observed"]["c3_svg"]["physical_pin_centres_mm"] == {
        "PLUS": [91, 75], "MINUS": [109, 75],
    }


def test_sheet_wiring_stroke_and_c3_stroke_match_part7():
    root, c3 = _c3()
    wire_widths = {
        float(x.attrib["stroke-width"])
        for x in root.iter(f"{NS}line")
        if x.attrib.get("data-layer") == "wires"
    }
    assert wire_widths == {float(c3.attrib["stroke-width"])}
    assert wire_widths == {_evidence()["observed"]["c3_svg"]["stroke_mm"]}


def test_selection_policy_is_conditional_not_silent_replacement():
    policy = _evidence()["source_preserving_policy"]
    assert policy["default_for_generic_teaching"] == "capacitor.polarized"
    assert policy["conditions"]
    assert policy["specialized_when"]
    assert policy["forbidden"]
    forbidden = " ".join(policy["forbidden"]).lower()
    assert "автоматически менять" in forbidden
    assert "полярност" in forbidden
    assert _evidence()["boundary"]["status_of_both"] == "DRAFT"


def test_narrative_preserves_source_ambiguity_and_catalog_ownership():
    report = REPORT_PATH.read_text(encoding="utf-8")
    for phrase in (
        "табл. 4", "поз. 2а", "поз. 2б", "поз. 10", "контур", "заливк",
        "1,5 мм", "8 мм", "DRAFT", "BLOCKED", "YGO", "PR #38",
    ):
        assert phrase.lower() in report.lower()
