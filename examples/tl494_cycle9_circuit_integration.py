"""MAIN3 #97/#107: real 23-component photo Circuit + checked TI DA1 adapter.

Source locked to e695c415. Real 15 Nets/62 contact memberships stay intact,
DA1 part inventory becomes the genuine 16-pin manufacturer model (FB is INPUT).
This is a typed topology fixture, NOT an approved routed photograph or ESKD
printed sheet. The source document does not provide verified component poses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.ic_circuit_adapter import (
    IcCircuitBinding,
    bind_ic_circuit,
    bind_ic_circuit_from_catalog,
)
from gost_schematic.electrical.tl494cn import (
    TI_DEVICE_ID,
    tl494cn_record,
    verify_tl494cn_ti_pinout,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.quantities import Quantity, QuantityKind

FROZEN_SOURCE_COMMIT = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FROZEN_SOURCE_BLOB = "c4cfd515782bf856a7a44fbe2c2ceacd303208d6"
FROZEN_FIXTURE_GIT_BLOB_SHA1 = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
FROZEN_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/tl494_photo_23_frozen_cycle9.json"
)

_EXTERNAL_PINS_BY_PART = {
    "capacitor.polarized": ("1", "2"),
    "capacitor.fixed": ("1", "2"),
    "resistor.fixed": ("1", "2"),
    "resistor.variable": ("1", "2", "3"),
    "transistor.mosfet_n_enh": ("1", "2", "3"),
    "diode.schottky": ("1", "2"),
    "inductor.ferromagnetic": ("1", "2"),
    "fuse.general": ("1", "2"),
    "reference.connector.x1": ("1", "2"),
    "reference.connector.x2": ("1", "2"),
}
_NOMINAL_KIND_BY_PART = {
    "capacitor.polarized": QuantityKind.CAPACITANCE,
    "capacitor.fixed": QuantityKind.CAPACITANCE,
    "resistor.fixed": QuantityKind.RESISTANCE,
    "resistor.variable": QuantityKind.RESISTANCE,
    "inductor.ferromagnetic": QuantityKind.INDUCTANCE,
}


def load_frozen_source(path: Path = FROZEN_FIXTURE) -> dict:
    data = path.read_bytes()
    # Git's immutable blob ID, pinned OUTSIDE the fixture itself. Reject
    # changed same-count/same-Net-count source, not merely missing items.
    header = b"blob " + str(len(data)).encode("ascii") + bytes((0,))
    if hashlib.sha1(header + data).hexdigest() != FROZEN_FIXTURE_GIT_BLOB_SHA1:
        raise ValueError("TL494_FROZEN_PHOTO_FIXTURE_BYTES_CHANGED")
    value = json.loads(data.decode("utf-8"))
    if (
        value.get("schema_version") != 1
        or value.get("source_commit") != FROZEN_SOURCE_COMMIT
        or value.get("source_blob_sha") != FROZEN_SOURCE_BLOB
        or value.get("status")
        != "FROZEN_SOURCE_PHOTO_TOPOLOGY_DRAFT_NOT_ENGINEERING_APPROVED"
        or not isinstance(value.get("components"), list)
        or not isinstance(value.get("nets"), dict)
        or len(value["components"]) != 23
        or len(value["nets"]) != 15
        or sum(len(m) for m in value["nets"].values()) != 62
    ):
        raise ValueError("TL494_FROZEN_PHOTO_SOURCE_NOT_23_15_62")
    if {x["ref"] for x in value["components"]} != {
        "DA1", "VT1", "VD1", "L1", "L2", "FU1", "X1", "X2",
        *(f"C{n}" for n in range(1, 8)),
        *(f"R{n}" for n in range(1, 9)),
    }:
        raise ValueError("TL494_FROZEN_PHOTO_BOM_MISMATCH")
    return value


def assert_frozen_photo_topology(
    binding: IcCircuitBinding, source: dict,
) -> None:
    """Reject a missing, rewired, renamed or forged photo Net, not just ERC."""
    if len(binding.circuit.components) != 23 or len(binding.circuit.nets) != 15:
        raise ValueError("TL494_FROZEN_PHOTO_COMPONENT_OR_NET_COUNT_DRIFT")
    source_parts = {
        row["ref"]: row["part_id"] for row in source["components"]
    }
    actual_parts = {
        item.reference: item.part_id for item in binding.circuit.components
    }
    expected_parts = dict(source_parts)
    if source_parts["DA1"] != "reference.tl494cn":
        raise ValueError("TL494_FROZEN_PHOTO_ORIGINAL_PART_NOT_FOUND")
    expected_parts["DA1"] = TI_DEVICE_ID
    if actual_parts != expected_parts:
        raise ValueError("TL494_FROZEN_PHOTO_PART_INVENTORY_DRIFT")
    expected_nets = {
        name: tuple(PinRef(*item.rsplit(".", 1)) for item in members)
        for name, members in source["nets"].items()
    }
    actual_nets = {net.name: net.members for net in binding.circuit.nets}
    if actual_nets != expected_nets:
        raise ValueError("TL494_FROZEN_PHOTO_NET_MEMBERSHIP_DRIFT")
    physical = {
        p for net in binding.circuit.nets for p in net.members
    }
    if len(physical) != 62 or {
        p for p in physical if p.reference == "DA1"
    } != {PinRef("DA1", str(i)) for i in range(1, 17)}:
        raise ValueError("TL494_FROZEN_PHOTO_ALL_16_PHYSICAL_REQUIRED")
    if binding.contact(PinRef("DA1", "3")).electrical_type.value != "input":
        raise ValueError("TL494_FROZEN_PHOTO_FB_MUST_BE_INPUT")
    if binding.contact(PinRef("DA1", "13")).electrical_type.value != "input":
        raise ValueError("TL494_FROZEN_PHOTO_OUTPUT_CTRL_MUST_BE_INPUT")


def build_frozen_photo_23() -> tuple[IcCircuitBinding, dict]:
    """Reusable QA/#115 constructor: actual 23 frozen source instances/Nets."""
    record, aliases = tl494cn_record()
    verify_tl494cn_ti_pinout(record.device)
    source = load_frozen_source()
    components = []
    external = {}
    for row in source["components"]:
        reference, original_part = row["ref"], row["part_id"]
        if reference == "DA1":
            if original_part != "reference.tl494cn":
                raise ValueError("TL494_FROZEN_PHOTO_DA1_SOURCE_NOT_ORIGINAL")
            if row["nominal_si"] is not None:
                raise ValueError("TL494_FROZEN_PHOTO_IC_HAS_NOMINAL")
            components.append(ComponentInstance(
                reference, TI_DEVICE_ID, record.placements[0].origin,
            ))
        else:
            if original_part not in _EXTERNAL_PINS_BY_PART:
                raise ValueError("TL494_FROZEN_PHOTO_UNKNOWN_EXTERNAL_PART")
            external[reference] = _EXTERNAL_PINS_BY_PART[original_part]
            amount = row["nominal_si"]
            if (amount is None) != (
                original_part not in _NOMINAL_KIND_BY_PART
            ):
                raise ValueError("TL494_FROZEN_PHOTO_UNKNOWN_NOMINAL_KIND")
            nominal = (
                Quantity(
                    _NOMINAL_KIND_BY_PART[original_part], Decimal(amount),
                ) if amount is not None else None
            )
            # Source netlist has no source photo x/y for passive placements;
            # default Point(0,0) is a NON-PRINTABLE placeholder.
            components.append(ComponentInstance(
                reference, original_part, Point(0, 0), nominal=nominal,
            ))
    nets = tuple(Net(name, tuple(
        PinRef(*item.rsplit(".", 1)) for item in members
    )) for name, members in source["nets"].items())
    circuit = Circuit(tuple(components), nets)
    binding = bind_ic_circuit(
        record, circuit, aliases=aliases, external_pin_numbers=external,
    )
    assert_frozen_photo_topology(binding, source)
    return binding, source


def bind_positioned_photo_circuit_from_catalog(
    original_circuit: Circuit,
    record,
    parts_by_id: Mapping[str, PartDefinition],
    *,
    aliases=None,
) -> IcCircuitBinding:
    """Safe #115 A3 upgrade: old DA1 part_id -> true TI ID, unchanged Nets.

    The original photo source is verified by *pinned fixture Git blob SHA1*
    before any conversion. The whole existing positioned Circuit is checked,
    not just its 16 IC pins: all 23 reference names, 15 source Net names,
    exact 62 (ref, number) tuples, all other original part IDs and actual SI
    nominal values. Only a NEW in-memory Circuit is returned; the source is
    never edited, even if its historical DA1 part type is wrong.
    """
    from gost_schematic.electrical.ic_serde import IcLibraryRecord

    if not isinstance(original_circuit, Circuit) or not isinstance(
        record, IcLibraryRecord,
    ):
        raise TypeError("TL494_PHOTO_REBIND_TYPED_CIRCUIT_AND_RECORD_REQUIRED")
    if record.device.identifier != TI_DEVICE_ID:
        raise ValueError("TL494_PHOTO_REBIND_TI_SOURCE_DEVICE_REQUIRED")
    verify_tl494cn_ti_pinout(record.device)
    source = load_frozen_source()
    if len(record.placements) != 1 or len(record.specs) != 1:
        raise ValueError("TL494_PHOTO_REBIND_EXACT_ONE_DA1_UNIT_REQUIRED")
    placement = record.placements[0]
    if placement.component_ref != "DA1":
        raise ValueError("TL494_PHOTO_REBIND_WRONG_PHYSICAL_REFERENCE")
    if (
        len(original_circuit.components) != 23
        or len(original_circuit.nets) != 15
        or sum(len(net.members) for net in original_circuit.nets) != 62
    ):
        raise ValueError("TL494_PHOTO_REBIND_23_15_62_SOURCE_MISMATCH")
    actual = {comp.reference: comp for comp in original_circuit.components}
    known = {row["ref"]: row for row in source["components"]}
    if len(actual) != 23 or set(actual) != set(known):
        raise ValueError("TL494_PHOTO_REBIND_COMPONENT_IDENTITY_MISMATCH")
    for reference, component in actual.items():
        original = known[reference]
        if (
            reference != "DA1"
            and component.part_id != original["part_id"]
        ):
            raise ValueError("TL494_PHOTO_REBIND_NON_IC_PART_CHANGED")
        if reference == "DA1" and (
            original["part_id"] != "reference.tl494cn"
            or component.part_id not in ("reference.tl494cn", TI_DEVICE_ID)
            or component.origin != placement.origin
            or component.transform != placement.transform
        ):
            raise ValueError("TL494_PHOTO_REBIND_DA1_PART_OR_POSE_MISMATCH")
        if original["nominal_si"] is None:
            if component.nominal is not None:
                raise ValueError("TL494_PHOTO_REBIND_UNSOURCED_NOMINAL")
        elif (
            component.nominal is None
            or component.nominal.si_value != Decimal(original["nominal_si"])
        ):
            raise ValueError("TL494_PHOTO_REBIND_BOM_NOMINAL_DRIFT")
    mapped = {net.name: net.members for net in original_circuit.nets}
    expected = {
        name: tuple(PinRef(*item.rsplit(".", 1)) for item in members)
        for name, members in source["nets"].items()
    }
    if len(mapped) != 15 or mapped != expected:
        raise ValueError("TL494_PHOTO_REBIND_NET_IDENTITY_OR_MEMBERSHIP_CHANGED")
    upgraded = Circuit(tuple(
        replace(comp, part_id=TI_DEVICE_ID)
        if comp.reference == "DA1" else comp
        for comp in original_circuit.components
    ), original_circuit.nets)
    if upgraded.nets is not original_circuit.nets:
        raise ValueError("TL494_PHOTO_REBIND_NET_TUPLE_MUTATED")
    result = bind_ic_circuit_from_catalog(
        record, upgraded, parts_by_id, aliases=aliases,
    )
    assert_frozen_photo_topology(result, source)
    if result.circuit.nets != original_circuit.nets:
        raise ValueError("TL494_PHOTO_REBIND_UNAUTHORIZED_NET_REWRITE")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    binding, source = build_frozen_photo_23()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(binding.to_json(), encoding="utf-8")
    again = IcCircuitBinding.from_json(args.output.read_text(encoding="utf-8"))
    assert again == binding
    assert_frozen_photo_topology(again, source)
    print(json.dumps({
        "status": "DRAFT_PHYSICAL_23_PART_CIRCUIT_NOT_ROUTED",
        "source": FROZEN_SOURCE_COMMIT,
        "components": len(binding.circuit.components),
        "nets": len(binding.circuit.nets),
        "net_members": sum(len(n.members) for n in binding.circuit.nets),
        "tl494_contacts": len(binding.contacts),
        "feedback_role": binding.contact(PinRef("DA1", "3")).electrical_type.value,
        "ctrl_role": binding.contact(PinRef("DA1", "13")).electrical_type.value,
        "return_json_exact": True,
        "paint_ink_owned_by": "PR #93",
        "routed_sheet": False,
        "geometry_source": "TL494 E3 editor portrait, not photo x/y",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
