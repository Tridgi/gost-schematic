"""Deterministic multi-component SVG, with optional geometry review layers.

The preview is not a declaration of ГОСТ conformity. Every SVG text viewer
must have the same physical font face used for FreeType measurement.
"""

from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import (
    Box,
    Primitive,
    enclosing_box,
    primitive_bounds,
    primitive_stroke_width,
)
from gost_schematic.core.units import format_mm, mm
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.primitives import draw_primitive


def _rect(parent: ET.Element, bounds: Box, **attributes: str) -> None:
    ET.SubElement(parent, "rect", {
        "x": format_mm(bounds.min_x),
        "y": format_mm(bounds.min_y),
        "width": format_mm(bounds.max_x - bounds.min_x),
        "height": format_mm(bounds.max_y - bounds.min_y),
        **attributes,
    })


def _instance_primitives(
    symbol: SymbolDefinition, instance: ComponentInstance,
) -> tuple[Primitive, ...]:
    return tuple(
        instance.transform.primitive(item, instance.origin)
        for item in symbol.graphics
    )


def render_sheet_svg(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    layout: SheetLayout,
    *,
    wires: tuple[WireObstacle, ...] = (),
    review_overlay: bool = False,
) -> str:
    """Render sheet primitives + resolved annotation positions, no routing inference."""
    shapes: list[tuple[ComponentInstance, SymbolDefinition, tuple[Primitive, ...]]] = []
    extents: list[Box] = [label.collision_bounds for label in layout.placements]
    for component in circuit.components:
        symbol = symbols_by_part.get(component.part_id)
        if symbol is None:
            raise ValueError(f"Unknown symbol for {component.reference}")
        primitives = _instance_primitives(symbol, component)
        shapes.append((component, symbol, primitives))
        extents.extend(
            primitive_bounds(item).expanded(
                (primitive_stroke_width(item, symbol.line_width_um) + 1) // 2
            )
            for item in primitives
        )
        if review_overlay:
            extents.extend(item.box for item in obstacles_for_component(symbol, component))
            extents.extend(
                item.reservation_bounds for item in layout.placements
                if item.reservation_bounds is not None
            )
    for wire in wires:
        extents.append(primitive_bounds(wire.line).expanded((wire.stroke_um + 1) // 2))
    if not extents:
        raise ValueError("Cannot render an empty sheet")
    viewport = enclosing_box(tuple(extents)).expanded(mm(3))
    width, height = viewport.max_x - viewport.min_x, viewport.max_y - viewport.min_y
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{format_mm(width)}mm",
        "height": f"{format_mm(height)}mm",
        "viewBox": " ".join(map(format_mm, (
            viewport.min_x, viewport.min_y, width, height,
        ))),
    })
    ET.SubElement(root, "title").text = "GOST Schematic: unapproved sheet layout review"
    for component, symbol, primitives in shapes:
        group = ET.SubElement(root, "g", {
            "data-reference": component.reference,
            "data-layer": "symbols",
            "stroke": "#000000",
            "stroke-width": format_mm(symbol.line_width_um),
            "stroke-linejoin": "miter",
            "stroke-linecap": "butt",
            "fill": "none",
        })
        for primitive in primitives:
            draw_primitive(group, primitive)

    for wire in wires:
        ET.SubElement(root, "line", {
            "data-layer": "wires",
            "x1": format_mm(wire.line.start.x),
            "y1": format_mm(wire.line.start.y),
            "x2": format_mm(wire.line.end.x),
            "y2": format_mm(wire.line.end.y),
            "stroke": "#000000",
            "stroke-width": format_mm(wire.stroke_um),
        })

    for label in layout.placements:
        text = ET.SubElement(root, "text", {
            "data-layer": "annotations",
            "data-owner": label.owner,
            "data-key": label.key,
            "x": format_mm(label.baseline.x),
            "y": format_mm(label.baseline.y),
            "font-size": format_mm(label.style.em_height_um),
            "font-family": label.style.font_family,
            "font-style": label.style.font_style,
            "fill": "#000000",
            "stroke": "none",
        })
        text.text = label.text
        if label.style.font_sha256 is not None:
            text.set("data-font-sha256", label.style.font_sha256)

    if review_overlay:
        debug = ET.SubElement(root, "g", {
            "data-layer": "geometry-review",
            "fill": "none",
        })
        for component, symbol, _ in shapes:
            for obstacle in obstacles_for_component(symbol, component):
                _rect(debug, obstacle.box, **{
                    "stroke": "#d79a3d" if obstacle.kind == "symbol" else "#168f78",
                    "stroke-width": "0.14",
                    "stroke-dasharray": "0.8,0.5",
                    "data-kind": obstacle.kind,
                    "data-owner": component.reference,
                })
            for pin in symbol.pins:
                at = component.transform.apply(pin.at) + component.origin
                ET.SubElement(debug, "circle", {
                    "cx": format_mm(at.x),
                    "cy": format_mm(at.y),
                    "r": "0.3",
                    "fill": "#168f78",
                })
        for label in layout.placements:
            _rect(debug, label.ink_bounds, **{
                "stroke": "#328bc9", "stroke-width": "0.12", "data-kind": "ink",
            })
            _rect(debug, label.collision_bounds, **{
                "stroke": "#8b5cf6", "stroke-width": "0.14",
                "stroke-dasharray": "0.7,0.5", "data-kind": "text-hitbox",
                "data-owner": label.owner, "data-key": label.key,
            })
            if label.reservation_bounds is not None:
                _rect(debug, label.reservation_bounds, **{
                    "stroke": "#64748b", "stroke-width": "0.1",
                    "stroke-dasharray": "0.4,0.4", "data-kind": "text-reservation",
                })
    return ET.tostring(root, encoding="unicode") + "\n"
