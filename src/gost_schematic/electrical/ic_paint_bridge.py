"""DRAFT two-phase ELEKTRIK #87 -> PAINT #88 binding, pending review.

PAINT PR #93 remains an independent dependency; the import is deliberately
lazy, so the electrical package can be installed without the graphics PR.
Every returned pin uses ONE authoritative (PinRef, integer-um Point) identity.
No E1, public Circuit, Net or standard catalog API is extended.
"""
from dataclasses import dataclass, replace

from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Side
from gost_schematic.electrical.ic import (
    IcField,
    IcKind,
    IcPortLayout,
    IcPinType,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import PinRef


@dataclass(frozen=True, slots=True)
class IcPinSideReflow:
    """Auditable local UGO side change; never changes physical pin identity."""

    unit_id: str
    pin_ref: PinRef
    old_side: Side
    new_side: Side


@dataclass(frozen=True, slots=True)
class IcPaintBinding:
    """An explicit revised electrical record and matching PAINT view objects."""

    record: IcLibraryRecord
    views: tuple[object, ...]
    unit_ids: tuple[str, ...]
    side_reflows: tuple[IcPinSideReflow, ...] = ()

    def verify_endpoints(self) -> None:
        """Exact *semantic and geometric* world contract, never just equality.

        A caller may not swap a pin label, electrical role, displayed row,
        unit view, drawing side, transform, or visible function while keeping
        the same external Point and still pass this release gate.
        """
        positions = resolve_ic_pin_positions(
            self.record.device, self.record.specs, self.record.placements,
        )
        expected_units = tuple(s.unit_id for s in self.record.specs)
        if (
            self.unit_ids != expected_units
            or len(self.views) != len(self.record.placements)
            or len(self.views) != len(self.unit_ids)
        ):
            raise ValueError("IC_PAINT_UNIT_COUNT_MISMATCH")
        placement_map = {p.unit_id: p for p in self.record.placements}
        unit_number = {
            u.id: i for i, u in enumerate(self.record.device.units, start=1)
        }
        seen_refs: set[PinRef] = set()
        for spec, view in zip(self.record.specs, self.views, strict=True):
            placement = placement_map[spec.unit_id]
            suffix = (
                f".{unit_number[spec.unit_id]}"
                if len(self.record.device.units) > 1 else ""
            )
            expected_reference = placement.component_ref + suffix
            if (
                view.reference != expected_reference
                or view.body != spec.body
                or view.origin != placement.origin
                or view.transform != placement.transform
                or view.content != _content(spec, self.record.device)
                or view.orientation.value != spec.profile.port_layout.value
                or view.function_rotation != spec.profile.function_angle.value
                or view.field_text_rotation != spec.profile.other_text_angle.value
            ):
                raise ValueError(f"IC_PAINT_VIEW_SEMANTIC_MISMATCH: {spec.unit_id}")
            if len(view.pins) != len(spec.rows):
                raise ValueError(f"IC_PAINT_PIN_COVERAGE_MISMATCH: {spec.unit_id}")
            for row, pin in zip(spec.rows, view.pins, strict=True):
                ref = PinRef(placement.component_ref, row.number)
                world = positions[ref]
                if (
                    ref in seen_refs
                    or pin.number != row.number
                    or pin.pin_id != f"{placement.component_ref}.P{row.number}"
                    or pin.side != row.side
                    or pin.row != row.visual_row
                    or pin.row_key != row.row_key
                    or pin.label != row.label
                    or pin.role != _role(
                        self.record.device.pin_map[row.number].electrical_type,
                    )
                ):
                    raise ValueError(f"IC_PAINT_PIN_SEMANTIC_MISMATCH: {ref}")
                if pin.anchor != world:
                    raise ValueError(f"IC_PIN_ANCHOR_MISMATCH: {ref}")
                seen_refs.add(ref)
        if seen_refs != set(positions):
            raise ValueError("IC_PAINT_PIN_COVERAGE_MISMATCH")
        if len({
            (reflow.unit_id, reflow.pin_ref)
            for reflow in self.side_reflows
        }) != len(self.side_reflows):
            raise ValueError("IC_PAINT_DUPLICATE_SIDE_REFLOW")
        for reflow in self.side_reflows:
            if (
                reflow.unit_id not in placement_map
                or reflow.pin_ref.reference
                != placement_map[reflow.unit_id].component_ref
                or reflow.pin_ref not in positions
                or reflow.old_side == reflow.new_side
            ):
                raise ValueError("IC_PAINT_INVALID_SIDE_REFLOW")


def _role(role: IcPinType) -> str:
    return {
        IcPinType.INPUT: "in",
        IcPinType.OUTPUT: "out",
        IcPinType.BIDIRECTIONAL: "bidir",
        IcPinType.POWER_INPUT: "power",
        IcPinType.POWER_OUTPUT: "power",
        IcPinType.OPEN_COLLECTOR: "out",
        IcPinType.PASSIVE: "passive",
        IcPinType.NC: "nc",
    }[role]


def _drawing_side(role: IcPinType, side: Side) -> Side:
    """Explicit draft view reflow; physical number and pin type are unchanged."""
    if role is IcPinType.INPUT:
        return Side.LEFT
    if role in (IcPinType.OUTPUT, IcPinType.OPEN_COLLECTOR):
        return Side.RIGHT
    return side


def _content(spec, device):
    # Exact visual text is explicitly supplied, not reconstructed from pin
    # numbers or guessed from a device name. No fixed character limit.
    from gost_schematic.rendering.ic_rectangular import IcFieldContent

    return IcFieldContent(
        function=spec.main_field,
        left_rows=(spec.aux_left,) if spec.aux_left is not None else (),
        right_rows=(spec.aux_right,) if spec.aux_right is not None else (),
        analog=device.kind is IcKind.ANALOG,
    )


def _preliminary_pins(spec, placement, device):
    from gost_schematic.rendering.ic_rectangular import ResolvedIcPin

    return tuple(
        ResolvedIcPin(
            pin_id=f"{placement.component_ref}.P{row.number}",
            number=row.number,
            label=row.label,
            side=row.side,
            row=row.visual_row,
            anchor=placement.transform.apply(row.anchor) + placement.origin,
            role=_role(device.pin_map[row.number].electrical_type),
            row_key=row.row_key,
        ) for row in spec.rows
    )


def propose_ic_paint_binding(
    record: IcLibraryRecord, style, measurer, *, policy=None,
) -> IcPaintBinding:
    """Measure the actual font, then explicitly author a NEW model revision.

    Old record, pin numbers, logical units, component references and Circuit
    Nets are never mutated. A new local body and new *local* outer lead points
    are approved as a new IcSymbolSpec by the caller. Renderer must accept
    these exact points; it may not auto-adjust them.

    A returned record is only a DRAFT candidate; it is not a certified UGO,
    datasheet pinout, or automatic public circuit upgrade.
    """
    from gost_schematic.rendering.ic_rectangular import (
        IcOrientation,
        IcRenderingPolicy,
        IcResolvedUnit,
        propose_ic_dimensions,
    )

    if not isinstance(record, IcLibraryRecord):
        raise TypeError("Expected an IcLibraryRecord")
    if policy is None:
        policy = IcRenderingPolicy()
    if not isinstance(policy, IcRenderingPolicy):
        raise TypeError("Expected IcRenderingPolicy")
    unit_order = {unit.id: i for i, unit in enumerate(record.device.units, 1)}
    placements = {place.unit_id: place for place in record.placements}
    new_specs = []
    views = []
    side_reflows = []
    for spec in record.specs:
        placement = placements[spec.unit_id]
        arrangement = (
            IcOrientation.LEFT_RIGHT
            if spec.profile.port_layout is IcPortLayout.LEFT_RIGHT
            else IcOrientation.TOP_BOTTOM
        )
        # PAINT #93 currently permits rotation of central function only
        # under TOP_BOTTOM. For LEFT_RIGHT this model is valid but printing
        # requires a separately reviewed source-backed PAINT ink profile.
        if (
            arrangement is IcOrientation.LEFT_RIGHT
            and (spec.profile.function_angle.value
                 or spec.profile.other_text_angle.value)
        ):
            raise ValueError(
                "IC_PAINT_LEFT_RIGHT_TEXT_ROTATION_BLOCKED:"
                " typed experimental profile survives but cannot be printed"
            )
        expected_sides = (
            (Side.LEFT, Side.RIGHT)
            if arrangement is IcOrientation.LEFT_RIGHT
            else (Side.TOP, Side.BOTTOM)
        )
        if any(row.side not in expected_sides for row in spec.rows):
            raise ValueError("IC_PORT_LAYOUT_MISMATCH: source physical sides")
        # Functional units may start at an even physical pin. Reflow their
        # graphical sides explicitly: an OUTPUT on LEFT, or INPUT on RIGHT,
        # is not an acceptable default PAINT presentation. These are NEW
        # view specs, not altered physical pins or altered Circuit.Nets.
        layout_rows = (
            tuple(replace(
                row, side=_drawing_side(
                    record.device.pin_map[row.number].electrical_type, row.side,
                ),
            ) for row in spec.rows)
            if arrangement is IcOrientation.LEFT_RIGHT else spec.rows
        )
        for old, revised_row in zip(spec.rows, layout_rows, strict=True):
            if old.side != revised_row.side:
                side_reflows.append(IcPinSideReflow(
                    spec.unit_id, PinRef(placement.component_ref, old.number),
                    old.side, revised_row.side,
                ))
        if any(
            (row.field is IcField.AUX_LEFT and row.side is not Side.LEFT)
            or (row.field is IcField.AUX_RIGHT and row.side is not Side.RIGHT)
            for row in layout_rows
        ):
            raise ValueError("IC_FIELD_SIDE_MISMATCH")
        # Deliberately DO NOT instantiate an intermediate IcSymbolSpec:
        # its previous anchors belong to the old sides, so they must fail
        # validation until fresh exact endpoints have been calculated.
        prelim = tuple(
            replace(pin, side=row.side)
            for pin, row in zip(
                _preliminary_pins(spec, placement, record.device),
                layout_rows, strict=True,
            )
        )
        content = _content(spec, record.device)
        dimensions = propose_ic_dimensions(
            content, prelim, style, measurer, policy,
            orientation=arrangement,
        )
        # PAINT returns the minimum measured geometry. The original rectangle
        # is not silently edited. Instead produce a freshly versioned record.
        # Never silently shrink an author's existing declared rectangle;
        # preserving its origin avoids hidden layout changes in other units.
        # A height increase is snapped to PAINT's measured row pitch.
        def ceil_multiple(value: int, quantum: int) -> int:
            return ((value + quantum - 1) // quantum) * quantum

        if spec.body.min_x % policy.module_um or spec.body.min_y % policy.module_um:
            raise ValueError("IC_GRID_MISMATCH: source body origin off module")
        width_um = ceil_multiple(
            max(spec.body.max_x - spec.body.min_x, dimensions.width_um),
            (
                policy.module_um if arrangement is IcOrientation.LEFT_RIGHT
                else dimensions.row_pitch_um
            ),
        )
        height_um = ceil_multiple(
            max(spec.body.max_y - spec.body.min_y, dimensions.height_um),
            (
                dimensions.row_pitch_um if arrangement is IcOrientation.LEFT_RIGHT
                else policy.module_um
            ),
        )
        body = Box(
            spec.body.min_x, spec.body.min_y,
            spec.body.min_x + width_um,
            spec.body.min_y + height_um,
        )
        new_rows = []
        for row in layout_rows:
            if row.visual_row >= dimensions.row_count:
                raise ValueError("IC_PIN_ROW_OVERFLOW")
            if arrangement is IcOrientation.LEFT_RIGHT:
                boundary = Point(
                    body.min_x if row.side is Side.LEFT else body.max_x,
                    body.min_y + row.visual_row * dimensions.row_pitch_um
                    + dimensions.row_pitch_um // 2,
                )
            else:
                # PAINT's vertical_as_canonical maps TOP/BOTTOM to a
                # reverse-indexed left/right canonical row. Derive x from
                # the same exact integer grid, not a pixel or SVG shift.
                last_column = max(r.visual_row for r in layout_rows)
                canon_row = last_column + 1 - row.visual_row
                boundary = Point(
                    body.max_x - canon_row * dimensions.row_pitch_um
                    - dimensions.row_pitch_um // 2,
                    body.min_y if row.side is Side.TOP else body.max_y,
                )
            normal = SIDE_VECTORS[row.side]
            anchor = Point(
                boundary.x + normal.x * dimensions.lead_length_um,
                boundary.y + normal.y * dimensions.lead_length_um,
            )
            new_rows.append(replace(row, anchor=anchor))
        new_spec = replace(
            spec, body=body, rows=tuple(new_rows),
            revision=spec.revision + 1,
        )
        new_specs.append(new_spec)

        # Rebuild from ELECTRICAL's authoritative new points, not from the
        # drawing calculation: world pin endpoints are resolved exactly once.
        final_pins = _preliminary_pins(new_spec, placement, record.device)
        suffix = f".{unit_order[spec.unit_id]}" if len(record.device.units) > 1 else ""
        views.append(IcResolvedUnit(
            reference=placement.component_ref + suffix,
            body=new_spec.body,
            pins=final_pins,
            content=content,
            origin=placement.origin,
            transform=placement.transform,
            orientation=arrangement,
            function_rotation=spec.profile.function_angle.value,
            field_text_rotation=spec.profile.other_text_angle.value,
        ))
    updated = IcLibraryRecord(record.device, tuple(new_specs), record.placements)
    binding = IcPaintBinding(
        updated, tuple(views), tuple(s.unit_id for s in record.specs),
        tuple(side_reflows),
    )
    binding.verify_endpoints()
    if tuple(p.number for p in record.device.pins) != tuple(
        p.number for p in binding.record.device.pins
    ):
        raise ValueError("IC_PHYSICAL_NUMBER_MUTATED")
    return binding
