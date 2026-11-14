"""Immutable photo/BOM and model/UGO contract for TL494 v4, #107/#110.

Never promote source-photo reading or an ERC success to approved electrical design.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from examples.tl494_full_native_model import SPEC, TRACED_NETS
from gost_schematic.model.pins import ElectricalType


SOURCE_PHOTOS = {
    "circuit": {
        "width_px": 640, "height_px": 290,
        "sha256": "e06e845fa3d269bf71880a8cb1ad2e59c8aa844a0486351228e9da936ac4100c",
    },
    "bom": {
        "width_px": 640, "height_px": 702,
        "sha256": "d54469d016eb80fe2a7b3e5aa2526da2494c20d3c18b7a1bcc8af624157fecb0",
    },
}
PIN_ALIASES = {
    "1": "1IN+", "2": "1IN-", "3": "FB", "4": "DTC",
    "5": "CT", "6": "RT", "7": "GND", "8": "C1",
    "9": "E1", "10": "E2", "11": "C2", "12": "VCC",
    "13": "OC", "14": "REF", "15": "2IN-", "16": "2IN+",
}
PIN_DESCRIPTIONS = {
    "1": "1IN+", "2": "1IN-", "3": "FEEDBACK", "4": "DTC",
    "5": "CT", "6": "RT", "7": "GND", "8": "C1",
    "9": "E1", "10": "E2", "11": "C2", "12": "VCC",
    "13": "OUTPUT CTRL", "14": "REF", "15": "2IN-", "16": "2IN+",
}
PIN_TYPES = {
    "1": ElectricalType.INPUT, "2": ElectricalType.INPUT,
    "3": ElectricalType.INPUT, "4": ElectricalType.INPUT,
    "5": ElectricalType.UNSPECIFIED, "6": ElectricalType.UNSPECIFIED,
    "7": ElectricalType.POWER_INPUT, "8": ElectricalType.OPEN_COLLECTOR,
    "9": ElectricalType.OUTPUT, "10": ElectricalType.OUTPUT,
    "11": ElectricalType.OPEN_COLLECTOR, "12": ElectricalType.POWER_INPUT,
    "13": ElectricalType.INPUT, "14": ElectricalType.POWER_OUTPUT,
    "15": ElectricalType.INPUT, "16": ElectricalType.INPUT,
}
SOURCE_SHEET_PARTS = {
    "C1":("capacitor.polarized","220 мкФ","100 В"),
    "C2":("capacitor.polarized","220 мкФ","63 В"),
    "C3":("capacitor.polarized","47 мкФ",""),
    "C4":("capacitor.fixed","10 нФ","103"),
    "C5":("capacitor.polarized","1000 мкФ","25 В"),
    "C6":("capacitor.polarized","1000 мкФ","25 В"),
    "C7":("capacitor.fixed","1 нФ","102"),
    "R1":("resistor.fixed","1 Ом","МЛТ"),
    "R2":("resistor.fixed","620 Ом","МЛТ"),
    "R3":("resistor.fixed","10 кОм","МЛТ"),
    "R4":("resistor.fixed","6,8 кОм","МЛТ"),
    "R5":("resistor.variable","1 кОм","МЛТ, подвижный контакт"),
    "R6":("resistor.fixed","1 Ом","МЛТ"),
    "R7":("resistor.fixed","680 кОм","МЛТ"),
    "R8":("resistor.fixed","10 Ом","МЛТ"),
    "VT1":("transistor.mosfet_n_enh","IRFZ44N","N-channel MOSFET G/D/S"),
    "VD1":("diode.schottky","1N5822","A/K"),
    "DA1":("reference.tl494cn","TL494CN","16 physical pins"),
    "L1":("inductor.ferromagnetic","100 мкГн","магнитопровод"),
    "L2":("inductor.ferromagnetic","100 мкГн","магнитопровод"),
    "FU1":("fuse.general","2 A",""),
    "X1":("reference.connector.x1","вход","2 контакта"),
    "X2":("reference.connector.x2","выход −12 В","2 контакта"),
}


class FrozenSourceError(AssertionError):
    """Source photo or source-specific Net/Part inventory changed unnoticed."""


def frozen_inventory() -> dict:
    """Independent, finite inventory; no file output and no Net synthesis."""
    if len(SOURCE_SHEET_PARTS) != 23 or len(TRACED_NETS) != 15:
        raise FrozenSourceError("P0: source reference/Net cardinality changed")
    if set(SOURCE_SHEET_PARTS) != set(SPEC):
        raise FrozenSourceError("P0: BOM reference mismatch")
    for ref,(part_id,_,_) in SOURCE_SHEET_PARTS.items():
        if SPEC[ref][0] != part_id:
            raise FrozenSourceError(f"P1: incorrect selected UGO at {ref}")
    seen = {}
    for net, pins in TRACED_NETS.items():
        for ref, number in pins:
            if ref not in SOURCE_SHEET_PARTS:
                raise FrozenSourceError(f"P0: unknown physical part {ref}")
            key=(ref,number)
            if key in seen:
                raise FrozenSourceError(
                    f"P0: physical contact {ref}.{number} reused: {seen[key]}, {net}"
                )
            seen[key]=net
    if {number for ref,number in seen if ref=="DA1"} != set(PIN_ALIASES):
        raise FrozenSourceError("P2: DA1 physical pin missing from source Net")
    if set(PIN_ALIASES)!=set(PIN_DESCRIPTIONS)!=set(PIN_TYPES):
        raise FrozenSourceError("P2: manufacturer / alias inventory mismatch")
    if len(set(PIN_ALIASES.values()))!=16 or any(
        len(x)>6 or not x for x in PIN_ALIASES.values()
    ):
        raise FrozenSourceError("P2: duplicate, empty or overlong display alias")
    if PIN_TYPES["3"] is not ElectricalType.INPUT:
        raise FrozenSourceError("P2: TI FEEDBACK must be input")
    if any("earth" in name.lower() or "pe"==name.lower()
           for name in TRACED_NETS):
        raise FrozenSourceError("P5: no physical protective earth in source circuit")
    return {
        "baseline_sha":"e695c415fdced164b0e0c39c5249d030795a0aa6",
        "component_count":len(SOURCE_SHEET_PARTS),
        "net_count":len(TRACED_NETS),
        "physical_pin_memberships":len(seen),
        "DA1_pin_count":16,
        "pin_display_aliases":PIN_ALIASES,
        "pin_manufacturer_functions":PIN_DESCRIPTIONS,
        "pin_electrical_types":{k:v.value for k,v in PIN_TYPES.items()},
        "source_components":{k:dict(
            symbol_id=v[0],value=v[1],description=v[2]
        ) for k,v in SOURCE_SHEET_PARTS.items()},
        "source_nets":{
            name:[f"{r}.{n}" for r,n in pins] for name,pins in TRACED_NETS.items()
        },
        "source_photo_checksums":SOURCE_PHOTOS,
        "common_role":"0V circuit reference; never infer PE/chassis",
        "symbol_status":"DRAFT; normative signoff pending",
        "remarks":[
            "Source circuit frequency remark ~100 kHz conflicts with RT=680 kΩ and CT=1 nF",
            "VD1 electrical A/K direction is traced from photo, not proven functional",
            "Pin labels FB and OC are EDITORIAL display aliases, not renamed PhysicalPin",
        ],
    }


def verify_local_source_photo(path: Path, kind: str):
    """Only meaningful for real bytes of one of the two exact user uploads."""
    expected=SOURCE_PHOTOS[kind]
    payload=path.read_bytes()
    digest=sha256(payload).hexdigest()
    if digest!=expected["sha256"]:
        raise FrozenSourceError(f"P0: photo {kind} hash mismatch: {digest}")
    return digest


if __name__=="__main__":
    import json
    print(json.dumps(frozen_inventory(),ensure_ascii=False,indent=2))
