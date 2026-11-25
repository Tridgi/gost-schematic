"""Functional keepout must affect routing, not merely diagnostic SVG."""
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Arc270, Line, Point, primitive_stroked_bounds
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.two_pin_orthogonal import route_two_pins
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("identifier", ("resistor.variable", "resistor.photo",
                                       "resistor.photo_vertical"))
def test_external_functional_ink_is_in_blue_zone(identifier):
    symbol = CatalogResolver().symbols[identifier]
    assert symbol.routing_keepouts
    for index, graphic in enumerate(symbol.graphics):
        if index in symbol.conductor_topology.conductor_indices:
            continue
        bounds = primitive_stroked_bounds(graphic, symbol.line_width_um)
        assert any(zone.includes(Point(bounds.min_x, bounds.min_y))
                   and zone.includes(Point(bounds.max_x, bounds.max_y))
                   for zone in symbol.routing_keepouts)
    clean = ET.fromstring(render_symbol_svg(symbol))
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert not clean.findall(f"{SVG}rect[@data-kind='routing-keepout']")
    assert len(review.findall(f"{SVG}rect[@data-kind='routing-keepout']")) == len(
        symbol.routing_keepouts
    )


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_photo_zone_blocks_wire_without_trapping_real_contacts(angle, mirror):
    symbol = CatalogResolver().symbols["resistor.photo"]
    transform = Transform(angle, mirror)
    zones = tuple(transform.box(box) for box in symbol.routing_boxes)
    start, end = transform.apply(Point(-15000, -8000)), transform.apply(Point(15000, -8000))
    route = route_two_pins(start, end, keepouts=zones)
    assert route.ok
    assert len(route.points) > 2
    for a, b in zip(route.points, route.points[1:], strict=False):
        assert not any(segment_intersects_box(Line(a, b), box) for box in zones)
    for pin in symbol.pins:
        assert not any(zone.expanded(550).includes(transform.apply(pin.at)) for zone in zones)


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_reactor_exact_arc_and_connected_winding(angle, mirror):
    symbol = CatalogResolver().symbols["reactor.current_limiting"]
    arc = next(item for item in symbol.graphics if isinstance(item, Arc270))
    transform = Transform(angle, mirror)
    rotated = transform.primitive(arc)
    assert rotated.endpoint(rotated.start_side) == transform.apply(arc.endpoint(arc.start_side))
    assert rotated.endpoint(rotated.end_side) == transform.apply(arc.endpoint(arc.end_side))
    assert rotated.clockwise == (not mirror)
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2"),)
    root = ET.fromstring(render_symbol_svg(symbol))
    assert root.find(f"{SVG}g/{SVG}path").get("d") == "M 0 -5 A 5 5 0 1 1 -5 0"
