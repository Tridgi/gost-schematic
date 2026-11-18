"""Real SVG sheet renderer and vector-cropped PNG for stored E3 revisions."""
import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Line
from gost_schematic.core.units import format_mm
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.rendering.sheet_svg import render_sheet_svg

from .catalog import CatalogResolver, ProjectError, digest
from .contracts import SchematicProject

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True, slots=True)
class ProjectView:
    svg: str
    png: bytes
    metadata: dict[str, Any]


def _mm(value: int) -> str:
    return format(Decimal(value) / 1000, "f")


def _view_box(svg: str) -> Box:
    root = ET.fromstring(svg)
    x, y, width, height = [int(Decimal(v) * 1000)
                           for v in root.attrib["viewBox"].split()]
    return Box(x, y, x + width, y + height)


def _component_bounds(project: SchematicProject, catalog: CatalogResolver,
                      reference: str) -> Box:
    found = next((c for c in project.circuit.components if c.reference == reference), None)
    if found is None:
        raise ProjectError("UNKNOWN_COMPONENT", reference)
    _, symbol = catalog.resolve(found.part_id)
    body = found.transform.box(symbol.body_keepout).translated(found.origin)
    pins = list(found.pin_positions(symbol).values())
    left = min([body.min_x, *(p.x for p in pins)]) - 5000
    right = max([body.max_x, *(p.x for p in pins)]) + 5000
    top = body.min_y - 10000
    bottom = max([body.max_y, *(p.y for p in pins)]) + 3000
    return Box(left, top, right, bottom)


def render(project: SchematicProject, catalog: CatalogResolver, *, mode: str = "clean",
           reference: str | None = None, max_px: int = 1600,
           target_dpi: int = 500) -> ProjectView:
    if mode not in ("clean", "diagnostic"):
        raise ProjectError("INVALID_MODE", mode)
    if type(max_px) is not int or not 64 <= max_px <= 4096:
        raise ProjectError("IMAGE_TOO_LARGE", "Expected max_px 64..4096")
    if type(target_dpi) is not int or not 72 <= target_dpi <= 600:
        raise ProjectError("INVALID_DPI", "Expected target_dpi 72..600")
    _, symbols = catalog.verify(list(project.catalog_lock))
    by_part = {lock["part_id"]: symbols[lock["symbol_id"]]
               for lock in project.catalog_lock}
    obstacles = tuple(
        WireObstacle(f"project-wire-{i}", Line(w.start, w.end),
                     stroke_um=project.stroke_widths_um[i], net_name=w.net_name)
        for i, w in enumerate(project.graph.segments)
    )
    svg = render_sheet_svg(
        project.circuit, by_part, SheetLayout((), ()),
        wires=obstacles, review_overlay=mode == "diagnostic",
    )
    root = ET.fromstring(svg)
    values = [Decimal(number) for number in root.attrib["viewBox"].split()]
    x, y, width, height = values
    root.set("viewBox", f"{x - 6:g} {y - 6:g} {width + 12:g} {height + 12:g}")
    root.set("width", f"{width + 12:g}mm")
    root.set("height", f"{height + 12:g}mm")
    junction_layer = ET.SubElement(root, f"{{{SVG_NS}}}g", {
        "data-layer": "explicit-junctions", "fill": "#000000", "stroke": "none",
    })
    for point in project.graph.junctions:
        ET.SubElement(junction_layer, f"{{{SVG_NS}}}circle", {
            "data-kind": "authored-junction", "cx": format_mm(point.x),
            "cy": format_mm(point.y), "r": "0.55",
        })
    labels_layer = ET.SubElement(root, f"{{{SVG_NS}}}g", {
        "data-layer": "project-refdes", "fill": "#222222", "stroke": "none",
        "font-family": "sans-serif", "font-size": "3.5", "text-anchor": "middle",
    })
    for row in project.labels:
        label = ET.SubElement(labels_layer, f"{{{SVG_NS}}}text", {
            "data-owner": row["text"], "x": format_mm(row["at_um"][0]),
            "y": format_mm(row["at_um"][1]),
        })
        label.text = row["text"]
    source_svg = ET.tostring(root, encoding="unicode") + "\n"
    source_hash = hashlib.sha256(source_svg.encode()).hexdigest()
    sheet = _view_box(source_svg)
    region = sheet
    if reference is not None:
        region = _component_bounds(project, catalog, reference).expanded(3000)
        try:
            region = Box(max(region.min_x, sheet.min_x),
                         max(region.min_y, sheet.min_y),
                         min(region.max_x, sheet.max_x),
                         min(region.max_y, sheet.max_y))
        except ValueError as exc:
            raise ProjectError("REGION_OUTSIDE_SHEET", reference) from exc
    width_um, height_um = region.max_x - region.min_x, region.max_y - region.min_y
    if reference is None:
        scale = Decimal(max_px) / max(width_um, height_um)
    else:
        scale = Decimal(target_dpi) / 25400
    width_px = max(1, int((Decimal(width_um) * scale).to_integral_value(ROUND_HALF_UP)))
    height_px = max(1, int((Decimal(height_um) * scale).to_integral_value(ROUND_HALF_UP)))
    if max(width_px, height_px) > 4096 or width_px * height_px > 12_000_000:
        raise ProjectError("IMAGE_TOO_LARGE", "View exceeds bounded raster budget")
    root.set("viewBox", " ".join(_mm(v) for v in (
        region.min_x, region.min_y, width_um, height_um,
    )))
    root.set("width", _mm(width_um) + "mm")
    root.set("height", _mm(height_um) + "mm")
    root.insert(1, ET.Element(f"{{{SVG_NS}}}rect", {
        "x": _mm(region.min_x), "y": _mm(region.min_y),
        "width": _mm(width_um), "height": _mm(height_um), "fill": "#ffffff",
        "data-layer": "viewport-background",
    }))
    view_svg = ET.tostring(root, encoding="unicode") + "\n"
    root.set("width", str(width_px))
    root.set("height", str(height_px))
    try:
        import resvg_py
        png = resvg_py.svg_to_bytes(
            svg_string=ET.tostring(root, encoding="unicode"),
            width=width_px, height=height_px,
        )
    except ImportError as exc:
        raise ProjectError("RASTERIZER_UNAVAILABLE", "Install [mcp] extra") from exc
    except Exception as exc:
        raise ProjectError("RASTERIZATION_FAILED", type(exc).__name__) from exc
    if len(png) > 8_000_000 or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ProjectError("RASTERIZATION_FAILED", "Invalid PNG output")
    selector = {"component": reference} if reference is not None else {"all": True}
    view_id = digest(json.dumps({
        "project_revision": project.revision, "source_svg": source_hash,
        "selector": selector, "mode": mode, "pixels": [width_px, height_px],
    }, sort_keys=True).encode())[:24]
    return ProjectView(view_svg, png, {
        "schema_version": 1, "project_id": project.project_id,
        "project_revision": project.revision, "project_kind": "E3",
        "source": "restored Circuit + ExternalWireGraph + locked physical catalog",
        "source_svg_sha256": source_hash,
        "view_svg_sha256": hashlib.sha256(view_svg.encode()).hexdigest(),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "view_id": view_id, "selector": selector,
        "bbox_mm": [_mm(v) for v in (
            region.min_x, region.min_y, region.max_x, region.max_y,
        )],
        "pixels": [width_px, height_px], "mime_type": "image/png",
        "rasterizer": "resvg_py",
        "font_warning": "Specimen refdes sans-serif, not approved GOST Type A",
    })
