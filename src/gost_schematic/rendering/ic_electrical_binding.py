"""Read-only, opt-in PAINT consumption of ELEKTRIK #87's verified binding.

This module has NO import-time dependency on unmerged PR #97. Calls require
the real typed implementation to be present in the runtime; fake source
Points, raw dicts and unverified PinRef/net inference are forbidden.
"""
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import render_resolved_ic


def render_verified_ic_paint_binding(
    binding, style, measurer, *, circuit: Circuit | None = None,
    review_overlay: bool = False, glyph_detail: bool = False,
    editor_overlay: bool = False,
):
    """Render actual resolved PinRef endpoints, with NO model revision edits.

    The electrical owner has already produced an explicit new IcSymbolSpec
    and resolved the external Point; PAINT neither calls the proposing step
    nor creates another physical view from an old spec here.
    """
    try:
        from gost_schematic.electrical.ic import (
            IcPinType,
            resolve_ic_pin_positions,
            validate_ic_circuit,
        )
        from gost_schematic.electrical.ic_paint_bridge import IcPaintBinding
    except ImportError as exc:
        raise RuntimeError(
            "IC_ELECTRICAL_MODEL_UNAVAILABLE: install reviewed PR #97"
        ) from exc
    if not isinstance(binding, IcPaintBinding):
        raise TypeError("IC_VERIFIED_ELECTRICAL_BINDING_REQUIRED")
    binding.verify_endpoints()
    record = binding.record
    resolved_before = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    original_nets = circuit.nets if circuit is not None else None
    refs = {placement.component_ref for placement in record.placements}
    if circuit is not None:
        if not isinstance(circuit, Circuit):
            raise TypeError("IC_CIRCUIT_TYPED_REQUIRED")
        if len(refs) != 1:
            raise ValueError("IC_MULTIPLE_PHYSICAL_COMPONENTS_REJECTED")
        validate_ic_circuit(record.device, circuit, next(iter(refs)))
    net_for_pin: dict[PinRef, str] = {}
    if circuit is not None:
        for net in circuit.nets:
            for member in net.members:
                if member in net_for_pin and member in resolved_before:
                    raise ValueError("IC_DUPLICATE_NET_MEMBERSHIP")
                net_for_pin[member] = net.name

    placement_by_unit = {p.unit_id: p for p in record.placements}
    outputs = []
    for unit_id, view in zip(binding.unit_ids, binding.views, strict=True):
        placement = placement_by_unit[unit_id]
        targets = []
        for pin in view.pins:
            physical = PinRef(placement.component_ref, pin.number)
            if resolved_before.get(physical) != pin.anchor:
                raise ValueError(
                    f"IC_PIN_ANCHOR_MISMATCH: {physical} source vs drawing"
                )
            pin_type = record.device.pin_map[pin.number].electrical_type
            nc = pin_type is IcPinType.NC
            targets.append(IcConnectionTarget(
                pin_id=pin.pin_id,
                pin_ref=physical,
                anchor=pin.anchor,
                connectable=not nc,
                net_id=net_for_pin.get(physical),
                reason="NC" if nc else None,
            ))
        outputs.append(render_resolved_ic(
            view, style, measurer,
            review_overlay=review_overlay,
            glyph_detail=glyph_detail,
            editor_targets=tuple(targets),
            editor_overlay=editor_overlay,
        ))
    resolved_after = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    if resolved_after != resolved_before or (
        circuit is not None and circuit.nets != original_nets
    ):
        raise AssertionError("IC_MODEL_MUTATED_DURING_PAINT")
    return tuple(outputs)
