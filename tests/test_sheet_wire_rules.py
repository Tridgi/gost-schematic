"""GOST 2.701-2008 dimensional wire checks require edge-to-edge gaps."""

from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import Line, Point
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.validation.sheet_wire_rules import validate_sheet_wire_rules


def _wire(identifier, x1, y1, x2, y2, width=300):
    return WireObstacle(
        identifier, Line(Point(x1, y1), Point(x2, y2)),
        stroke_um=width,
    )


def _codes(wires):
    return {issue.code for issue in validate_sheet_wire_rules(wires)}


def test_default_and_two_extreme_permitted_wire_widths():
    for width in (200, 300, 400, 1000):
        assert _codes((_wire("W", 0, 0, 10000, 0, width),)) == set()


def test_out_of_range_or_zero_stroke_is_eskd_error():
    for width in (0, 199, 1001):
        issues = validate_sheet_wire_rules(
            (_wire("W", 0, 0, 10000, 0, width),)
        )
        assert issues[0].code == "ESKD_WIRE_WIDTH_OUT_OF_RANGE"
        assert issues[0].severity == Severity.ERROR


def test_parallel_horizontal_printed_clearance_requires_3mm_not_centerline_3mm():
    a = _wire("a", 0, 0, 10000, 0)
    at_3mm_centers = _wire("b", 0, 3000, 10000, 3000)
    at_3mm_printed_gap = _wire("b", 0, 3300, 10000, 3300)
    assert "ESKD_PARALLEL_WIRE_CLEARANCE" in _codes((a, at_3mm_centers))
    assert _codes((a, at_3mm_printed_gap)) == set()


def test_vertical_parallel_rules_with_unequal_strokes_are_exact():
    a = _wire("left", 0, 0, 0, 10000, 200)
    nearly = _wire("right", 3599, 0, 3599, 10000, 1000)
    exact = _wire("right", 3600, 0, 3600, 10000, 1000)
    assert "ESKD_PARALLEL_WIRE_CLEARANCE" in _codes((a, nearly))
    assert _codes((a, exact)) == set()


def test_parallel_wires_without_overlapping_running_spans_are_not_adjacent():
    first = _wire("a", 0, 0, 4000, 0)
    last = _wire("b", 4000, 500, 8000, 500)
    assert _codes((first, last)) == set()


def test_horizontal_vertical_crossings_are_outside_this_specific_width_gap_check():
    horizontal = _wire("h", -5000, 0, 5000, 0)
    vertical = _wire("v", 0, -5000, 0, 5000)
    assert _codes((horizontal, vertical)) == set()


def test_diagonal_is_a_warning_not_automatic_nonconformance():
    diagonal = _wire("w", 0, 0, 1000, 1000)
    issues = validate_sheet_wire_rules((diagonal,))
    assert len(issues) == 1
    assert issues[0].code == "ESKD_WIRE_DIAGONAL_REVIEW"
    assert issues[0].severity == Severity.WARNING


def test_invalid_width_on_diagonal_reports_error_and_warning():
    issues = validate_sheet_wire_rules(
        (_wire("w", 0, 0, 3000, 3000, 150),)
    )
    assert {item.code for item in issues} == {
        "ESKD_WIRE_WIDTH_OUT_OF_RANGE", "ESKD_WIRE_DIAGONAL_REVIEW"
    }


def test_duplicate_wire_ids_do_not_hide_spatial_checks():
    first = _wire("W1", 0, 0, 10000, 0)
    second = _wire("W1", 0, 1000, 10000, 1000)
    assert "ESKD_PARALLEL_WIRE_CLEARANCE" in _codes((first, second))
