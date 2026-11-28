"""Readable, side-aware terminal labels for native transistor review matrices."""
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Side
from gost_schematic.model.pins import GraphicPin

SVG = "{http://www.w3.org/2000/svg}"


def add_pin_label(parent: ET.Element, pin: GraphicPin) -> None:
    x, y = pin.at.x / 1000, pin.at.y / 1000
    if pin.side in (Side.TOP, Side.BOTTOM):
        # Never put the text baseline on a vertical conductor.
        x += 1.6
        y += 0.6
        anchor = "start"
    else:
        y -= 1.6
        anchor = "middle"
    ET.SubElement(parent, SVG + "text", {
        "x": str(x), "y": str(y), "font-size": "1.8",
        "font-family": "sans-serif", "text-anchor": anchor,
        "fill": "#24364a", "data-pin-label": pin.number,
    }).text = pin.label
