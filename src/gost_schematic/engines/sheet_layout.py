"""Whole-sheet annotation coordinator; semantic model and SVG stay separate.

Orchestrates existing engines rather than putting circuit/standard logic into
the reusable symbol catalog. Placed components are never modified by layout.
"""

from dataclasses import dataclass, replace

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
)
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationPlacement,
    AnnotationRequest,
    AnnotationRole,
    HorizontalAlign,
    TextStyle,
    VerticalAlign,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import NominalDisplayConfiguration
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.annotation_checks import validate_annotation_scene


@dataclass(frozen=True, slots=True)
class SheetLabelProfile:
    """Preferred sheet-readable label locations, in integer micrometres.

    These are configurable editorial offsets, NOT dimensions prescribed by ГОСТ.
    Position designators follow ГОСТ 2.702-2011 §5.3.11: above or right.
    """

    body_gap_um: int = 1700
    side_gap_um: int = 2000

    def __post_init__(self) -> None:
        if type(self.body_gap_um) is not int or self.body_gap_um <= 0:
            raise ValueError("body_gap_um must be positive integer micrometres")
        if type(self.side_gap_um) is not int or self.side_gap_um <= 0:
            raise ValueError("side_gap_um must be positive integer micrometres")


@dataclass(frozen=True, slots=True)
class SheetLayout:
    """Immutable placements/diagnostics; callers may re-layout after any edit."""

    placements: tuple[AnnotationPlacement, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == Severity.ERROR for issue in self.diagnostics)


def _global_box(symbol: SymbolDefinition, instance: ComponentInstance) -> Box:
    return instance.transform.box(symbol.body_keepout).translated(instance.origin)


def _graphic_box(symbol: SymbolDefinition, instance: ComponentInstance) -> Box:
    return instance.transform.box(symbol.bounds).translated(instance.origin)


def sheet_label_requests(
    requests: tuple[AnnotationRequest, ...],
    symbol: SymbolDefinition,
    instance: ComponentInstance,
    profile: SheetLabelProfile,
) -> tuple[AnnotationRequest, ...]:
    """Map only refdes/value slots to global candidates, preserving all other roles.

    Body geometry determines the label's vertical reference; symbol bounds
    include external leads for choosing right/left positions. The candidate
    anchors are already in document coordinates and MUST NOT rotate with the UGO.
    """
    body = _global_box(symbol, instance)
    graphics = _graphic_box(symbol, instance)
    center_x = (body.min_x + body.max_x) // 2
    top = body.min_y - profile.body_gap_um
    bottom = body.max_y + profile.body_gap_um
    right = graphics.max_x + profile.side_gap_um
    left = graphics.min_x - profile.side_gap_um

    output: list[AnnotationRequest] = []
    for request in requests:
        if request.slot.role == AnnotationRole.REFDES:
            candidates = (
                Anchor(Point(center_x, top), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),
                Anchor(Point(right, top), HorizontalAlign.LEFT, VerticalAlign.BOTTOM),
            )
        elif request.slot.role == AnnotationRole.VALUE:
            candidates = (
                Anchor(Point(center_x, bottom), HorizontalAlign.CENTER, VerticalAlign.TOP),
                Anchor(Point(right, bottom), HorizontalAlign.LEFT, VerticalAlign.TOP),
                Anchor(Point(left, bottom), HorizontalAlign.RIGHT, VerticalAlign.TOP),
            )
        else:
            output.append(request)
            continue

        output.append(replace(
            request,
            slot=replace(request.slot, candidates=candidates, reserved_region=None),
            origin=Point(0, 0),
            transform=Transform(),
        ))
    return tuple(output)


def layout_sheet(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    configuration: NominalDisplayConfiguration | None = None,
    profile: SheetLabelProfile | None = None,
    wires: tuple[WireObstacle, ...] = (),
    forbidden_boxes: tuple[BoxObstacle, ...] = (),
) -> SheetLayout:
    """Place every visible label with all components and conductor obstacles.

    Same-input results are deterministic. Every call rebinds actual formatted
    value text, remeasures its glyphs and creates fresh hitboxes.
    """
    profile = profile or SheetLabelProfile()
    config = configuration or NominalDisplayConfiguration()
    diagnostics: list[Diagnostic] = []
    requests: list[AnnotationRequest] = []
    blocked = list(forbidden_boxes)
    graphics: list[tuple[str, Box]] = []
    corridors = []
    seen: set[str] = set()

    if not circuit.components:
        return SheetLayout((), (Diagnostic(
            "SHEET_EMPTY", Severity.ERROR, "No components on the sheet",
        ),))

    for component in circuit.components:
        if component.reference in seen:
            diagnostics.append(Diagnostic(
                "DUPLICATE_REFERENCE", Severity.ERROR,
                f"Duplicate component reference: {component.reference}", component.reference,
            ))
            continue
        seen.add(component.reference)
        symbol = symbols_by_part.get(component.part_id)
        if symbol is None:
            diagnostics.append(Diagnostic(
                "UNKNOWN_SHEET_SYMBOL", Severity.ERROR,
                f"No symbol defined for part {component.part_id}", component.reference,
            ))
            continue
        geometry = _graphic_box(symbol, component)
        graphics.append((component.reference, geometry.expanded(
            (symbol.line_width_um + 1) // 2
        )))
        blocked.extend(obstacles_for_component(symbol, component))
        corridors.extend(pin_corridors_for_component(symbol, component))
        try:
            bound = bind_component_annotations(symbol, component, style, config)
        except ValueError as error:
            diagnostics.append(Diagnostic(
                "INVALID_NOMINAL_ANNOTATION", Severity.ERROR,
                str(error), component.reference,
            ))
            continue
        diagnostics.extend(bound.diagnostics)
        requests.extend(sheet_label_requests(bound.requests, symbol, component, profile))

    # Detect real graphical component overlaps, not merely text collisions.
    for i, (left_name, left) in enumerate(graphics):
        for right_name, right in graphics[i + 1:]:
            if left.overlaps(right):
                diagnostics.append(Diagnostic(
                    "SYMBOL_GEOMETRY_OVERLAP", Severity.ERROR,
                    f"{left_name} and {right_name} graphical extents intersect",
                    left_name,
                ))

    # Protected connector exits cannot be occupied by other components.
    for corridor in corridors:
        for name, bounds in graphics:
            if name != corridor.pin.reference and corridor.box.overlaps(bounds):
                diagnostics.append(Diagnostic(
                    "PIN_EXIT_OBSTRUCTED", Severity.ERROR,
                    f"{name} blocks {corridor.identifier}", corridor.pin.reference,
                ))

    arranged = place_annotations(
        tuple(requests), measurer, boxes=tuple(blocked), wires=wires,
    )
    diagnostics.extend(arranged.diagnostics)
    diagnostics.extend(validate_annotation_scene(
        arranged.placements, boxes=tuple(blocked), wires=wires,
    ))
    return SheetLayout(arranged.placements, tuple(diagnostics))
