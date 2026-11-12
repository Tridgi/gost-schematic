"""Issue #34: bounded, deterministic one-net orthogonal path regression."""

import json
from xml.etree import ElementTree as ET

import pytest

from examples.review_two_pin_routing import report_json, specimen, specimen_svg
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.units import mm
from gost_schematic.engines.routing.two_pin_orthogonal import route_two_pins
from gost_schematic.validation.external_wire_checks import WireSegment


def p(x, y):
    return Point(x, y)


def codes(route):
    return {item.code for item in route.diagnostics}


def edges(route):
    return tuple(Line(a, b) for a, b in zip(
        route.points, route.points[1:], strict=False
    ))


def check_route(route, first, last):
    assert route.ok and route.diagnostics == ()
    assert route.points[0] == first and route.points[-1] == last
    assert all(
        (edge.start.x == edge.end.x) != (edge.start.y == edge.end.y)
        for edge in edges(route)
    )
    assert all(
        (left.start.x == left.end.x) != (right.start.x == right.end.x)
        for left, right in zip(edges(route), edges(route)[1:], strict=False)
    )
    assert route.external_graph("N").junctions == ()


@pytest.mark.parametrize("end", [
    p(10000, 0), p(-10000, 0), p(0, 10000), p(0, -10000),
])
def test_straight_route_has_no_bends(end):
    result = route_two_pins(p(0, 0), end)
    assert result.points == (p(0, 0), end)
    check_route(result, p(0, 0), end)


def test_one_bend_between_non_aligned_pins():
    route = route_two_pins(p(-2000, -3000), p(8000, 7000))
    check_route(route, p(-2000, -3000), p(8000, 7000))
    assert len(route.points) == 3


def test_keepout_requires_two_bends_and_positive_clearance():
    box = Box(4000, -2000, 6000, 2000)
    route = route_two_pins(p(0, 0), p(10000, 0), keepouts=(box,))
    check_route(route, p(0, 0), p(10000, 0))
    assert len(route.points) == 4
    assert all(
        not segment_intersects_box(edge, box.expanded(550))
        for edge in edges(route)
    )


def test_permuted_obstacles_and_repeat_calls_are_byte_stable():
    a, b = Box(4000, -2000, 6000, 2000), Box(11000, 2000, 14000, 4000)
    expected = route_two_pins(p(0, 0), p(10000, 0), keepouts=(a, b))
    assert expected.ok
    for _ in range(12):
        assert route_two_pins(p(0, 0), p(10000, 0), keepouts=(b, a)) == expected


def test_blocked_port_fails_closed_without_any_partial_wire():
    result = route_two_pins(
        p(0, 0), p(10000, 0), keepouts=(Box(-1000, -1000, 1000, 1000),),
    )
    assert codes(result) == {"ROUTE_PORT_BLOCKED"} and not result.points
    with pytest.raises(ValueError, match="No completed"):
        result.external_graph("N")


def test_no_path_through_full_height_wall_inside_fixed_window():
    route = route_two_pins(
        p(0, 0), p(10000, 0), keepouts=(Box(4000, -10000, 6000, 10000),),
        bounds=Box(0, -10000, 10000, 10000),
    )
    assert codes(route) == {"ROUTE_NO_PATH"}
    assert not route.points


@pytest.mark.parametrize("foreign", [
    WireSegment(p(4000, -2000), p(4000, 2000), "OTHER"),
    WireSegment(p(4000, 0), p(7000, 0), "OTHER"),
    WireSegment(p(4000, -2000), p(6000, 2000), "OTHER"),
    WireSegment(p(4000, -2000), p(4000, 2000), "N"),
])
def test_foreign_wires_never_cross_touch_or_overlap_even_same_net(foreign):
    route = route_two_pins(p(0, 0), p(10000, 0), existing_wires=(foreign,))
    check_route(route, p(0, 0), p(10000, 0))
    keepout = Box(
        min(foreign.start.x, foreign.end.x), min(foreign.start.y, foreign.end.y),
        max(foreign.start.x, foreign.end.x) + 1,
        max(foreign.start.y, foreign.end.y) + 1,
    ).expanded(700)
    assert all(
        not segment_intersects_box(edge, keepout) for edge in edges(route)
    )


def test_existing_wire_becomes_uncrossable_wall_in_window():
    wire = WireSegment(p(4000, -10000), p(4000, 10000), "OTHER")
    route = route_two_pins(
        p(0, 0), p(10000, 0), existing_wires=(wire,),
        bounds=Box(0, -10000, 10000, 10000),
    )
    assert codes(route) == {"ROUTE_NO_PATH"}


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"grid_um": 0}, "ROUTE_GRID_INVALID"),
    ({"grid_um": True}, "ROUTE_GRID_INVALID"),
    ({"grid_um": 1.5}, "ROUTE_GRID_INVALID"),
    ({"clearance_um": -1}, "ROUTE_OPTIONS_INVALID"),
    ({"clearance_um": False}, "ROUTE_OPTIONS_INVALID"),
    ({"stroke_um": 0}, "ROUTE_OPTIONS_INVALID"),
    ({"max_cells": 0}, "ROUTE_OPTIONS_INVALID"),
    ({"keepouts": (None,)}, "ROUTE_OBSTACLE_INVALID"),
    ({"existing_wires": ("bad",)}, "ROUTE_OBSTACLE_INVALID"),
    ({"bounds": "bad"}, "ROUTE_WINDOW_INVALID"),
])
def test_invalid_configuration_rejects_all_malformed_inputs(kwargs, expected):
    result = route_two_pins(p(0, 0), p(10000, 0), **kwargs)
    assert codes(result) == {expected} and result.points == ()


def test_off_grid_non_integer_invalid_contact_and_coincident_pin():
    with pytest.raises(TypeError):
        Point(1.2, 0)
    with pytest.raises(TypeError):
        Point(True, 0)
    assert codes(route_two_pins("bad", p(10000, 0))) == {
        "ROUTE_COORDINATE_INVALID",
    }
    assert codes(route_two_pins(p(1, 0), p(10000, 0))) == {"ROUTE_OFF_GRID"}
    assert codes(route_two_pins(p(0, 0), p(10001, 0))) == {"ROUTE_OFF_GRID"}
    assert codes(route_two_pins(p(0, 0), p(0, 0))) == {"ROUTE_COINCIDENT_PINS"}


def test_route_grid_is_exact_and_no_silent_snap():
    result = route_two_pins(p(0, 0), p(6000, 0), grid_um=2000)
    assert result.points == (p(0, 0), p(6000, 0))
    assert codes(route_two_pins(p(0, 0), p(5000, 0), grid_um=2000)) == {
        "ROUTE_OFF_GRID",
    }


def test_reject_invalid_window_and_resource_exhaustion():
    assert codes(route_two_pins(
        p(0, 0), p(10000, 0), bounds=Box(0, -1000, 9000, 1000),
    )) == {"ROUTE_WINDOW_INVALID"}
    assert codes(route_two_pins(
        p(0, 0), p(10000, 0),
        bounds=Box(-50000, -50000, 50000, 50000), max_cells=100,
    )) == {"ROUTE_CELL_LIMIT"}


def test_real_parts_and_reused_existing_erc_validating_generated_graph():
    circuit, keepouts, result = specimen()
    assert [item.reference for item in circuit.components] == ["R1", "R2", "C1"]
    assert len(circuit.nets) == 1 and len(keepouts) == 3
    check_route(result, p(28000, 20000), p(91000, 20000))
    assert len(result.points) == 4
    assert len(result.external_graph("LINK").segments) == 3
    assert all(
        not segment_intersects_box(edge, box.expanded(550))
        for edge in edges(result) for box in keepouts
    )


@pytest.mark.parametrize("review", [False, True])
def test_svg_wire_endpoints_are_identical_to_router_output(review):
    _, _, route = specimen()
    root = ET.fromstring(specimen_svg(review=review))
    lines = [
        item for item in root.iter("{http://www.w3.org/2000/svg}line")
        if item.attrib.get("data-layer") == "wires"
    ]
    assert len(lines) == len(route.external_graph("LINK").segments)
    for line, segment in zip(lines, route.external_graph("LINK").segments, strict=True):
        assert (
            Point(mm(line.attrib["x1"]), mm(line.attrib["y1"])),
            Point(mm(line.attrib["x2"]), mm(line.attrib["y2"])),
        ) == (segment.start, segment.end)


def test_svg_and_json_are_deterministic_without_time_or_randomness():
    assert specimen_svg() == specimen_svg()
    assert specimen_svg(review=True) == specimen_svg(review=True)
    assert report_json() == report_json()
    report = json.loads(report_json())
    assert report["status"] == "EXPERIMENTAL ROUTING"
    assert report["net"]["members"] == ["R1.2", "C1.1"]
    assert len(report["route_points_um"]) == 4
    assert report["wire_diagnostics"] == report["clearance_diagnostics"] == []
