"""Review-only C3 placement candidate: NEVER alters the authored fixture.

Issue #44 proposed component + wire coordinates are applied only to copied
in-memory values. The original electrical reference is unchanged and is the
default export. Do not merge the proposed graph into electrical source here.
"""
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.annotations import TextStyle
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

_SVG = "{http://www.w3.org/2000/svg}"


def proposed_c3_geometry():
    """Pure snapshot for comparison, not a mutation or accepted routing fix."""
    circuit, graph = authored_specimen()
    c3 = next(item for item in circuit.components if item.reference == "C3")
    if (c3.part_id, c3.origin) != (
        "capacitor.electrolytic", Point(100000, 75000),
    ):
        raise ValueError("C3 original fixture changed; revisit Issue #44 proposal")
    expected = (
        ((40000, 40000), (40000, 80000), "TOP"),
        ((40000, 80000), (84000, 80000), "TOP"),
        ((84000, 80000), (84000, 75000), "TOP"),
        ((84000, 75000), (91000, 75000), "TOP"),
        ((120000, 40000), (120000, 75000), "RIGHT"),
        ((120000, 75000), (109000, 75000), "RIGHT"),
    )
    observed = tuple(
        ((part.start.x, part.start.y), (part.end.x, part.end.y), part.net_name)
        for part in graph.segments[-6:]
    )
    if observed != expected:
        raise ValueError("C3 authored wires changed; do not patch unknown source")
    candidate = replace(circuit, components=tuple(
        replace(item, origin=Point(100000, 80000))
        if item.reference == "C3" else item
        for item in circuit.components
    ))
    new_tail = (
        WireSegment(Point(40000, 40000), Point(40000, 80000), "TOP"),
        WireSegment(Point(40000, 80000), Point(91000, 80000), "TOP"),
        WireSegment(Point(120000, 40000), Point(120000, 80000), "RIGHT"),
        WireSegment(Point(120000, 80000), Point(109000, 80000), "RIGHT"),
    )
    alternative = ExternalWireGraph(
        (*graph.segments[:-6], *new_tail), graph.junctions,
    )
    return (circuit, graph), (candidate, alternative)


def _crop(svg: str, kind: str, *, review: bool) -> str:
    """Explicit comparison crop only, not a production-sheet clip."""
    root = ET.fromstring(svg)
    root.set("width", "55mm")
    root.set("height", "36mm")
    root.set("viewBox", "76 57 55 36")
    root.set("data-c3-review-kind", kind)
    root.set("data-c3-preview-crop", "true")
    root.set("data-not-approved-routing", "true")
    root.set("data-view", "diagnostic" if review else "clean")
    title = ET.SubElement(root, _SVG + "title")
    title.text = "C3: " + kind + " — hypothetical review only"
    return ET.tostring(root, encoding="unicode") + "\n"


def generate_c3_comparison(output_dir: Path, style: TextStyle) -> dict:
    (original, draft), (candidate, proposal) = proposed_c3_geometry()
    parts, symbols = definitions()
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    c3_symbol = by_part["capacitor.electrolytic"]
    if c3_symbol.identifier != "capacitor.electrolytic":
        raise ValueError("C3 expected real electrolytic symbol")
    if c3_symbol.revision != 1:
        raise ValueError("C3 catalog symbol revision changed; review required")
    for kind, circuit, graph in (
        ("as-authored", original, draft),
        ("proposal-only", candidate, proposal),
    ):
        violations = validate_external_wires(circuit, graph, parts, symbols)
        if violations:
            raise ValueError(f"{kind}: invalid proposed external wires: " + str(
                [(v.code, v.subject) for v in violations]
            ))
        errors = [
            v for v in validate_circuit(circuit, parts, symbols)
            if v.severity.value == "error"
        ]
        if errors:
            raise ValueError(f"{kind}: ERC errors: " + str([v.code for v in errors]))
        for diagnostic in (False, True):
            rendered = render_external_wire_sheet(
                circuit, graph, by_part, style, PillowTextMeasurer(),
                diagnostic=diagnostic,
            )
            if not rendered.layout.valid:
                raise ValueError(f"{kind}: invalid annotation layout")
            name = f"c3-{kind}-{'diagnostic' if diagnostic else 'clean'}.svg"
            (output_dir / name).write_text(
                _crop(rendered.svg, kind, review=diagnostic),
                encoding="utf-8",
            )
    raw = next(c for c in original.components if c.reference == "C3")
    shifted = next(c for c in candidate.components if c.reference == "C3")
    report = {
        "status": "DRAFT_PLACEMENT_PROPOSAL_ONLY",
        "source": "Issue #44; original examples/review_end_to_end_circuit.py unchanged",
        "symbol": {"id": c3_symbol.identifier, "revision": c3_symbol.revision,
                   "status": c3_symbol.status.value},
        "physical_part": raw.part_id,
        "original_origin_um": [raw.origin.x, raw.origin.y],
        "proposed_origin_um": [shifted.origin.x, shifted.origin.y],
        "original_pins_um": {
            p: [at.x, at.y] for p, at in raw.pin_positions(c3_symbol).items()
        },
        "proposed_pins_um": {
            p: [at.x, at.y] for p, at in shifted.pin_positions(c3_symbol).items()
        },
        "original_wire_count": len(draft.segments),
        "proposed_wire_count": len(proposal.segments),
        "original_junctions_um": [[p.x, p.y] for p in draft.junctions],
        "proposed_junctions_um": [[p.x, p.y] for p in proposal.junctions],
        "net_names": [net.name for net in original.nets],
        "note": "The proposed authored placement must be reviewed by ELEKTRIK.",
    }
    (output_dir / "c3-comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
