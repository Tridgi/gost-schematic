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
    IcPinType,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import PinRef


@dataclass(frozen=True, slots=True)
class IcPaintBinding:
    """An explicit revised electrical record and matching PAINT view objects."""

    record: IcLibraryRecord
    views: tuple[object, ...]
    unit_ids: tuple[str, ...]

    def verify_endpoints(self) -> None:
        """No tolerance: resolved model points equal all PAINT world endpoints."""
        positions = resolve_ic_pin_positions(
            self.record.device, self.record.specs, self.record.placements,
        )
        view_refs = set()
        if len(self.views) != len(self.record.placements) or len(self.unit_ids) != len(self.views):
            raise ValueError("IC_PAINT_UNIT_COUNT_MISMATCH")
        placement_map = {p.unit_id: p for p in self.record.placements}
        for unit_id, view in zip(self.unit_ids, self.views, strict=True):
            placement = placement_map[unit_id]
            for pin in view.pins:
                ref = PinRef(placement.component_ref, pin.number)
                if ref in view_refs or positions.get(ref) != pin.anchor:
                    raise ValueError(f"IC_PIN_ANCHOR_MISMATCH: {ref}")
                view_refs.add(ref)
        if view_refs != set(positions):
            raise ValueError("IC_PAINT_PIN_COVERAGE_MISMATCH")


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
    for spec in record.specs:
        placement = placements[spec.unit_id]
        if any(row.side not in (Side.LEFT, Side.RIGHT) for row in spec.rows):
            raise ValueError("IC_UNSUPPORTED_VERTICAL_PORT: ESKD signoff required")
        if any(row.field is IcField.AUX_LEFT and row.side is not Side.LEFT
               or row.field is IcField.AUX_RIGHT and row.side is not Side.RIGHT
               for row in spec.rows):
            raise ValueError("IC_FIELD_SIDE_MISMATCH")
        prelim = _preliminary_pins(spec, placement, record.device)
        content = _content(spec, record.device)
        dimensions = propose_ic_dimensions(content, prelim, style, measurer, policy)
        # PAINT returns the minimum measured geometry. The original rectangle
        # is not silently edited. Instead produce a freshly versioned record.
        body = Box(
            spec.body.min_x, spec.body.min_y,
            spec.body.min_x + dimensions.width_um,
            spec.body.min_y + dimensions.height_um,
        )
        new_rows = []
        for row in spec.rows:
            if row.visual_row >= dimensions.row_count:
                raise ValueError("IC_PIN_ROW_OVERFLOW")
            boundary = Point(
                body.min_x if row.side is Side.LEFT else body.max_x,
                body.min_y + row.visual_row * dimensions.row_pitch_um
                + dimensions.row_pitch_um // 2,
            )
            normal = SIDE_VECTORS[row.side]
            anchor = Point(
                boundary.x + normal.x * dimensions.lead_length_um,
                boundary.y + normal.y * dimensions.lead_length_um,
            )
            new_rows.append(replace(row, anchor=anchor))
        new_spec = replace(
            spec, body=body, rows=tuple(new_rows), revision=spec.revision + 1,
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
        ))
    updated = IcLibraryRecord(record.device, tuple(new_specs), record.placements)
    binding = IcPaintBinding(updated, tuple(views), tuple(s.unit_id for s in record.specs))
    binding.verify_endpoints()
    if tuple(p.number for p in record.device.pins) != tuple(
        p.number for p in binding.record.device.pins
    ):
        raise ValueError("IC_PHYSICAL_NUMBER_MUTATED")
    return binding
