"""DRAFT refdes candidates anchored to visible UGO strokes, not tap keepouts.

Issue #68: no netlist, pin, symbol, routing or source-fixture mutations.
Preference: nearest collision-free above or right, exact measured glyph ink.
The ink and conductor keepouts use integer micrometres; the printed text stays
upright across eight orthogonal component transforms.
"""
from dataclasses import dataclass
from math import hypot

from gost_schematic.core.geometry import (
    Box,
    Rectangle,
    Semicircle,
    enclosing_box,
    primitive_stroked_bounds,
)
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.annotations import (
    AnnotationPlacement,
    AnnotationRole,
    TextStyle,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle, wire_intersects_box
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class VisualRefdesProfile:
    """Measured minimum visual gap and tie-break preference, NOT GOST dimensions."""

    graphic_gap_um: int = 1200
    side_gap_um: int = 1100

    def __post_init__(self) -> None:
        if (type(self.graphic_gap_um) is not int or self.graphic_gap_um <= 0
                or type(self.side_gap_um) is not int or self.side_gap_um <= 0):
            raise ValueError("Refdes gaps must be positive integer micrometres")


def main_ugo_graphic_bounds(
    symbol: SymbolDefinition,
    component: ComponentInstance,
) -> Box:
    """Real stroked winding arcs; rectangular body or full graphic fallback.

    A tap stem is not a winding lobe and must never pull the L1 reference
    label away from its *visible winding*. Other strokes and connectors are
    still protected separately as obstacles.
    """
    selected = tuple(
        primitive for primitive in symbol.graphics
        if isinstance(primitive, Semicircle)
    )
    if not selected:
        selected = tuple(
            primitive for primitive in symbol.graphics
            if isinstance(primitive, Rectangle)
        )
    if not selected:
        selected = symbol.graphics
    return enclosing_box(tuple(
        primitive_stroked_bounds(
            component.transform.primitive(primitive, component.origin),
            symbol.line_width_um,
        )
        for primitive in selected
    ))


def distance_ink_to_main_ugo_um(ink: Box, main: Box) -> float:
    """Nearest AABB-to-AABB ink distance; zero means intersecting geometry."""
    dx = max(main.min_x - ink.max_x, ink.min_x - main.max_x, 0)
    dy = max(main.min_y - ink.max_y, ink.min_y - main.max_y, 0)
    return hypot(dx, dy)


def legacy_keepout_label_ink(
    symbol: SymbolDefinition,
    component: ComponentInstance,
    metrics,
) -> Box:
    """Reconstruct the old SVG rule at physical x=origin, y=keepout top-2.5mm.

    This faithfully retains the *old authored baseline*, but evaluates glyph
    ink with the same calibrated font used for the modern comparison.
    """
    keepout = component.transform.box(symbol.body_keepout).translated(component.origin)
    baseline_x = component.origin.x - (
        metrics.ink_box.min_x + metrics.ink_box.max_x
    ) // 2
    baseline_y = keepout.min_y - 2500
    from gost_schematic.core.geometry import Point

    return metrics.ink_box.translated(Point(baseline_x, baseline_y))


def _baseline_for_ink_left_bottom(metrics, left: int, bottom: int):
    from gost_schematic.core.geometry import Point

    return Point(left - metrics.ink_box.min_x, bottom - metrics.ink_box.max_y)


def _candidate_positions(main: Box, metrics, profile: VisualRefdesProfile):
    """Deterministic above/right candidates, including tap-safe above-right."""
    i = metrics.ink_box
    width = i.max_x - i.min_x
    height = i.max_y - i.min_y
    cx = (main.min_x + main.max_x) // 2
    cy = (main.min_y + main.max_y) // 2
    gap = profile.graphic_gap_um
    side = profile.side_gap_um
    # Candidate generation uses only actual printed glyph bounds, never
    # CSS em-height or conservative body keepout as the visual reference.
    return (
        ("above", cx - width // 2, main.min_y - gap - height),
        ("above-right", main.max_x + side, main.min_y - gap - height),
        ("above-left", main.min_x - side - width, main.min_y - gap - height),
        ("right-high", main.max_x + side, cy - height),
        ("right-center", main.max_x + side, cy - height // 2),
        ("right-lower", main.max_x + side, cy),
        ("above-far-right", main.max_x + side * 2, main.min_y - gap - height),
        ("above-far-left", main.min_x - side * 2 - width,
         main.min_y - gap - height),
    )


def _is_obstructed(
    area: Box,
    boxes: tuple[BoxObstacle, ...],
    wires: tuple[WireObstacle, ...],
    existing: list[AnnotationPlacement],
) -> bool:
    return (
        any(area.overlaps(block.box) for block in boxes)
        or any(wire_intersects_box(wire, area) for wire in wires)
        or any(
            area.overlaps(label.collision_bounds)
            or (
                label.reservation_bounds is not None
                and area.overlaps(label.reservation_bounds)
            )
            for label in existing
        )
    )


def place_refdes_near_visible_graphics(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    wires: tuple[WireObstacle, ...] = (),
    extra_boxes: tuple[BoxObstacle, ...] = (),
    existing_placements: tuple[AnnotationPlacement, ...] = (),
    profile: VisualRefdesProfile | None = None,
) -> tuple[AnnotationPlacement, ...]:
    """Choose nearest collision-free measured ink. Fail closed if impossible."""
    profile = profile or VisualRefdesProfile()
    boxes = list(extra_boxes)
    objects = []
    for component in circuit.components:
        symbol = symbols_by_part.get(component.part_id)
        if symbol is None:
            raise ValueError("UNKNOWN_REFDES_SYMBOL: " + component.part_id)
        main = main_ugo_graphic_bounds(symbol, component)
        objects.append((component, symbol, main))
        keepout = component.transform.box(symbol.body_keepout).translated(
            component.origin
        )
        boxes.append(BoxObstacle(
            component.reference + ".body", keepout, "symbol", component.reference,
        ))
        boxes.extend(obstacles_for_component(symbol, component))
        for index, primitive in enumerate(symbol.graphics):
            boxes.append(BoxObstacle(
                f"{component.reference}.graphic.{index}",
                primitive_stroked_bounds(
                    component.transform.primitive(primitive, component.origin),
                    symbol.line_width_um,
                ), "graphic", component.reference,
            ))
        for pin in pin_corridors_for_component(symbol, component):
            boxes.append(BoxObstacle(
                pin.identifier, pin.box, "pin_escape", component.reference,
            ))
    protected = tuple(boxes)
    placements: list[AnnotationPlacement] = []
    for component, _, main in objects:
        metrics = measurer.measure(component.reference, style)
        candidates = []
        for rank, (kind, left, top) in enumerate(
            _candidate_positions(main, metrics, profile)
        ):
            ink = Box(left, top,
                      left + metrics.ink_box.max_x - metrics.ink_box.min_x,
                      top + metrics.ink_box.max_y - metrics.ink_box.min_y)
            hitbox = ink.expanded(style.clearance_um)
            if _is_obstructed(hitbox, protected, wires,
                              [*existing_placements, *placements]):
                continue
            score = distance_ink_to_main_ugo_um(ink, main)
            candidates.append((score, rank, kind, ink, hitbox))
        if not candidates:
            raise ValueError(
                f"REFDES_UNPLACEABLE: {component.reference}; "
                "no above/right glyph box satisfies graphic/pin/wire clearances"
            )
        _, rank, _, ink, hitbox = min(
            candidates, key=lambda item: (item[0], item[1]),
        )
        baseline = _baseline_for_ink_left_bottom(
            metrics, ink.min_x, ink.max_y,
        )
        placements.append(AnnotationPlacement(
            owner=component.reference,
            key="refdes",
            role=AnnotationRole.REFDES,
            text=component.reference,
            style=style,
            baseline=baseline,
            ink_bounds=ink,
            collision_bounds=hitbox,
            reservation_bounds=None,
            candidate_index=rank,
        ))
    return tuple(placements)


def apply_visible_refdes_to_layout(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    standard_layout,
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    wires: tuple[WireObstacle, ...] = (),
    profile: VisualRefdesProfile | None = None,
):
    """Explicit opt-in replacement on a *copy* of ordinary SheetLayout.

    The default layout_sheet()/render_sheet_svg() APIs and archived fixture
    output remain unchanged. Values, warnings and other annotations survive.
    Any blocked label fails closed before a new SVG is emitted.
    """
    from gost_schematic.engines.sheet_layout import SheetLayout

    if not isinstance(standard_layout, SheetLayout) or not standard_layout.valid:
        raise ValueError("REFDES_PREVIEW_INVALID_BASE_LAYOUT")
    non_refdes = tuple(
        label for label in standard_layout.placements
        if label.role != AnnotationRole.REFDES
    )
    previous = tuple(
        label for label in standard_layout.placements
        if label.role == AnnotationRole.REFDES
    )
    if {p.owner for p in previous} != {
        component.reference for component in circuit.components
    } or len(previous) != len(circuit.components):
        raise ValueError("REFDES_PREVIEW_MISSING_OR_DUPLICATE_REF")
    revised = place_refdes_near_visible_graphics(
        circuit, symbols_by_part, style, measurer,
        wires=wires, existing_placements=non_refdes, profile=profile,
    )
    replacement = {placement.owner: placement for placement in revised}
    placements = tuple(
        replacement[item.owner] if item.role == AnnotationRole.REFDES else item
        for item in standard_layout.placements
    )
    return SheetLayout(placements, standard_layout.diagnostics)
