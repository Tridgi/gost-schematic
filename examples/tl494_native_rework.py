"""Native GOST Schematic Engine DRAFT power-stage reconstruction.

Authoritative component graphics: installed SymbolDefinition catalogue.
Authoritative pin coordinates: ComponentInstance.pin_positions(symbol).
Wires: manually authored ExternalWireGraph, exact integer um; never SVG guesswork.
Type A: inspected OpenGost type A actual font, measured by engine.
This is a genuine native render of ONLY the 11-component power stage,
NOT the TL494 control circuit, NOT a finished ESKD electrical drawing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.annotations import (
    Anchor, AnnotationRole, AnnotationSlot, HorizontalAlign, VerticalAlign,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph, WireSegment, validate_external_wires,
)
from gost_schematic.validation.symbol_checks import validate_symbol


def P(x: int, y: int) -> Point:
    return Point(x * 1000, y * 1000)


def contact_part(*, destination: bool) -> tuple[PartDefinition, SymbolDefinition]:
    """Two separate real terminal islands (not the same net)."""
    code = "reference.connector.x2" if destination else "reference.connector.x1"
    if destination:
        body = Box(0, -3000, 6000, 18000)
        strokes = (
            Rectangle(body),
            Line(P(-10, 0), P(0, 0)),
            Line(P(-10, 15), P(0, 15)),
        )
        pins = (
            GraphicPin("1", P(-10, 0), Side.LEFT, "1"),
            GraphicPin("2", P(-10, 15), Side.LEFT, "2"),
        )
    else:
        body = Box(-6000, -3000, 0, 18000)
        strokes = (
            Rectangle(body),
            Line(P(0, 0), P(10, 0)),
            Line(P(0, 15), P(10, 15)),
        )
        pins = (
            GraphicPin("1", P(10, 0), Side.RIGHT, "1"),
            GraphicPin("2", P(10, 15), Side.RIGHT, "2"),
        )
    slots = (AnnotationSlot(
        "refdes", AnnotationRole.REFDES, (
            Anchor(P(0, -8), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),
        ), required=True,
    ),)
    symbol = SymbolDefinition(
        identifier=code, revision=1, graphics=strokes, pins=pins,
        body_keepout=body, line_width_um=300, status=SymbolStatus.DRAFT,
        annotation_slots=slots,
        standard_refs=("EXPERIMENTAL: two physical contacts; not catalog approved",),
    )
    part = PartDefinition(
        identifier=code, reference_prefix="X", symbol_id=code,
        pins=(
            PhysicalPin("1", "CONTACT_1", ElectricalType.PASSIVE),
            PhysicalPin("2", "CONTACT_2", ElectricalType.PASSIVE),
        ),
    )
    return part, symbol


def build():
    resolver = CatalogResolver()
    parts = dict(resolver.parts)
    symbols = dict(resolver.symbols)
    for part, symbol in (contact_part(destination=False), contact_part(destination=True)):
        parts[part.identifier] = part
        symbols[symbol.identifier] = symbol
        errors = [d for d in validate_symbol(symbol) if d.severity.value == "error"]
        if errors:
            raise AssertionError(f"{part.identifier}: invalid custom terminal: {errors}")
    specs = (
        ("X1", "reference.connector.x1", 20, 45, 0, None),
        ("L1", "inductor.air_core", 115, 45, 0, ("100", Unit.MICROHENRY)),
        ("VT1", "transistor.mosfet_n_enh", 170, 135, 0, None),
        ("C1", "capacitor.polarized", 225, 29, 0, ("220", Unit.MICROFARAD)),
        ("C2", "capacitor.polarized", 225, 65, 0, ("220", Unit.MICROFARAD)),
        ("VD1", "diode.schottky", 270, 130, 270, None),
        ("L2", "inductor.air_core", 315, 45, 0, ("100", Unit.MICROHENRY)),
        ("C5", "capacitor.polarized", 345, 145, 270, ("1000", Unit.MICROFARAD)),
        ("C6", "capacitor.polarized", 385, 145, 270, ("1000", Unit.MICROFARAD)),
        ("FU1", "fuse.general", 411, 45, 0, None),
        ("X2", "reference.connector.x2", 470, 45, 0, None),
    )
    components = tuple(ComponentInstance(
        name, part_id, P(x, y), Transform(rotation=rot),
        Quantity.from_unit(*value) if value is not None else None,
    ) for name, part_id, x, y, rot, value in specs)
    circuit = Circuit(components, (
        Net("INPUT_POS", (PinRef("X1", "1"), PinRef("L1", "1"))),
        Net("COMMON", (
            PinRef("X1", "2"), PinRef("X2", "2"), PinRef("VT1", "3"),
            PinRef("VD1", "1"), PinRef("C5", "1"), PinRef("C6", "1"),
        )),
        Net("SWITCH", (
            PinRef("L1", "2"), PinRef("VT1", "2"),
            PinRef("C1", "1"), PinRef("C2", "1"),
        )),
        Net("ENERGY_TRANSFER", (
            PinRef("C1", "2"), PinRef("C2", "2"),
            PinRef("VD1", "2"), PinRef("L2", "1"),
        )),
        Net("OUT_BEFORE_FUSE", (
            PinRef("L2", "2"), PinRef("C5", "2"),
            PinRef("C6", "2"), PinRef("FU1", "1"),
        )),
        Net("OUTPUT_NEG", (PinRef("FU1", "2"), PinRef("X2", "1"))),
    ))
    pos = {}
    for c in components:
        part = parts[c.part_id]
        sym = symbols[part.symbol_id]
        if {p.number for p in part.pins} != {p.number for p in sym.pins}:
            raise AssertionError(f"Catalogue pin mismatch for {c.reference}")
        pos[c.reference] = {n: (p.x // 1000, p.y // 1000)
                            for n, p in c.pin_positions(sym).items()}
    expected = {
        ("X1", "1"): (30, 45), ("X1", "2"): (30, 60),
        ("L1", "1"): (103, 45), ("L1", "2"): (127, 45),
        ("VT1", "1"): (159, 135), ("VT1", "2"): (170, 117),
        ("VT1", "3"): (170, 146),
        ("C1", "1"): (217, 29), ("C1", "2"): (233, 29),
        ("C2", "1"): (217, 65), ("C2", "2"): (233, 65),
        ("VD1", "1"): (270, 140), ("VD1", "2"): (270, 120),
        ("L2", "1"): (303, 45), ("L2", "2"): (327, 45),
        ("C5", "1"): (345, 153), ("C5", "2"): (345, 137),
        ("C6", "1"): (385, 153), ("C6", "2"): (385, 137),
        ("FU1", "1"): (402, 45), ("FU1", "2"): (420, 45),
        ("X2", "1"): (460, 45), ("X2", "2"): (460, 60),
    }
    for (ref, num), at in expected.items():
        if pos[ref][num] != at:
            raise AssertionError(f"Real catalogue pin drift: {ref}.{num}: "
                                 f"{pos[ref][num]} != {at}")
    return circuit, parts, symbols, pos


def W(net: str, x1: int, y1: int, x2: int, y2: int) -> WireSegment:
    if x1 != x2 and y1 != y2:
        raise AssertionError("Only exactly orthogonal nonzero wires allowed")
    return WireSegment(P(x1, y1), P(x2, y2), net)


def source_graph() -> ExternalWireGraph:
    commands = [
        # Input. No vertical connection between X1.1 and X1.2.
        ("INPUT_POS",30,45,103,45),
        # Common wire and return branches.
        ("COMMON",30,60,30,220), ("COMMON",30,220,455,220),
        ("COMMON",170,146,170,220),
        ("COMMON",270,140,270,220),
        ("COMMON",345,153,345,220),
        ("COMMON",385,153,385,220),
        ("COMMON",455,220,455,60), ("COMMON",455,60,460,60),
        # L1 output → VT1 drain → C1/C2 positive.
        ("SWITCH",127,45,170,45), ("SWITCH",170,45,200,45),
        ("SWITCH",170,45,170,117), ("SWITCH",200,29,200,65),
        ("SWITCH",200,45,200,29), ("SWITCH",200,29,217,29),
        ("SWITCH",200,65,217,65),
        # Capacitors' negative electrodes → VD1 cathode and L2.
        ("ENERGY_TRANSFER",233,29,250,29),
        ("ENERGY_TRANSFER",250,29,250,65),
        ("ENERGY_TRANSFER",233,65,250,65),
        ("ENERGY_TRANSFER",250,45,270,45),
        ("ENERGY_TRANSFER",270,45,303,45),
        ("ENERGY_TRANSFER",270,45,270,120),
        # Output filter before fuse. C5/C6 plus go to return, not the negative output.
        ("OUT_BEFORE_FUSE",327,45,402,45),
        ("OUT_BEFORE_FUSE",345,45,345,137),
        ("OUT_BEFORE_FUSE",385,45,385,137),
        ("OUTPUT_NEG",420,45,460,45),
    ]
    junctions = (
        P(170,45), P(200,45), P(200,29), P(200,65), P(250,45),
        P(250,29), P(250,65), P(270,45), P(345,45), P(385,45),
        P(170,220),P(270,220),P(345,220),P(385,220),P(455,220),
    )
    return ExternalWireGraph(tuple(W(*v) for v in commands), junctions)


def generate(output: Path, font: Path) -> dict:
    circuit, parts, symbols, poses = build()
    graph = source_graph()
    issues = validate_external_wires(circuit, graph, parts, symbols)
    erc = validate_circuit(circuit, parts, symbols)
    # Keep the layout report even when the manual topology remains DRAFT.
    font_report = inspect_type_a_font(
        font, h_um=3500, family="OpenGost Type A TT",
        require_family_match=True,
    )
    symbols_by_part = {identifier: symbols[part.symbol_id]
                       for identifier, part in parts.items()}
    sheet_clean = render_external_wire_sheet(
        circuit, graph, symbols_by_part,
        font_report.style, PillowTextMeasurer(),
        diagnostic=False, strict_layout=False,
    )
    sheet_debug = render_external_wire_sheet(
        circuit, graph, symbols_by_part,
        font_report.style, PillowTextMeasurer(),
        diagnostic=True, strict_layout=False,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output/"TL494_native_power_clean.svg").write_text(sheet_clean.svg,encoding="utf-8")
    (output/"TL494_native_power_diagnostic.svg").write_text(sheet_debug.svg,encoding="utf-8")
    ET.fromstring(sheet_clean.svg)
    ET.fromstring(sheet_debug.svg)
    if any(x in sheet_clean.svg for x in ("#168f78", "#d79a3d", "#148a74")):
        raise AssertionError("Diagnostics leaked into clean native render")
    report = {
        "status": "DRAFT_NATIVE_POWER_STAGE_ONLY",
        "source": "GOST Schematic Engine native Parts/Symbols, Circuit and WireGraph",
        "reference_drawing_complete": False,
        "reasons_incomplete": (
            "TL494 16-pin controller and feedback/timing circuitry are not "
            "included in this 11-component power-stage sample",
        ),
        "component_count": len(circuit.components),
        "net_count": len(circuit.nets),
        "wire_segments": len(graph.segments),
        "physical_pin_coordinates_mm": poses,
        "font": {
            "family": font_report.reported_face[0],
            "sha256":font_report.style.font_sha256,
            "cap_height_target_um":3500,
            "cap_height_measured_um":font_report.measured_cap_height_um,
        },
        "wire_diagnostics": [
            {"code":d.code,"severity":d.severity.value,"message":d.message}
            for d in issues
        ],
        "erc_diagnostics": [
            {"code":d.code,"severity":d.severity.value,"message":d.message}
            for d in erc
        ],
        "layout_diagnostics": [
            {"code":d.code,"severity":d.severity.value,"message":d.message}
            for d in sheet_clean.layout.diagnostics
        ],
        "layout_valid":sheet_clean.layout.valid,
        "wire_valid":not any(d.severity.value=="error" for d in issues),
        "erc_valid":not any(d.severity.value=="error" for d in erc),
        "experiment_not_eskd_approved":True,
    }
    (output/"TL494_native_power_manifest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "native_components":len(circuit.components),
        "real_nets":len(circuit.nets),
        "wire_segments":len(graph.segments),
        "wire_errors":sum(d.severity.value=="error" for d in issues),
        "erc_errors":sum(d.severity.value=="error" for d in erc),
        "layout_valid":sheet_clean.layout.valid,
        "font":font_report.reported_face[0],
    },ensure_ascii=False))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--font-file",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    generate(args.output,args.font_file)


if __name__=="__main__":
    main()
