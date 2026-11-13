"""Issue #44: calibrated, independent comparison on the REAL six-component sheet.

No auto placement or routing implementation is changed. The candidate uses the
coordinates in Issue #44 and must pass electrical/physical validation first.
"""

from dataclasses import replace

import pytest

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.circuit import Circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)
from scripts.qa_followup_layout_quality import illustration_cost_um, measure_route


def _pt(x_mm, y_mm):
    return Point(x_mm * 1000, y_mm * 1000)


def _branch(*xy):
    return tuple(_pt(x, y) for x, y in xy)


OLD_TOP = _branch((40, 40), (40, 80), (84, 80), (84, 75), (91, 75))
OLD_RIGHT = _branch((120, 40), (120, 75), (109, 75))
NEW_TOP = _branch((40, 40), (40, 80), (91, 80))
NEW_RIGHT = _branch((120, 40), (120, 80), (109, 80))


def _segments(points, name):
    return tuple(
        WireSegment(a, b, name)
        for a, b in zip(points, points[1:], strict=False)
    )


def _candidate():
    old_circuit, old_graph = authored_specimen()
    moved = replace(
        next(item for item in old_circuit.components if item.reference == "C3"),
        origin=_pt(100, 80),
    )
    circuit = Circuit(
        tuple(moved if item.reference == "C3" else item
              for item in old_circuit.components),
        old_circuit.nets,
    )
    graph = ExternalWireGraph(
        (
            *old_graph.segments[:-6],
            *_segments(NEW_TOP, "TOP"),
            *_segments(NEW_RIGHT, "RIGHT"),
        ),
        old_graph.junctions,
    )
    return (old_circuit, old_graph), (circuit, graph)


def test_issue44_sample_old_and_new_are_both_electrically_valid_real_catalog():
    (old_circuit, old_graph), (candidate, modified_graph) = _candidate()
    parts, symbols = definitions()
    assert len(old_circuit.components) == len(candidate.components) == 6
    assert len(old_circuit.nets) == len(candidate.nets) == 5
    assert candidate.nets == old_circuit.nets
    assert old_graph.junctions == modified_graph.junctions
    assert candidate.components[:-1] == old_circuit.components[:-1]
    assert len(old_graph.segments) - len(modified_graph.segments) == 2
    assert validate_external_wires(old_circuit, old_graph, parts, symbols) == ()
    assert validate_external_wires(candidate, modified_graph, parts, symbols) == ()
    c3 = next(item for item in candidate.components if item.reference == "C3")
    assert c3.pin_positions(symbols["capacitor.electrolytic"]) == {
        "1": _pt(91, 80), "2": _pt(109, 80),
    }


def test_issue44_moved_c3_does_not_crash_other_symbols_or_block_other_lead_tips():
    (_, _), (candidate, _) = _candidate()
    parts, symbols = definitions()
    changed = _segments(NEW_TOP, "TOP") + _segments(NEW_RIGHT, "RIGHT")
    c3 = next(item for item in candidate.components if item.reference == "C3")
    c3_body = c3.transform.box(
        symbols["capacitor.electrolytic"].body_keepout
    ).translated(c3.origin)
    for segment in changed:
        edge = Line(segment.start, segment.end)
        assert not segment_intersects_box(edge, c3_body.expanded(550))
        for device in candidate.components:
            if device.reference == "C3":
                continue
            body = device.transform.box(
                symbols[parts[device.part_id].symbol_id].body_keepout
            ).translated(device.origin)
            assert not segment_intersects_box(edge, body.expanded(550)), (
                device.reference, edge
            )


def test_issue44_dogleg_reduction_is_measurable_not_just_aesthetic_opinion():
    old_top, old_right = measure_route(OLD_TOP), measure_route(OLD_RIGHT)
    new_top, new_right = measure_route(NEW_TOP), measure_route(NEW_RIGHT)
    assert (old_top.length_um, old_right.length_um) == (96000, 46000)
    assert (new_top.length_um, new_right.length_um) == (91000, 51000)
    assert sum(x.length_um for x in (old_top, old_right)) == 142000
    assert sum(x.length_um for x in (new_top, new_right)) == 142000
    assert (old_top.bend_count, old_right.bend_count) == (3, 1)
    assert (new_top.bend_count, new_right.bend_count) == (1, 1)
    assert old_top.detour_um == 10000 and old_top.backtrack_um == 5000
    assert old_top.axial_reversals == 1 and old_top.short_legs == 2
    assert new_top.detour_um == new_top.backtrack_um == 0
    assert new_top.axial_reversals == 0 and new_top.short_legs == 0
    assert illustration_cost_um((old_top, old_right)) == 187000
    assert illustration_cost_um((new_top, new_right), moved_um=5000) == 157000


def test_loop_and_malformed_routes_are_not_silently_given_good_quality_scores():
    loop = measure_route(_branch((0, 0), (20, 0), (20, 10), (0, 10), (0, 0)))
    assert loop.closed_loop
    assert loop.endpoint_manhattan_um == 0
    assert loop.length_um == 60000
    assert loop.backtrack_um == 30000
    assert loop.axial_reversals == 2
    with pytest.raises(ValueError, match="orthogonal"):
        measure_route((Point(0, 0), Point(1000, 1000)))
    with pytest.raises(ValueError, match="orthogonal"):
        measure_route((Point(0, 0), Point(0, 0)))
    with pytest.raises(ValueError, match="At least two"):
        measure_route((Point(0, 0),))
    with pytest.raises(ValueError, match="short_leg_um"):
        measure_route((Point(0, 0), Point(1000, 0)), short_leg_um=0)
