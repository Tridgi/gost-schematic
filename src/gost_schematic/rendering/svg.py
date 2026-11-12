"""Standalone inspection SVG for individual symbols (not a finished schematic)."""
import xml.etree.ElementTree as ET

from gost_schematic.core.units import format_mm, mm
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.primitives import draw_primitive


def render_symbol_svg(symbol: SymbolDefinition, *, review_overlay: bool = False) -> str:
    bounds = symbol.stroked_bounds.expanded(mm(3))
    width = bounds.max_x - bounds.min_x
    height = bounds.max_y - bounds.min_y
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{format_mm(width)}mm",
        "height": f"{format_mm(height)}mm",
        "viewBox": " ".join(format_mm(value) for value in
                            (bounds.min_x, bounds.min_y, width, height)),
    })
    ET.SubElement(svg, "title").text = symbol.identifier
    graph = ET.SubElement(svg, "g", {
        "stroke": "#000000",
        "fill": "none",
        "stroke-width": format_mm(symbol.line_width_um),
        "stroke-linejoin": "miter",
        "stroke-linecap": "butt",
    })
    for item in symbol.graphics:
        draw_primitive(graph, item)
    if review_overlay:
        box = symbol.body_keepout
        ET.SubElement(svg, "rect", {
            "x": format_mm(box.min_x), "y": format_mm(box.min_y),
            "width": format_mm(box.max_x - box.min_x),
            "height": format_mm(box.max_y - box.min_y),
            "stroke": "#c07c2a",
            "stroke-dasharray": "1,0.7",
            "stroke-width": "0.15",
            "fill": "none",
        })
        for pin in symbol.pins:
            ET.SubElement(svg, "circle", {
                "cx": format_mm(pin.at.x), "cy": format_mm(pin.at.y),
                "r": "0.5", "fill": "#148a74",
            })
    return ET.tostring(svg, encoding="unicode") + "\n"
