"""Draft magnetic paths: explicit crossings, independent winding groups and D4."""
from dataclasses import replace

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transductor.parallel_single_phase", (("1", "2"), ("3", "4"))),
    ("magnetic_amplifier.four_work_three_control", (
        ("1", "2"), ("10", "9"), ("11", "12"), ("13", "14"),
        ("3", "4"), ("5", "6"), ("7", "8"),
    )),
)


@pytest.mark.parametrize("identifier,groups", CASES)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_remaining_profiles(identifier, groups, rotation, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == groups
    assert len(part.pins) == len(symbol.pins) == sum(map(len, groups))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    tx = Transform(rotation, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, item in enumerate(symbol.graphics):
        if index not in symbol.conductor_topology.conductor_indices:
            box = tx.box(primitive_stroked_bounds(item, symbol.line_width_um))
            assert any(tx.box(z).includes(Point(box.min_x, box.min_y))
                       and tx.box(z).includes(Point(box.max_x, box.max_y))
                       for z in symbol.routing_keepouts)


def test_parallel_transductor_crossing_is_not_a_junction():
    symbol = CatalogResolver().symbols["transductor.parallel_single_phase"]
    topology = symbol.conductor_topology
    assert Point(11000, 0) not in topology.junctions
    broken = replace(symbol, conductor_topology=replace(
        topology, junctions=(*topology.junctions, Point(11000, 0)),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(broken).diagnostics
    }
