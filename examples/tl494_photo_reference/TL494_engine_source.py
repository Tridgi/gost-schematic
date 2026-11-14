"""Rebuild an experimental native Circuit for the photo-traced TL494CN design.

Run from repository root:
    python -m examples.tl494_photo_reference.TL494_engine_source

This script uses actual GOST Schematic Engine Circuit, ComponentInstance,
Net, PinRef, PartDefinition and SymbolDefinition types. The photo-traced
SVG is intentionally an AUXILIARY rendering, not native approved sheet SVG.
No ProjectService import or .gseproj write occurs for the DRAFT IC model.
"""
from __future__ import annotations

import json
from pathlib import Path

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.symbol_checks import validate_symbol

HERE = Path(__file__).resolve().parent

IC = {
    "1": "1IN+", "2": "1IN-", "3": "FEEDBACK", "4": "DTC",
    "5": "CT", "6": "RT", "7": "GND", "8": "C1",
    "9": "E1", "10": "E2", "11": "C2", "12": "VCC",
    "13": "OUTPUT CTRL", "14": "REF", "15": "2IN-", "16": "2IN+",
}
LEFT = ("2", "4", "3", "5", "6", "7", "1", "16")
RIGHT = ("12", "15", "14", "13", "8", "11", "9", "10")
PART_IDS = {
    **{f"C{i}": "capacitor.electrolytic" for i in (1, 2, 3, 5, 6)},
    "C4": "capacitor.fixed", "C7": "capacitor.fixed",
    **{f"R{i}": "resistor.fixed" for i in (1, 2, 3, 4, 6, 7, 8)},
    "R5": "resistor.variable",
    "VT1": "transistor.mosfet_n_enh", "VD1": "diode.schottky",
    "L1": "inductor.air_core", "L2": "inductor.air_core",
    "FU1": "fuse.general", "DA1": "tl494.photo.ic",
    "X1": "tl494.photo.connector", "X2": "tl494.photo.connector",
}
PHOTO_XY = {
    "X1": (22, 97), "X2": (620, 97),
    "L1": (237, 97), "L2": (500, 97), "FU1": (567, 97),
    "C1": (394, 82), "C2": (394, 113), "C3": (113, 148),
    "C4": (78, 190), "C5": (524, 204), "C6": (550, 204),
    "C7": (157, 240),
    "R1": (135, 145), "R2": (179, 145), "R3": (110, 190),
    "R4": (62, 207), "R5": (62, 237), "R6": (135, 242),
    "R7": (181, 242), "R8": (286, 245),
    "DA1": (214, 162), "VT1": (344, 230), "VD1": (447, 180),
}

def draft_ic() -> tuple[PartDefinition, SymbolDefinition]:
    """Typed 16-contact schematic rectangle, not a validated TL494 layout."""
    parts = tuple(
        PhysicalPin(n, IC[n], ElectricalType.UNSPECIFIED)
        for n in sorted(IC, key=int)
    )
    pins = []
    lines = []
    for side, numbers in ((Side.LEFT, LEFT), (Side.RIGHT, RIGHT)):
        for index, number in enumerate(numbers):
            y = 7_000 + index * 10_000
            x1, x2 = (-10_000, 0) if side is Side.LEFT else (53_000, 63_000)
            lines.append(Line(Point(x1, y), Point(x2, y)))
            pins.append(GraphicPin(number, Point(x1 if side is Side.LEFT else x2, y), side, IC[number]))
    sym = SymbolDefinition(
        identifier="tl494.photo.ic", revision=1,
        graphics=(Rectangle(Box(0, 0, 53_000, 84_000)), *lines),
        pins=tuple(pins), body_keepout=Box(0, 0, 53_000, 84_000),
        line_width_um=300, status=SymbolStatus.DRAFT,
    )
    part = PartDefinition(
        identifier=sym.identifier, reference_prefix="DA",
        symbol_id=sym.identifier, pins=parts,
    )
    return part, sym

def draft_connector() -> tuple[PartDefinition, SymbolDefinition]:
    pins = (
        PhysicalPin("1", "CONTACT_1", ElectricalType.PASSIVE),
        PhysicalPin("2", "CONTACT_2", ElectricalType.PASSIVE),
    )
    sym = SymbolDefinition(
        identifier="tl494.photo.connector", revision=1,
        graphics=(
            Rectangle(Box(-2_000, -3_000, 2_000, 3_000)),
            Line(Point(-8_000, -1_000), Point(-2_000, -1_000)),
            Line(Point(-8_000, 1_000), Point(-2_000, 1_000)),
        ),
        pins=(
            GraphicPin("1", Point(-8_000, -1_000), Side.LEFT),
            GraphicPin("2", Point(-8_000, 1_000), Side.LEFT),
        ),
        body_keepout=Box(-2_000, -3_000, 2_000, 3_000),
        line_width_um=300, status=SymbolStatus.DRAFT,
    )
    part = PartDefinition(
        identifier=sym.identifier, reference_prefix="X",
        symbol_id=sym.identifier, pins=pins,
    )
    return part, sym

def to_physical(reference: str, alias: str) -> str:
    """Map photo labels +/− and A/K to real catalog physical pin numbers."""
    if reference.startswith("C") and reference[1:] in {"1", "2", "3", "5", "6"}:
        return {"+" : "1", "-" : "2"}.get(alias, alias)
    if reference == "VD1":
        return {"A": "1", "K": "2"}.get(alias, alias)
    return alias

def make_circuit() -> tuple[Circuit, dict, dict]:
    model = json.loads((HERE / "TL494_netlist.json").read_text(encoding="utf-8"))
    resolver = CatalogResolver()
    parts = dict(resolver.parts)
    symbols = dict(resolver.symbols)
    for part, symbol in (draft_ic(), draft_connector()):
        assert not any(d.severity.value == "error" for d in validate_symbol(symbol))
        parts[part.identifier] = part
        symbols[symbol.identifier] = symbol
    components = tuple(
        ComponentInstance(name, part_id, Point(*(v * 1000 for v in PHOTO_XY[name])))
        for name, part_id in PART_IDS.items()
    )
    nets = tuple(
        Net(row["name"], tuple(
            PinRef(ref["reference"], to_physical(ref["reference"], ref["number"]))
            for ref in row["members"]
        ))
        for row in model["nets"]
    )
    circuit = Circuit(components, nets)
    for component in circuit.components:
        part = parts[component.part_id]
        symbol = symbols[part.symbol_id]
        if {p.number for p in part.pins} != {p.number for p in symbol.pins}:
            raise AssertionError(f"part/symbol mismatch: {component.reference}")
    for net in circuit.nets:
        for pin in net.members:
            comp = next(c for c in circuit.components if c.reference == pin.reference)
            valid = {p.number for p in parts[comp.part_id].pins}
            if pin.number not in valid:
                raise AssertionError(f"invalid PinRef {pin.reference}.{pin.number}")
    return circuit, parts, symbols

def main() -> None:
    circuit, parts, symbols = make_circuit()
    diagnostics = validate_circuit(circuit, parts, symbols)
    print(f"Native Circuit: {len(circuit.components)} components / "
          f"{len(circuit.nets)} Nets / {sum(len(n.members) for n in circuit.nets)} PinRefs")
    print(f"Native ERC diagnostics: {len(diagnostics)}")
    for d in diagnostics:
        print(f"{d.severity.value}: {d.code}: {d.message}")
    print("SVG sources are auxiliary photo drawings, not official ESKD-approved engine exports.")
    # The absence of manufacturer-approved TL494 and connector catalog entries is
    # deliberately NOT hidden by this script or by a forged .gseproj.

if __name__ == "__main__":
    main()
