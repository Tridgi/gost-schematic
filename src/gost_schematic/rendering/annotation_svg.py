"""Vector SVG inspection for resolved annotations with optional diagnostic overlays."""

from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import (
    Box,
    Point,
    enclosing_box,
    primitive_bounds,
    primitive_stroke_width,
)
from gost_schematic.core.units import format_mm, mm
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.model.annotations import AnnotationPlacement
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.primitives import draw_primitive


def _rect(parent: ET.Element, box: Box, **style: str) -> None:
    ET.SubElement(parent, "rect", {
        "x": format_mm(box.min_x),
        "y": format_mm(box.min_y),
        "width": format_mm(box.max_x - box.min_x),
        "height": format_mm(box.max_y - box.min_y),
        **style,
    })


def _point(instance: ComponentInstance, at: Point) -> Point:
    return instance.transform.apply(at) + instance.origin


def render_annotation_svg(
    symbol: SymbolDefinition,
    instance: ComponentInstance,
    placements: tuple[AnnotationPlacement, ...],
    *,
    wires: tuple[WireObstacle, ...] = (),
    review_overlay: bool = False,
) -> str:
    """Inspect one placed symbol and its text.

    Rendered text requires the SAME font face as the layout engine to be
    installed in the SVG viewer. No proprietary font is embedded by default.
    """
    transformed = tuple(
        instance.transform.primitive(primitive, instance.origin)
        for primitive in symbol.graphics
    )

    boxes = [
        primitive_bounds(item).expanded(
            (primitive_stroke_width(item, symbol.line_width_um) + 1) // 2
        )
        for item in transformed
    ]
    boxes += [item.collision_bounds for item in placements]
    boxes += [
        item.reservation_bounds for item in placements
        if item.reservation_bounds is not None
    ]
    for obstacle in wires:
        boxes.append(primitive_bounds(obstacle.line).expanded(
            (obstacle.stroke_um + 1) // 2
        ))
    if review_overlay:
        boxes.extend(item.box for item in obstacles_for_component(symbol, instance))
    viewport = enclosing_box(tuple(boxes)).expanded(mm(3))
    width = viewport.max_x - viewport.min_x
    height = viewport.max_y - viewport.min_y
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{format_mm(width)}mm",
        "height": f"{format_mm(height)}mm",
        "viewBox": " ".join(format_mm(value) for value in (
            viewport.min_x, viewport.min_y, width, height,
        )),
    })
    ET.SubElement(root, "title").text = f"{symbol.identifier}: {instance.reference}"
    drawing = ET.SubElement(root, "g", {
        "stroke": "#000000", "fill": "none",
        "stroke-width": format_mm(symbol.line_width_um),
        "stroke-linejoin": "miter", "stroke-linecap": "butt",
    })
    for primitive in transformed:
        draw_primitive(drawing, primitive)
    for wire in wires:
        ET.SubElement(root, "line", {
            "x1": format_mm(wire.line.start.x), "y1": format_mm(wire.line.start.y),
            "x2": format_mm(wire.line.end.x), "y2": format_mm(wire.line.end.y),
            "stroke": "#000000",
            "stroke-width": format_mm(wire.stroke_um),
        })
    for placement in placements:
        label = ET.SubElement(root, "text", {
            "x": format_mm(placement.baseline.x),
            "y": format_mm(placement.baseline.y),
            "font-family": placement.style.font_family,
            "font-style": placement.style.font_style,
            "font-size": format_mm(placement.style.em_height_um),
            "fill": "#000000",
            "stroke": "none",
            "data-owner": placement.owner,
            "data-role": placement.role.value,
            "data-key": placement.key,
        })
        label.text = placement.text
        if placement.style.font_sha256 is not None:
            label.set("data-font-sha256", placement.style.font_sha256)

    if review_overlay:
        overlay = ET.SubElement(root, "g", {"data-layer": "geometry-review"})
        for obstacle in obstacles_for_component(symbol, instance):
            _rect(overlay, obstacle.box,
                  stroke="#d79a3d" if obstacle.kind == "symbol" else "#16a085",
                  fill="none", **{"stroke-width": "0.14", "stroke-dasharray": "0.8,0.6"})
        for pin in symbol.pins:
            at = _point(instance, pin.at)
            ET.SubElement(overlay, "circle", {
                "cx": format_mm(at.x), "cy": format_mm(at.y), "r": "0.3",
                "fill": "#168e7b",
            })
        for placement in placements:
            _rect(overlay, placement.collision_bounds, stroke="#8b5cf6",
                  fill="none", **{"stroke-dasharray": "0.7,0.4", "stroke-width": "0.14"})
            _rect(overlay, placement.ink_bounds, stroke="#328bc9",
                  fill="none", **{"stroke-width": "0.12"})
            if placement.reservation_bounds is not None:
                _rect(overlay, placement.reservation_bounds, stroke="#64748b",
                      fill="none", **{"stroke-dasharray": "0.4,0.4", "stroke-width": "0.1"})
    return ET.tostring(root, encoding="unicode") + "\n"
