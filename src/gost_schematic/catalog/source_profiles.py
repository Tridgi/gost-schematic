"""Fail-closed source-photo UGO selection and physical-glyph acceptance.

A source component's configured SymbolDefinition is a deliberate engineering
decision, not a suggestion to auto-substitute a visually similar UGO.
The 13-component TL494 subset is source-SHA pinned and remains DRAFT.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Line, Point, StyledLine
from gost_schematic.model.circuit import ComponentInstance, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

CATALOG = Path(str(files("gost_schematic").joinpath("catalog")))
PINNED_REFERENCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
REQUIRED_REFERENCES = (
    "VD1", "VT1", "C1", "C2", "C3", "C4", "C5", "C6", "C7",
    "L1", "L2", "FU1", "R5",
)


class SymbolProfileMismatch(ValueError):
    code = "SYMBOL_PROFILE_MISMATCH"


@dataclass(frozen=True, slots=True)
class SourceGlyphBinding:
    reference: str
    instance: ComponentInstance
    symbol: SymbolDefinition
    part: PartDefinition
    pin_refs: tuple[PinRef, ...]
    pin_positions: tuple[Point, ...]
    figure_reference: str


def read_source_manifest() -> dict:
    path = CATALOG / "source_profiles" / "tl494_source_20261114.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    if (content.get("schema_version") != 1
        or content.get("reference_sha") != PINNED_REFERENCE_SHA
        or content.get("status") != "DRAFT"):
        raise SymbolProfileMismatch("Unpinned TL494 reference source manifest")
    records = content["profiles"]
    if (len(records) != len(REQUIRED_REFERENCES)
        or tuple(item["reference"] for item in records) != REQUIRED_REFERENCES):
        raise SymbolProfileMismatch("Source 13-symbol order, ID or inventory changed")
    if len({row["reference"] for row in records}) != len(records):
        raise SymbolProfileMismatch("Duplicate reference")
    return content


def load_catalog_pair(symbol_id: str) -> tuple[SymbolDefinition, PartDefinition]:
    """Read *actual packaged* symbol/part, never a reconstructed SVG icon."""
    if symbol_id == "inductor.ferromagnetic":
        built = load_inductor(CATALOG / "inductors" / (symbol_id + ".json"))
        return built.symbol, built.part
    family, _, item = symbol_id.partition(".")
    folder = {
        "capacitor": "capacitors",
        "diode": "diodes",
        "fuse": "fuses",
        "resistor": "resistors",
        "transistor": "transistors",
    }.get(family)
    if not folder or not item:
        raise SymbolProfileMismatch(f"Unknown physical catalog family: {symbol_id}")
    filename = item.replace(".with_case", "_with_case") + ".json"
    return (
        load_symbol(CATALOG / "symbols" / folder / filename),
        load_part(CATALOG / "parts" / folder / filename),
    )


def _line(symbol: SymbolDefinition, index: int) -> Line:
    result = symbol.graphics[index]
    if not isinstance(result, Line):
        raise SymbolProfileMismatch(f"{symbol.identifier}: missing physical line #{index}")
    return result


def check_ink_contract(symbol: SymbolDefinition, part: PartDefinition) -> None:
    """Strong structural checks, not an independent GOST 1:1 sign-off."""
    if symbol.status is not SymbolStatus.DRAFT:
        raise SymbolProfileMismatch("Unreviewed source symbol cannot be APPROVED")
    if part.symbol_id != symbol.identifier or len(part.pins) != len(symbol.pins):
        raise SymbolProfileMismatch("Graphic and physical contact inventory differ")
    if {p.number for p in part.pins} != {p.number for p in symbol.pins}:
        raise SymbolProfileMismatch("Graphic and physical contact identifiers differ")
    result = inspect_conductor_topology(symbol)
    if not result.valid:
        raise SymbolProfileMismatch(f"Invalid true conducting strokes: {result.diagnostics}")
    id_ = symbol.identifier
    if id_ == "diode.schottky":
        # Source ГОСТ 2.730-73 table 4/9 and table 5/9: opposite hooks
        # terminate on different sides; do NOT symmetrize the asymmetry.
        lines = [_line(symbol, i) for i in range(len(symbol.graphics))]
        expected = (
            (Point(2500, -3300), Point(4200, -3300)),
            (Point(4200, -3300), Point(4200, -1800)),
            (Point(2500, 3300), Point(800, 3300)),
            (Point(800, 3300), Point(800, 4800)),
        )
        if tuple((s.start, s.end) for s in lines[6:10]) != expected:
            raise SymbolProfileMismatch("Schottky asymmetric two-hook cathode changed")
        if tuple(p.label for p in symbol.pins) != ("A", "K"):
            raise SymbolProfileMismatch("Schottky A/K changed")
        if result.pin_islands != (("1",), ("2",)):
            raise SymbolProfileMismatch("Schottky A/K incorrectly connected by ink")
    elif id_ == "transistor.mosfet_n_enh":
        if tuple(p.label for p in symbol.pins) != ("G", "D", "S"):
            raise SymbolProfileMismatch("MOSFET G/D/S roles altered")
        if len(symbol.pins) != 3:
            raise SymbolProfileMismatch("MOSFET must have exactly 3 physical pins")
        gate = _line(symbol, 0)
        metal = _line(symbol, 3)
        if gate.end.x >= 0 or gate.end.x != metal.start.x:
            raise SymbolProfileMismatch("MOS gate incorrectly touched source channel")
        if _line(symbol, 4).end != Point(0, -1000):
            raise SymbolProfileMismatch("MOS enhancement gap changed")
        if _line(symbol, 5).start != Point(0, 1000):
            raise SymbolProfileMismatch("MOS enhancement gap shorted")
        if _line(symbol, 6).end.x >= _line(symbol, 6).start.x:
            raise SymbolProfileMismatch("MOS N arrow reversed")
        if result.pin_islands != (("1",), ("2",), ("3",)):
            raise SymbolProfileMismatch("MOS 3 contacts electrically shorted")
    elif id_ in ("capacitor.fixed", "capacitor.polarized"):
        a = _line(symbol, 2)
        b = _line(symbol, 3)
        if (a.start.x != a.end.x or b.start.x != b.end.x
            or a.start.y != b.start.y or a.end.y != b.end.y
            or a.start.x == b.start.x):
            raise SymbolProfileMismatch("Thin capacitor plate geometry changed")
        if id_ == "capacitor.polarized":
            if tuple(p.label for p in symbol.pins) != ("+", "-"):
                raise SymbolProfileMismatch("Thin polarized capacitor lacks positive plate")
            if len(symbol.graphics) != 6:
                raise SymbolProfileMismatch("Polarized source must use thin plate style")
        elif len(symbol.graphics) != 4 or any(p.label for p in symbol.pins):
            raise SymbolProfileMismatch("Fixed capacitor has non-source polarity signs")
    elif id_ == "inductor.ferromagnetic":
        core = tuple(g for g in symbol.graphics if isinstance(g, StyledLine))
        if len(core) != 1 or core[0] in (
            symbol.graphics[i] for i in symbol.conductor_topology.conductor_indices
        ):
            raise SymbolProfileMismatch("Missing or electrically shorted magnetic core")
        if not any("ферромагнит" in source.lower() for source in symbol.standard_refs):
            raise SymbolProfileMismatch("Winding material is not source confirmed")
    elif id_ == "resistor.variable":
        if len(symbol.pins) != 3 or symbol.pins[2].label != "W":
            raise SymbolProfileMismatch("Physical slider/wiper was lost")
        if result.pin_islands != (("1",), ("2",), ("3",)):
            raise SymbolProfileMismatch("Wiper was incorrectly joined through ink")
    elif id_ == "fuse.general" and (
        len(symbol.pins) != 2 or result.pin_islands != (("1",), ("2",))
    ):
        raise SymbolProfileMismatch("Fuse is not a zero-ohm Net bridge")


def bind_tl494_source(
    components: Iterable[ComponentInstance],
    parts: Mapping[str, PartDefinition],
    symbols: Mapping[str, SymbolDefinition],
) -> tuple[SourceGlyphBinding, ...]:
    """Reject every wrong catalog choice, missing physical pin and changed D4."""
    manifest = read_source_manifest()
    source_components = tuple(components)
    instances = {component.reference: component for component in source_components}
    if len(instances) != len(source_components):
        raise SymbolProfileMismatch("Duplicate positional reference")
    bindings = []
    for entry in manifest["profiles"]:
        reference = entry["reference"]
        inst = instances.get(reference)
        expected = entry["symbol_id"]
        if inst is None or inst.part_id != expected:
            raise SymbolProfileMismatch(
                f"{reference}: expected {expected}, got "
                f"{None if inst is None else inst.part_id}"
            )
        if (inst.transform.rotation != entry["rotation"]
            or inst.transform.mirror_x != entry["mirror_x"]):
            raise SymbolProfileMismatch(f"{reference}: source D4 pose changed")
        part = parts.get(inst.part_id)
        symbol = symbols.get(inst.part_id)
        if part is None or symbol is None:
            raise SymbolProfileMismatch(f"{reference}: unknown actual physical catalog pair")
        check_ink_contract(symbol, part)
        if [pin.name for pin in part.pins] != entry["expected_physical_roles"]:
            raise SymbolProfileMismatch(f"{reference}: fake PhysicalPin role or number")
        if [pin.label for pin in symbol.pins] != entry["expected_graphic_labels"]:
            raise SymbolProfileMismatch(f"{reference}: incorrect GraphicPin label")
        positions = inst.pin_positions(symbol)
        if len(positions) != len(part.pins) or len(set(positions.values())) != len(part.pins):
            raise SymbolProfileMismatch(f"{reference}: lost physical terminal after D4")
        bindings.append(SourceGlyphBinding(
            reference, inst, symbol, part,
            tuple(PinRef(reference, pin.number) for pin in part.pins),
            tuple(positions[pin.number] for pin in part.pins),
            entry["standard_figure"],
        ))
    return tuple(bindings)
