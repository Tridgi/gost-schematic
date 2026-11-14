"""Conservative TRUE-width full-sheet ink collision preflight; no fake PASS.

AABB envelopes contain real measured OpenGOST glyph-run ink and transformed
catalog strokes. Orthogonal authored wire strokes use exact integer-µm
envelopes, including physical width. Arc bounds are conservative review
candidates, not an independent calibrated ISO/GOST 1:1 certification.
"""
from dataclasses import dataclass

from gost_schematic.core.geometry import Box, primitive_stroked_bounds
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.ic_rectangular import IcRendered
from gost_schematic.validation.external_wire_checks import ExternalWireGraph


@dataclass(frozen=True, slots=True)
class SheetInkFinding:
    code: str
    text_owner: str
    ink_kind: str
    source: str
    overlap_box_um: tuple[int, int, int, int]


def _wire_ink_box(a, b, stroke_um: int) -> Box:
    if stroke_um <= 0:
        raise ValueError("SHEET_WIRE_STROKE_NONPOSITIVE")
    d = (stroke_um + 1) // 2
    return Box(
        min(a.x, b.x)-d, min(a.y, b.y)-d,
        max(a.x, b.x)+d+1, max(a.y, b.y)+d+1,
    )


def audit_full_native_sheet_ink(
    circuit: Circuit,
    graph: ExternalWireGraph,
    symbols_by_part: dict[str, SymbolDefinition],
    layout: SheetLayout,
    ic_rendered: IcRendered,
    *,
    wire_stroke_um: int = 300,
    clearance_um: int = 1000,
) -> tuple[SheetInkFinding, ...]:
    """Inspect independently placed native sheet text, UGO and wires.

    Return full unresolved physical issues, do NOT recolor source lines
    or silently convert a collision warning into a zero-error print claim.
    """
    if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
        raise TypeError("SHEET_INK_TYPED_CIRCUIT_AND_WIREGRAPH_REQUIRED")
    if not isinstance(layout, SheetLayout) or not isinstance(ic_rendered, IcRendered):
        raise TypeError("SHEET_INK_TYPED_LAYOUT_AND_PAINT_REQUIRED")
    if type(clearance_um) is not int or clearance_um < 0:
        raise ValueError("SHEET_INK_INVALID_CLEARANCE")
    wires = tuple(
        (
            f"wire:{idx}:{segment.net_name}",
            _wire_ink_box(segment.start, segment.end, wire_stroke_um),
        )
        for idx, segment in enumerate(graph.segments)
    )
    graphics = []
    for component in circuit.components:
        if component.reference == "DA1":
            # Genuine IC ink is measured separately by IcRendered; generic
            # surrogate must not be double counted as a printed UGO.
            continue
        symbol = symbols_by_part[component.part_id]
        for index, primitive in enumerate(symbol.graphics):
            world = component.transform.primitive(primitive, component.origin)
            graphics.append((
                f"{component.reference}:stroke:{index}",
                primitive_stroked_bounds(world, symbol.line_width_um),
            ))
    run_ink = [
        (label.owner, label.key, label.ink_bounds)
        for label in layout.placements if label.owner != "DA1"
    ]
    native_text_kinds = {
        "function", "main-text", "pin-label", "pin-number",
        "refdes", "field-text",
    }
    run_ink.extend(
        ("DA1", ink.kind, ink.box)
        for ink in ic_rendered.ink if ink.kind in native_text_kinds
    )
    findings = []
    for owner, kind, actual_ink in run_ink:
        protected = actual_ink.expanded(clearance_um)
        for identifier, wire in wires:
            if protected.overlaps(wire):
                findings.append(SheetInkFinding(
                    "SHEET_TEXT_TO_WIRE_INK_OR_1MM_GAP",
                    owner, kind, identifier,
                    (actual_ink.min_x, actual_ink.min_y,
                     actual_ink.max_x, actual_ink.max_y),
                ))
        for identifier, symbol_ink in graphics:
            if identifier.startswith(owner+":"):
                continue
            if protected.overlaps(symbol_ink):
                findings.append(SheetInkFinding(
                    "SHEET_TEXT_TO_OTHER_UGO_STROKE_OR_1MM_GAP",
                    owner, kind, identifier,
                    (actual_ink.min_x, actual_ink.min_y,
                     actual_ink.max_x, actual_ink.max_y),
                ))
    return tuple(findings)
