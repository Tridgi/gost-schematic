"""R3: actual transformer contacts, shared winding and isolated secondary groups."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, Side, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transformer.auto_fixed", (("1", "2", "3", "4"),)),
    ("transformer.auto_regulated", (("1", "2", "3", "4"),)),
    ("transformer.current_single", (("1", "2"), ("3", "4"),)),
    ("transformer.current_dual_common_core", (("1", "2"), ("3", "4"), ("5", "6"),)),
    ("transformer.current_dual_separate_cores", (("1", "2"), ("3", "4"), ("5", "6"),)),
    ("transformer.voltage_measurement", (("1", "2"), ("3", "4"),)),
)


@pytest.mark.parametrize("identifier,groups", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_measurement_topology_and_protected_geometry(identifier, groups, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    assert inspect_conductor_topology(symbol).pin_islands == groups
    assert inspect_conductor_topology(symbol).valid
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert len(part.pins) == len(symbol.pins) == sum(map(len, groups))
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, graphic in enumerate(symbol.graphics):
        if index not in symbol.conductor_topology.conductor_indices:
            b = tx.box(primitive_stroked_bounds(graphic, symbol.line_width_um))
            assert any(tx.box(z).includes(Point(b.min_x, b.min_y))
                       and tx.box(z).includes(Point(b.max_x, b.max_y))
                       for z in symbol.routing_keepouts)
    svg = "{http://www.w3.org/2000/svg}"
    clean = ET.fromstring(render_symbol_svg(symbol))
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert not clean.findall(f"{svg}rect[@data-kind='routing-keepout']")
    assert len(review.findall(f"{svg}circle")) == len(symbol.pins)


def test_ct_graphic_axis_is_not_a_galvanic_connection():
    symbol = CatalogResolver().symbols["transformer.current_single"]
    assert symbol.pins[0].side == Side.TOP
    assert symbol.pins[1].side == Side.BOTTOM
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2"), ("3", "4"))
    # Adding a junction at the graphic overlap must be rejected as a bridge.
    broken = replace(symbol, conductor_topology=replace(
        symbol.conductor_topology, junctions=(Point(0, -4000),),
    ))
    trace = inspect_conductor_topology(broken)
    assert not trace.valid
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {d.code for d in trace.diagnostics}


def test_auto_common_terminal_is_physically_distinct_but_conductively_shared():
    catalog = CatalogResolver()
    for identifier in ("transformer.auto_fixed", "transformer.auto_regulated"):
        part, symbol = catalog.resolve(identifier)
        assert len({p.at for p in symbol.pins}) == 4
        assert part.pins[2].name == "COMMON_OUTPUT"
        assert inspect_conductor_topology(symbol).pin_islands == (("1", "2", "3", "4"),)
