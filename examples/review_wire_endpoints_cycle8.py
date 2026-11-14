"""Issue #90/#100: read-only synthetic E3 wire-end vs X/T/XP/XS review.

All DD/VT/XP/XS parts are SYNTHETIC design fixtures, not real pinouts.
The green squares are editor-only diagnostics, not ГОСТ output or conductive
connections. No Circuit.Net or ExternalWireGraph is mutated by rendering.

Usage:
  python -m examples.review_wire_endpoints_cycle8 --output-dir output/wire-ends
  python -m examples.review_wire_endpoints_cycle8 --output-dir output/wire-ends --png
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.netrefs import NetIdentity
from gost_schematic.electrical.wire_endpoints import (
    WireEndSide,
    collect_wire_endpoints,
)
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.external_wire_sheet import build_external_wire_obstacles
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.wire_end_overlay import wire_endpoint_svg
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

_URI = "http://www.w3.org/2000/svg"
_NS = "{" + _URI + "}"


def fixture():
    """One deliberate dangling CTRL gap, one explicit tee, one unjoined X."""
    specs = (
        ("synthetic.dd", "DD", (
            ("5", Point(0, 0)), ("6", Point(0, 30000)),
            ("NC", Point(8000, 15000)),
        ), Box(-4000, 8000, 4000, 22000), Line(Point(0, 8000), Point(0, 22000))),
        ("synthetic.vt", "VT", (("G", Point(0, 0)),),
         Box(1000, -4000, 4000, 4000), Line(Point(2000, -3500), Point(2000, 3500))),
        ("synthetic.xp", "XP", (("1", Point(0, 0)),),
         Box(1000, -4000, 4000, 4000), Line(Point(2000, -3500), Point(2000, 3500))),
        ("synthetic.xs", "XS", (("1", Point(0, 0)),),
         Box(1000, -4000, 4000, 4000), Line(Point(2000, -3500), Point(2000, 3500))),
    )
    parts = {}
    symbols = {}
    for part_id, prefix, pins, keepout, stroke in specs:
        symbol_id = part_id + ".symbol"
        symbols[symbol_id] = SymbolDefinition(
            symbol_id, 1, (stroke,),
            tuple(GraphicPin(n, at, Side.RIGHT) for n, at in pins),
            keepout, 300,
        )
        parts[part_id] = PartDefinition(
            part_id, prefix, symbol_id,
            tuple(PhysicalPin(
                n, n, ElectricalType.UNSPECIFIED if n == "NC" else ElectricalType.PASSIVE,
            ) for n, _ in pins),
        )
    components = (
        ComponentInstance("DD1", "synthetic.dd", Point(20000, 40000)),
        ComponentInstance("VT1", "synthetic.vt", Point(110000, 40000)),
        ComponentInstance("XP1", "synthetic.xp", Point(110000, 70000)),
        ComponentInstance("XS1", "synthetic.xs", Point(65000, 30000)),
    )
    actual_nets = (
        Net("CTRL", (PinRef("DD1", "5"), PinRef("VT1", "G"))),
        Net("AUX", (PinRef("DD1", "6"), PinRef("XP1", "1"))),
        Net("SHIELD", (PinRef("XS1", "1"),)),
    )
    circuit = Circuit(components, actual_nets)
    wires = (
        WireSegment(Point(20000, 40000), Point(60000, 40000), "CTRL"),
        WireSegment(Point(110000, 40000), Point(70000, 40000), "CTRL"),
        WireSegment(Point(20000, 70000), Point(110000, 70000), "AUX"),
        WireSegment(Point(65000, 30000), Point(65000, 80000), "SHIELD"),
        WireSegment(Point(50000, 70000), Point(50000, 90000), "AUX"),
    )
    graph = ExternalWireGraph(wires, (Point(50000, 70000),))
    identities = tuple(NetIdentity("N-" + n.name, n.name, n.members) for n in actual_nets)
    wire_ids = ("W-CTRL-A", "W-CTRL-B", "W-AUX", "W-SHIELD", "W-AUX-TEE")
    blocked_pins = frozenset((PinRef("DD1", "NC"),))
    blocked_wire_ends = frozenset((("W-CTRL-B", WireEndSide.END),))
    return circuit, graph, identities, wire_ids, parts, symbols, blocked_pins, blocked_wire_ends


def generate(*, font_file: Path | None = None) -> tuple[str, str, dict]:
    circuit, graph, nets, wire_ids, parts, symbols, blocked_pins, blocked_ends = fixture()
    snapshot = collect_wire_endpoints(
        circuit, graph, nets, wire_ids, parts, symbols,
        blocked_pins=blocked_pins, blocked_wire_ends=blocked_ends,
    )
    by_part = {part_id: symbols[part.symbol_id] for part_id, part in parts.items()}
    base = render_sheet_svg(
        circuit, by_part, SheetLayout((), ()),
        wires=build_external_wire_obstacles(graph),
    )
    root = ET.fromstring(base)
    junctions = ET.SubElement(root, _NS + "g", {
        "data-layer": "explicit-junctions", "stroke": "none", "fill": "#000000",
    })
    for p in graph.junctions:
        ET.SubElement(junctions, _NS + "circle", {
            "data-kind": "authored-junction",
            "cx": format_mm(p.x), "cy": format_mm(p.y), "r": "0.55",
        })
    if font_file is not None:
        # Real font measurement via existing Type A infrastructure. Typography
        # on this isolated synthetic fixture is still DRAFT, not approved ESKD.
        from gost_schematic.standards.type_a_font import inspect_type_a_font

        style = inspect_type_a_font(font_file, h_um=2500).style
        labels = ET.SubElement(root, _NS + "g", {
            "data-layer": "synthetic-device-labels",
            "font-family": style.font_family,
            "font-size": format_mm(style.em_height_um),
            "stroke": "none", "fill": "black",
            "data-font-sha256": style.font_sha256,
        })
        for name, x, y in (
            ("DD1 SYNTHETIC", 11000, 32000),
            ("VT1 SYNTHETIC", 112000, 32000),
            ("XP1 SYNTHETIC", 112000, 62000),
            ("XS1 SYNTHETIC", 67000, 23000),
        ):
            ET.SubElement(labels, _NS + "text", {
                "x": format_mm(x), "y": format_mm(y),
            }).text = name
    clean_input = ET.tostring(root, encoding="unicode") + "\n"
    clean = wire_endpoint_svg(
        clean_input, snapshot, parts, symbols,
        blocked_pins=blocked_pins, blocked_wire_ends=blocked_ends,
    )
    diagnostic = wire_endpoint_svg(
        clean_input, snapshot, parts, symbols, diagnostic=True,
        blocked_pins=blocked_pins, blocked_wire_ends=blocked_ends,
    )
    report = {
        "schema_version": 1,
        "approval": "DRAFT_SYNTHETIC_EDITOR_ONLY",
        "real_circuit_nets": [
            {"name": n.name, "members": [
                {"reference": pin.reference, "number": pin.number}
                for pin in n.members
            ]} for n in circuit.nets
        ],
        "wire_count": len(graph.segments),
        "crossings_without_junction": [
            {"id": x.id, "point_um": [x.point.x, x.point.y],
             "net_ids": [x.first_net_id, x.second_net_id]}
            for x in snapshot.nonjoining_crossings
        ],
        "explicit_junctions_um": [[p.x, p.y] for p in graph.junctions],
        "real_endpoints": [
            {
                "id": e.id, "net_id": e.net_id,
                "wire_id": e.wire_id, "wire_index": e.wire_index,
                "point_um": [e.point.x, e.point.y],
                "termination": e.termination.value,
                "state": e.state.value, "can_accept_connection": e.can_accept_connection,
                "reason": e.reason_code,
            } for e in snapshot.wire_endpoints
        ],
        "physical_contacts": [
            {"id": c.id, "connector": c.connector, "reason": c.reason_code,
             "state": c.state.value, "can_accept_connection": c.can_accept_connection}
            for c in snapshot.physical_contacts
        ],
        "font": "OpenGost Type A pinned external" if font_file else "not embedded",
        "warning": "Synthetic pins, no real vendor mapping or UI/transaction implementation",
    }
    return clean, diagnostic, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--font-file", type=Path)
    parser.add_argument("--png", action="store_true")
    args = parser.parse_args()
    clean, diagnostic, report = generate(font_file=args.font_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for label, svg in (("clean", clean), ("diagnostic", diagnostic)):
        (args.output_dir / f"wire-endpoints-{label}.svg").write_text(svg, "utf-8")
        if args.png:
            import resvg_py
            (args.output_dir / f"wire-endpoints-{label}-300dpi.png").write_bytes(
                resvg_py.svg_to_bytes(svg_string=svg, dpi=300)
            )
    (args.output_dir / "wire-endpoints.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        "utf-8",
    )
    print("DRAFT: one authored T, one unjoined X, actual pin/XP/XS, free wire ends")


if __name__ == "__main__":
    main()
