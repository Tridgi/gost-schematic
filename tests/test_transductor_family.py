"""Two new transductor profiles: physical port identity and graphic isolation."""
from dataclasses import replace

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transductor.general", (("1",), ("2",))),
    ("transductor.series_single_phase", (("1", "2"), ("3", "4"))),
)


@pytest.mark.parametrize("identifier,groups", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_transductor_profiles(identifier, groups, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == groups
    assert len(part.pins) == len(symbol.pins) == sum(map(len, groups))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    transform = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(transform.box(b).expanded(550).includes(transform.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, item in enumerate(symbol.graphics):
        if index not in symbol.conductor_topology.conductor_indices:
            b = transform.box(primitive_stroked_bounds(item, symbol.line_width_um))
            assert any(transform.box(z).includes(Point(b.min_x, b.min_y))
                       and transform.box(z).includes(Point(b.max_x, b.max_y))
                       for z in symbol.routing_keepouts)


def test_magnetic_core_must_not_become_a_conductor():
    _, symbol = CatalogResolver().resolve("transductor.series_single_phase")
    # The first magnetic stroke crosses the exact shared endpoints of two
    # adjacent semicircles in both windings; wrongly selecting that stroke
    # and marking intersections must trigger a bridge diagnostic.
    index = len(symbol.graphics) - 6
    topology = replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices, index),
        junctions=(Point(-8000, -5000), Point(-8000, 5000)),
    )
    trace = inspect_conductor_topology(replace(symbol, conductor_topology=topology))
    assert not trace.valid
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {d.code for d in trace.diagnostics}
