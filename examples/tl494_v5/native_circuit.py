"""TL494 V5: real typed source Circuit, IC owner and catalog owner contracts.

Read-only, NOT printable. No fabricated PE, Net, wire, graphics or ground.
Owner modules #97 and #113 must be pinned into an isolated test environment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from examples.tl494_named_photo_sheet import full_components, photo_nets
from examples.tl494_v4.engine_adapter import build_power_v4
from examples.tl494_v4.model_contract import SOURCE_SHEET_PARTS, frozen_inventory
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin

SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
IC_SHA = "6161e9102cbc0c9e0491fb27ed7a496dc0b274bc"
CATALOG_SHA = "edc71a48035723d48a203ae2ea12588701f68ba8"
PAINT_SHA = "e3ea841dbe087952577121d5690fe41e9a9a5c83"
NET_RENAMES = {
    "a_INPUT_PLUS": "INPUT_POS",
    "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
    "TRANSFER": "ENERGY_TRANSFER",
}


def _owner_part(device) -> PartDefinition:
    """Convert actual TI physical metadata without guessing pin labels."""
    types = {
        "input": ElectricalType.INPUT,
        "output": ElectricalType.OUTPUT,
        "bidirectional": ElectricalType.BIDIRECTIONAL,
        "power_input": ElectricalType.POWER_INPUT,
        "power_output": ElectricalType.POWER_OUTPUT,
        "open_collector": ElectricalType.OPEN_COLLECTOR,
        "passive": ElectricalType.PASSIVE,
        "nc": ElectricalType.UNSPECIFIED,
    }
    if len(device.pins) != 16:
        raise ValueError("V5_EXACT_16_MANUFACTURER_PINS_REQUIRED")
    return PartDefinition(
        identifier="reference.tl494cn",
        reference_prefix="DA",
        symbol_id="reference.tl494cn",
        pins=tuple(
            PhysicalPin(pin.number, pin.name, types[pin.electrical_type.value])
            for pin in device.pins
        ),
    )


@dataclass(frozen=True, slots=True)
class NativeV5Assembly:
    circuit: Circuit
    parts: dict
    symbols: dict
    owner_ic_record: object
    owner_aliases: object
    source_UGO_bindings: tuple
    status: str = "DRAFT_MODEL_ONLY_NO_PRINT"

    def verify(self) -> None:
        inventory = frozen_inventory()
        if len(self.circuit.components) != 23 or len(self.circuit.nets) != 15:
            raise AssertionError("V5_BOM_OR_NET_COUNT_DRIFT")
        if {part.reference for part in self.circuit.components} != set(
            SOURCE_SHEET_PARTS
        ):
            raise AssertionError("V5_REF_DESIGNATOR_DRIFT")
        actual_nets = {
            net.name: [
                f"{pin.reference}.{pin.number}" for pin in net.members
            ] for net in self.circuit.nets
        }
        baseline_nets = {
            NET_RENAMES.get(name, name): members
            for name, members in inventory["source_nets"].items()
        }
        if actual_nets != baseline_nets:
            raise AssertionError("V5_PINREF_NET_IDENTITY_DRIFT")
        physical = self.parts["reference.tl494cn"].pins
        if {pin.number for pin in physical} != {
            str(i) for i in range(1, 17)
        } or len(physical) != 16:
            raise AssertionError("V5_TI_16_PHYSICAL_PINS_LOST")
        for pin_id in ("3", "13"):
            target = next(p for p in physical if p.number == pin_id)
            if target.electrical_type is not ElectricalType.INPUT:
                raise AssertionError(f"V5_TI_PIN_{pin_id}_MUST_BE_INPUT")
        if len(self.source_UGO_bindings) != 13 or {
            p.reference for p in self.source_UGO_bindings
        } != {"VD1", "VT1", "C1", "C2", "C3", "C4", "C5",
              "C6", "C7", "L1", "L2", "FU1", "R5"}:
            raise AssertionError("V5_YGO13_NOT_REAL_SOURCE_PROFILE")
        if any(
            binding.symbol.status.value != "draft"
            for binding in self.source_UGO_bindings
        ):
            raise AssertionError("V5_CANNOT_AUTO_APPROVE_UGO")
        if "PE" in actual_nets or "CHASSIS" in actual_nets:
            raise AssertionError("V5_PHANTOM_PROTECTIVE_GROUND")


    def manifest(self) -> dict:
        self.verify()
        return {
            "status": self.status,
            "source_sha": SOURCE_SHA,
            "owner_shas": {
                "ELEKTRIK_IC": IC_SHA,
                "YGO2": CATALOG_SHA,
                "PAINT": PAINT_SHA,
            },
            "components": len(self.circuit.components),
            "nets": {
                net.name: [
                    f"{p.reference}.{p.number}" for p in net.members
                ] for net in self.circuit.nets
            },
            "physical_DA1_pins": 16,
            "BOM": {
                ref: {
                    "part_id": data[0],
                    "nominal": data[1],
                    "source_description": data[2],
                } for ref, data in SOURCE_SHEET_PARTS.items()
            },
            "source_UGO": {
                binding.reference: {
                    "part_id": binding.part.identifier,
                    "symbol_id": binding.symbol.identifier,
                    "gost_source_figure": binding.figure_reference,
                    "pins": [
                        f"{p.reference}.{p.number}"
                        for p in binding.pin_refs
                    ],
                    "normative": "DRAFT_NOT_APPROVED",
                } for binding in self.source_UGO_bindings
            },
            "old_known_bad_DRC": {
                "errors": 9, "warnings": 32,
                "wires": 91, "junctions": 37,
            },
            "print_gate": "BLOCKED until full router and QA",
        }


def assemble_native_v5() -> NativeV5Assembly:
    """Use ACTUAL owner source; unavailable contracts fail, never stubbed."""
    from gost_schematic.catalog.source_profiles import bind_tl494_source
    from gost_schematic.electrical.tl494cn import (
        IcFunctionReading,
        TI_SHORT_LABELS,
        tl494cn_record,
    )

    frozen_inventory()
    source, parts, symbols, _old_positions = build_power_v4()
    record, aliases = tl494cn_record(
        "DA1", reading=IcFunctionReading.BOTTOM_TO_TOP
    )
    owner_part = _owner_part(record.device)
    parts = dict(parts)
    parts[owner_part.identifier] = owner_part
    da1 = ComponentInstance(
        "DA1", owner_part.identifier, record.placements[0].origin
    )
    components = full_components(source.components, da1)
    glyphs = bind_tl494_source(components, parts, symbols)
    if aliases.component_ref != "DA1" or {
        label.physical_number: label.schematic_short_label
        for label in aliases.labels
    } != TI_SHORT_LABELS:
        raise AssertionError("V5_OWNER_IC_ALIAS_MISMATCH")
    circuit = Circuit(tuple(components), photo_nets())
    result = NativeV5Assembly(
        circuit, dict(parts), dict(symbols), record, aliases,
        tuple(glyphs),
    )
    result.verify()
    return result


def export_source_manifest(path: Path) -> dict:
    """Export QA model/BOM/Netlist only, not a misleading AFTER drawing."""
    result = assemble_native_v5().manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
