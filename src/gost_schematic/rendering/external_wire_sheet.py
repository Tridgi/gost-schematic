"""Private adapter: render authored external wire geometry and explicit junctions.

The graph's segments/junctions are the ONLY source of wire ink and node dots.
T/X crossings are never inferred from SVG geometry or converted into nets.
The existing sheet layout and SVG renderer remain the rendering authorities.
"""
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.engines.sheet_layout import SheetLayout, layout_sheet
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

_SVG_URI = "http://www.w3.org/2000/svg"
_SVG = "{" + _SVG_URI + "}"
ET.register_namespace("", _SVG_URI)


@dataclass(frozen=True, slots=True)
class ExternalWireSheet:
    """Immutable rendered review result; not an API/electrical model object."""

    svg: str
    layout: SheetLayout
    wires: tuple[WireObstacle, ...]


def build_external_wire_obstacles(
    graph: ExternalWireGraph,
    *,
    stroke_um: int = 300,
) -> tuple[WireObstacle, ...]:
    """Copy each authored segment verbatim, including order and exact endpoints."""
    if type(stroke_um) is not int or stroke_um <= 0:
        raise ValueError("External-wire stroke must be positive integer µm")
    return tuple(
        WireObstacle(
            f"external-{index:02d}",
            Line(segment.start, segment.end),
            stroke_um=stroke_um,
            net_name=segment.net_name,
        )
        for index, segment in enumerate(graph.segments)
    )


def _on_segment(segment: WireSegment, point: Point) -> bool:
    """Exact integer coordinates, only for checking a visible authored marker.

    Not used to infer electrical connections. The validator in
    validation/external_wire_checks.py owns all electrical semantics.
    """
    start, end = segment.start, segment.end
    cross = (
        (end.x - start.x) * (point.y - start.y)
        - (end.y - start.y) * (point.x - start.x)
    )
    return (
        cross == 0
        and min(start.x, end.x) <= point.x <= max(start.x, end.x)
        and min(start.y, end.y) <= point.y <= max(start.y, end.y)
    )


def render_external_wire_sheet(
    circuit: Circuit,
    graph: ExternalWireGraph,
    symbols_by_part: dict[str, SymbolDefinition],
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    diagnostic: bool = False,
    stroke_um: int = 300,
    junction_radius_um: int = 550,
    strict_layout: bool = True,
) -> ExternalWireSheet:
    """Render existing Circuit and exact authored ExternalWireGraph, without edits.

    Component annotations are obtained only from the existing layout_sheet,
    which treats all external wires as placement obstacles. The only extra
    SVG geometry is *one circle per explicit graph.junctions point*. Unmarked
    X crossings and T touches remain unmarked; no inferred net connectivity.
    """
    if type(junction_radius_um) is not int or junction_radius_um <= 0:
        raise ValueError("Junction radius must be positive integer µm")
    wires = build_external_wire_obstacles(graph, stroke_um=stroke_um)
    for point in graph.junctions:
        if not any(_on_segment(segment, point) for segment in graph.segments):
            raise ValueError(
                f"Authored junction {point.x},{point.y} lies outside all wires"
            )
    layout = layout_sheet(
        circuit, symbols_by_part, style, measurer, wires=wires,
    )
    if strict_layout and not layout.valid:
        errors = "; ".join(
            f"{item.code}: {item.message}"
            for item in layout.diagnostics if item.severity.value == "error"
        )
        raise ValueError(f"External wire sheet layout invalid: {errors}")
    root = ET.fromstring(render_sheet_svg(
        circuit, symbols_by_part, layout,
        wires=wires, review_overlay=diagnostic,
    ))
    root.set("data-approval-status", "DRAFT")
    root.set("data-wire-source", "authored-external-wire-graph")
    root.set("data-explicit-junction-count", str(len(graph.junctions)))
    ET.SubElement(root, _SVG + "desc").text = (
        "DRAFT rendering of authored external wires. Only graph.junctions "
        "are drawn as electrical connection dots; no connectivity is "
        "inferred from wire crossings. Font is not embedded."
    )

    # Retain original endpoints and exact order of existing rendered wire lines.
    painted_wires = root.findall(".//" + _SVG + "line[@data-layer='wires']")
    if len(painted_wires) != len(graph.segments):
        raise ValueError("Sheet SVG silently omitted external wire segments")
    for index, (painted, segment) in enumerate(
        zip(painted_wires, graph.segments, strict=True)
    ):
        expected = (
            format_mm(segment.start.x),
            format_mm(segment.start.y),
            format_mm(segment.end.x),
            format_mm(segment.end.y),
        )
        actual = tuple(painted.get(key) for key in ("x1", "y1", "x2", "y2"))
        if actual != expected:
            raise ValueError(f"External wire {index} coordinates changed in SVG")
        painted.set("data-net", segment.net_name)
        painted.set("data-wire-index", str(index))

    marks = ET.SubElement(root, _SVG + "g", {
        "data-layer": "explicit-junctions",
        "fill": "#000000",
        "stroke": "none",
    })
    for point in graph.junctions:
        ET.SubElement(marks, _SVG + "circle", {
            "data-kind": "authored-junction",
            "cx": format_mm(point.x),
            "cy": format_mm(point.y),
            "r": format_mm(junction_radius_um),
        })
    if len(marks) != len(graph.junctions):
        raise ValueError("Sheet SVG silently omitted explicitly authored junctions")
    if diagnostic:
        annotations = ET.SubElement(root, _SVG + "metadata", {
            "data-layer": "external-wire-layout-diagnostics",
        })
        annotations.text = "; ".join(
            f"{item.severity.value}:{item.code}:{item.subject or ''}"
            for item in layout.diagnostics
        )
    return ExternalWireSheet(
        ET.tostring(root, encoding="unicode") + "\n",
        layout,
        wires,
    )
