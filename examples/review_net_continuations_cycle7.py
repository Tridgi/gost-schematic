"""Cycle7 DRAFT two-sheet CTRL continuation; no invented physical connector.

Generated SVG and optional PNG are **editorial review artifacts**, not norm
approved; font ink boxes and ГОСТ form/arrow are outside this experiment.
"""

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point
from gost_schematic.electrical.netrefs import (
    ContinuationAddressBinding,
    ContinuationAddressKind,
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


def specimen_three_sheet() -> NetContinuationProject:
    """Eight local real pin stubs; three nets, four pairs and three sheets.

    CTRL has two independent continuation pairs over all three sheets.
    All parts/pin numbers are SYNTHETIC; there is no vendor pinout claim.
    """
    part_refs = ("DD1", "VT1", "DD3", "DA1", "DA2", "VT2", "DD2", "DA3")
    parts = tuple(ComponentInstance(ref, "SYNTHETIC_" + ref) for ref in part_refs)
    physical_nets = (
        Net("CTRL", (
            PinRef("DD1", "5"), PinRef("VT1", "G"),
            PinRef("DD3", "1"), PinRef("DA1", "2"),
        )),
        Net("REF", (PinRef("DA2", "3"), PinRef("VT2", "G"))),
        Net("ENABLE", (PinRef("DD2", "7"), PinRef("DA3", "2"))),
    )
    nets = tuple(NetIdentity("N-" + net.name, net.name, net.members)
                 for net in physical_nets)
    sheets = tuple(ContinuationSheet("S" + str(n), n) for n in (1, 2, 3))
    # Explicit, reciprocal continuation addresses: zone-based and real
    # element/pin address forms coexist; neither can forge Net connectivity.
    specs = (
        ("C1-OUT", "CTRL", "S1", 1, "1/D4", "2/B7",
         80000, 40000, "SOURCE", "DD1", "5", 60000),
        ("C1-IN", "CTRL", "S2", 2, "2/B7", "1/D4",
         140000, 40000, "TARGET", "VT1", "G", 160000),
        ("C2-OUT", "CTRL", "S2", 2, "DD3.1", "DA1.2",
         80000, 70000, "SOURCE", "DD3", "1", 60000),
        ("C2-IN", "CTRL", "S3", 3, "DA1.2", "DD3.1",
         140000, 70000, "TARGET", "DA1", "2", 160000),
        ("R-OUT", "REF", "S1", 1, "1/A6", "3/F2",
         80000, 100000, "SOURCE", "DA2", "3", 60000),
        ("R-IN", "REF", "S3", 3, "3/F2", "1/A6",
         140000, 100000, "TARGET", "VT2", "G", 160000),
        ("E-OUT", "ENABLE", "S2", 2, "2/C5", "3/E4",
         80000, 150000, "SOURCE", "DD2", "7", 60000),
        ("E-IN", "ENABLE", "S3", 3, "3/E4", "2/C5",
         140000, 150000, "TARGET", "DA3", "2", 160000),
    )
    endpoints = tuple(
        NetContinuationEndpoint(
            marker, "N-" + net_name, sheet_id, sheet_num, local, remote,
            Point(x, y), net_name, ContinuationDirection[direction],
        )
        for (marker, net_name, sheet_id, sheet_num, local, remote,
             x, y, direction, _, _, _) in specs
    )
    stubs = tuple(
        ContinuationStub(
            "WIRE-" + marker, marker, PinRef(ref, pin),
            Point(start_x, y), Point(x, y),
        )
        for (marker, _, _, _, _, _, x, y, _, ref, pin, start_x) in specs
    )
    pairs = (
        ContinuationPair("PAIR-C1", "C1-OUT", "C1-IN", ContinuationScope.GLOBAL),
        ContinuationPair("PAIR-C2", "C2-OUT", "C2-IN", ContinuationScope.GLOBAL),
        ContinuationPair("PAIR-R", "R-OUT", "R-IN", ContinuationScope.GLOBAL),
        ContinuationPair("PAIR-E", "E-OUT", "E-IN", ContinuationScope.GLOBAL),
    )
    address_bindings = tuple(
        ContinuationAddressBinding(
            marker,
            ContinuationAddressKind.ELEMENT_PIN
            if local in ("DD3.1", "DA1.2")
            else ContinuationAddressKind.SHEET_ZONE,
            ref if local in ("DD3.1", "DA1.2") else sheet_id,
            PinRef(ref, pin) if local in ("DD3.1", "DA1.2") else None,
        )
        for (marker, _, sheet_id, _, local, _, _, _, _, ref, pin, _) in specs
    )
    project = NetContinuationProject(
        Circuit(parts, physical_nets), nets, sheets, endpoints, pairs, stubs,
        schema_version=2, address_bindings=address_bindings,
    )
    anchors = {stub.pin: stub.start for stub in stubs}
    if validate_net_continuations(project, physical_pin_anchors=anchors):
        raise AssertionError("Three-sheet multi-Net demonstration is invalid")
    return project


def _elem(parent: ET.Element, tag: str, attrs: dict[str, str]) -> ET.Element:
    return ET.SubElement(parent, tag, attrs)


def sheet_svg(
    project: NetContinuationProject, sheet_id: str, *,
    font_path: str | Path | None = None, review_overlay: bool = False,
    external_keepouts: tuple[Box, ...] = (),
    review_connection_zones: bool = False,
) -> str:
    """View-only SVG; measured geometry checks optional actual layout obstacles.

    External keepouts include nearby components, page frame/title block and
    protected neighboring annotations, excluding authored pin contact openings.
    Green connection boxes are editor diagnostics, never printed conductors.
    """
    if type(external_keepouts) is not tuple or not all(
        isinstance(region, Box) for region in external_keepouts
    ):
        raise TypeError("external_keepouts must be tuple[Box]")
    if (external_keepouts or review_connection_zones) and font_path is None:
        raise ValueError("E3_CONT_MEASURED_PROFILE_REQUIRED")
    if review_connection_zones and not review_overlay:
        raise ValueError("E3_CONT_EDITOR_ZONES_REQUIRE_REVIEW")
    if font_path is not None:
        return _measured_sheet_svg(
            project, sheet_id, font_path, review_overlay,
            external_keepouts, review_connection_zones,
        )
    if validate_net_continuations(project):
        raise ValueError("Must validate typed net identity before drawing")
    sheet = next(x for x in project.sheets if x.id == sheet_id)
    # Use exactly ONE namespace declaration, independent of the global
    # ElementTree registry and import order in PAINT/other SVG modules.
    root = ET.Element("svg", {
        "xmlns": SVG_NS, "width": "210mm", "height": "297mm",
        "viewBox": "0 0 210000 297000", "data-schema": "E3",
        "data-source": "DRAFT-only-sheet-continuation-not-a-connector",
        "data-approval": "DRAFT_UNMEASURED_FONT",
        "data-sheet-id": sheet.id, "data-sheet-number": str(sheet.number),
    })
    ET.SubElement(root, "title").text = (
        f"Cycle7 DRAFT physical net continuation sheet {sheet.number}"
    )
    ET.SubElement(root, "desc").text = (
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



def _measured_sheet_svg(
    project: NetContinuationProject, sheet_id: str,
    font_path: str | Path, review_overlay: bool,
    external_keepouts: tuple[Box, ...],
    review_connection_zones: bool,
) -> str:
    """Fail-closed OpenGost Type A preview, measured actual ink not character counts.

    Arrows and project sheet/zone address notation remain ESKD-review DRAFT.
    Marker/connector geometry never creates or infers a physical PinRef.
    """
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    diagnostics = validate_net_continuations(project)
    if diagnostics:
        raise ValueError("; ".join(x.code for x in diagnostics))
    sheet = next((s for s in project.sheets if s.id == sheet_id), None)
    if sheet is None:
        raise ValueError("E3_CONT_SHEET_UNKNOWN")
    label_font = inspect_type_a_font(font_path, h_um=3500)
    address_font = inspect_type_a_font(font_path, h_um=2500)
    if label_font.style.font_sha256 != address_font.style.font_sha256:
        raise ValueError("E3_CONT_FONT_SHA_MISMATCH")
    measure = PillowTextMeasurer()
    padding_um = 1000  # Editorial clearance, not a mandatory GOST constant.
    page_safe = Box(10000, 10000, 200000, 287000)  # A4, editorial 10 mm area.
    root = ET.Element("svg", {
        "xmlns": SVG_NS, "width": "210mm", "height": "297mm",
        "viewBox": "0 0 210000 297000",
        "data-schema": "E3",
        "data-approval": "DRAFT_MEASURED_TYPE_A_ESKD_PENDING",
        "data-source": "continuation-is-not-a-physical-connector",
        "data-sheet-id": sheet.id, "data-sheet-number": str(sheet.number),
        "data-font-sha256": label_font.style.font_sha256,
    })
    ET.SubElement(root, "title").text = f"DRAFT measured continuation, sheet {sheet.number}"
    ET.SubElement(root, "desc").text = (
        "Actual OpenGost Type A glyph ink/keepouts; GOST marker geometry and "
        "sheet-address profile await ESKD. Only authored local wires are electrical."
    )
    endpoints = {e.id: e for e in project.endpoints if e.sheet_id == sheet_id}
    # Precise text rectangles are drawing keepouts; they cannot establish a Net.
    text_regions: list[tuple[str, Box, Box]] = []
    electrical_regions: list[Box] = []
    graphic_regions: list[tuple[str, str, Box]] = []
    connection_zones: list[tuple[str, Box]] = []

    def place_text(
        marker: NetContinuationEndpoint, kind: str, content: str,
        style, baseline_y: int, alignment: str,
    ) -> None:
        glyph = measure.measure(content, style).ink_box
        if alignment == "center":
            baseline_x = marker.anchor.x - (glyph.min_x + glyph.max_x) // 2
        elif alignment == "right-of-arrow":
            baseline_x = marker.anchor.x + 3500 - glyph.min_x
        else:
            baseline_x = marker.anchor.x - 3500 - glyph.max_x
        baseline = Point(baseline_x, baseline_y)
        ink = glyph.translated(baseline)
        reserved = ink.expanded(padding_um)
        if not (
            page_safe.includes(Point(reserved.min_x, reserved.min_y))
            and page_safe.includes(Point(reserved.max_x, reserved.max_y))
        ):
            raise ValueError(f"E3_CONT_TEXT_PAGE_OVERFLOW: {marker.id} {kind}")
        text_regions.append((marker.id + ":" + kind, ink, reserved))
        _elem(root, "text", {
            "x": str(baseline.x), "y": str(baseline.y),
            "font-family": style.font_family, "font-style": style.font_style,
            "font-size": str(style.em_height_um),
            "fill": "black", "stroke": "none",
            "data-role": "measured-" + kind,
            "data-marker-id": marker.id,
            "data-font-sha256": style.font_sha256,
            "data-ink-box": ",".join(str(v) for v in (
                ink.min_x, ink.min_y, ink.max_x, ink.max_y,
            )),
            "data-protected-box": ",".join(str(v) for v in (
                reserved.min_x, reserved.min_y, reserved.max_x, reserved.max_y,
            )),
        }).text = content

    for stub in project.stubs:
        marker = endpoints.get(stub.endpoint_id)
        if marker is None:
            continue
        if stub.start.y != stub.end.y:
            raise ValueError("E3_CONT_VERTICAL_MARKER_PROFILE_BLOCKED")
        outward = 1 if stub.end.x > stub.start.x else -1
        x, y = marker.anchor.x, marker.anchor.y
        _elem(root, "line", {
            "x1": str(stub.start.x), "y1": str(stub.start.y),
            "x2": str(stub.end.x), "y2": str(stub.end.y),
            "stroke": "black", "stroke-width": "300",
            "data-role": "explicit-real-wire-stub", "data-stub-id": stub.id,
            "data-pin-ref": f"{stub.pin.reference}.{stub.pin.number}",
            "data-net-id": marker.net_id,
        })
        # Review-only solid arrow; final GOST proportions need ESKD approval.
        back = x - outward * 2000
        _elem(root, "path", {
            "d": f"M {back} {y-1100} L {x} {y} L {back} {y+1100}",
            "fill": "none", "stroke": "black", "stroke-width": "150",
            "data-role": "DRAFT-visual-continuation-marker",
            "data-marker-id": marker.id, "data-net-id": marker.net_id,
        })
        wire_box = Box(
            min(stub.start.x, stub.end.x) - 150, y - 150,
            max(stub.start.x, stub.end.x) + 150, y + 150,
        )
        arrow_box = Box(
            min(back, x) - 150, y - 1250, max(back, x) + 150, y + 1250,
        )
        electrical_regions.extend((wire_box, arrow_box))
        graphic_regions.extend((
            (marker.id, "wire", wire_box),
            (marker.id, "arrow", arrow_box),
        ))
        connection_zones.append((
            marker.id, Box(x - 1000, y - 1000, x + 1000, y + 1000),
        ))
        place_text(
            marker, "net-label", marker.label, label_font.style,
            y - 6000, "center",
        )
        place_text(
            marker, "remote-address", marker.target_address, address_font.style,
            y + 950, "right-of-arrow" if outward == 1 else "left-of-arrow",
        )
    for name, role, box in graphic_regions:
        if not (page_safe.includes(Point(box.min_x, box.min_y))
                and page_safe.includes(Point(box.max_x, box.max_y))):
            raise ValueError(f"E3_CONT_GRAPHIC_PAGE_OVERFLOW: {name} {role}")
        if any(box.overlaps(obstacle) for obstacle in external_keepouts):
            raise ValueError(f"E3_CONT_GRAPHIC_EXTERNAL_COLLISION: {name} {role}")
        if any(
            box.overlaps(other)
            for owner, _, other in graphic_regions if owner != name
        ):
            raise ValueError(f"E3_CONT_GRAPHIC_GRAPHIC_COLLISION: {name} {role}")
    for i, (name, _ink, protected) in enumerate(text_regions):
        if any(protected.overlaps(obstacle) for obstacle in external_keepouts):
            raise ValueError(f"E3_CONT_TEXT_EXTERNAL_COLLISION: {name}")
        if any(protected.overlaps(occupied) for occupied in electrical_regions):
            raise ValueError(f"E3_CONT_TEXT_WIRE_COLLISION: {name}")
        if any(
            protected.overlaps(other[2])
            for j, other in enumerate(text_regions) if j != i
        ):
            raise ValueError(f"E3_CONT_TEXT_TEXT_COLLISION: {name}")
        if review_overlay:
            _elem(root, "rect", {
                "x": str(protected.min_x), "y": str(protected.min_y),
                "width": str(protected.max_x - protected.min_x),
                "height": str(protected.max_y - protected.min_y),
                "fill": "none", "stroke": "#009577",
                "stroke-width": "120", "stroke-dasharray": "600,400",
                "data-role": "review-text-keepout", "data-owner": name,
            })
    if review_connection_zones:
        for marker_id, zone in connection_zones:
            _elem(root, "rect", {
                "x": str(zone.min_x), "y": str(zone.min_y),
                "width": str(zone.max_x - zone.min_x),
                "height": str(zone.max_y - zone.min_y),
                "stroke": "#009577", "fill": "none",
                "stroke-width": "120", "stroke-dasharray": "350,250",
                "data-role": "editor-only-connection-keepout",
                "data-marker-id": marker_id, "data-print": "false",
            })
    return ET.tostring(root, encoding="unicode") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--png", action="store_true", help="Create 300-DPI DRAFT PNG")
    parser.add_argument("--font-file", type=Path, help="Exact OpenGost Type A font")
    parser.add_argument("--review-overlay", action="store_true")
    parser.add_argument("--connection-zones", action="store_true",
                        help="Editor-only review targets, never printed")
    parser.add_argument("--three-sheet", action="store_true",
                        help="Three sheets, three real nets, four explicit pairs")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    project = specimen_three_sheet() if args.three_sheet else specimen()
    source = netrefs_to_json(project)
    if netrefs_to_json(netrefs_from_json(source, project.circuit)) != source:
        raise AssertionError("Continuation JSON failed exact roundtrip")
    filename = "three-sheet-nets.json" if args.three_sheet else "two-sheet-ctrl.json"
    (args.output_dir / filename).write_text(source, encoding="utf-8")
    for sheet in project.sheets:
        name = f"sheet-{sheet.number}"
        svg = sheet_svg(
            project, sheet.id, font_path=args.font_file,
            review_overlay=args.review_overlay,
            review_connection_zones=args.connection_zones,
        )
        (args.output_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
        if args.png:
            import resvg_py

            image = resvg_py.svg_to_bytes(svg_string=svg, dpi=300)
            (args.output_dir / f"{name}-300dpi.png").write_bytes(image)
    print(
        "DRAFT E3: "
        f"{len(project.circuit.nets)} real Circuit.Nets, "
        f"{len(project.pairs)} explicit pairs on {len(project.sheets)} sheets; "
        "no phantom physical connector or invisible cross-sheet conductor"
    )


if __name__ == "__main__":
    main()
