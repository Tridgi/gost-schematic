"""Issue #63: independent, pinned standards evidence for PR #59 form 1.

Never imports PR #59 production rendering into integration. Tests verify
documentary evidence and the *actual* historical/live C3 fixtures. They do
not certify a printout or authorize changing any UGO status.
"""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "standards" / "issue-63-form-one-matrix.json"
REPORT = ROOT / "docs" / "standards" / "issue-63-form-one-review.md"
PNG = ROOT / "docs" / "standards" / "evidence" / "issue63-form-one-pr59-300dpi.png"
ARCHIVE = ROOT / "tests" / "fixtures" / "electrical-cycle3"
CURRENT = ROOT / "tests" / "fixtures" / "electrical-layout44"
SVG = "{http://www.w3.org/2000/svg}"


def _evidence():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def _fixture(folder):
    diagram = ET.parse(folder / "end-to-end-clean.svg").getroot()
    record = json.loads(
        (folder / "end-to-end-diagnostics.json").read_text(encoding="utf-8")
    )
    wires = [
        elem for elem in diagram.iter(f"{SVG}line")
        if elem.get("data-layer") == "wires"
    ]
    return diagram, record, wires


def _segment(line):
    return tuple(
        float(line.attrib[key]) for key in ("x1", "y1", "x2", "y2")
    )


def _serialized_wire(wire):
    return (
        wire["start_um"][0] / 1000,
        wire["start_um"][1] / 1000,
        wire["end_um"][0] / 1000,
        wire["end_um"][1] / 1000,
    )


def test_matrix_has_38_sourced_independent_results_without_fake_approval():
    data = _evidence()
    assert data["issue"] == 63
    assert data["schema_version"] == 1
    assert data["target"]["pr"] == 59
    assert data["target"]["form_one_blob_sha"] == (
        "9025fefd18ec9e50118d7353f5b2565eb064b5c4"
    )
    assert data["target"]["production_modified"] is False
    assert data["summary"]["verdict"] == "BLOCKED_FOR_FORMAL_PAPER_KD"
    records = data["matrix"]
    assert len(records) >= 35
    assert len({record["id"] for record in records}) == len(records)
    for record in records:
        assert record["id"].startswith("F63-")
        assert record["status"] in {"PASS", "FAIL", "BLOCKED"}
        assert record["observation"] and record["source"]
    actual = {
        status: sum(record["status"] == status for record in records)
        for status in ("PASS", "FAIL", "BLOCKED")
    }
    assert actual == data["summary"]["counts"] == {
        "PASS": 24, "FAIL": 6, "BLOCKED": 8,
    }
    assert set(data["summary"]["blocking_fail"]) <= {
        record["id"] for record in records if record["status"] == "FAIL"
    }
    assert not data["boundary"]["merge_allowed"]
    assert "parallel/rendering-sheet-cycle5" in data["boundary"]["do_not_change"]


def test_geometric_profile_and_font_reconstruction_are_explicit():
    profile = _evidence()["observed"]
    frame = profile["frame_bbox_mm"]
    title = profile["form_bbox_mm"]
    assert profile["paper_mm"] == [210, 297]
    assert frame == [20, 5, 205, 292]
    assert title == [20, 237, 205, 292]
    assert title[2] - title[0] == 185
    assert title[3] - title[1] == 55
    assert profile["form_size_mm"] == [185, 55]
    assert [b - a for a, b in profile["letter_cells_mm"]] == [5, 5, 5]
    assert profile["role_col_mm"] == [0, 17]
    assert profile["actual_role_row_height_mm"] == 5
    assert profile["grid_lines"] == 25
    assert profile["external_stroke_mm"] > profile["grid_stroke_mm"]
    assert profile["captext_count"] == 15
    assert profile["heading_h_mm"] == 2.5
    assert profile["css_em_mm"] > profile["heading_h_mm"]
    assert profile["minimum_measured_ink_margin_mm"] >= (
        profile["padding_required_mm"]
    )


def test_visual_evidence_is_real_300dpi_png_no_embedded_font():
    data = _evidence()["observed"]
    assert PNG.is_file()
    assert hashlib.sha256(PNG.read_bytes()).hexdigest() == data["png_sha256"]
    with Image.open(PNG) as image:
        assert image.format == "PNG"
        assert image.size == tuple(data["png_size_px"]) == (2232, 697)
        assert abs(image.info["dpi"][0] - data["png_dpi"]) < 0.1
        assert abs(image.info["dpi"][1] - data["png_dpi"]) < 0.1
    assert not list(PNG.parent.glob("*.ttf"))
    assert not list(PNG.parent.glob("*.otf"))


def test_missing_structural_graphs_and_overwritten_roles_are_not_marked_pass():
    records = {r["id"]: r for r in _evidence()["matrix"]}
    for key in ("F63-22", "F63-23", "F63-24", "F63-25", "F63-26", "F63-27"):
        assert records[key]["status"] == "FAIL"
    assert "(30)" in records["F63-22"]["observation"]
    assert "(33)" in records["F63-23"]["observation"]
    assert "(35)" in records["F63-24"]["observation"]
    assert "(31)" in records["F63-25"]["observation"]
    assert "(11)" in records["F63-26"]["observation"]
    assert "(12)" in records["F63-27"]["observation"]
    assert records["F63-32"]["status"] == "BLOCKED"


def test_archival_issue35_is_consistent_with_its_own_18_wire_record():
    diagram, record, wires = _fixture(ARCHIVE)
    assert len(wires) == len(record["authored_wires"]) == 18
    assert diagram.get("viewBox") == "8.85 12.85 114.301 70.301"
    for svg_segment, authored in zip(wires, record["authored_wires"], strict=True):
        assert _segment(svg_segment) == _serialized_wire(authored)
    destinations = {
        pair for wire in record["authored_wires"]
        for pair in (tuple(wire["start_um"]), tuple(wire["end_um"]))
    }
    assert (91000, 75000) in destinations
    assert (109000, 75000) in destinations
    review = (ROOT / "tests" / "test_standards_issue_35.py").read_text("utf-8")
    assert 'FIXTURE.with_name("end-to-end-diagnostics.json")' in review
    assert "archival" in review.lower()


def test_live_issue44_is_16_wire_and_preserves_5_nets_and_polarity():
    diagram, record, wires = _fixture(CURRENT)
    assert len(wires) == len(record["authored_wires"]) == 16
    assert diagram.get("viewBox") == "8.85 12.85 114.301 74.301"
    for svg_segment, authored in zip(wires, record["authored_wires"], strict=True):
        assert _segment(svg_segment) == _serialized_wire(authored)
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    assert len(graph.segments) == 16
    assert len(graph.junctions) == 3
    assert len(circuit.components) == 6
    assert len(circuit.nets) == 5
    c3 = next(item for item in circuit.components if item.reference == "C3")
    assert c3.origin == Point(100000, 80000)
    part = parts[c3.part_id]
    assert part.symbol_id == "capacitor.electrolytic"
    assert c3.pin_positions(symbols[part.symbol_id]) == {
        "1": Point(91000, 80000),
        "2": Point(109000, 80000),
    }
    assert _evidence()["observed"]["current_live_wires"] == 16
    assert _evidence()["observed"]["archive_issue35_wires"] == 18


def test_report_is_explicit_about_1_to_1_limits_and_case_fixes():
    report = REPORT.read_text(encoding="utf-8")
    for phrase in (
        "ГОСТ Р 2.104-2023", "обязательное приложение Б",
        "185×55", "0.879", "2.5", "300 DPI",
        "Разраб.", "Копировал", "Зона", "Вер.",
        "title_values", "TITLE_FIELD_OVERFLOW",
        "18", "16", "C3", "PASS", "FAIL", "BLOCKED",
        "PR #59", "PR #62",
    ):
        assert phrase.casefold() in report.casefold()
