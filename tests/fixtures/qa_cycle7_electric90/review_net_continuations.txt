"""Cycle7 DRAFT two-sheet CTRL continuation; no invented physical connector.

Generated SVG and optional PNG are **editorial review artifacts**, not norm
approved; font ink boxes and ГОСТ form/arrow are outside this experiment.
"""

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import (
    ContinuationDirection,
    ContinuationPair,
    ContinuationScope,
    ContinuationSheet,
    ContinuationStub,
    NetContinuationEndpoint,
    NetContinuationProject,
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.electrical.netrefs_serde import (
    netrefs_from_json,
    netrefs_to_json,
)
from gost_schematic.model.circuit import (
    Circuit,
    ComponentInstance,
    Net,
    PinRef,
)

SVG_NS = "http://www.w3.org/2000/svg"


def specimen() -> NetContinuationProject:
    """Two visible local wires, ONE pre-existing real CTRL Circuit.Net."""
    dd = ComponentInstance("DD1", "SYNTHETIC_IC_DD")
    vt = ComponentInstance("VT1", "SYNTHETIC_FET_VT")
    ctrl = Net("CTRL", (PinRef("DD1", "5"), PinRef("VT1", "G")))
    circuit = Circuit((dd, vt), (ctrl,))
    nets = (NetIdentity("N-CTRL-001", ctrl.name, ctrl.members),)
    sheets = (ContinuationSheet("S1", 1), ContinuationSheet("S2", 2))
    endpoints = (
        NetContinuationEndpoint(
            "M-OUT", "N-CTRL-001", "S1", 1,
            "1/D4", "2/B7", Point(80000, 40000), "CTRL",
            ContinuationDirection.SOURCE,
        ),
        NetContinuationEndpoint(
            "M-IN", "N-CTRL-001", "S2", 2,
            "2/B7", "1/D4", Point(140000, 40000), "CTRL",
            ContinuationDirection.TARGET,
        ),
    )
    pairs = (ContinuationPair(
        "PAIR-CTRL", "M-OUT", "M-IN", ContinuationScope.GLOBAL,
    ),)
    stubs = (
        ContinuationStub(
            "WIRE-DD", "M-OUT", PinRef("DD1", "5"),
            Point(60000, 40000), Point(80000, 40000),
        ),
        ContinuationStub(
            "WIRE-VT", "M-IN", PinRef("VT1", "G"),
            Point(160000, 40000), Point(140000, 40000),
        ),
    )
    project = NetContinuationProject(circuit, nets, sheets, endpoints, pairs, stubs)
    anchors = {PinRef("DD1", "5"): Point(60000, 40000),
               PinRef("VT1", "G"): Point(160000, 40000)}
    if validate_net_continuations(project, physical_pin_anchors=anchors):
        raise AssertionError("Two-sheet continuation example is semantically invalid")
    return project


def _elem(parent: ET.Element, tag: str, attrs: dict[str, str]) -> ET.Element:
    return ET.SubElement(parent, f"{{{SVG_NS}}}{tag}", attrs)


def sheet_svg(project: NetContinuationProject, sheet_id: str) -> str:
    """Diagnostic-free view-only SVG: no invisible cross-sheet conductor."""
    if validate_net_continuations(project):
        raise ValueError("Must validate typed net identity before drawing")
    sheet = next(x for x in project.sheets if x.id == sheet_id)
    # ElementTree namespace registry is process-global; other pytest suites
    # register their own defaults. Reset it for byte-stable goldens on CI.
    ET.register_namespace("", SVG_NS)
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": "210mm", "height": "297mm",
        "viewBox": "0 0 210000 297000", "data-schema": "E3",
        "data-source": "DRAFT-only-sheet-continuation-not-a-connector",
        "data-approval": "DRAFT_UNMEASURED_FONT",
        "data-sheet-id": sheet.id, "data-sheet-number": str(sheet.number),
    })
    ET.SubElement(root, f"{{{SVG_NS}}}title").text = (
        f"Cycle7 DRAFT physical net continuation sheet {sheet.number}"
    )
    ET.SubElement(root, f"{{{SVG_NS}}}desc").text = (
        "Separate visible wire stubs; no hidden conductor between sheets. "
        "Unmeasured text Type A; ESKD signoff pending."
    )
    ends = {x.id: x for x in project.endpoints if x.sheet_id == sheet.id}
    for stub in project.stubs:
        marker = ends.get(stub.endpoint_id)
        if marker is None:
            continue
        _elem(root, "line", {
            "x1": str(stub.start.x), "y1": str(stub.start.y),
            "x2": str(stub.end.x), "y2": str(stub.end.y),
            "stroke": "black", "stroke-width": "300",
            "data-role": "explicit-real-wire-stub",
            "data-pin-ref": f"{stub.pin.reference}.{stub.pin.number}",
            "data-net-id": marker.net_id, "data-stub-id": stub.id,
        })
        _elem(root, "path", {
            "d": (
                f"M {marker.anchor.x-1000} {marker.anchor.y-2000} "
                f"L {marker.anchor.x} {marker.anchor.y} "
                f"L {marker.anchor.x-1000} {marker.anchor.y+2000}"
                if marker.direction is ContinuationDirection.SOURCE else
                f"M {marker.anchor.x+1000} {marker.anchor.y-2000} "
                f"L {marker.anchor.x} {marker.anchor.y} "
                f"L {marker.anchor.x+1000} {marker.anchor.y+2000}"
            ),
            "stroke": "black", "stroke-width": "300", "fill": "none",
            "data-role": "DRAFT-visual-continuation-marker",
            "data-marker-id": marker.id,
        })
        _elem(root, "text", {
            "x": str(marker.anchor.x),
            "y": str(marker.anchor.y - 6000),
            "font-family": "OpenGost Type A, sans-serif",
            "font-size": "3500", "text-anchor": "middle",
            "data-role": "unmeasured-net-label",
        }).text = marker.label
        _elem(root, "text", {
            "x": str(marker.anchor.x),
            "y": str(marker.anchor.y + 6500),
            "font-family": "OpenGost Type A, sans-serif",
            "font-size": "2500", "text-anchor": "middle",
            "data-role": "unmeasured-remote-address",
        }).text = marker.target_address
    return ET.tostring(root, encoding="unicode") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--png", action="store_true", help="Create 300-DPI DRAFT PNG")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    project = specimen()
    source = netrefs_to_json(project)
    if netrefs_to_json(netrefs_from_json(source, project.circuit)) != source:
        raise AssertionError("Continuation JSON failed exact roundtrip")
    (args.output_dir / "two-sheet-ctrl.json").write_text(source, encoding="utf-8")
    for sheet in project.sheets:
        name = f"sheet-{sheet.number}"
        svg = sheet_svg(project, sheet.id)
        (args.output_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
        if args.png:
            import resvg_py

            image = resvg_py.svg_to_bytes(svg_string=svg, dpi=300)
            (args.output_dir / f"{name}-300dpi.png").write_bytes(image)
    print("DRAFT CTRL: one physical Circuit.Net, 2 separate visible sheet fragments")


if __name__ == "__main__":
    main()
