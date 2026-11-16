"""Validated gscad-project v2 to physical SVG/PNG. No canvas screenshots.

SymbolDefinition.graphics is the sole UGO ink source; source Nets/PinRef
and authored wire segments are taken verbatim. Export does not route.
"""
from __future__ import annotations

import json
from dataclasses import replace
from itertools import pairwise
from xml.etree import ElementTree as ET

from ui.bridge.export.canonical import (
    PAGE_UM,
    ExportError,
    ExportRequest,
    ExportResult,
    export,
    mm,
)

_S = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")


def _draw_validated(document: dict, sheet_id: str) -> bytes:
    """Private converter: caller has already invoked #122 validate()."""
    from ui.editor.src.model.contract import pin_world

    project = document["project"]
    sheet = next((s for s in project["sheets"] if s["id"] == sheet_id), None)
    if sheet is None:
        raise ExportError("UNKNOWN_SHEET: " + sheet_id)
    components = {c["id"]: c for c in project["components"]}
    symbols = {s["id"]: s for s in project["symbol_definitions"]}
    nets = {n["id"]: n for n in project["nets"]}
    layers = {item["id"]: item for item in sheet["layers"]}

    def printable(layer_id: str) -> bool:
        layer = layers[layer_id]
        return (layer["visible"] and layer["printable"] and
                layer["kind"] != "diagnostics")

    # Only actual source content, not UI grid/selection/camera.
    root = ET.Element(_S + "svg", {
        "data-source-model": "gscad-project-v2",
        "data-sheet-id": sheet_id,
        "data-source-status": project["provenance"]["status"],
        "data-source-net-count": str(len(nets)),
        "data-authored-wire-count": str(len(sheet["wires"])),
    })
    extents: list[tuple[int, int, int, int]] = []

    def bounds(points: list[tuple[int, int]], stroke_um: int) -> None:
        if stroke_um <= 0:
            raise ExportError("BAD_STROKE_WIDTH")
        pad = (stroke_um + 1) // 2 + 2
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        extents.append((min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad))

    def line(parent: ET.Element, a: tuple[int, int], b: tuple[int, int],
             width: int, **metadata: str) -> None:
        if a == b:
            raise ExportError("ZERO_LENGTH_GRAPHIC")
        ET.SubElement(parent, _S + "line", {
            "x1": mm(a[0]), "y1": mm(a[1]),
            "x2": mm(b[0]), "y2": mm(b[1]),
            "stroke": "#000000", "stroke-width": mm(width),
            "stroke-linecap": "butt", "fill": "none", **metadata,
        })
        bounds([a,b], width)

    def polyline(parent: ET.Element, points: list[tuple[int, int]],
                 width: int, **metadata: str) -> None:
        for a, b in pairwise(points):
            line(parent, a, b, width, **metadata)

    for inst in sheet["instances"]:
        if not printable(inst["layer_id"]):
            continue
        component = components[inst["component_id"]]
        symbol = symbols[inst["symbol_id"]]
        group = ET.SubElement(root, _S + "g", {
            "data-layer": "symbols", "data-instance-id": inst["id"],
            "data-component-id": component["id"], "data-reference": component["refdes"],
            "data-symbol-id": symbol["id"],
            "data-pinrefs": json.dumps([
                [component["id"], pin["physical_pin_number"]] for pin in symbol["pins"]
            ], ensure_ascii=False, separators=(",", ":")),
            "fill": "none", "stroke": "#000000",
        })
        for primitive in symbol["graphics"]:
            kind = primitive["kind"]
            points = [pin_world(inst,p) for p in primitive["points_um"]]
            width = primitive["stroke_um"]
            if kind == "rect":
                if len(points) != 2:
                    raise ExportError("RECT_NEEDS_2_CORNERS")
                x0,x1 = sorted((points[0][0],points[1][0]))
                y0,y1 = sorted((points[0][1],points[1][1]))
                if x0 == x1 or y0 == y1:
                    raise ExportError("DEGENERATE_RECT")
                ET.SubElement(group, _S + "rect", {
                    "x": mm(x0), "y": mm(y0),
                    "width": mm(x1-x0), "height": mm(y1-y0),
                    "stroke": "#000000", "stroke-width": mm(width), "fill": "none",
                })
                bounds([(x0,y0),(x1,y1)],width)
            elif kind in ("line", "polyline"):
                if kind == "line" and len(points) != 2:
                    raise ExportError("LINE_NEEDS_2_POINTS")
                polyline(group, points, width)
            else:
                raise ExportError("UNSUPPORTED_SYMBOL_PRIMITIVE: " + kind)

    for wire in sheet["wires"]:
        if not printable(wire["layer_id"]):
            continue
        net = nets[wire["net_id"]]
        group = ET.SubElement(root, _S + "g", {
            "data-layer": "wires", "data-wire-id": wire["id"],
            "data-net": net["name"], "data-net-id": net["id"],
            "data-pinrefs": json.dumps([
                [v["anchor"]["component_id"],v["anchor"]["physical_pin_number"]]
                for v in wire["vertices"] if v["anchor"]["kind"] == "pin"
            ], ensure_ascii=False, separators=(",", ":")),
        })
        vertices = {v["id"]:v for v in wire["vertices"]}
        for segment in wire["segments"]:
            a = tuple(vertices[segment["from_vertex_id"]]["at_um"])
            b = tuple(vertices[segment["to_vertex_id"]]["at_um"])
            if a[0] != b[0] and a[1] != b[1]:
                raise ExportError("NONORTHOGONAL_WIRE")
            line(group, a, b, 300, **{"data-segment-id":segment["id"]})

    for junction in sheet["junctions"]:
        if printable(junction["layer_id"]):
            x,y = junction["at_um"]
            ET.SubElement(root, _S + "circle", {
                "data-layer":"explicit-junctions",
                "data-junction-id":junction["id"],
                "data-net":nets[junction["net_id"]]["name"],
                "cx":mm(x),"cy":mm(y),"r":"0.55",
                "fill":"#000000","stroke":"none",
            })
            bounds([(x-550,y-550),(x+550,y+550)],1)
    # Splice is invisible; geometric X/T never creates a dot.

    for graphic in sheet["graphics"]:
        if not printable(graphic["layer_id"]):
            continue
        group = ET.SubElement(root, _S + "g", {
            "data-layer":"graphics", "data-id":graphic["id"],
            "data-kind":graphic["kind"], "data-electrical":"false",
        })
        points = [tuple(p) for p in graphic["points_um"]]
        if graphic["kind"] == "line" and len(points) != 2:
            raise ExportError("LINE_NEEDS_2_POINTS")
        polyline(group,points,graphic["stroke_um"])

    for name in ("texts","labels"):
        for item in sheet[name]:
            if not printable(item["layer_id"]) or not item["text"]:
                continue
            x,y = item["at_um"]
            h = item.get("height_um",3500)
            # Conservative viewport envelope, NOT a verified font-ink box.
            extents.append((x-h,y-2*h,x+(len(item["text"])+1)*h,y+h))
            label = ET.SubElement(root, _S + "text", {
                "data-layer":"annotations", "data-id":item["id"],
                "x":mm(x), "y":mm(y), "font-size":mm(h),
                "font-family":"OpenGost Type A",
                "fill":"#000000","stroke":"none",
            })
            label.text = item["text"]
            if item.get("role") == "net_annotation":
                label.set("data-net",nets[item["net_id"]]["name"])

    if not extents:
        extents.append((0,0,1000,1000))
    x0 = min(e[0] for e in extents)
    y0 = min(e[1] for e in extents)
    x1 = max(e[2] for e in extents)
    y1 = max(e[3] for e in extents)
    width,height = x1-x0,y1-y0
    root.attrib.update({
        "width":mm(width)+"mm","height":mm(height)+"mm",
        "viewBox":" ".join(map(mm,(x0,y0,width,height))),
    })
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)+b"\n"


def render_v2_source(document: dict, sheet_id: str, *, expected_project_sha256: str) -> bytes:
    """Validate all physical PinRefs, anchors and source inventory before export."""
    from ui.editor.src.model.contract import digest, validate

    validate(document)
    if digest(document) != expected_project_sha256:
        raise ExportError("SOURCE_SHA_CONFLICT: project snapshot changed")
    return _draw_validated(document,sheet_id)


def export_v2(document: dict, sheet_id: str, request: ExportRequest,
              *, expected_project_sha256: str) -> ExportResult:
    """Preserve exact physical sheet X/Y; render PNG from the canonical SVG."""
    # Reject page mismatches instead of silently scaling or cropping an A3
    # snapshot through an unrelated A4/A2 print profile.
    sheet = next((s for s in document["project"]["sheets"] if s["id"] == sheet_id), None)
    if sheet is None:
        raise ExportError("UNKNOWN_SHEET: " + sheet_id)
    page_size = PAGE_UM[request.page]
    if request.orientation == "landscape":
        page_size = page_size[::-1]
    if tuple(sheet["frame"]["size_um"]) != page_size:
        raise ExportError("SHEET_PAGE_SIZE_MISMATCH: no implicit paper resize")
    source = render_v2_source(document,sheet_id,
                              expected_project_sha256=expected_project_sha256)
    if request.source_project_sha256 not in (None,expected_project_sha256):
        raise ExportError("REQUEST_SOURCE_SHA_CONFLICT")
    return export(source,replace(request,source_project_sha256=expected_project_sha256,
                                 page_coords=True))
