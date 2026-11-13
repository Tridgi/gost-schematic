"""Independent ESKD review evidence: PR 59/78/80 and Issue 82.

This suite audits only the source-traced documentary package and a frozen
independent 300-DPI artifact. Passing is NOT GOST certification of the PRs.
It does not read or modify other contributors' worktree branches.
"""

import hashlib
import json
from pathlib import Path
from struct import unpack

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/standards/form1-e1-espd-review-20261113.json"
REPORT = ROOT / "docs/standards/independent-review-form1-e1-espd-20261113.md"
ESPD = ROOT / "docs/standards/issue-82-program-flowchart-boundary.md"
PNG = ROOT / "docs/standards/evidence/form-one-59-20261113-300dpi.png"


def _evidence():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_independent_sha_and_scope_are_frozen():
    data = _evidence()
    assert data["base_sha"] == "e79a12003144a1981bdec829573784215ecaf6d7"
    assert data["pinned"] == {
        "pr59": "71ee7f0c26d2f2f41a67d9e4450aa33d265286fa",
        "pr78": "c49b7632cac33eafd77b29cc746a37978838f3e4",
        "pr80": "9c7f62510baafb12685acb67c5034ebfbb8a6b8b",
    }
    assert data["approval"] == "DRAFT_INDEPENDENT_REVIEW"
    for p in ("src/", "examples/", "tests/fixtures/", "main"):
        assert p in data["not_allowed"]


def test_six_historical_failures_are_fixed_but_full_paper_not_signed():
    data = _evidence()
    items = {x["id"]: x for x in data["cards"]}
    assert [items[f"FORM-0{i}"]["status"] for i in range(1, 7)] == [
        "PASS",
    ] * 6
    assert items["FORM-11"]["status"] == "BLOCKED"
    assert items["FORM-12"]["status"] == "BLOCKED"
    assert data["form1"]["old_six_fail_status"] == "ALL_FIXED_AT_CODE_LEVEL"
    assert data["form1"]["physical_paper_print_checked"] is False
    for n in (10, 11, 12, 13, 30, 31, 32, 33, 35):
        assert str(n) in REPORT.read_text(encoding="utf-8")


def test_title_block_glyph_metrics_are_not_fake_css_sizes():
    form = _evidence()["form1"]
    assert form["width_mm"] == 185
    assert form["height_mm"] == 55
    assert form["role_rows"] == 5
    assert form["role_ink_inset_mm"] == form["min_measured_ink_inset_mm"] == 0.8
    assert form["cap_height_mm"] == 2.5
    assert form["css_em_mm"] == 3.914
    assert form["captions_total"] == 19
    assert form["stroke_outline_mm"] == 0.7
    assert form["stroke_grid_mm"] == 0.25


def test_frozen_png_has_actual_expected_bytes_and_300dpi_header():
    data = _evidence()["form1"]
    assert PNG.is_file()
    raw = PNG.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert raw[12:16] == b"IHDR"
    assert unpack(">II", raw[16:24]) == tuple(data["raster_px"]) == (2232, 756)
    assert hashlib.sha256(raw).hexdigest() == data["raster_sha256"]
    assert data["raster_dpi"] == 300
    assert not list(PNG.parent.glob("*.ttf"))
    assert not list(PNG.parent.glob("*.otf"))


def test_parallel_ink_gap_repro_no_axis_confusion():
    d = _evidence()["compatibility"]
    assert d["line_ink_min_gap_um"] == 3000
    assert d["visual_stroke_um"] == 350
    assert d["ygo_current_axis_threshold_um"] == 3000
    assert d["correct_equal_stroke_axis_min_um"] == 3350
    assert d["ygo_current_axis_threshold_um"] - d["visual_stroke_um"] == 2650
    assert d["correct_equal_stroke_axis_min_um"] - d["visual_stroke_um"] == 3000
    bad = next(c for c in _evidence()["cards"] if c["id"] == "E1-05")
    assert bad["status"] == "FAIL"
    assert "ГОСТ 2.701" in bad["source"]


def test_fraction_bridge_is_blocked_and_is_not_a_gost_port_rule():
    d = _evidence()["compatibility"]
    frac = d["fraction_example"]
    assert frac["height_um"] == 36000
    assert frac["t"] == "0.3333"
    assert frac["exact_offset_um"] == 11998.8
    assert frac["visual_offset_um"] == 11999
    assert frac["model_error"] == "E1_PORT_OFF_GRID"
    assert d["overall"] == "BLOCKED_FOR_JOINT_INTEGRATION"
    assert next(c for c in _evidence()["cards"] if c["id"] == "E1-04")[
        "status"
    ] == "PASS"


def test_crossing_and_arrow_recommendations_not_overclaimed():
    cards = {c["id"]: c for c in _evidence()["cards"]}
    assert cards["E1-10"]["status"] == "PASS_WITH_EDITORIAL_CAVEAT"
    assert cards["E1-11"]["status"] == "PASS_WITH_EDITORIAL_CAVEAT"
    assert cards["E1-09"]["status"] == "BLOCKED"
    assert cards["E1-12"]["status"] == "BLOCKED"


def test_espd_program_document_type_and_graphics_are_distinct():
    d = _evidence()
    keys = {c["id"] for c in d["cards"]}
    assert {"ESPD-01", "ESPD-02", "ESPD-03", "ESPD-04", "ESPD-05",
            "ESPD-06", "ESPD-07", "ESPD-08", "ESPD-09"} <= keys
    report = ESPD.read_text(encoding="utf-8")
    for marker in (
        "19.701-90", "19.101-77", "19.104-78", "19.105-78",
        "19.106-78", "Одномерные массивы", "Терминатор", "Решение",
        "границы цикла", "Соединитель", "§4.2.4", "NOT IMPLEMENTED",
    ):
        assert marker.casefold() in report.casefold()
    assert "NOT IMPLEMENTED" in report
