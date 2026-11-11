"""Deterministic annotation placement with independent ink and collision boxes."""

from collections.abc import Mapping
from dataclasses import dataclass

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationPlacement,
    AnnotationRequest,
    HorizontalAlign,
    MeasuredText,
    TextStyle,
    VerticalAlign,
)
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.model.symbol import SymbolDefinition

from .collision import BoxObstacle, WireObstacle, wire_intersects_box
from .metrics import TextMeasurer


@dataclass(frozen=True, slots=True)
class AnnotationLayoutResult:
    placements: tuple[AnnotationPlacement, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == Severity.ERROR for item in self.diagnostics)


def _align_text(anchor: Point, metrics: MeasuredText, candidate: Anchor) -> Point:
    box = metrics.ink_box
    if candidate.horizontal == HorizontalAlign.LEFT:
        x = anchor.x - box.min_x
    elif candidate.horizontal == HorizontalAlign.CENTER:
        x = anchor.x - (box.min_x + box.max_x) // 2
    else:
        x = anchor.x - box.max_x
    if candidate.vertical == VerticalAlign.TOP:
        y = anchor.y - box.min_y
    elif candidate.vertical == VerticalAlign.CENTER:
        y = anchor.y - (box.min_y + box.max_y) // 2
    else:
        y = anchor.y - box.max_y
    return Point(x, y)


def _conflicts(
    area: Box,
    boxes: tuple[BoxObstacle, ...],
    wires: tuple[WireObstacle, ...],
    existing: list[AnnotationPlacement],
) -> tuple[str, ...]:
    conflicts = [
        f"{item.kind}:{item.identifier}"
        for item in boxes
        if area.overlaps(item.box)
    ]
    conflicts.extend(
        f"wire:{item.identifier}"
        for item in wires
        if wire_intersects_box(item, area)
    )
    conflicts.extend(
        f"annotation:{item.owner}.{item.key}"
        for item in existing
        if area.overlaps(item.collision_bounds)
        or (item.reservation_bounds is not None and area.overlaps(item.reservation_bounds))
    )
    return tuple(conflicts)


def place_annotations(
    requests: tuple[AnnotationRequest, ...],
    measurer: TextMeasurer,
    boxes: tuple[BoxObstacle, ...] = (),
    wires: tuple[WireObstacle, ...] = (),
) -> AnnotationLayoutResult:
    """Find the first collision-free candidate; never suppress unplaceable text.

    Input request order determines priority. Every placement stays readable after
    rotation or mirror: the local anchor transforms, but SVG glyphs stay upright.
    """
    placed: list[AnnotationPlacement] = []
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[str, str]] = set()
    for request in requests:
        if not request.visible:
            continue
        identity = (request.owner, request.slot.key)
        if identity in seen:
            diagnostics.append(Diagnostic(
                "DUPLICATE_ANNOTATION", Severity.ERROR,
                f"Duplicate annotation {request.owner}.{request.slot.key}", request.owner,
            ))
            continue
        seen.add(identity)
        metrics = measurer.measure(request.text, request.style)
        reservation = (
            request.transform.box(request.slot.reserved_region).translated(request.origin)
            if request.slot.reserved_region is not None
            else None
        )
        options = request.slot.candidates[:1] if request.locked else request.slot.candidates
        failures: list[str] = []
        for index, candidate in enumerate(options):
            anchor = request.transform.apply(candidate.at) + request.origin
            baseline = _align_text(anchor, metrics, candidate)
            ink = metrics.ink_box.translated(baseline)
            hitbox = ink.expanded(request.style.clearance_um)
            blocking = _conflicts(hitbox, boxes, wires, placed)
            if reservation is not None:
                blocking += _conflicts(reservation, boxes, wires, placed)
            if blocking:
                failures.extend(blocking)
                continue
            placed.append(AnnotationPlacement(
                owner=request.owner,
                key=request.slot.key,
                role=request.slot.role,
                text=request.text,
                style=request.style,
                baseline=baseline,
                ink_bounds=ink,
                collision_bounds=hitbox,
                reservation_bounds=reservation,
                candidate_index=index,
            ))
            break
        else:
            diagnostics.append(Diagnostic(
                "ANNOTATION_UNPLACEABLE", Severity.ERROR,
                f"No collision-free position for {request.owner}.{request.slot.key}: "
                + ", ".join(sorted(set(failures))),
                request.owner,
            ))
    return AnnotationLayoutResult(tuple(placed), tuple(diagnostics))


def requests_for_component(
    symbol: SymbolDefinition,
    component: ComponentInstance,
    style: TextStyle,
    values: Mapping[str, str] | None = None,
) -> tuple[AnnotationRequest, ...]:
    """Bind symbol-level slots to instance-specific text without mutating definitions."""
    bindings = values or {}
    requests: list[AnnotationRequest] = []
    for slot in symbol.annotation_slots:
        value = component.reference if slot.key == "refdes" else bindings.get(slot.key, "")
        if value:
            requests.append(AnnotationRequest(
                owner=component.reference, slot=slot, text=value, style=style,
                origin=component.origin, transform=component.transform,
            ))
        elif slot.required:
            raise ValueError(f"Missing mandatory annotation {component.reference}.{slot.key}")
    return tuple(requests)


def obstacles_for_component(
    symbol: SymbolDefinition,
    component: ComponentInstance,
    *,
    pin_corridor_length_um: int = 1800,
    pin_corridor_width_um: int = 800,
) -> tuple[BoxObstacle, ...]:
    """Body keepout and reserved pin-escape regions in global coordinates."""
    if pin_corridor_length_um <= 0 or pin_corridor_width_um <= 0:
        raise ValueError("Pin corridor dimensions must be positive")
    keepout = component.transform.box(symbol.body_keepout).translated(component.origin)
    obstacles = [BoxObstacle(
        f"{component.reference}.body", keepout, "symbol", component.reference,
    )]
    half = (pin_corridor_width_um + 1) // 2
    for pin in symbol.pins:
        at = component.transform.apply(pin.at) + component.origin
        side = component.transform.side(pin.side)
        if side == Side.LEFT:
            bounds = Box(at.x - pin_corridor_length_um, at.y - half, at.x, at.y + half)
        elif side == Side.RIGHT:
            bounds = Box(at.x, at.y - half, at.x + pin_corridor_length_um, at.y + half)
        elif side == Side.TOP:
            bounds = Box(at.x - half, at.y - pin_corridor_length_um, at.x + half, at.y)
        else:
            bounds = Box(at.x - half, at.y, at.x + half, at.y + pin_corridor_length_um)
        obstacles.append(BoxObstacle(
            f"{component.reference}.pin.{pin.number}", bounds, "pin_escape",
            component.reference,
        ))
    return tuple(obstacles)
