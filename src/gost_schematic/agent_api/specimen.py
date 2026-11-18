"""Read-only bridge to the repository's authored six-part review example.

No diagram is reconstructed from pixels. Each scenario uses the immutable
Circuit, ExternalWireGraph, real catalog definitions and sheet SVG renderer.
Only fixed, in-repository examples are selectable (no arbitrary path/module).
"""

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gost_schematic.core.units import format_mm
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.external_wire_checks import ExternalWireGraph

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True, slots=True)
class Specimen:
    reference: str
    circuit: Circuit
    graph: ExternalWireGraph
    parts: dict[str, PartDefinition]
    symbols: dict[str, SymbolDefinition]
    scenario: object


def load_specimen(project_ref: str) -> Specimen:
    """The provider is intentionally an allowlisted, fixed review example."""
    # This import is deliberately fixed. Never import a module supplied by the MCP client.
    try:
        from examples.review_end_to_end_circuit import definitions, scenarios
    except ImportError as exc:
        raise ValueError(
            "SPECIMEN_UNAVAILABLE: launch from an editable repository checkout "
            "containing examples/review_end_to_end_circuit.py"
        ) from exc

    cases = {case.identifier: case for case in scenarios()}
    prefix = "six-part"
    if project_ref == prefix:
        name = "valid"
    elif project_ref.startswith(prefix + ":"):
        name = project_ref[len(prefix) + 1:]
    else:
        raise ValueError("UNKNOWN_PROJECT: only six-part and fixed six-part:<case> are supported")
    if name not in cases:
        raise ValueError("UNKNOWN_PROJECT: unsupported built-in specimen case")
    case = cases[name]
    parts, symbols = definitions()
    return Specimen(project_ref, case.circuit, case.graph, parts, symbols, case.scenario)


def render_specimen_svg(scene: Specimen, *, diagnostic: bool = False) -> str:
    """Layer explicit junctions/labels over the existing deterministic SVG engine."""
    from examples.review_end_to_end_circuit import renderer_wires

    by_part = {key: scene.symbols[part.symbol_id] for key, part in scene.parts.items()}
    original = render_sheet_svg(
        scene.circuit,
        by_part,
        SheetLayout((), ()),
        wires=renderer_wires(scene.graph),
        review_overlay=diagnostic,
    )
    root = ET.fromstring(original)
    x, y, w, h = (float(number) for number in root.get("viewBox", "").split())
    # Preserve refdes that protrude above the default geometry-only viewport.
    root.set("viewBox", f"{x - 6:g} {y - 6:g} {w + 12:g} {h + 12:g}")
    root.set("width", f"{w + 12:g}mm")
    root.set("height", f"{h + 12:g}mm")
    junctions = ET.SubElement(root, f"{{{SVG_NS}}}g", {
        "data-layer": "explicit-junctions", "fill": "#000000", "stroke": "none",
    })
    for point in scene.graph.junctions:
        ET.SubElement(junctions, f"{{{SVG_NS}}}circle", {
            "data-kind": "authored-junction",
            "cx": format_mm(point.x), "cy": format_mm(point.y), "r": "0.55",
        })
    labels = ET.SubElement(root, f"{{{SVG_NS}}}g", {
        "data-layer": "specimen-refdes", "fill": "#222222", "stroke": "none",
        "font-family": "sans-serif", "font-size": "3.5", "text-anchor": "middle",
    })
    for component in scene.circuit.components:
        symbol = by_part[component.part_id]
        top = component.transform.box(symbol.body_keepout).translated(component.origin).min_y
        label = ET.SubElement(labels, f"{{{SVG_NS}}}text", {
            "data-owner": component.reference,
            "x": format_mm(component.origin.x), "y": format_mm(top - 2500),
        })
        label.text = component.reference

    if diagnostic:
        net_labels = ET.SubElement(root, f"{{{SVG_NS}}}g", {
            "data-layer": "semantic-net-labels",
            "fill": "#2459a6", "stroke": "none",
            "font-family": "sans-serif", "font-size": "1.8",
        })
        for index, wire in enumerate(scene.graph.segments):
            a, b = wire.start, wire.end
            if abs(a.x - b.x) + abs(a.y - b.y) < 16000:
                continue
            label = ET.SubElement(net_labels, f"{{{SVG_NS}}}text", {
                "x": format_mm((a.x + b.x) // 2),
                "y": format_mm((a.y + b.y) // 2 - 900),
                "data-wire-index": str(index),
            })
            label.text = wire.net_name

    return ET.tostring(root, encoding="unicode") + "\n"
