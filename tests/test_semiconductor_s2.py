"""Source-reviewed avalanche diode and single-phase rectifier (GOST table 5/12)."""
from dataclasses import replace

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

CASES = (
    ("diode.zener_bidirectional", ("T1", "T2")),
    ("rectifier.bridge_single_phase", ("AC1", "AC2", "DC+", "DC-")),
)


@pytest.mark.parametrize("identifier,roles", CASES)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_s2_ports_independent_under_d4(identifier, roles, rotation, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    assert tuple(p.name for p in part.pins) == roles
    assert tuple(p.label for p in symbol.pins) == roles
    assert inspect_conductor_topology(symbol).pin_islands == tuple(
        (str(i),) for i in range(1, len(roles) + 1)
    )
    assert inspect_conductor_topology(symbol).valid
    assert symbol.conductor_topology.conductor_indices == tuple(range(len(roles)))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    tx = Transform(rotation, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    row = audit_symbol(symbol)
    assert not row["uncovered_functional_bounds"]
    assert not row["blocked_cardinal_escapes"]


def test_symmetric_zener_has_two_triangles_and_opposed_avalanche_hooks():
    _, symbol = CatalogResolver().resolve("diode.zener_bidirectional")
    assert len(symbol.graphics) == 12
    assert Line(Point(0, -3300), Point(2000, -3300)) in symbol.graphics
    assert Line(Point(0, 3300), Point(-2000, 3300)) in symbol.graphics
    assert Line(Point(-5000, 0), Point(5000, 0)) in symbol.graphics
    assert all(p.side in (Side.LEFT, Side.RIGHT) for p in symbol.pins)


def test_bridge_gost_port_order_and_polarity():
    part, symbol = CatalogResolver().resolve("rectifier.bridge_single_phase")
    assert tuple(p.at for p in symbol.pins) == (
        Point(0, -12000), Point(0, 12000), Point(12000, 0), Point(-12000, 0),
    )
    assert tuple(p.side for p in symbol.pins) == (Side.TOP, Side.BOTTOM, Side.RIGHT, Side.LEFT)
    assert tuple(p.polarity.value for p in part.pins) == ("none", "none", "positive", "negative")
    assert symbol.graphics[4:8] == (
        Line(Point(0, -7000), Point(7000, 0)),
        Line(Point(7000, 0), Point(0, 7000)),
        Line(Point(0, 7000), Point(-7000, 0)),
        Line(Point(-7000, 0), Point(0, -7000)),
    )


@pytest.mark.parametrize("identifier,roles", CASES)
def test_graphical_device_cannot_become_a_short(identifier, roles):
    _, symbol = CatalogResolver().resolve(identifier)
    bridge = Line(symbol.pins[0].at, symbol.pins[1].at)
    wrong = replace(symbol, graphics=(*symbol.graphics, bridge),
                    conductor_topology=replace(
                        symbol.conductor_topology,
                        conductor_indices=(*symbol.conductor_topology.conductor_indices,
                                           len(symbol.graphics)),
                    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }
