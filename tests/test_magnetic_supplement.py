"""Supplemental R5 entries: preserve independent port and winding topology."""
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("magnetic_amplifier.general", (("1",), ("2",), ("3",),)),
    ("transformer.magnetic_memory", (("1", "2",), ("3", "4",),)),
    ("magnetic_amplifier.parallel_work", (("1", "2",), ("3", "4",),)),
)


@pytest.mark.parametrize("identifier,groups", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_supplemental_magnetic_profiles(identifier, groups, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == groups
    assert len(symbol.pins) == len(part.pins) == sum(map(len, groups))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, item in enumerate(symbol.graphics):
        if index not in symbol.conductor_topology.conductor_indices:
            box = tx.box(primitive_stroked_bounds(item, symbol.line_width_um))
            assert any(tx.box(z).includes(Point(box.min_x, box.min_y))
                       and tx.box(z).includes(Point(box.max_x, box.max_y))
                       for z in symbol.routing_keepouts)
    ns = "{http://www.w3.org/2000/svg}"
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert len(review.findall(f"{ns}circle")) == len(symbol.pins)
    assert len(review.findall(f"{ns}rect[@data-kind='routing-keepout']")) == 1
