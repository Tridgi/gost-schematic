"""A pin corridor protects a physical connector, not all wires on its net."""

from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.collision import BoxObstacle, WireObstacle
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.routing.clearance import (
    validate_port_reservations,
    validate_wire_clearance,
)
from gost_schematic.engines.routing.ports import pin_corridors_for_component
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef


def _ports(resistor, *, rotation=0, mirror=False):
    instance = ComponentInstance(
        "R1", "resistor", Point(20000, 15000), Transform(rotation, mirror),
    )
    return pin_corridors_for_component(resistor, instance)


def _codes(items):
    return {issue.code for issue in items}


def test_each_corridor_has_owner_pin_and_outward_geometry(resistor):
    left, right = _ports(resistor)
    assert left.pin == PinRef("R1", "1")
    assert left.contact == Point(12000, 15000)
    assert left.side == Side.LEFT
    assert left.box == Box(10200, 14600, 12000, 15400)
    assert right.pin == PinRef("R1", "2")
    assert right.contact == Point(28000, 15000)
    assert right.box == Box(28000, 14600, 29800, 15400)


@pytest.mark.parametrize(
    ("rotation", "mirror", "expected_side", "point"),
    [
        (0, False, Side.LEFT, Point(12000, 15000)),
        (90, False, Side.TOP, Point(20000, 7000)),
        (180, False, Side.RIGHT, Point(28000, 15000)),
        (270, False, Side.BOTTOM, Point(20000, 23000)),
        (0, True, Side.RIGHT, Point(28000, 15000)),
        (90, True, Side.BOTTOM, Point(20000, 23000)),
        (180, True, Side.LEFT, Point(12000, 15000)),
        (270, True, Side.TOP, Point(20000, 7000)),
    ],
)
def test_port_transforms_preserve_identity_and_outward_direction(
    resistor, rotation, mirror, expected_side, point,
):
    left = _ports(resistor, rotation=rotation, mirror=mirror)[0]
    assert left.pin == PinRef("R1", "1")
    assert left.side == expected_side
    assert left.contact == point
    assert left.box.includes(point)


def test_own_wire_must_start_at_contact_and_go_outwards(resistor):
    left = _ports(resistor)[0]
    wire = WireObstacle(
        "left-connection", Line(left.contact, Point(9500, 15000)),
        attached_pin=left.pin,
        net_name="NET_A",
    )
    assert validate_wire_clearance((wire,), corridors=(left,)) == ()
    reverse = replace(wire, line=Line(Point(9500, 15000), left.contact))
    assert validate_wire_clearance((reverse,), corridors=(left,)) == ()


def test_same_net_different_pin_does_not_gain_access(resistor):
    left = _ports(resistor)[0]
    foreign = WireObstacle(
        "foreign", Line(left.contact, Point(9500, 15000)),
        attached_pin=PinRef("R2", "1"),
        net_name="NET_A",
    )
    assert _codes(validate_wire_clearance((foreign,), corridors=(left,))) == {
        "ROUTE_PIN_ESCAPE_BLOCKED",
    }


def test_same_pin_without_contact_or_outward_orientation_is_blocked(resistor):
    left = _ports(resistor)[0]
    tangential = WireObstacle(
        "tangent", Line(left.contact, Point(12000, 13000)), attached_pin=left.pin,
    )
    crossing = WireObstacle(
        "crossing", Line(Point(11000, 14000), Point(11000, 16000)),
        attached_pin=left.pin,
    )
    for wire in (tangential, crossing):
        assert "ROUTE_PIN_ESCAPE_BLOCKED" in _codes(
            validate_wire_clearance((wire,), corridors=(left,)),
        )


def test_port_never_excuses_a_route_through_component_body(resistor):
    left = _ports(resistor)[0]
    instance = ComponentInstance("R1", "resistor", Point(20000, 15000))
    body = obstacles_for_component(resistor, instance)[0]
    wire = WireObstacle(
        "into-body", Line(left.contact, Point(22000, 15000)),
        attached_pin=left.pin,
    )
    assert "ROUTE_OBSTACLE_OVERLAP" in _codes(
        validate_wire_clearance((wire,), corridors=(left,), blocked=(body,)),
    )


def test_netlist_check_requires_correct_physical_pin_membership(resistor):
    left = _ports(resistor)[0]
    circuit = Circuit(
        (ComponentInstance("R1", "resistor"),),
        (Net("GND", (PinRef("R1", "1"),)),),
    )
    wire = WireObstacle(
        "wrong-net", Line(left.contact, Point(9000, 15000)),
        attached_pin=left.pin,
        net_name="VCC",
    )
    assert _codes(validate_wire_clearance(
        (wire,), corridors=(left,), circuit=circuit,
    )) == {"ROUTE_NET_MISMATCH"}
    correct = replace(wire, net_name="GND")
    assert validate_wire_clearance((correct,), corridors=(left,), circuit=circuit) == ()


def test_annotations_stay_clear_of_even_their_own_pin_escape(resistor):
    instance = ComponentInstance("R1", "resistor", Point(20000, 15000))
    text_obstacles = obstacles_for_component(resistor, instance)
    corridor = _ports(resistor)[0]
    assert text_obstacles[1].identifier == corridor.identifier
    assert text_obstacles[1].box == corridor.box
    assert text_obstacles[1].kind == "pin_escape"


def test_foreign_symbol_or_text_cannot_occupy_connector_corridor(resistor):
    corridor = _ports(resistor)[0]
    obstruction = BoxObstacle("R2.body", Box(10800, 14600, 11800, 15400))
    issues = validate_port_reservations((corridor,), blocked=(obstruction,))
    assert _codes(issues) == {"PIN_CORRIDOR_OBSTRUCTED"}


def test_adjacent_connector_reservations_cannot_overlap(resistor):
    left = _ports(resistor)[0]
    neighboring = replace(
        left, pin=PinRef("R2", "1"),
        contact=Point(11800, 15000),
        box=Box(10000, 14600, 11800, 15400),
    )
    assert _codes(validate_port_reservations((left, neighboring))) == {
        "PIN_CORRIDOR_OVERLAP",
    }


def test_pin_width_even_and_odd_are_centered_and_not_widened(resistor):
    instance = ComponentInstance("R1", "resistor")
    ports = pin_corridors_for_component(resistor, instance, width_um=801)
    for port in ports:
        assert port.box.max_y - port.box.min_y == 801
    with pytest.raises(ValueError):
        pin_corridors_for_component(resistor, instance, width_um=0)
    with pytest.raises(ValueError):
        pin_corridors_for_component(resistor, instance, length_um=-1)


def test_annotation_obstacles_remain_forbidden_for_any_wire():
    text_box = BoxObstacle("R1.value", Box(0, 0, 5000, 2000), "annotation")
    wire = WireObstacle(
        "N1", Line(Point(-1000, 1000), Point(6000, 1000)),
        attached_pin=PinRef("R1", "1"),
    )
    assert _codes(validate_wire_clearance((wire,), blocked=(text_box,))) == {
        "ROUTE_OBSTACLE_OVERLAP",
    }
