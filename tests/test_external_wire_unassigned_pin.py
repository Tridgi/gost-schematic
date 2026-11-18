"""Issue #40: an external wire may never silently traverse an unused real pin.

Catalog-based regression: all physical contacts are reconstructed from real
part/symbol definitions; no synthetic part or fake graphic pin is introduced.
"""

from dataclasses import FrozenInstanceError

import pytest

from examples.review_end_to_end_circuit import definitions
from examples.review_external_wire_catalog import catalog_sheet
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

CATALOG_IDS = (
    "resistor.fixed",
    "capacitor.fixed",
    "capacitor.polarized",
    "capacitor.electrolytic",
    "inductor.tapped",
)
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


@pytest.fixture(scope="module")
def real_catalog():
    return definitions()


def _codes(issues):
    return {issue.code for issue in issues}


def _origin_for_contact(at: Point, symbol, pin_number: str) -> Point:
    local = next(pin.at for pin in symbol.pins if pin.number == pin_number)
    return Point(at.x - local.x, at.y - local.y)


def _real_crossing(
    catalog,
    part_id: str,
    rotation: int = 0,
    mirror: bool = False,
    direction: tuple[int, int] = (1, 0),
    offset_um: int = 0,
):
    """Move the unassigned symbol only; keep the electrical wire fixed.

    Both endpoints are actual physical resistor contacts with correct net
    membership. One unassigned X1.2 is exactly on the wire interior at offset 0.
    offset=1 shifts the *physical pin* orthogonally by precisely one micrometre.
    """
    _, symbols = catalog
    dx, dy = direction
    tx = Transform(rotation, mirror)
    original = ComponentInstance("X1", part_id, Point(100000, 100000), tx)
    crossed = original.pin_positions(symbols[part_id])["2"]
    victim = ComponentInstance(
        "X1",
        part_id,
        Point(100000 - dy * offset_um, 100000 + dx * offset_um),
        tx,
    )
    source_at = Point(crossed.x - 40000 * dx, crossed.y - 40000 * dy)
    target_at = Point(crossed.x + 40000 * dx, crossed.y + 40000 * dy)

    # Horizontal left-to-right: R1.2 / R2.1; right-to-left: R1.1 / R2.2.
    # Other resistor terminals therefore point away from the single wire.
    # For vertical traversal their other pins also sit away from its X.
    source_pin = "1" if dx < 0 else "2"
    target_pin = "2" if dx < 0 else "1"
    source = ComponentInstance(
        "R1",
        "resistor.fixed",
        _origin_for_contact(source_at, symbols["resistor.fixed"], source_pin),
    )
    target = ComponentInstance(
        "R2",
        "resistor.fixed",
        _origin_for_contact(target_at, symbols["resistor.fixed"], target_pin),
    )
    circuit = Circuit(
        (source, victim, target),
        (Net("SIG", (PinRef("R1", source_pin), PinRef("R2", target_pin))),),
    )
    wire = WireSegment(source_at, target_at, "SIG")
    graph = ExternalWireGraph((wire,))
    assert victim.pin_positions(symbols[part_id])["2"] == (
        Point(crossed.x - dy * offset_um, crossed.y + dx * offset_um)
    )
    assert circuit.nets[0].members == (
        PinRef("R1", source_pin), PinRef("R2", target_pin)
    )
    return circuit, graph, crossed


def test_original_qa_reproducer_on_real_resistor_json(real_catalog):
    parts, symbols = real_catalog
    resistor = symbols["resistor.fixed"]
    contacts = {pin.number: pin.at for pin in resistor.pins}
    delta = contacts["2"] - contacts["1"]
    first = ComponentInstance(
        "R1", "resistor.fixed", Point(-contacts["1"].x, -contacts["1"].y)
    )
    second_pin1 = Point(delta.x + 30000, delta.y)
    second = ComponentInstance(
        "R2", "resistor.fixed",
        _origin_for_contact(second_pin1, resistor, "1"),
    )
    circuit = Circuit(
        (first, second),
        (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    graph = ExternalWireGraph((
        WireSegment(Point(0, 0), second_pin1, "SIG"),
    ))
    assert first.pin_positions(resistor) == {
        "1": Point(0, 0), "2": delta,
    }
    issues = validate_external_wires(circuit, graph, parts, symbols)
    assert _codes(issues) == {"WIRE_PIN_CONTACT_UNDECLARED"}
    assert [(item.subject, item.severity.value) for item in issues] == [
        ("R1", "error")
    ]
    assert "R1.2" in issues[0].message
    assert graph.junctions == () and circuit.nets[0].members == (
        PinRef("R1", "1"), PinRef("R2", "1")
    )


@pytest.mark.parametrize("part_id", CATALOG_IDS)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("direction", DIRECTIONS, ids=("east", "west", "south", "north"))
def test_all_real_part_transforms_and_orthogonal_traversals_fail_closed(
    real_catalog, part_id, rotation, mirror, direction,
):
    parts, symbols = real_catalog
    circuit, graph, crossed = _real_crossing(
        real_catalog, part_id, rotation, mirror, direction
    )
    issues = validate_external_wires(circuit, graph, parts, symbols)
    matches = [
        item for item in issues
        if item.code == "WIRE_PIN_CONTACT_UNDECLARED"
        and item.subject == "X1"
        and "X1.2" in item.message
    ]
    assert len(matches) == 1
    assert matches[0].severity.value == "error"
    assert "WIRE_NET_SHORT" not in _codes(issues)
    assert "WIRE_PIN_UNASSIGNED" not in _codes(issues)
    assert "WIRE_PIN_NET_MISMATCH" not in _codes(issues)
    assert crossed not in graph.junctions
    assert all(member.reference != "X1" for net in circuit.nets for member in net.members)
    with pytest.raises(FrozenInstanceError):
        graph.segments[0].net_name = "BAD"


@pytest.mark.parametrize("part_id", CATALOG_IDS)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("direction", DIRECTIONS, ids=("east", "west", "south", "north"))
def test_one_micrometre_near_miss_does_not_create_a_pin_or_net(
    real_catalog, part_id, rotation, mirror, direction,
):
    parts, symbols = real_catalog
    circuit, graph, _ = _real_crossing(
        real_catalog, part_id, rotation, mirror, direction, offset_um=1
    )
    assert validate_external_wires(circuit, graph, parts, symbols) == ()


@pytest.mark.parametrize("part_id", CATALOG_IDS)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_diagonal_interior_pin_touch_is_reported_for_real_catalog(
    real_catalog, part_id, rotation, mirror,
):
    parts, symbols = real_catalog
    circuit, _, crossed = _real_crossing(
        real_catalog, part_id, rotation, mirror
    )
    # Derive two actual resistor endpoint positions on the same 45° diagonal.
    r1 = ComponentInstance(
        "R1", "resistor.fixed",
        _origin_for_contact(
            Point(crossed.x - 40000, crossed.y - 40000),
            symbols["resistor.fixed"], "2",
        ),
    )
    r2 = ComponentInstance(
        "R2", "resistor.fixed",
        _origin_for_contact(
            Point(crossed.x + 40000, crossed.y + 40000),
            symbols["resistor.fixed"], "1",
        ),
    )
    circuit = Circuit(
        (r1, circuit.components[1], r2),
        (Net("SIG", (PinRef("R1", "2"), PinRef("R2", "1"))),),
    )
    start = r1.pin_positions(symbols["resistor.fixed"])["2"]
    end = r2.pin_positions(symbols["resistor.fixed"])["1"]
    graph = ExternalWireGraph((WireSegment(start, end, "SIG"),))
    issues = validate_external_wires(circuit, graph, parts, symbols)
    assert any(
        issue.code == "WIRE_PIN_CONTACT_UNDECLARED"
        and issue.subject == "X1"
        and "X1.2" in issue.message
        for issue in issues
    )
    assert "WIRE_NET_SHORT" not in _codes(issues)


def test_unassigned_pin_at_wire_endpoint_preserves_existing_error(real_catalog):
    parts, symbols = real_catalog
    circuit, graph, crossed = _real_crossing(real_catalog, "resistor.fixed")
    source, _, target = circuit.components
    full = graph.segments[0]
    split = ExternalWireGraph((
        WireSegment(full.start, crossed, "SIG"),
        WireSegment(crossed, full.end, "SIG"),
    ))
    issues = validate_external_wires(circuit, split, parts, symbols)
    assert "WIRE_PIN_UNASSIGNED" in _codes(issues)
    assert not any(
        item.code == "WIRE_PIN_CONTACT_UNDECLARED" and "X1.2" in item.message
        for item in issues
    )
    assert (source, target) == (circuit.components[0], circuit.components[2])


def test_explicit_junction_never_assigns_a_physical_pin_implicitly(real_catalog):
    parts, symbols = real_catalog
    circuit, graph, crossed = _real_crossing(real_catalog, "capacitor.electrolytic")
    with_junction = ExternalWireGraph(graph.segments, (crossed,))
    issues = validate_external_wires(circuit, with_junction, parts, symbols)
    assert "WIRE_PIN_UNASSIGNED" in _codes(issues)
    assert not any(
        item.code == "WIRE_PIN_CONTACT_UNDECLARED" and "X1.2" in item.message
        for item in issues
    )
    assert "WIRE_NET_SHORT" not in _codes(issues)
    assert all(ref.reference != "X1" for net in circuit.nets for ref in net.members)


def test_assigned_pin_passed_by_non_junction_wire_is_still_an_error(real_catalog):
    parts, symbols = real_catalog
    circuit, graph, _ = _real_crossing(real_catalog, "resistor.fixed")
    victim = circuit.components[1]
    circuit = Circuit(
        circuit.components,
        (*circuit.nets, Net("OTHER", (PinRef(victim.reference, "2"),))),
    )
    issues = validate_external_wires(circuit, graph, parts, symbols)
    assert "WIRE_PIN_CONTACT_UNDECLARED" in _codes(issues)
    assert "WIRE_NET_SHORT" not in _codes(issues)


def test_real_catalog_crossing_of_two_wires_without_pin_remains_unconnected(
    real_catalog,
):
    parts, symbols = real_catalog
    circuit, graph = catalog_sheet()
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    crossing = Point(70000, 40000)
    assert crossing not in graph.junctions
    connected = ExternalWireGraph(graph.segments, (*graph.junctions, crossing))
    assert "WIRE_NET_SHORT" in _codes(
        validate_external_wires(circuit, connected, parts, symbols)
    )
