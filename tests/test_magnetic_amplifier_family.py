"""R5: working and bias windings, magnetic-only graphics, D4 clearance."""
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import (
    Circle,
    Point,
    Semicircle,
    StyledLine,
    primitive_stroked_bounds,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transformer.controlled_single_phase", (("1", "2"), ("3", "4"), ("5", "6"),), 8, 1),
    ("transformer.controlled_three_phase", (("1", "2", "3"), ("4", "5", "6"), ("7", "8"),), 20, 1),
    ("magnetic_amplifier.common_control", (("1", "2"), ("3", "4"), ("5", "6"),), 10, 6),
    ("magnetic_amplifier.series_opposed", (("1", "2"), ("3", "4"),), 8, 6),
    ("magnetic_amplifier.rectangular_hysteresis", (("1", "2"), ("3", "4"), ("5", "6"),), 10, 6),
)


@pytest.mark.parametrize("identifier,groups,arcs,cores", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_magnetic_system_islands_and_ink(identifier, groups, arcs, cores, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == groups
    assert len(symbol.pins) == len(part.pins) == sum(map(len, groups))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert sum(isinstance(g, Semicircle) for g in symbol.graphics) == arcs
    assert sum(isinstance(g, StyledLine) for g in symbol.graphics) == cores
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, item in enumerate(symbol.graphics):
        if isinstance(item, (Circle, StyledLine)):
            assert index not in symbol.conductor_topology.conductor_indices
        if isinstance(item, Semicircle) or index not in symbol.conductor_topology.conductor_indices:
            b = tx.box(primitive_stroked_bounds(item, symbol.line_width_um))
            assert any(tx.box(z).includes(Point(b.min_x, b.min_y))
                       and tx.box(z).includes(Point(b.max_x, b.max_y))
                       for z in symbol.routing_keepouts), (identifier, index)
    ns = "{http://www.w3.org/2000/svg}"
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert len(review.findall(f"{ns}circle")) == len(symbol.pins)
    assert len(review.findall(f"{ns}rect[@data-kind='routing-keepout']")) == 1
