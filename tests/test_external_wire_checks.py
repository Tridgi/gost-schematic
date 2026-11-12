"""Regression tests for the independent, explicitly authored external wire graph."""

import pytest

from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

PART = PartDefinition(
    "fixture.two_pin", "X", "fixture.symbol",
    (
        PhysicalPin("1", "A", ElectricalType.PASSIVE),
        PhysicalPin("2", "B", ElectricalType.PASSIVE),
    ),
)
SYMBOL = SymbolDefinition(
    identifier="fixture.symbol",
    revision=1,
    graphics=(Line(Point(0, 0), Point(100000, 100000)),),
    pins=(
        GraphicPin("1", Point(0, 0), Side.LEFT),
        GraphicPin("2", Point(100000, 100000), Side.RIGHT),
    ),
    body_keepout=Box(45000, 45000, 55000, 55000),
    line_width_um=300,
)


def p(x, y):
    return Point(x, y)


def w(x1, y1, x2, y2, net="A"):
    return WireSegment(p(x1, y1), p(x2, y2), net)


def check(circuit, *segments, junctions=()):
    return validate_external_wires(
        circuit, ExternalWireGraph(tuple(segments), tuple(junctions)),
        {PART.identifier: PART}, {SYMBOL.identifier: SYMBOL},
    )


def sheet(positions, **nets):
    return Circuit(
        tuple(ComponentInstance(ref, PART.identifier, point) for ref, point in positions.items()),
        tuple(Net(name, tuple(PinRef(ref, "1") for ref in references))
              for name, references in nets.items()),
    )


def codes(diagnostics):
    return {issue.code for issue in diagnostics}


def test_exact_endpoints_form_complete_net():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    assert check(circuit, w(0, 0, 5000, 0), w(5000, 0, 10000, 0)) == ()


def test_unmarked_orthogonal_crossing_keeps_distinct_nets():
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(10000, 0),
         "Y1": p(5000, -5000), "Y2": p(5000, 5000)},
        A=("X1", "X2"), B=("Y1", "Y2"),
    )
    horizontal = w(0, 0, 10000, 0)
    vertical = w(5000, -5000, 5000, 5000, "B")
    assert check(circuit, horizontal, vertical) == ()
    assert "WIRE_NET_SHORT" in codes(check(
        circuit, horizontal, vertical, junctions=(p(5000, 0),),
    ))


@pytest.mark.parametrize("junction", [False, True])
def test_t_junction_requires_explicit_contact(junction):
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(10000, 0), "X3": p(5000, 5000)},
        A=("X1", "X2", "X3"),
    )
    diagnostics = check(
        circuit, w(0, 0, 10000, 0), w(5000, 0, 5000, 5000),
        junctions=(p(5000, 0),) if junction else (),
    )
    if junction:
        assert diagnostics == ()
    else:
        assert {"WIRE_NET_DISCONNECTED", "WIRE_DANGLING_END"} <= codes(diagnostics)


def test_same_net_positive_collinear_overlap_is_real_connection():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    assert check(circuit, w(0, 0, 6000, 0), w(4000, 0, 10000, 0)) == ()


def test_different_net_positive_collinear_overlap_is_short():
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(6000, 0),
         "Y1": p(4000, 0), "Y2": p(10000, 0)},
        A=("X1", "X2"), B=("Y1", "Y2"),
    )
    diagnostics = check(circuit, w(0, 0, 6000, 0), w(4000, 0, 10000, 0, "B"))
    assert "WIRE_NET_SHORT" in codes(diagnostics)


def test_missing_wire_between_semantic_net_members_is_detected():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    assert {"WIRE_NET_DISCONNECTED", "WIRE_PIN_UNWIRED"} <= codes(check(circuit))


def test_one_micrometre_gap_is_not_automatically_snapped():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    diagnostics = check(circuit, w(0, 0, 4999, 0), w(5000, 0, 10000, 0))
    assert {"WIRE_NET_DISCONNECTED", "WIRE_DANGLING_END"} <= codes(diagnostics)


def test_orphan_conductor_is_not_mistaken_for_valid_branch():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    diagnostics = check(
        circuit, w(0, 0, 10000, 0), w(20000, 0, 25000, 0),
    )
    assert "WIRE_ORPHAN_CONDUCTOR" in codes(diagnostics)
    assert "WIRE_NET_DISCONNECTED" not in codes(diagnostics)


def test_single_ended_branch_reports_dangling_endpoint():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    diagnostics = check(
        circuit, w(0, 0, 10000, 0), w(5000, 0, 5000, 5000),
        junctions=(p(5000, 0),),
    )
    assert "WIRE_DANGLING_END" in codes(diagnostics)
    assert "WIRE_NET_DISCONNECTED" not in codes(diagnostics)


def test_wire_pin_on_segment_interior_needs_explicit_contact():
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(10000, 0), "X3": p(5000, 0)},
        A=("X1", "X2", "X3"),
    )
    assert {
        "WIRE_PIN_CONTACT_UNDECLARED",
        "WIRE_PIN_UNWIRED",
        "WIRE_NET_DISCONNECTED",
    } <= codes(check(circuit, w(0, 0, 10000, 0)))
    assert check(circuit, w(0, 0, 10000, 0), junctions=(p(5000, 0),)) == ()


def test_incorrect_wire_net_label_does_not_override_physical_netlist():
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(10000, 0), "Y1": p(50000, 0)},
        A=("X1", "X2"), B=("Y1",),
    )
    issues = check(circuit, w(0, 0, 10000, 0, "B"))
    assert {"WIRE_PIN_NET_MISMATCH", "WIRE_NET_SHORT"} <= codes(issues)


def test_unknown_net_label_and_junction_without_conductor_are_reported():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1", "X2"))
    diagnostics = check(
        circuit, w(0, 0, 10000, 0, "MISSING"),
        junctions=(p(30000, 40000),),
    )
    assert {"WIRE_UNKNOWN_NET", "WIRE_JUNCTION_DANGLING"} <= codes(diagnostics)


def test_attached_pin_not_declared_on_any_net_is_an_error():
    circuit = sheet({"X1": p(0, 0), "X2": p(10000, 0)}, A=("X1",))
    assert "WIRE_PIN_UNASSIGNED" in codes(check(circuit, w(0, 0, 10000, 0)))


def test_missing_component_pin_is_reported_without_crashing():
    circuit = Circuit(
        (ComponentInstance("X1", PART.identifier),),
        (Net("A", (PinRef("X1", "1"), PinRef("Z9", "1"))),),
    )
    assert {"WIRE_UNKNOWN_PIN", "WIRE_NET_DISCONNECTED"} <= codes(check(circuit))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_rotated_and_mirrored_pins_follow_physical_identity(rotation, mirror):
    tx = Transform(rotation, mirror)
    start = tx.apply(p(100000, 100000)) + p(20000, 20000)
    end = start + p(7000, 4000)
    circuit = Circuit(
        (ComponentInstance("X1", PART.identifier, p(20000, 20000), tx),
         ComponentInstance("X2", PART.identifier, end)),
        (Net("A", (PinRef("X1", "2"), PinRef("X2", "1"))),),
    )
    assert validate_external_wires(
        circuit, ExternalWireGraph((WireSegment(start, end, "A"),)),
        {PART.identifier: PART}, {SYMBOL.identifier: SYMBOL},
    ) == ()


def test_diagonal_crossing_without_node_is_unconnected():
    circuit = sheet(
        {"X1": p(0, 0), "X2": p(10000, 10000),
         "Y1": p(0, 10000), "Y2": p(10000, 0)},
        A=("X1", "X2"), B=("Y1", "Y2"),
    )
    first = w(0, 0, 10000, 10000)
    second = w(0, 10000, 10000, 0, "B")
    assert check(circuit, first, second) == ()
    assert "WIRE_NET_SHORT" in codes(check(
        circuit, first, second, junctions=(p(5000, 5000),),
    ))


def test_junction_at_unwired_pin_is_still_invalid():
    circuit = sheet({"X1": p(0, 0)}, A=("X1",))
    issues = check(circuit, junctions=(p(0, 0),))
    assert "WIRE_JUNCTION_DANGLING" in codes(issues)


def test_invalid_segment_and_duplicate_junction_fail_fast():
    with pytest.raises(ValueError, match="Zero-length"):
        w(0, 0, 0, 0)
    with pytest.raises(ValueError, match="Duplicate junction"):
        ExternalWireGraph((), (p(0, 0), p(0, 0)))
