"""Reproducible external-wire diagnostic review using actual catalog components.

This is a authored *test* sheet, not an automatic router or verified ESKD design.
All coordinates are exact integer micrometres. Run as a module or a script:
    python examples/review_external_wire_catalog.py --output output/wire-catalog-review.json
"""

import argparse
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)


def catalog_definitions() -> tuple[dict[str, PartDefinition], dict[str, SymbolDefinition]]:
    """Load the real, versioned part/symbol JSON, including the authored winding."""
    root = files("gost_schematic").joinpath("catalog")
    parts: dict[str, PartDefinition] = {}
    symbols: dict[str, SymbolDefinition] = {}
    for kind in ("resistors/fixed", "capacitors/fixed", "capacitors/polarized"):
        part = load_part(Path(str(root.joinpath(f"parts/{kind}.json"))))
        symbol = load_symbol(Path(str(root.joinpath(f"symbols/{kind}.json"))))
        if part.symbol_id != symbol.identifier:
            raise ValueError(f"Catalog part/symbol mismatch: {part.identifier}")
        parts[part.identifier] = part
        symbols[symbol.identifier] = symbol
    winding = load_inductor(Path(str(root.joinpath("inductors/inductor.tapped.json"))))
    parts[winding.part.identifier] = winding.part
    symbols[winding.symbol.identifier] = winding.symbol
    return parts, symbols


@dataclass(frozen=True, slots=True)
class ReviewCase:
    name: str
    circuit: Circuit
    graph: ExternalWireGraph
    expected_codes: tuple[str, ...]


def _point(x: int, y: int) -> Point:
    return Point(x, y)


def _wire(x1: int, y1: int, x2: int, y2: int, net: str) -> WireSegment:
    return WireSegment(_point(x1, y1), _point(x2, y2), net)


def catalog_sheet() -> tuple[Circuit, ExternalWireGraph]:
    """5 catalog components, 5 semantic nets, one marked T and two unmarked X.

    Endpoints and three-way junction are intentionally authored, never routed
    by the validator. Inductor winding's physical pins 1, 2 and tap 3 have
    *different* external net memberships.
    """
    circuit = Circuit(
        components=(
            ComponentInstance("R1", "resistor.fixed", _point(20000, 20000)),
            ComponentInstance("R2", "resistor.fixed", _point(20000, 60000)),
            ComponentInstance("C1", "capacitor.fixed", _point(60000, 20000)),
            ComponentInstance("C2", "capacitor.polarized", _point(60000, 60000)),
            ComponentInstance("L1", "inductor.tapped", _point(100000, 40000)),
        ),
        nets=(
            Net("TOP", (PinRef("R1", "2"), PinRef("C1", "1"), PinRef("L1", "1"))),
            Net("LEFT", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("BOTTOM", (PinRef("R2", "2"), PinRef("C2", "1"))),
            Net("TAP", (PinRef("C1", "2"), PinRef("L1", "3"))),
            Net("RIGHT", (PinRef("C2", "2"), PinRef("L1", "2"))),
        ),
    )
    graph = ExternalWireGraph(
        segments=(
            _wire(28000, 20000, 52000, 20000, "TOP"),
            _wire(40000, 20000, 40000, 40000, "TOP"),
            _wire(40000, 40000, 88000, 40000, "TOP"),
            _wire(12000, 20000, 12000, 60000, "LEFT"),
            _wire(28000, 60000, 52000, 60000, "BOTTOM"),
            _wire(68000, 20000, 98000, 20000, "TAP"),
            _wire(98000, 20000, 98000, 31000, "TAP"),
            _wire(68000, 60000, 70000, 60000, "RIGHT"),
            _wire(70000, 60000, 70000, 27000, "RIGHT"),
            _wire(70000, 27000, 120000, 27000, "RIGHT"),
            _wire(120000, 27000, 120000, 40000, "RIGHT"),
            _wire(120000, 40000, 112000, 40000, "RIGHT"),
        ),
        junctions=(_point(40000, 20000),),
    )
    return circuit, graph


def review_cases() -> tuple[ReviewCase, ...]:
    """Named faults are minimal mutations of one known-good physical sheet."""
    circuit, graph = catalog_sheet()
    original = graph.segments
    return (
        ReviewCase("valid_catalog_sheet", circuit, graph, ()),
        ReviewCase(
            "missing_t_junction",
            circuit, ExternalWireGraph(original),
            ("WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED"),
        ),
        ReviewCase(
            "one_micrometre_break",
            circuit,
            ExternalWireGraph(
                (
                    _wire(28000, 20000, 39999, 20000, "TOP"),
                    _wire(40000, 20000, 52000, 20000, "TOP"),
                    *original[1:],
                ),
                graph.junctions,
            ),
            ("WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED"),
        ),
        ReviewCase(
            "crossing_short_with_junction",
            circuit,
            ExternalWireGraph(original, (*graph.junctions, _point(70000, 40000))),
            ("WIRE_NET_SHORT",),
        ),
        ReviewCase(
            "wrong_bottom_net",
            circuit,
            ExternalWireGraph(
                (*original[:4], _wire(28000, 60000, 52000, 60000, "LEFT"), *original[5:]),
                graph.junctions,
            ),
            ("WIRE_NET_SHORT", "WIRE_PIN_NET_MISMATCH"),
        ),
        ReviewCase(
            "orphan_conductor",
            circuit,
            ExternalWireGraph(
                (*original, _wire(140000, 70000, 150000, 70000, "TOP")),
                graph.junctions,
            ),
            ("WIRE_DANGLING_END", "WIRE_ORPHAN_CONDUCTOR"),
        ),
        ReviewCase(
            "unwired_capacitor_pin",
            circuit,
            ExternalWireGraph((*original[:4], *original[5:]), graph.junctions),
            ("WIRE_NET_DISCONNECTED", "WIRE_PIN_UNWIRED"),
        ),
    )


def review_document() -> dict[str, object]:
    """JSON-safe stable diagnostics from real catalog definitions; no clock or host paths."""
    parts, symbols = catalog_definitions()
    entries: list[dict[str, object]] = []
    for case in review_cases():
        found = validate_external_wires(case.circuit, case.graph, parts, symbols)
        diagnostics = sorted(
            (
                {
                    "code": diagnostic.code,
                    "severity": diagnostic.severity.value,
                    "subject": diagnostic.subject,
                    "message": diagnostic.message,
                }
                for diagnostic in found
            ),
            key=lambda item: (
                str(item["code"]),
                str(item["subject"] or ""),
                str(item["message"]),
                str(item["severity"]),
            ),
        )
        codes = tuple(sorted({diagnostic["code"] for diagnostic in diagnostics}))
        expected = tuple(sorted(case.expected_codes))
        if codes != expected:
            raise AssertionError(f"{case.name}: diagnostic drift {codes} != {expected}")
        entries.append({
            "id": case.name,
            "components": [
                {
                    "reference": instance.reference,
                    "part_id": instance.part_id,
                    "pins_um": {
                        number: [point.x, point.y]
                        for number, point in sorted(
                            instance.pin_positions(
                                symbols[parts[instance.part_id].symbol_id]
                            ).items()
                        )
                    },
                }
                for instance in case.circuit.components
            ],
            "nets": [
                {
                    "name": net.name,
                    "pins": [f"{member.reference}.{member.number}" for member in net.members],
                }
                for net in case.circuit.nets
            ],
            "wire_count": len(case.graph.segments),
            "junctions_um": [[p.x, p.y] for p in case.graph.junctions],
            "expected_codes": sorted(case.expected_codes),
            "diagnostics": diagnostics,
            "result": "pass" if not diagnostics else "diagnostics",
        })
    return {
        "schema_version": 1,
        "kind": "external_wire_catalog_review",
        "status": "experimental_not_eskd_approved",
        "catalog_parts": sorted(parts),
        "case_count": len(entries),
        "cases": entries,
    }


def review_json() -> str:
    return json.dumps(review_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(review_json().encode("utf-8"))
    print(f"Catalog wire review written: {args.output}")


if __name__ == "__main__":
    main()
