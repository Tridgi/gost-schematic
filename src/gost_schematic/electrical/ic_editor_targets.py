"""Typed ELEKTRIK IC external-contact manifest for PAINT's editor layer.

Physical identity, logical-unit ownership and topology come ONLY from
IcLibraryRecord + validated Circuit.Net. Visual text (VCC/GND/NC) must never
create a physical pin or an electrical net. Exact integer-µm coordinates.
"""
from dataclasses import dataclass

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.ic import (
    IcPinType,
    resolve_ic_pin_positions,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_paint_bridge import IcPaintBinding
from gost_schematic.model.circuit import Circuit, PinRef

_PAINT_ROLES = {
    IcPinType.INPUT: "in",
    IcPinType.OUTPUT: "out",
    IcPinType.BIDIRECTIONAL: "bidir",
    IcPinType.POWER_INPUT: "power",
    IcPinType.POWER_OUTPUT: "power",
    IcPinType.OPEN_COLLECTOR: "out",
    IcPinType.PASSIVE: "passive",
    IcPinType.NC: "nc",
}


@dataclass(frozen=True, slots=True)
class IcPhysicalEditorContact:
    """Complete authoritative source; NOT an interactive green-square hitbox."""

    device_id: str
    package_id: str
    component_ref: str
    unit_id: str
    pin_ref: PinRef
    physical_number: str
    pin_name: str
    role: str
    electrical_type: IcPinType
    anchor: Point
    net_id: str | None
    connectable: bool
    reason: str | None

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v for v in (
            self.device_id, self.package_id, self.component_ref,
            self.unit_id, self.physical_number, self.pin_name,
        )):
            raise ValueError("IC_EDITOR_IDENTITY_MISSING")
        if not isinstance(self.pin_ref, PinRef) or (
            self.pin_ref.reference != self.component_ref
            or self.pin_ref.number != self.physical_number
        ):
            raise ValueError("IC_EDITOR_FOREIGN_PHYSICAL_PINREF")
        if not isinstance(self.electrical_type, IcPinType) or not isinstance(
            self.anchor, Point,
        ):
            raise TypeError("IC_EDITOR_TYPED_CONTACT_REQUIRED")
        if self.role != _PAINT_ROLES[self.electrical_type]:
            raise ValueError("IC_EDITOR_ROLE_TYPE_MISMATCH")
        if type(self.connectable) is not bool:
            raise TypeError("IC_EDITOR_CONNECTABLE_TYPED_BOOL_REQUIRED")
        if self.net_id is not None and (
            not isinstance(self.net_id, str) or not self.net_id.strip()
        ):
            raise ValueError("IC_EDITOR_INVALID_NET_NAME")
        if self.reason is not None and (
            not isinstance(self.reason, str) or not self.reason.strip()
        ):
            raise ValueError("IC_EDITOR_INVALID_DISABLE_REASON")
        if self.electrical_type is IcPinType.NC:
            if self.connectable or self.net_id is not None or (
                self.reason != "NC_PHYSICAL_PIN"
            ):
                raise ValueError("IC_EDITOR_NC_MUST_BE_DISABLED")
        elif not self.connectable and self.reason is None:
            raise ValueError("IC_EDITOR_DISABLED_CONTACT_REQUIRES_REASON")
        elif self.connectable and self.reason is not None:
            raise ValueError("IC_EDITOR_ENABLED_CONTACT_HAS_DISABLE_REASON")


@dataclass(frozen=True, slots=True)
class IcEditorContactManifest:
    """All physical pin targets in every unit, never selected highlights."""

    contacts: tuple[IcPhysicalEditorContact, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.contacts, tuple) or not self.contacts:
            raise ValueError("IC_EDITOR_COMPLETE_INVENTORY_REQUIRED")
        if any(not isinstance(c, IcPhysicalEditorContact) for c in self.contacts):
            raise TypeError("IC_EDITOR_TYPED_CONTACT_REQUIRED")
        if len({c.pin_ref for c in self.contacts}) != len(self.contacts):
            raise ValueError("IC_EDITOR_DUPLICATE_PHYSICAL_CONTACT")
        if len({c.anchor for c in self.contacts}) != len(self.contacts):
            raise ValueError("IC_EDITOR_DUPLICATE_ANCHOR")
        if len({(c.component_ref, c.unit_id, c.physical_number)
                for c in self.contacts}) != len(self.contacts):
            raise ValueError("IC_EDITOR_DUPLICATE_UNIT_CONTACT")

    def for_unit(self, unit_id: str) -> tuple[IcPhysicalEditorContact, ...]:
        selected = tuple(c for c in self.contacts if c.unit_id == unit_id)
        if not selected:
            raise ValueError("IC_EDITOR_UNKNOWN_UNIT")
        return selected


def make_ic_editor_manifest(
    binding: IcPaintBinding, circuit: Circuit | None = None,
) -> IcEditorContactManifest:
    """Derive complete manifest from real model; no inferred VCC/NC nets."""
    if not isinstance(binding, IcPaintBinding):
        raise TypeError("IC_PAINT_BINDING_TYPED_REQUIRED")
    binding.verify_endpoints()
    record = binding.record
    if circuit is not None and not isinstance(circuit, Circuit):
        raise TypeError("IC_EDITOR_TYPED_CIRCUIT_REQUIRED")
    physical_ref = record.placements[0].component_ref
    if circuit is not None:
        validate_ic_circuit(record.device, circuit, physical_ref)
    net_names = {}
    if circuit is not None:
        for net in circuit.nets:
            for member in net.members:
                if member.reference != physical_ref:
                    continue
                if member in net_names:
                    raise ValueError("IC_EDITOR_DUPLICATE_NET_MEMBERSHIP")
                net_names[member] = net.name
    positions = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    placement_map = {p.unit_id: p for p in record.placements}
    contacts = []
    for uid, view in zip(binding.unit_ids, binding.views, strict=True):
        placement = placement_map[uid]
        if placement.component_ref != physical_ref:
            raise ValueError("IC_EDITOR_FOREIGN_COMPONENT")
        for pin in view.pins:
            physical = record.device.pin_map[pin.number]
            ref = PinRef(physical_ref, pin.number)
            if ref not in positions or pin.anchor != positions[ref]:
                raise ValueError("IC_EDITOR_PINREF_ENDPOINT_MISMATCH")
            pin_type = physical.electrical_type
            contacts.append(IcPhysicalEditorContact(
                device_id=record.device.identifier,
                package_id=record.device.package.package_id,
                component_ref=physical_ref,
                unit_id=uid,
                pin_ref=ref,
                physical_number=pin.number,
                pin_name=physical.name,
                role=_PAINT_ROLES[pin_type],
                electrical_type=pin_type,
                anchor=positions[ref],
                net_id=net_names.get(ref),
                connectable=pin_type is not IcPinType.NC,
                reason="NC_PHYSICAL_PIN" if pin_type is IcPinType.NC else None,
            ))
    result = IcEditorContactManifest(tuple(contacts))
    if len(result.contacts) != record.device.package.pin_count:
        raise ValueError("IC_EDITOR_INCOMPLETE_PHYSICAL_PACKAGE")
    return result


def verify_ic_editor_manifest(
    binding: IcPaintBinding,
    provided: IcEditorContactManifest,
    circuit: Circuit | None = None,
) -> None:
    """No 1µm slack, wrong physical owner, unit or counterfeit net allowed."""
    if not isinstance(provided, IcEditorContactManifest):
        raise TypeError("IC_EDITOR_TYPED_MANIFEST_REQUIRED")
    expected = make_ic_editor_manifest(binding, circuit)
    if provided != expected:
        if len(provided.contacts) != len(expected.contacts):
            raise ValueError("IC_EDITOR_INCOMPLETE_TARGETS")
        for wanted, actual in zip(expected.contacts, provided.contacts, strict=True):
            if wanted.pin_ref != actual.pin_ref or (
                wanted.component_ref != actual.component_ref
            ):
                raise ValueError("IC_EDITOR_FOREIGN_PHYSICAL_PINREF")
            if wanted.unit_id != actual.unit_id:
                raise ValueError("IC_EDITOR_WRONG_LOGICAL_UNIT")
            if wanted.anchor != actual.anchor:
                raise ValueError("IC_EDITOR_PINREF_ENDPOINT_MISMATCH")
        raise ValueError("IC_EDITOR_CONTACT_SEMANTIC_OR_NET_MISMATCH")


def make_paint_editor_targets(
    binding: IcPaintBinding,
    manifest: IcEditorContactManifest,
    circuit: Circuit | None = None,
) -> tuple[tuple[object, ...], ...]:
    """Convert complete typed per-unit source to PAINT #93's existing API.

    Green is a visual review marker only, never a connection transaction.
    """
    from gost_schematic.rendering.ic_hotspots import (
        IcConnectionTarget,
        verify_ic_connection_targets,
    )

    verify_ic_editor_manifest(binding, manifest, circuit)
    result = []
    for uid, view in zip(binding.unit_ids, binding.views, strict=True):
        source = manifest.for_unit(uid)
        targets = tuple(IcConnectionTarget(
            pin_id=f"{c.component_ref}.P{c.physical_number}",
            pin_ref=c.pin_ref,
            anchor=c.anchor,
            connectable=c.connectable,
            net_id=c.net_id,
            reason=c.reason,
        ) for c in source)
        checked = verify_ic_connection_targets(view.pins, targets)
        if len(checked) != len(view.pins) or {
            t.pin_id for t in checked
        } != {p.pin_id for p in view.pins}:
            raise ValueError("IC_EDITOR_INCOMPLETE_TARGETS")
        result.append(checked)
    return tuple(result)


def render_ic_editor_review(
    binding: IcPaintBinding, style, measurer, *,
    circuit: Circuit | None = None, diagnostics: bool = False,
) -> tuple[object, ...]:
    """Clean mode never emits green/red squares. Diagnostic mode emits all."""
    from gost_schematic.rendering.ic_rectangular import render_resolved_ic

    manifest = make_ic_editor_manifest(binding, circuit)
    per_view = make_paint_editor_targets(binding, manifest, circuit)
    result = []
    for view, targets in zip(binding.views, per_view, strict=True):
        result.append(render_resolved_ic(
            view, style, measurer,
            editor_targets=targets if diagnostics else (),
            editor_overlay=diagnostics,
            review_overlay=diagnostics,
            glyph_detail=diagnostics,
        ))
    return tuple(result)
