"""Issue #58: a foreign-net wire interior must not hide behind valid pin attachment.

All positions use real catalog resistor physical pin #1, exact integer µm.
These are ordinary passing regressions, not xfail and not pinned old SHA.
"""

from dataclasses import FrozenInstanceError

import pytest

from examples.review_end_to_end_circuit import definitions
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)


@pytest.fixture(scope="module")
def resistor_catalog():
    parts, symbols = definitions()
    return (
        {"resistor.fixed": parts["resistor.fixed"]},
        {"resistor.fixed": symbols["resistor.fixed"]},
    )


def _transform_compose(a: Transform, b: Transform) -> Transform:
    for mirror in (False, True):
        for rotation in (0, 90, 180, 270):
            candidate = Transform(rotation, mirror)
            if all(
                candidate.apply(v) == a.apply(b.apply(v))
                for v in (Point(1, 0), Point(0, 1))
            ):
                return candidate
    raise AssertionError("No exact D4 composition")


def _place(ref, contact: Point, symbol, transform: Transform):
    at = next(pin.at for pin in symbol.pins if pin.number == "1")
    return ComponentInstance(
        ref, "resistor.fixed", contact - transform.apply(at), transform
    )


def _case(catalog, rotation=0, mirror=False, reverse=False, near_miss_um=0):
    _, symbols = catalog
    symbol = symbols["resistor.fixed"]
    global_tx = Transform(rotation, mirror)
    point = global_tx.apply
    offset = point(Point(near_miss_um, 0))
    contacts = {
        "R1": point(Point(0, 0)),
        "R2": point(Point(-20000, 0)),
        "R3": point(Point(0, -10000)) + offset,
        "R4": point(Point(0, 10000)) + offset,
    }
    transforms = {
        "R1": global_tx,
        "R2": _transform_compose(global_tx, Transform(180)),
        "R3": _transform_compose(global_tx, Transform(270)),
        "R4": _transform_compose(global_tx, Transform(90)),
    }
    components = tuple(
        _place(ref, contacts[ref], symbol, transforms[ref])
        for ref in ("R1", "R2", "R3", "R4")
    )
    assert all(
        item.pin_positions(symbol)["1"] == contacts[item.reference]
        for item in components
    )
    circuit = Circuit(
        components,
        (
            Net("A", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("B", (PinRef("R3", "1"), PinRef("R4", "1"))),
        ),
    )
    line_a = WireSegment(contacts["R2"], contacts["R1"], "A")
    line_b = WireSegment(contacts["R3"], contacts["R4"], "B")
    if reverse:
        line_a = WireSegment(line_a.end, line_a.start, "A")
        line_b = WireSegment(line_b.end, line_b.start, "B")
    return circuit, ExternalWireGraph((line_a, line_b)), contacts


def _issues(catalog, circuit, graph):
    return validate_external_wires(circuit, graph, *catalog)


def _codes(issues):
    return {item.code for item in issues}


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
def test_QA_58_foreign_B_interior_hits_attached_A_pin(
    resistor_catalog, rotation, mirror, reverse,
):
    circuit, graph, contacts = _case(
        resistor_catalog, rotation=rotation, mirror=mirror, reverse=reverse
    )
    issues = _issues(resistor_catalog, circuit, graph)
    assert _codes(issues) == {"WIRE_PIN_CONTACT_UNDECLARED"}, issues
    assert len(issues) == 1
    assert issues[0].severity.value == "error"
    assert issues[0].subject == "R1"
    assert "R1.1" in issues[0].message
    assert graph.junctions == ()
    assert all(contacts["R1"] not in (s.start, s.end) for s in graph.segments[1:])
    assert _codes(issues).isdisjoint({
        "WIRE_NET_SHORT", "WIRE_PIN_NET_MISMATCH", "WIRE_PIN_UNASSIGNED"
    })
    assert circuit.nets[0].members == (PinRef("R1", "1"), PinRef("R2", "1"))
    assert circuit.nets[1].members == (PinRef("R3", "1"), PinRef("R4", "1"))


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("reverse", (False, True))
def test_QA_58_one_um_miss_is_valid_unjoined_X(
    resistor_catalog, rotation, mirror, reverse,
):
    circuit, graph, _ = _case(
        resistor_catalog, rotation, mirror, reverse, near_miss_um=1,
    )
    assert _issues(resistor_catalog, circuit, graph) == ()
    assert graph.junctions == ()


def test_exact_original_QA_58_coordinates_and_reverse_wire_order(resistor_catalog):
    circuit, graph, contacts = _case(resistor_catalog)
    assert contacts == {
        "R1": Point(0, 0),
        "R2": Point(-20000, 0),
        "R3": Point(0, -10000),
        "R4": Point(0, 10000),
    }
    assert graph.segments == (
        WireSegment(Point(-20000, 0), Point(0, 0), "A"),
        WireSegment(Point(0, -10000), Point(0, 10000), "B"),
    )
    reversed_order = ExternalWireGraph(graph.segments[::-1])
    assert _issues(resistor_catalog, circuit, graph) == (
        _issues(resistor_catalog, circuit, reversed_order)
    )


def test_explicit_foreign_junction_still_reports_real_short(resistor_catalog):
    circuit, graph, contacts = _case(resistor_catalog)
    connected = ExternalWireGraph(graph.segments, (contacts["R1"],))
    issues = _issues(resistor_catalog, circuit, connected)
    assert "WIRE_NET_SHORT" in _codes(issues)
    assert "WIRE_PIN_CONTACT_UNDECLARED" not in _codes(issues)
    # Only an authored junction joins the two separate electrical islands.
    assert "WIRE_NET_SHORT" not in _codes(
        _issues(resistor_catalog, circuit, graph)
    )


def test_original_issue_40_unassigned_contact_stays_an_error(resistor_catalog):
    parts, symbols = resistor_catalog
    symbol = symbols["resistor.fixed"]
    p1, p2 = (next(pin.at for pin in symbol.pins if pin.number == n)
              for n in ("1", "2"))
    first = _place("R1", Point(0, 0), symbol, Transform())
    delta = p2 - p1
    target = Point(delta.x + 30000, delta.y)
    second = _place("R2", target, symbol, Transform())
    circuit = Circuit(
        (first, second),
        (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    graph = ExternalWireGraph((WireSegment(Point(0, 0), target, "SIG"),))
    issues = validate_external_wires(circuit, graph, parts, symbols)
    assert _codes(issues) == {"WIRE_PIN_CONTACT_UNDECLARED"}
    assert "R1.2" in issues[0].message
    assert "WIRE_NET_SHORT" not in _codes(issues)


def test_normal_same_net_t_junction_is_not_a_short(resistor_catalog):
    _, symbols = resistor_catalog
    symbol = symbols["resistor.fixed"]
    contacts = {"R1": Point(-20000, 0), "R2": Point(20000, 0),
                "R3": Point(0, -10000)}
    transforms = {"R1": Transform(180), "R2": Transform(),
                  "R3": Transform(270)}
    circuit = Circuit(
        tuple(_place(r, contacts[r], symbol, transforms[r]) for r in contacts),
        (Net("A", tuple(PinRef(r, "1") for r in contacts)),),
    )
    graph = ExternalWireGraph((
        WireSegment(contacts["R1"], contacts["R2"], "A"),
        WireSegment(contacts["R3"], Point(0, 0), "A"),
    ), (Point(0, 0),))
    assert _issues(resistor_catalog, circuit, graph) == ()
    # Without the declared T node, no electrical merger should be inferred.
    missing_junction = ExternalWireGraph(graph.segments)
    issues = _issues(resistor_catalog, circuit, missing_junction)
    assert "WIRE_NET_SHORT" not in _codes(issues)
    assert "WIRE_DANGLING_END" in _codes(issues)


def test_no_mutation_of_circuit_or_wire_segments(resistor_catalog):
    circuit, graph, _ = _case(resistor_catalog)
    before = (circuit.components, circuit.nets, graph.segments, graph.junctions)
    _issues(resistor_catalog, circuit, graph)
    assert before == (circuit.components, circuit.nets,
                      graph.segments, graph.junctions)
    with pytest.raises(FrozenInstanceError):
        graph.segments[1].net_name = "A"
