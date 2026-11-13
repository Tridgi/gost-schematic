"""Run: python -m examples.review_two_pin_routing --output-dir output/routing-cycle4

Three REAL catalog components: resistor R1, resistor blocker R2, electrolytic
C1. Only R1.2 -> C1.1 is routed; no autorouting of any other net. This is an
experimental connectivity/geometry demonstration, not an approved ESKD sheet.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_end_to_end_circuit import definitions
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.units import format_mm
from gost_schematic.engines.routing.clearance import validate_wire_clearance
from gost_schematic.engines.routing.two_pin_orthogonal import TwoPinRoute
from gost_schematic.engines.routing.two_pin_sheet import route_circuit_two_pins
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.external_wire_checks import validate_external_wires


def specimen() -> tuple[Circuit, tuple[Box, ...], TwoPinRoute]:
    parts, symbols = definitions()
    circuit = Circuit(
        (
            ComponentInstance("R1", "resistor.fixed", Point(20000, 20000)),
            ComponentInstance("R2", "resistor.fixed", Point(60000, 20000)),
            ComponentInstance("C1", "capacitor.electrolytic", Point(100000, 20000)),
        ),
        (Net("LINK", (PinRef("R1", "2"), PinRef("C1", "1"))),),
    )
    keepouts = tuple(
        item.transform.box(symbols[parts[item.part_id].symbol_id].body_keepout)
        .translated(item.origin)
        for item in circuit.components
    )
    # The typed adapter protects every physical pin, not only body keepouts.
    route = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "2"), PinRef("C1", "1"),
        net_name="LINK", grid_um=1000, clearance_um=400,
        stroke_um=300, max_cells=20000,
    )
    if not route.ok:
        raise AssertionError(f"Unexpected routing failure: {route.diagnostics}")
    if validate_external_wires(circuit, route.external_graph("LINK"), parts, symbols):
        raise AssertionError("Calculated route fails external-wire ERC")
    wires = wire_obstacles(route)
    blocked = tuple(
        BoxObstacle(f"{item.reference}.body", box, owner=item.reference)
        for item, box in zip(circuit.components, keepouts, strict=True)
    )
    if validate_wire_clearance(wires, blocked=blocked, circuit=circuit):
        raise AssertionError("Calculated route violates body clearance")
    return circuit, keepouts, route


def wire_obstacles(route: TwoPinRoute) -> tuple[WireObstacle, ...]:
    return tuple(
        WireObstacle(f"auto-{i}", Line(a, b), stroke_um=300, net_name="LINK")
        for i, (a, b) in enumerate(zip(route.points, route.points[1:], strict=False))
    )


def report_json() -> str:
    circuit, keepouts, route = specimen()
    graph = route.external_graph("LINK")
    content = {
        "schema_version": 1,
        "status": "EXPERIMENTAL ROUTING",
        "algorithm": "bounded-orthogonal-dijkstra",
        "components": [
            {"reference": item.reference, "part_id": item.part_id}
            for item in circuit.components
        ],
        "net": {"name": "LINK", "members": ["R1.2", "C1.1"]},
        "grid_um": 1000,
        "clearance_um": 400,
        "stroke_um": 300,
        "keepouts_um": [
            [box.min_x, box.min_y, box.max_x, box.max_y] for box in keepouts
        ],
        "route_points_um": [[p.x, p.y] for p in route.points],
        "segments_um": [
            [[s.start.x, s.start.y], [s.end.x, s.end.y]]
            for s in graph.segments
        ],
        "wire_diagnostics": [],
        "clearance_diagnostics": [],
    }
    return json.dumps(content, indent=2, sort_keys=True) + "\n"


def specimen_svg(*, review: bool = False) -> str:
    circuit, _, route = specimen()
    _, symbols = definitions()
    xml = render_sheet_svg(
        circuit, symbols, SheetLayout((), ()),
        wires=wire_obstacles(route), review_overlay=review,
    )
    root = ET.fromstring(xml)
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    labels = ET.SubElement(root, f"{{{namespace}}}g", {
        "data-layer": "specimen-labels", "fill": "#000000",
        "font-family": "sans-serif", "font-size": "3.5",
        "text-anchor": "middle", "stroke": "none",
    })
    for item in circuit.components:
        label = ET.SubElement(labels, f"{{{namespace}}}text", {
            "data-owner": item.reference,
            "x": format_mm(item.origin.x),
            "y": format_mm(item.origin.y - 8000),
        })
        label.text = item.reference
    return ET.tostring(root, encoding="unicode") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, contents in (
        ("two-pin-clean.svg", specimen_svg()),
        ("two-pin-review.svg", specimen_svg(review=True)),
        ("two-pin-diagnostics.json", report_json()),
    ):
        path = args.output_dir / filename
        path.write_bytes(contents.encode("utf-8"))
        print(f"Created {path}")


if __name__ == "__main__":
    main()
