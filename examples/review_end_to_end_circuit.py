"""Reproducible six-part electrical circuit specimen; NOT an autorouter or ESKD approval.

Run: python -m examples.review_end_to_end_circuit --output-dir output/electrical-cycle3
Uses real catalog definitions, independently authored external wires and the
existing (read-only) sheet SVG renderer. SVG wire coordinates are copied
directly from the same immutable ExternalWireGraph validated by ERC.
"""

import argparse
import json
from dataclasses import dataclass, replace
from importlib.resources import files
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_external_wire_catalog import catalog_definitions, catalog_sheet
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.diagnostics import Diagnostic
from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.units import format_mm
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.potentials import NetPotential, PotentialScenario
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)


def definitions() -> tuple[dict[str, PartDefinition], dict[str, SymbolDefinition]]:
    """Real PartDefinition and SymbolDefinition; no physical/symbol mock or SVG probing."""
    parts, symbols = catalog_definitions()
    root = files("gost_schematic").joinpath("catalog")
    path = "capacitors/electrolytic.json"
    part = load_part(Path(str(root.joinpath(f"parts/{path}"))))
    symbol = load_symbol(Path(str(root.joinpath(f"symbols/{path}"))))
    if part.symbol_id != symbol.identifier:
        raise ValueError("Electrolytic physical part mismatches symbol")
    parts[part.identifier] = part
    symbols[symbol.identifier] = symbol
    return parts, symbols


def _segment(x1: int, y1: int, x2: int, y2: int, net: str) -> WireSegment:
    return WireSegment(Point(x1, y1), Point(x2, y2), net)


def authored_specimen() -> tuple[Circuit, ExternalWireGraph]:
    """Six real devices, five physically separate external nets, three marked junctions.

    The new electrolytic C3 has PLUS=pin 1 on TOP, MINUS=pin 2 on RIGHT.
    All coordinates are authored integers in µm, never inferred from rendered SVG.
    """
    original, graph = catalog_sheet()
    components = (
        *original.components,
        ComponentInstance("C3", "capacitor.electrolytic", Point(100000, 80000)),
    )
    nets = tuple(
        replace(
            net,
            members=(*net.members, PinRef("C3", "1" if net.name == "TOP" else "2")),
        ) if net.name in {"TOP", "RIGHT"} else net
        for net in original.nets
    )
    # Shared endpoint nodes are also marked explicitly for unambiguous SVG.
    wires = (*graph.segments,
             _segment(40000, 40000, 40000, 80000, "TOP"),
             _segment(40000, 80000, 91000, 80000, "TOP"),
             _segment(120000, 40000, 120000, 80000, "RIGHT"),
             _segment(120000, 80000, 109000, 80000, "RIGHT"))
    junctions = (
        *graph.junctions,
        Point(40000, 40000),
        Point(120000, 40000),
    )
    return Circuit(components, nets), ExternalWireGraph(wires, junctions)


def potentials(*, reverse_electrolytic: bool = False) -> PotentialScenario:
    """Assumed single operating point, not a solved/simulated circuit."""
    pairs = (
        ("TOP", "-2" if reverse_electrolytic else "12"),
        ("LEFT", "10"),
        ("BOTTOM", "6"),
        ("TAP", "9"),
        ("RIGHT", "0"),
    )
    return PotentialScenario(
        "reverse-C3" if reverse_electrolytic else "nominal-static",
        tuple(NetPotential.from_volts(name, voltage, reference_id="sheet-0V")
              for name, voltage in pairs),
    )


@dataclass(frozen=True, slots=True)
class Case:
    identifier: str
    circuit: Circuit
    graph: ExternalWireGraph
    scenario: PotentialScenario
    expected_wire_codes: tuple[str, ...]
    expected_erc_codes: tuple[str, ...] = ()


def scenarios() -> tuple[Case, ...]:
    circuit, graph = authored_specimen()
    all_wires = graph.segments
    return (
        Case("valid", circuit, graph, potentials(), ()),
        Case(
            "electrolytic_pin_unwired", circuit,
            ExternalWireGraph(all_wires[:-1], graph.junctions),
            potentials(), ("WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED", "WIRE_PIN_UNWIRED"),
        ),
        Case(
            "short_at_unmarked_crossing", circuit,
            ExternalWireGraph(all_wires, (*graph.junctions, Point(40000, 60000))),
            potentials(), ("WIRE_NET_SHORT",),
        ),
        Case(
            "one_micrometre_gap", circuit,
            ExternalWireGraph(
                (*all_wires[:13],
                 _segment(40001, 80000, 91000, 80000, "TOP"),
                 *all_wires[14:]),
                graph.junctions,
            ),
            potentials(), ("WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED"),
        ),
        Case(
            "missing_t_junction", circuit,
            ExternalWireGraph(all_wires, graph.junctions[1:]),
            potentials(), ("WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED"),
        ),
        Case(
            "reverse_electrolytic_bias", circuit, graph, potentials(reverse_electrolytic=True),
            (), ("POLARITY_REVERSED",),
        ),
    )


def _diagnostic(item: Diagnostic) -> dict[str, str | None]:
    return {
        "code": item.code,
        "message": item.message,
        "severity": item.severity.value,
        "subject": item.subject,
    }


def _sorted_diagnostics(values: tuple[Diagnostic, ...]) -> list[dict[str, str | None]]:
    return sorted(
        (_diagnostic(item) for item in values),
        key=lambda d: (str(d["code"]), str(d["subject"] or ""), str(d["message"])),
    )


def diagnose(case: Case) -> dict[str, object]:
    parts, symbols = definitions()
    wires = _sorted_diagnostics(validate_external_wires(
        case.circuit, case.graph, parts, symbols,
    ))
    erc = _sorted_diagnostics(validate_circuit(
        case.circuit, parts, symbols, scenario=case.scenario,
    ))
    wire_codes = tuple(sorted({d["code"] for d in wires}))
    # Expected ERC warning-only UGO status is retained; assert specifically the
    # hard errors and the polarity test rather than suppressing warnings.
    erc_errors = tuple(sorted({d["code"] for d in erc if d["severity"] == "error"}))
    if wire_codes != tuple(sorted(case.expected_wire_codes)):
        raise AssertionError(f"{case.identifier}: unexpected wire codes: {wire_codes}")
    if erc_errors != tuple(sorted(case.expected_erc_codes)):
        raise AssertionError(f"{case.identifier}: unexpected ERC errors: {erc_errors}")
    return {
        "id": case.identifier,
        "net_count": len(case.circuit.nets),
        "wire_count": len(case.graph.segments),
        "junctions_um": [[p.x, p.y] for p in case.graph.junctions],
        "scenario": case.scenario.name,
        "expected_wire_codes": sorted(case.expected_wire_codes),
        "expected_erc_error_codes": sorted(case.expected_erc_codes),
        "wire_diagnostics": wires,
        "erc_diagnostics": erc,
    }


def c3_manual_layout_metrics() -> dict[str, object]:
    """Compare exact authored C3 branches before/after a MANUAL 5mm Y shift.

    This reports geometric quality only. It does not optimize placement,
    search for better arrangements, or mutate the electrical netlist.
    """
    _, graph = authored_specimen()
    new_top = graph.segments[-4:-2]
    new_right = graph.segments[-2:]

    def path_points(wires: tuple[WireSegment, ...]) -> tuple[Point, ...]:
        if any(a.end != b.start for a, b in pairwise(wires)):
            raise AssertionError("C3 branch has disconnected authored segments")
        return (wires[0].start, *(wire.end for wire in wires))

    def metrics(points: tuple[Point, ...]) -> dict[str, int]:
        steps = tuple(
            (b.x - a.x, b.y - a.y)
            for a, b in pairwise(points)
        )
        if any((dx == 0) == (dy == 0) for dx, dy in steps):
            raise AssertionError("C3 manual branch must be nonzero orthogonal")
        directions = tuple((0 if dy == 0 else 1) for dx, dy in steps)
        length = sum(abs(dx) + abs(dy) for dx, dy in steps)
        manhattan = (
            abs(points[-1].x - points[0].x)
            + abs(points[-1].y - points[0].y)
        )
        excess = length - manhattan
        return {
            "length_um": length,
            "bends": sum(a != b for a, b in pairwise(directions)),
            "manhattan_excess_um": excess,
            "backtrack_um": excess // 2,
        }

    original_top = (
        Point(40000, 40000), Point(40000, 80000),
        Point(84000, 80000), Point(84000, 75000),
        Point(91000, 75000),
    )
    original_right = (
        Point(120000, 40000), Point(120000, 75000),
        Point(109000, 75000),
    )
    plans = {
        "before": {"TOP": original_top, "RIGHT": original_right},
        "after": {
            "TOP": path_points(new_top),
            "RIGHT": path_points(new_right),
        },
    }
    result: dict[str, object] = {
        "method": "manual-authored-specimen-correction-not-auto-placement",
        "c3_origin_before_um": [100000, 75000],
        "c3_origin_after_um": [100000, 80000],
    }
    for key, branches in plans.items():
        top = metrics(branches["TOP"])
        right = metrics(branches["RIGHT"])
        result[key] = {
            "TOP": top,
            "RIGHT": right,
            "combined_length_um": top["length_um"] + right["length_um"],
            "combined_bends": top["bends"] + right["bends"],
        }
    return result


def report() -> dict[str, object]:
    cases = scenarios()
    parts, symbols = definitions()
    circuit, graph = authored_specimen()
    return {
        "schema_version": 1,
        "kind": "electrical_end_to_end_specimen",
        "manual_c3_layout_comparison": c3_manual_layout_metrics(),
        "status": "experimental_not_eskd_approved",
        "catalog_ids": sorted(parts),
        "components": [
            {
                "reference": component.reference,
                "part_id": component.part_id,
                "physical_pins_um": {
                    number: [point.x, point.y]
                    for number, point in sorted(component.pin_positions(
                        symbols[parts[component.part_id].symbol_id]
                    ).items())
                },
            }
            for component in circuit.components
        ],
        "nets": [{
            "name": net.name,
            "pins": [f"{ref.reference}.{ref.number}" for ref in net.members],
        } for net in circuit.nets],
        "authored_wires": [{
            "net": segment.net_name,
            "start_um": [segment.start.x, segment.start.y],
            "end_um": [segment.end.x, segment.end.y],
        } for segment in graph.segments],
        "cases": [diagnose(case) for case in cases],
    }


def report_json() -> str:
    return json.dumps(report(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def renderer_wires(graph: ExternalWireGraph) -> tuple[WireObstacle, ...]:
    """Single source of coordinates for both checker and existing SVG renderer."""
    return tuple(
        WireObstacle(
            f"external-{i:02d}", Line(item.start, item.end),
            stroke_um=300, net_name=item.net_name,
        )
        for i, item in enumerate(graph.segments)
    )


def specimen_svg(*, review: bool = False) -> str:
    """Existing SVG renderer read-only; add specimen-only ref labels/junction dots.

    The renderer does not currently depict junction dots. We add only explicitly
    authored junction circles in a separate local layer, not inferred contacts.
    This does not alter the renderer API or netlist.
    """
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    svg_text = render_sheet_svg(
        circuit, by_part, SheetLayout((), ()),
        wires=renderer_wires(graph), review_overlay=review,
    )
    root = ET.fromstring(svg_text)
    group = ET.SubElement(root, f"{{{SVG_NAMESPACE}}}g", {
        "data-layer": "explicit-junctions",
        "fill": "#000000",
        "stroke": "none",
    })
    for point in graph.junctions:
        ET.SubElement(group, f"{{{SVG_NAMESPACE}}}circle", {
            "data-kind": "authored-junction",
            "cx": format_mm(point.x),
            "cy": format_mm(point.y),
            "r": "0.55",
        })
    labels = ET.SubElement(root, f"{{{SVG_NAMESPACE}}}g", {
        "data-layer": "specimen-refdes",
        "fill": "#222222",
        "stroke": "none",
        "font-family": "sans-serif",
        "font-size": "3.5",
        "text-anchor": "middle",
    })
    for component in circuit.components:
        symbol = by_part[component.part_id]
        top = component.transform.box(symbol.body_keepout).translated(component.origin).min_y
        text = ET.SubElement(labels, f"{{{SVG_NAMESPACE}}}text", {
            "data-owner": component.reference,
            "x": format_mm(component.origin.x),
            "y": format_mm(top - 2500),
        })
        text.text = component.reference
    return ET.tostring(root, encoding="unicode") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files_to_write = (
        ("end-to-end-clean.svg", specimen_svg()),
        ("end-to-end-review.svg", specimen_svg(review=True)),
        ("end-to-end-diagnostics.json", report_json()),
    )
    for filename, contents in files_to_write:
        path = args.output_dir / filename
        path.write_bytes(contents.encode("utf-8"))
        print(f"Created {path}")


if __name__ == "__main__":
    main()
