"""Single SVG representation for all immutable geometric primitives.

Styles are explicit per-primitive when required (ferrite core, interrupted
magnetodielectric core); other shapes inherit the symbol's stroke width.
"""

from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import (
    Circle,
    Line,
    Primitive,
    Rectangle,
    Semicircle,
    Side,
    StyledLine,
)
from gost_schematic.core.units import format_mm


def _arc_path(arc: Semicircle) -> str:
    """One exact semicircular SVG arc; no line-segment approximation."""
    x, y, r = arc.center.x, arc.center.y, arc.radius
    if arc.bulge == Side.TOP:
        begin, end, sweep = (x - r, y), (x + r, y), 1
    elif arc.bulge == Side.BOTTOM:
        begin, end, sweep = (x - r, y), (x + r, y), 0
    elif arc.bulge == Side.RIGHT:
        begin, end, sweep = (x, y - r), (x, y + r), 1
    else:
        begin, end, sweep = (x, y - r), (x, y + r), 0
    return (
        f"M {format_mm(begin[0])} {format_mm(begin[1])} "
        f"A {format_mm(r)} {format_mm(r)} 0 0 {sweep} "
        f"{format_mm(end[0])} {format_mm(end[1])}"
    )


def draw_primitive(parent: ET.Element, item: Primitive) -> ET.Element:
    """Append one real SVG primitive with no mixing of physical and view coords."""
    if isinstance(item, StyledLine):
        attrs = {
            "x1": format_mm(item.start.x), "y1": format_mm(item.start.y),
            "x2": format_mm(item.end.x), "y2": format_mm(item.end.y),
            "stroke-width": format_mm(item.stroke_width_um),
        }
        if item.dash_pattern_um:
            attrs["stroke-dasharray"] = ",".join(map(format_mm, item.dash_pattern_um))
        return ET.SubElement(parent, "line", attrs)
    if isinstance(item, Line):
        return ET.SubElement(parent, "line", {
            "x1": format_mm(item.start.x), "y1": format_mm(item.start.y),
            "x2": format_mm(item.end.x), "y2": format_mm(item.end.y),
        })
    if isinstance(item, Rectangle):
        box = item.box
        return ET.SubElement(parent, "rect", {
            "x": format_mm(box.min_x), "y": format_mm(box.min_y),
            "width": format_mm(box.max_x - box.min_x),
            "height": format_mm(box.max_y - box.min_y),
        })
    if isinstance(item, Circle):
        return ET.SubElement(parent, "circle", {
            "cx": format_mm(item.center.x), "cy": format_mm(item.center.y),
            "r": format_mm(item.radius),
        })
    if isinstance(item, Semicircle):
        return ET.SubElement(parent, "path", {"d": _arc_path(item)})
    raise TypeError(f"Unsupported SVG primitive: {type(item)!r}")
