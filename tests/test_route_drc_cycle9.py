"""Issue #108/#109: source-frozen TL494 geometric DRC and safe route preview."""
from dataclasses import replace
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from examples.review_tl494_route_drc import load_frozen_source, make_review_svg, report
from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.netrefs import NetIdentity
from gost_schematic.electrical.reference_markers import (
    NetReferenceMarker,
    ReferenceAnchor,
    ReferenceRole,
    validate_reference_markers,
)
from gost_schematic.engines.orthogonal_route_planner import (
    evaluate_placement,
    preview_metrics,
    preview_orthogonal_route,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment
from gost_schematic.validation.route_drc import audit_route_drc

_SVG_NS = "{http://www.w3.org/2000/svg}"


def sample(*wires, net_names=("A", "B"), junctions=()):
    circuit = Circuit(
        tuple(ComponentInstance(f"P{i}", "fixture") for i in range(len(net_names))),
        tuple(Net(name, (PinRef(f"P{i}", "1"),))
              for i, name in enumerate(net_names)),
    )
    return circuit, ExternalWireGraph(tuple(wires), tuple(junctions))


def w(x1, y1, x2, y2, name="A"):
    return WireSegment(Point(x1, y1), Point(x2, y2), name)


@pytest.mark.parametrize(("center", "expected"), (
    (301, True),     # Stroke-aware EDGE gap 1µm, NOT a 3mm clearance.
    (3290, True),    # 2.990 mm printed edge-to-edge.
    (3299, True),    # 2.999 mm at 0.300mm stroke.
    (3300, False),   # Exactly 3.000 mm edge-to-edge is legal.
    (3301, False),
))
def test_exact_parallel_print_edge_threshold(center, expected):
    circuit, graph = sample(
        w(0, 0, 10000, 0), w(0, center, 10000, center, "B"),
    )
    result = audit_route_drc(circuit, graph, stroke_um=300)
    findings = [i for i in result.findings
                if i.code == "DRC_PARALLEL_STROKE_CLEARANCE"]
    assert bool(findings) is expected
    measurement = result.parallel_measurements[0]
    assert measurement.measured_edge_um == center - 300
    assert measurement.compliant is not expected
    assert measurement.required_um == 3000


def test_overlapping_projection_only_and_no_universal_3mm_on_X():
    circuit, graph = sample(
        w(0, 0, 10000, 0),
        w(15000, 3290, 25000, 3290, "B"),
        w(5000, -10000, 5000, 10000, "B"),
    )
    result = audit_route_drc(circuit, graph)
    assert not result.parallel_measurements
    assert result.crossing_pairs == 1
    assert result.crossing_different_net == 1
    assert any(f.code == "DRC_UNMARKED_DIFFERENT_NET_X" and
               f.severity == "warning" for f in result.findings)
    assert all(f.code != "DRC_PARALLEL_STROKE_CLEARANCE" for f in result.findings)


def test_real_t_only_when_explicit_authored_same_net_junction():
    wires = (w(0, 0, 10000, 0), w(5000, 0, 5000, 8000))
    circuit, graph = sample(*wires, net_names=("A",))
    bad = audit_route_drc(circuit, graph)
    assert "DRC_SAME_NET_T_NO_DOT" in {x.code for x in bad.findings}
    good = audit_route_drc(circuit, replace(graph, junctions=(Point(5000, 0),)))
    assert good.valid
    assert good.explicit_junctions == 1
    assert good.crossing_pairs == 0


def test_different_net_t_even_if_same_pixel_not_semantic_merge():
    circuit, graph = sample(
        w(0, 0, 10000, 0),
        w(5000, 0, 5000, 8000, "B"),
    )
    audit = audit_route_drc(circuit, graph)
    assert "DRC_FOREIGN_NET_T_TOUCH" in {f.code for f in audit.findings}
    assert circuit.nets[0].name == "A" and circuit.nets[1].name == "B"


def test_cross_net_collinear_ink_and_unmarked_three_way_branch():
    circuit, graph = sample(
        w(0, 0, 10000, 0),
        w(5000, 0, 15000, 0, "B"),
    )
    report = audit_route_drc(circuit, graph)
    assert any(not x.compliant and x.same_line for x in report.parallel_measurements)
    assert "DRC_PARALLEL_STROKE_CLEARANCE" in {f.code for f in report.findings}
    circuit, graph = sample(
        w(0, 0, 5000, 0), w(5000, 0, 10000, 0),
        w(5000, 0, 5000, 5000), net_names=("A",),
    )
    result = audit_route_drc(circuit, graph)
    assert "DRC_UNMARKED_BRANCH_3PLUS" in {x.code for x in result.findings}


def _fixture_symbols(gap):
    symbol = SymbolDefinition(
        "fixture.symbol", 1, (Line(Point(0, 0), Point(1000, 0)),),
        (GraphicPin("1", Point(0, 0), Side.LEFT),),
        Box(0, 0, 1000, 1000), 300,
    )
    circuit = Circuit((
        ComponentInstance("P0", "fixture", Point(0, 0)),
        ComponentInstance("P1", "fixture", Point(gap, 0)),
    ), (Net("A", (PinRef("P0", "1"), PinRef("P1", "1"))),))
    return circuit, ExternalWireGraph(()), {"fixture": symbol}


@pytest.mark.parametrize(("center", "two_mm_error", "one_mm_error"), (
    (2200, True, True),
    (3000, True, False),
    (3500, False, False),
))
def test_two_mm_UGO_and_one_mm_separate_graphic_stroke_gap(
    center, two_mm_error, one_mm_error,
):
    circuit, graph, symbols = _fixture_symbols(center)
    result = audit_route_drc(circuit, graph, symbols_by_part=symbols)
    codes = {f.code for f in result.findings}
    assert ("DRC_SYMBOL_2MM" in codes) is two_mm_error
    assert ("DRC_SYMBOL_GRAPHIC_1MM" in codes) is one_mm_error
    assert result.checked_symbol_geometry


def test_measured_text_keepout_uses_true_box_and_wire_stroke():
    circuit, graph = sample(w(0, 0, 10000, 0), net_names=("A",))
    labels = (SimpleNamespace(
        collision_bounds=Box(3000, -800, 6000, 500), owner="R5",
    ),)
    result = audit_route_drc(circuit, graph, annotation_placements=labels)
    assert "DRC_WIRE_TEXT_KEEP_OUT" in {f.code for f in result.findings}
    assert result.checked_measured_text
    shifted = (SimpleNamespace(
        collision_bounds=Box(3000, 5000, 6000, 6000), owner="R5",
    ),)
    assert audit_route_drc(circuit, graph, annotation_placements=shifted).valid


def test_source_freeze_has_exact_all_91_real_wires_and_16_DA_pin_refs():
    circuit, graph, source = load_frozen_source()
    assert len(circuit.components) == 23
    assert len(circuit.nets) == 15
    assert len(graph.segments) == 91
    assert len(graph.junctions) == 37
    assert source["source_head_sha"] == "e695c415fdced164b0e0c39c5249d030795a0aa6"
    assert {p.number for net in circuit.nets for p in net.members
            if p.reference == "DA1"} == {str(i) for i in range(1, 17)}
    assert circuit.nets == load_frozen_source()[0].nets
    assert graph == load_frozen_source()[1]
    result = report()
    assert result["wire_count"] == 91 and result["net_count"] == 15
    assert result["total_wire_length_um"] > 1000000
    assert result["parallel_measurements"]
    assert result["error_count"] > 0  # Unreadable source must NOT get false green.
    assert not result["full_3_2_1mm_sheet_certified"]
    assert not result["checked_symbol_geometry"]
    assert not result["checked_measured_text"]
    root = ET.fromstring(make_review_svg(result))
    assert len(root.findall(f".//{_SVG_NS}line[@data-layer='wires']")) == 91
    assert len(root.findall(f".//{_SVG_NS}g[@data-layer='editor-route-drc']")) == 1


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_D4_transform_invariance_never_synthesizes_an_X_or_node(rotation, mirror):
    tx = Transform(rotation, mirror)
    circuit, graph = sample(
        w(0, 0, 10000, 0),
        w(5000, 0, 5000, 8000),
        net_names=("A",), junctions=(Point(5000, 0),),
    )
    rotated = ExternalWireGraph(
        tuple(WireSegment(tx.apply(s.start), tx.apply(s.end), s.net_name)
              for s in graph.segments),
        tuple(tx.apply(p) for p in graph.junctions),
    )
    result = audit_route_drc(circuit, rotated)
    assert result.valid and result.explicit_junctions == 1
    assert result.crossing_pairs == 0
    assert result.wire_count == 2


def test_common_view_marker_never_treats_source_COMMON_as_PE():
    circuit, graph, _ = load_frozen_source()
    common = next(n for n in circuit.nets if n.name == "COMMON")
    identity = NetIdentity("N-COMMON", common.name, common.members)
    anchor = graph.segments[1].end
    label = NetReferenceMarker(
        "GND-1", identity.id, ReferenceRole.COMMON_0V, anchor,
        ReferenceAnchor.AUTHORED_WIRE, wire_index=1,
        source_evidence="TL494 e695c415 source COMMON lower rail",
    )
    validate_reference_markers(circuit, graph, (identity,), (label,))
    assert graph.segments[1].net_name == "COMMON"
    with pytest.raises(ValueError, match="NO_IMPLICIT_PE_TO_COMMON"):
        validate_reference_markers(circuit, graph, (identity,), (
            replace(label, id="PE-1", role=ReferenceRole.PROTECTIVE_EARTH),
        ))
    with pytest.raises(ValueError, match="FOREIGN_NET_OR_OFF_WIRE"):
        validate_reference_markers(circuit, graph, (identity,), (
            replace(label, wire_index=0),
        ))


def _route_fixture(obstacle=False):
    sym = SymbolDefinition(
        "fixture.route", 1, (Line(Point(0, -2000), Point(4000, -2000)),),
        (GraphicPin("1", Point(6000, 0), Side.RIGHT),
         GraphicPin("2", Point(-2000, 0), Side.LEFT)),
        Box(0, -2000, 4000, 2000), 300,
    )
    part = PartDefinition(
        "fixture", "X", sym.identifier,
        (PhysicalPin("1", "P", ElectricalType.PASSIVE),
         PhysicalPin("2", "N", ElectricalType.PASSIVE)),
    )
    components = [
        ComponentInstance("X1", "fixture", Point(10000, 20000)),
        ComponentInstance("X2", "fixture", Point(60000, 20000)),
    ]
    if obstacle:
        components.append(ComponentInstance("X3", "fixture", Point(32000, 20000)))
    circuit = Circuit(tuple(components), (
        Net("A", (PinRef("X1", "1"), PinRef("X2", "2"))),
    ))
    return circuit, ExternalWireGraph(()), {"fixture": part}, {"fixture": sym}


def test_deterministic_straight_orthogonal_two_physical_pin_preview():
    circuit, graph, parts, symbols = _route_fixture()
    untouched = (circuit, graph)
    kwargs = dict(page_box=Box(0, 0, 100000, 80000))
    a = preview_orthogonal_route(
        circuit, graph, PinRef("X1", "1"), PinRef("X2", "2"),
        "A", parts, symbols, **kwargs,
    )
    b = preview_orthogonal_route(
        circuit, graph, PinRef("X1", "1"), PinRef("X2", "2"),
        "A", parts, symbols, **kwargs,
    )
    assert a == b and a.valid
    assert a.waypoints == (Point(16000, 20000), Point(58000, 20000))
    assert a.bends == a.crossings == 0
    assert (circuit, graph) == untouched
    assert preview_metrics(a)["electrical_modifications"] == 0


def test_router_avoids_real_component_and_minimizes_bends():
    circuit, graph, parts, symbols = _route_fixture(obstacle=True)
    result = preview_orthogonal_route(
        circuit, graph, PinRef("X1", "1"), PinRef("X2", "2"),
        "A", parts, symbols, page_box=Box(0, 0, 100000, 80000),
    )
    assert result.valid, result.diagnostics
    assert result.bends >= 2
    assert result.crossings == 0
    assert result.length_um > 42000
    assert all((a.x == b.x) != (a.y == b.y)
               for a, b in zip(result.waypoints, result.waypoints[1:]))
    assert len(graph.segments) == 0


def test_router_foreign_net_cannot_be_connected_by_matching_ink():
    circuit, graph, parts, symbols = _route_fixture()
    changed = replace(circuit, nets=(
        Net("A", (PinRef("X1", "1"),)),
        Net("B", (PinRef("X2", "2"),)),
    ))
    got = preview_orthogonal_route(
        changed, graph, PinRef("X1", "1"), PinRef("X2", "2"),
        "A", parts, symbols, page_box=Box(0, 0, 100000, 80000),
    )
    assert not got.valid
    assert got.diagnostics == ("ROUTE_NET_PIN_NOT_MEMBER",)
    assert changed.nets[0].members == (PinRef("X1", "1"),)
    assert not got.waypoints


def test_reject_too_small_page_suggests_larger_format_not_tiny_UGO():
    circuit, graph, _, symbols = _route_fixture()
    result = evaluate_placement(
        circuit, symbols, page="A4", margin_um=220000, functional_flow=False,
    )
    assert not result.feasible
    assert "ROUTE_PAGE_CAPACITY" in {f.code for f in result.findings}
    assert result.suggested_page in ("A2", "A1", "A0")
    assert len(circuit.components) == 2 and graph.segments == ()


def test_route_far_detour_refuses_instead_of_hidden_u_turn():
    circuit, graph, parts, symbols = _route_fixture(obstacle=True)
    result = preview_orthogonal_route(
        circuit, graph, PinRef("X1", "1"), PinRef("X2", "2"),
        "A", parts, symbols, page_box=Box(0, 0, 100000, 80000),
        max_detour_ratio=1,
    )
    assert not result.valid
    assert result.diagnostics == ("ROUTE_EXCESSIVE_DETOUR_REPLACE_LAYOUT",)
