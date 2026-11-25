"""Functional keepout must affect routing, not merely diagnostic SVG."""
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Arc270, Box, Line, Point, primitive_stroked_bounds
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.two_pin_orthogonal import route_two_pins
from gost_schematic.engines.routing.two_pin_sheet import route_circuit_two_pins
from gost_schematic.model.annotations import AnnotationPlacement, AnnotationRole, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.rendering.annotation_svg import render_annotation_svg
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


# Fixed accepted minimum, while the loop below also covers future protected symbols.
PROTECTED = {
    "resistor.variable", "resistor.variable_side_wiper", "resistor.trimmer",
    "resistor.trimmer_top_wiper", "resistor.photo", "resistor.photo_vertical",
    "resistor.thermistor_ntc", "resistor.thermistor_ntc_vertical",
    "resistor.thermistor_ptc", "resistor.thermistor_ptc_vertical",
    "resistor.strain_linear", "resistor.strain_linear_vertical",
    "resistor.strain_nonlinear", "resistor.strain_nonlinear_vertical",
    "resistor.varistor", "resistor.varistor_vertical",
    "resistor.varistor_reference", "resistor.varistor_reference_vertical",
    "resistor.magnetic", "resistor.rheostat", "resistor.trimmer_rheostat",
    "reactor.current_limiting",
}


def test_all_protected_catalog_ink_contacts_and_overlays():
    catalog = CatalogResolver()
    protected = {key: s for key, s in catalog.symbols.items() if s.routing_keepouts}
    assert PROTECTED <= protected.keys()
    for key, symbol in protected.items():
        assert inspect_conductor_topology(symbol).valid, key
        for index, primitive in enumerate(symbol.graphics):
            if index in symbol.conductor_topology.conductor_indices:
                continue
            box = primitive_stroked_bounds(primitive, symbol.line_width_um)
            assert any(zone.includes(Point(box.min_x, box.min_y))
                       and zone.includes(Point(box.max_x, box.max_y))
                       for zone in symbol.routing_keepouts), (key, index)
        for rotation in (0, 90, 180, 270):
            for mirror in (False, True):
                transform = Transform(rotation, mirror)
                instance = ComponentInstance("X1", key, Point(20000, 30000), transform)
                boxes = [transform.box(b).translated(instance.origin)
                         for b in symbol.routing_boxes]
                for pin in symbol.pins:
                    assert not any(b.expanded(550).includes(
                        transform.apply(pin.at) + instance.origin) for b in boxes), (key, pin)
                image = ET.fromstring(render_annotation_svg(
                    symbol, instance, (), review_overlay=True))
                assert len(image.findall(
                    f".//{SVG}rect[@data-kind='routing-keepout']"
                )) == len(symbol.routing_keepouts), key


def test_sheet_adapter_routes_around_optical_zone_and_measured_label():
    catalog = CatalogResolver()
    source, target = PinRef("R1", "1"), PinRef("R2", "1")
    # Fixed-resistor pin 1 is at x=-8 mm. Place its body away from the link.
    circuit = Circuit((
        ComponentInstance("R1", "resistor.fixed", Point(-23000, -8000),
                          Transform(180)),
        ComponentInstance("R2", "resistor.fixed", Point(23000, -8000)),
        ComponentInstance("R3", "resistor.photo", Point(0, 0)),
    ), (Net("LINK", (source, target)),))
    photo = catalog.symbols["resistor.photo"]
    result = route_circuit_two_pins(circuit, catalog.parts, catalog.symbols,
                                    source, target, net_name="LINK")
    assert result.ok, result.diagnostics
    assert len(result.points) > 2
    text_box = Box(-8000, -15000, 6000, -13000)
    note = AnnotationPlacement("R3", "note", AnnotationRole.NOTE, "t°",
                               TextStyle("fixture.ttf", "Fixture"),
                               Point(-8000, -13000), text_box, text_box, None, 0)
    result = route_circuit_two_pins(circuit, catalog.parts, catalog.symbols,
                                    source, target, net_name="LINK", annotations=(note,))
    assert result.ok, result.diagnostics
    for a, b in zip(result.points, result.points[1:], strict=False):
        assert not any(segment_intersects_box(Line(a, b), box.expanded(550))
                       for box in (*photo.routing_boxes, text_box))
