"""Cycle11: reversible source ref-ID to signed TI TL494CN Circuit mapping.

The original circuit and 15 Net tuples remain immutable. This is NOT
equating arbitrary part ID strings or using an IC painter as the source of
physical pin semantics: owner #97 verifies manufacturer data + frozen photo.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from examples.tl494_v5.native_circuit import NativeV5Assembly
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition

# These owner modules are staged by the specialized IC/PAINT jobs but are
# deliberately absent in the base RECON checkout. Late-bound imports prevent
# Ruff/isort from classifying the very same source differently across jobs.
IcCircuitBinding = import_module(
    "gost_schematic.electrical.ic_circuit_adapter"
).IcCircuitBinding
TI_DEVICE_ID = import_module("gost_schematic.electrical.tl494cn").TI_DEVICE_ID

SOURCE_PART_ID = "reference.tl494cn"
PHYSICAL_REF = "DA1"


@dataclass(frozen=True, slots=True)
class VerifiedCompactTiBinding:
    source_circuit: Circuit
    signed: IcCircuitBinding
    part: PartDefinition
    source_part_id: str = SOURCE_PART_ID
    signed_part_id: str = TI_DEVICE_ID

    def verify(self) -> None:
        if not isinstance(self.source_circuit, Circuit) or not isinstance(
            self.signed, IcCircuitBinding,
        ):
            raise TypeError("TL494_C11_SOURCE_AND_SIGNED_BINDING_REQUIRED")
        self.signed.validate()
        if (
            self.source_part_id != SOURCE_PART_ID
            or self.signed_part_id != TI_DEVICE_ID
            or self.signed.part != self.part
            or self.part.identifier != self.signed_part_id
        ):
            raise ValueError("TL494_C11_SIGNED_MANUFACTURER_PART_CHANGED")
        source = self.source_circuit
        signed = self.signed.circuit
        if (
            len(source.components) != 23 or len(signed.components) != 23
            or len(source.nets) != 15 or len(signed.nets) != 15
            or source.nets is not signed.nets
        ):
            raise ValueError("TL494_C11_SOURCE_NET_TUPLE_CHANGED")
        before = {item.reference: item for item in source.components}
        after = {item.reference: item for item in signed.components}
        if len(before) != 23 or set(before) != set(after):
            raise ValueError("TL494_C11_SOURCE_COMPONENT_LOSS")
        if (
            before[PHYSICAL_REF].part_id != SOURCE_PART_ID
            or after[PHYSICAL_REF].part_id != TI_DEVICE_ID
        ):
            raise ValueError("TL494_C11_UNVERIFIED_IC_PART_SUBSTITUTION")
        for ref, old in before.items():
            new = after[ref]
            if (
                old.reference != new.reference
                or old.nominal != new.nominal
                or old.origin != new.origin
                or old.transform != new.transform
                or (ref != PHYSICAL_REF and old != new)
            ):
                raise ValueError("TL494_C11_NON_IC_OR_PHYSICAL_GEOMETRY_CHANGED")
        physical = {
            p.number: p for p in self.part.pins
        }
        if len(physical) != 16 or set(physical) != {
            str(i) for i in range(1, 17)
        }:
            raise ValueError("TL494_C11_FACTORY_16_PHYSICAL_PINS_MISSING")
        for number, manufacturer_name in (("3", "FEEDBACK"), ("13", "OUTPUT CTRL")):
            pin = physical[number]
            if (
                pin.name != manufacturer_name
                or pin.electrical_type.value != "input"
            ):
                raise ValueError("TL494_C11_FACTORY_TI_INPUT_ROLE_CHANGED")
        if sum(len(net.members) for net in signed.nets) != 62:
            raise ValueError("TL494_C11_62_REAL_NET_MEMBERS_REQUIRED")
        for number in physical:
            pinref = PinRef(PHYSICAL_REF, number)
            matches = [
                net for net in signed.nets if pinref in net.members
            ]
            if len(matches) != 1:
                raise ValueError("TL494_C11_TI_PIN_NET_NOT_UNIQUE")

    def reverse_source(self) -> Circuit:
        """Return original source *object*, not a synthesized alias Net."""
        self.verify()
        return self.source_circuit

    def seal_paint(self, paint_binding):
        """Explicit #97 geometry consent before sealing all 16 PAINT contacts.

        The owner painter may legitimately revise SVG terminal locations.
        Every moved *physical* PinRef requires consent tied to the exact
        signed original record; the complete Circuit and Nets never change.
        """
        from gost_schematic.electrical.ic import resolve_ic_pin_positions
        from gost_schematic.electrical.ic_graphic_revision import (
            IcGeometryConsent,
            ic_record_fingerprint,
        )

        self.verify()
        old = resolve_ic_pin_positions(
            self.signed.record.device,
            self.signed.record.specs,
            self.signed.record.placements,
        )
        proposed = resolve_ic_pin_positions(
            paint_binding.record.device,
            paint_binding.record.specs,
            paint_binding.record.placements,
        )
        if set(old) != set(proposed) or len(old) != 16:
            raise ValueError("TL494_C11_PAINT_PROPOSED_PHYSICAL_PIN_LOSS")
        moved = tuple(ref for ref in old if old[ref] != proposed[ref])
        active = {
            pin for net in self.signed.circuit.nets
            for pin in net.members if pin in old
        }
        consent = IcGeometryConsent(
            ic_record_fingerprint(self.signed.record),
            moved,
            tuple(ref for ref in moved if ref in active),
        )
        revised, delta = self.signed.revise(
            paint_binding.record, consent=consent,
        )
        if set(delta.moved) != set(moved) or (
            revised.circuit is not self.signed.circuit
            or revised.circuit.nets is not self.source_circuit.nets
        ):
            raise ValueError("TL494_C11_PAINT_REVISE_SOURCE_NET_DRIFT")
        result = revised.seal_paint_overlay(paint_binding)
        result.verify_against(revised, paint_binding)
        if len(result.per_unit_targets) != 1 or (
            len(result.per_unit_targets[0]) != 16
        ):
            raise ValueError("TL494_C11_PAINT_NOT_16_SIGNED_TARGETS")
        return revised, result


def bind_verified_compact_ti(
    assembly: NativeV5Assembly, source_circuit: Circuit,
) -> VerifiedCompactTiBinding:
    """Make one manufacturer Circuit from actual compact source positions.

    Strict owner #97 API loads locked photo fixture and checks 23 refs, 15
    original Net names, 62 physical PinRefs, exact old/new TI part-ID mapping.
    No authority is inferred from string resemblance or source SVG artwork.
    """
    from examples.tl494_cycle9_circuit_integration import (
        bind_positioned_photo_circuit_from_catalog,
    )

    if not isinstance(assembly, NativeV5Assembly) or not isinstance(
        source_circuit, Circuit,
    ):
        raise TypeError("TL494_C11_REAL_SOURCE_ASSEMBLY_AND_CIRCUIT_REQUIRED")
    assembly.verify()
    if (
        source_circuit.components is not assembly.circuit.components
        or len(source_circuit.nets) != 15
    ):
        raise ValueError("TL494_C11_SOURCE_COMPONENT_INVENTORY_NOT_IDENTICAL")
    signed = bind_positioned_photo_circuit_from_catalog(
        source_circuit, assembly.owner_ic_record, assembly.parts,
        aliases=assembly.owner_aliases,
    )
    result = VerifiedCompactTiBinding(
        source_circuit=source_circuit,
        signed=signed,
        part=signed.part,
    )
    result.verify()
    return result
