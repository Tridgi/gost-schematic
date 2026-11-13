"""Cycle4: exact wire graph to SVG, no implicit T/X electrical inference."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import (
    authored_specimen,
    definitions,
)
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.units import mm
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.external_wire_sheet import (
    build_external_wire_obstacles,
    render_external_wire_sheet,
)
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("unit-test-face.ttf", "Unit Test", 3500, 500)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


def _specimen(*, graph=None, review=False, strict=True, measurer=None):
    circuit, actual = authored_specimen()
    parts, symbols = definitions()
    by_part = {part_id: symbols[part.symbol_id] for part_id, part in parts.items()}
    return render_external_wire_sheet(
        circuit, graph or actual, by_part, STYLE, measurer or FixedInk(),
        diagnostic=review, strict_layout=strict,
    )


def _root(rendered):
    return ET.fromstring(rendered.svg)


def _markers(rendered):
    root = _root(rendered)
    return root.findall(f".//{SVG}g[@data-layer='explicit-junctions']/{SVG}circle")


def _wire_elements(rendered):
    return _root(rendered).findall(f".//{SVG}line[@data-layer='wires']")


@pytest.mark.parametrize("diagnostic", (False, True))
def test_valid_six_part_graph_renders_exact_segments_pins_and_junctions(diagnostic):
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    immutable = (circuit, graph, parts.copy(), symbols.copy())
    rendered = _specimen(review=diagnostic)
    assert rendered.layout.valid, [(d.code, d.message) for d in rendered.layout.diagnostics]
    assert len(rendered.wires) == len(graph.segments) == 16
    assert tuple(
        (w.line.start, w.line.end, w.net_name) for w in rendered.wires
    ) == tuple((seg.start, seg.end, seg.net_name) for seg in graph.segments)
    lines = _wire_elements(rendered)
    assert len(lines) == len(graph.segments)
    for index, (line, authored) in enumerate(zip(lines, graph.segments, strict=True)):
        assert (Point(mm(line.get("x1")), mm(line.get("y1"))),
                Point(mm(line.get("x2")), mm(line.get("y2")))) == (
                    authored.start, authored.end,
                )
        assert line.get("data-net") == authored.net_name
        assert line.get("data-wire-index") == str(index)
        assert line.get("stroke-width") == "0.3"

    markers = _markers(rendered)
    assert [Point(mm(m.get("cx")), mm(m.get("cy"))) for m in markers] == list(
        graph.junctions
    )
    assert all(m.get("data-kind") == "authored-junction" for m in markers)
    root = _root(rendered)
    assert root.get("data-approval-status") == "DRAFT"
    assert root.get("data-explicit-junction-count") == str(len(graph.junctions))
    assert root.get("data-wire-source") == "authored-external-wire-graph"
    assert bool(root.findall(f".//{SVG}g[@data-layer='geometry-review']")) == diagnostic
    assert not root.findall(f".//{SVG}image")
    labels = root.findall(f".//{SVG}text[@data-layer='annotations']")
    assert {label.get("data-owner") for label in labels} == {
        part.reference for part in circuit.components
    }
    assert {label.get("data-key") for label in labels} == {"refdes"}
    assert all("transform" not in label.attrib for label in labels)
    assert (circuit, graph, parts, symbols) == immutable
    assert validate_external_wires(circuit, graph, parts, symbols) == ()


def test_T_node_is_authored_and_unmarked_X_stays_unmarked():
    _, graph = authored_specimen()
    assert Point(40000, 40000) in graph.junctions  # authored multi-wire T node
    assert Point(40000, 60000) not in graph.junctions  # X across distinct nets
    output = _specimen(graph=graph)
    marked = {
        (mm(dot.get("cx")), mm(dot.get("cy"))) for dot in _markers(output)
    }
    assert (40000, 40000) in marked
    assert (40000, 60000) not in marked
    assert len(marked) == len(graph.junctions)
    # Removing an authored mark is visible and never automatically recovered.
    without = ExternalWireGraph(
        graph.segments, tuple(p for p in graph.junctions if p != Point(40000, 40000)),
    )
    output_without = _specimen(graph=without, strict=False)
    assert len(_markers(output_without)) == len(graph.junctions) - 1
    assert (40000, 40000) not in {
        (mm(dot.get("cx")), mm(dot.get("cy")))
        for dot in _markers(output_without)
    }


def test_explicit_X_mark_is_rendered_even_when_electrical_validator_flags_short():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    point = Point(40000, 60000)
    assert point not in graph.junctions
    short = ExternalWireGraph(graph.segments, (*graph.junctions, point))
    codes = {d.code for d in validate_external_wires(circuit, short, parts, symbols)}
    assert "WIRE_NET_SHORT" in codes
    rendered = _specimen(graph=short, review=True)
    markers = [(mm(dot.get("cx")), mm(dot.get("cy"))) for dot in _markers(rendered)]
    assert markers[-1] == (point.x, point.y)
    assert len(markers) == len(short.junctions)
    # Rendering does NOT validate/override the semantic Circuit.net memberships.
    assert circuit == authored_specimen()[0]


def test_wire_coordinate_drift_is_not_rounded_or_recomputed():
    _, graph = authored_specimen()
    start = graph.segments[0]
    drift = WireSegment(
        Point(start.start.x + 1, start.start.y), start.end, start.net_name,
    )
    edited = ExternalWireGraph((drift, *graph.segments[1:]), graph.junctions)
    actual = _specimen(graph=edited, strict=False)
    assert (mm(_wire_elements(actual)[0].get("x1")),
            mm(_wire_elements(actual)[0].get("y1"))) == (
                drift.start.x, drift.start.y,
            )
    assert (mm(_wire_elements(actual)[0].get("x2")),
            mm(_wire_elements(actual)[0].get("y2"))) == (
                drift.end.x, drift.end.y,
            )


def test_graph_junction_outside_all_wires_is_explicit_error():
    _, graph = authored_specimen()
    faulty = ExternalWireGraph(
        graph.segments, (*graph.junctions, Point(999999, 999999)),
    )
    with pytest.raises(ValueError, match="lies outside all wires"):
        _specimen(graph=faulty)


def test_overlap_labels_are_detected_by_standard_layout_engine():
    class MassiveInk:
        def measure(self, text, style):
            return MeasuredText(
                Box(-9_000_000, -9_000_000, 9_000_000, 9_000_000),
                18_000_000,
            )

    with pytest.raises(ValueError, match="External wire sheet layout invalid"):
        _specimen(measurer=MassiveInk())
    altered = _specimen(measurer=MassiveInk(), strict=False, review=True)
    assert not altered.layout.valid
    assert "ANNOTATION_UNPLACEABLE" in {
        d.code for d in altered.layout.diagnostics
    }
    assert _root(altered).find(
        f".//{SVG}metadata[@data-layer='external-wire-layout-diagnostics']"
    ) is not None


def test_deterministic_svg_and_clean_diagnostic_separation():
    one = _specimen()
    two = _specimen()
    review = _specimen(review=True)
    assert one == two
    assert one.svg != review.svg
    assert not _root(one).findall(f".//{SVG}g[@data-layer='geometry-review']")
    assert _root(review).findall(f".//{SVG}g[@data-layer='geometry-review']")
    assert len(_markers(one)) == len(_markers(review))
    assert _wire_elements(one)[0].attrib == _wire_elements(review)[0].attrib


@pytest.mark.parametrize("bad_stroke", (-1, 0, 0.25, True))
def test_only_positive_integer_wire_strokes_allowed(bad_stroke):
    _, graph = authored_specimen()
    with pytest.raises(ValueError, match="stroke"):
        build_external_wire_obstacles(graph, stroke_um=bad_stroke)


def test_radius_guards_without_mutating_original_graph():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    by_part = {item.identifier: symbols[item.symbol_id] for item in parts.values()}
    for radius in (0, -100, 1.2, True):
        with pytest.raises(ValueError, match="radius"):
            render_external_wire_sheet(
                circuit, graph, by_part, STYLE, FixedInk(), junction_radius_um=radius,
            )
    assert graph == authored_specimen()[1]


def test_renderer_does_not_derive_netlist_from_crossing_geometry():
    circuit, graph = authored_specimen()
    original_nets = circuit.nets
    output = _specimen(graph=graph)
    assert output.layout.valid
    assert circuit.nets == original_nets
    assert all(w.attached_pin is None for w in output.wires)
    assert all(w.net_name for w in output.wires)


def test_no_silent_loss_of_junctions_for_unusual_endpoint_order():
    _, graph = authored_specimen()
    reverse_order = ExternalWireGraph(
        tuple(
            replace(seg, start=seg.end, end=seg.start)
            for seg in reversed(graph.segments)
        ),
        tuple(reversed(graph.junctions)),
    )
    output = _specimen(graph=reverse_order)
    assert [Point(mm(dot.get("cx")), mm(dot.get("cy"))) for dot in _markers(output)] == [
        *reverse_order.junctions,
    ]
    assert [
        Point(mm(l.get("x1")), mm(l.get("y1"))) for l in _wire_elements(output)
    ] == [segment.start for segment in reverse_order.segments]
