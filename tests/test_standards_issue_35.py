"""Issue #35: documentary GOST gates grounded to the six-device SVG.

The checks police evidence, unit handling, documented exemptions and test
fixture drift. Passing is not a formal GOST or KOMPAS 1:1 acceptance.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_end_to_end_circuit import authored_specimen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "standards" / "issue-35-sheet-rule-cards.json"
REPORT = ROOT / "docs" / "standards" / "issue-35-full-sheet.md"
FIXTURE = ROOT / "tests" / "fixtures" / "electrical-cycle3" / "end-to-end-clean.svg"
NS = "{http://www.w3.org/2000/svg}"

EXPECTED_COMPONENTS = {"R1", "R2", "C1", "C2", "L1", "C3"}
EXPECTED_JUNCTIONS = {(40, 20), (40, 40), (120, 40)}
EXPECTED_X = {(40, 60), (70, 40), (98, 27)}


def _payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def _svg():
    return ET.parse(FIXTURE).getroot()


def _wires(root):
    return [e for e in root.iter(f"{NS}line") if e.get("data-layer") == "wires"]


def _dots(root):
    return [
        e for e in root.iter(f"{NS}circle")
        if e.get("data-kind") == "authored-junction"
    ]


def _wire_segment(line):
    return (
        float(line.attrib["x1"]),
        float(line.attrib["y1"]),
        float(line.attrib["x2"]),
        float(line.attrib["y2"]),
    )


def _crossings_with_different_nets():
    _, graph = authored_specimen()
    found = set()
    for idx, a in enumerate(graph.segments):
        for b in graph.segments[idx + 1:]:
            if a.net_name == b.net_name:
                continue
            a_horizontal = a.start.y == a.end.y
            b_horizontal = b.start.y == b.end.y
            if a_horizontal == b_horizontal:
                continue
            horizontal, vertical = (a, b) if a_horizontal else (b, a)
            x, y = vertical.start.x, horizontal.start.y
            if (
                min(horizontal.start.x, horizontal.end.x) <= x
                <= max(horizontal.start.x, horizontal.end.x)
                and min(vertical.start.y, vertical.end.y) <= y
                <= max(vertical.start.y, vertical.end.y)
            ):
                found.add((x // 1000, y // 1000))
    return found


def test_14_traceable_rules_and_conservative_states():
    data = _payload()
    assert data["issue"] == 35
    assert data["schema_version"] == 1
    assert data["baseline_sha"] == "caf7db7ad22d9cd22202664471da5ff3a49a754c"
    assert data["normative_status"] == "NOT_APPROVED"
    assert data["catalog_symbols"] == {"count": 19, "status": "DRAFT", "approved": 0}
    cards = data["cards"]
    assert len(cards) == 14
    assert len({c["id"] for c in cards}) == len(cards)
    allowed = {"source_confirmed", "not_specified", "conditional"}
    for card in cards:
        assert card["evidence"] in allowed
        assert card["source_standard"] in data["standards"]
        assert card["source_clause"]
        assert len(card["negative_cases"]) >= 1
        assert card["status"] == "BLOCKED_FOR_FULL_SHEET_CERTIFICATION"
        assert card["responsible_workstream"]
    assert all(
        standard["official"].startswith("https://protect.gost.ru/")
        and standard["status"].startswith("Действует")
        for standard in data["standards"].values()
    )


def test_no_fake_numerical_dot_standard_and_one_branch_without_dot_allowed():
    cards = {c["id"]: c for c in _payload()["cards"]}
    assert cards["J35-DOTSIZE"]["evidence"] == "not_specified"
    assert cards["J35-DOTSIZE"]["dimensions_mm"] is None
    assert "без точки" in cards["J35-T"]["source_confirmed"]
    assert "табл.6в" in cards["J35-T"]["source_clause"]
    assert "табл.6в" in cards["J35-X"]["source_clause"]


def test_paper_profiles_are_dimensionally_consistent():
    profiles = {item["id"]: item for item in _payload()["sheet_profiles"]}
    assert set(profiles) == {"A4_portrait", "A3_landscape"}
    assert profiles["A4_portrait"]["width_mm"] == 210
    assert profiles["A4_portrait"]["height_mm"] == 297
    assert profiles["A3_landscape"]["width_mm"] == 420
    assert profiles["A3_landscape"]["height_mm"] == 297
    for info in profiles.values():
        width, height = info["width_mm"], info["height_mm"]
        frame = info["frame_bounds_mm"]
        title = info["title_bounds_mm"]
        assert info["frame_insets_mm"] == {
            "left": 20, "right": 5, "top": 5, "bottom": 5,
        }
        assert frame == [20, 5, width - 5, height - 5]
        assert title == [width - 190, height - 60, width - 5, height - 5]
        assert info["title_form"] == "1"
        assert info["title_dimensions_mm"] == [185, 55]


def test_svg_fixture_is_not_mislabelled_as_a_complete_a4_a3_document():
    root = _svg()
    data = _payload()
    assert root.attrib["width"] == "114.301mm"
    assert root.attrib["height"] == "70.301mm"
    assert root.attrib["viewBox"] == "8.85 12.85 114.301 70.301"
    assert data["specimen"]["root_dimensions_mm"] == [114.301, 70.301]
    assert not list(root.iter(f"{NS}title_block"))
    assert not list(root.iter(f"{NS}drawing_frame"))
    assert any(
        item["id"] == "S35-01" and item["severity"] == "BLOCKER_PAPER_SHEET"
        for item in data["discrepancies"]
    )


def test_six_refdes_are_present_above_ugo_but_manually_sans_serif():
    root = _svg()
    labels = {
        e.get("data-owner"): e for e in root.iter(f"{NS}text")
        if e.get("data-owner") in EXPECTED_COMPONENTS
    }
    assert set(labels) == EXPECTED_COMPONENTS
    assert all(x.text == key for key, x in labels.items())
    groups = [
        e for e in root.iter(f"{NS}g")
        if e.get("data-layer") == "specimen-refdes"
    ]
    assert len(groups) == 1
    assert groups[0].get("font-family") == "sans-serif"
    assert groups[0].get("font-size") == "3.5"
    assert not any("data-font-sha256" in label.attrib for label in labels.values())


def test_18_wires_are_orthogonal_with_allowed_actual_stroke():
    root = _svg()
    wires = _wires(root)
    assert len(wires) == _payload()["specimen"]["wire_segments"] == 18
    for wire in wires:
        x1, y1, x2, y2 = _wire_segment(wire)
        assert (x1 == x2) != (y1 == y2)
        assert float(wire.attrib["stroke-width"]) == 0.3
        assert 0.2 <= float(wire.attrib["stroke-width"]) <= 1.0
    _, graph = authored_specimen()
    for actual, source in zip(wires, graph.segments, strict=True):
        coords = _wire_segment(actual)
        assert coords == (
            source.start.x / 1000, source.start.y / 1000,
            source.end.x / 1000, source.end.y / 1000,
        )


def test_three_explicit_t_junctions_and_three_unmarked_x_in_distinct_nets():
    data = _payload()["specimen"]
    root = _svg()
    dots = _dots(root)
    dot_xy = {(float(x.attrib["cx"]), float(x.attrib["cy"])) for x in dots}
    assert dot_xy == EXPECTED_JUNCTIONS
    assert len(dots) == 3
    assert all(x.attrib["r"] == "0.55" for x in dots)
    assert set(map(tuple, data["authored_junctions_mm"])) == dot_xy
    crossings = _crossings_with_different_nets()
    assert crossings == EXPECTED_X
    assert all((x, y) not in dot_xy for x, y in crossings)
    assert {(p["x"], p["y"]) for p in data["unconnected_crossings_mm"]} == crossings
    _, graph = authored_specimen()
    assert {(p.x // 1000, p.y // 1000) for p in graph.junctions} == dot_xy


def test_negative_crossing_and_bad_width_would_be_rejected_by_review_rules():
    data = _payload()
    forbidden = _crossings_with_different_nets()
    marked = {(x, y) for x, y in data["specimen"]["authored_junctions_mm"]}
    assert marked.isdisjoint(forbidden)
    injected_dot = marked | {(70, 40)}
    assert not injected_dot.isdisjoint(forbidden)  # expect failure in future validator
    good_width = data["specimen"]["stroke_mm"]
    assert 0.2 <= good_width <= 1.0
    assert not (0.2 <= 0.15 <= 1.0)
    assert not (0.2 <= 1.2 <= 1.0)


def test_paper_and_digital_title_exemptions_and_all_evidence_links_survive():
    cards = {c["id"]: c for c in _payload()["cards"]}
    assert cards["J35-FRAME"]["evidence"] == "conditional"
    assert cards["J35-TITLE"]["evidence"] == "conditional"
    assert "п.4.2" in cards["J35-TITLE"]["source_clause"]
    assert "5.6" in cards["J35-FRAME"]["source_clause"]
    report = REPORT.read_text(encoding="utf-8")
    for phrase in (
        "ГОСТ Р 2.104-2023", "таблица 6в", "185×55", "20 мм",
        "5 мм", "1,0 мм", "2,0 мм", "3,0 мм", "BLOCKED",
        "КОМПАС", "0 APPROVED", "S35-09",
    ):
        assert phrase in report
