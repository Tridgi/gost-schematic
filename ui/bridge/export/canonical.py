"""Safe deterministic page compositor for existing GOST Schematic Python SVG.

This is an R1 export bridge, not a gscad-project v2 serializer. Source electrical
identity and authentic symbol geometry come from the existing Python engine;
this module never infers connectivity, creates UGO, or consumes editor DOM.

The source is expected to be output of render_sheet_svg or
render_external_wire_sheet (review_overlay=False / diagnostic=False).
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
S = "{" + SVG_NS + "}"
ET.register_namespace("", SVG_NS)

PAGE_UM = {"A4": (210_000, 297_000), "A3": (297_000, 420_000),
           "A2": (420_000, 594_000)}
_ALLOWED_TAGS = frozenset({"svg", "g", "line", "rect", "circle", "path", "text",
                           "title", "desc", "metadata", "polyline"})
_ALLOWED_ATTRS = frozenset({
    "width", "height", "viewBox", "version", "x", "y", "x1", "y1",
    "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill",
    "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap", "stroke-dasharray",
    "font-size", "font-family", "font-style", "text-anchor", "id",
})
_FORBIDDEN_LAYERS = frozenset({"geometry-review", "external-wire-layout-diagnostics",
                               "selection", "editor", "grid", "pin-markers",
                               "handles", "drag-preview", "viewport"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_COLOR = re.compile(r"^(?:none|transparent|black|white|#[0-9a-fA-F]{3,8})$")
_SVG_PATH = re.compile(r"^[\s0-9,.+\-AaMmLlHhVvCcQqTtZzSs]*$")
_MAX_XML_BYTES = 16 * 1024 * 1024
_MAX_NODES = 100_000
_MAX_PIXELS = 60_000_000


class ExportError(ValueError):
    """A fail-closed input, geometry, or rendering precondition."""


def mm(um: int) -> str:
    """Exact Decimal conversion; one integer micrometre becomes 0.001 mm."""
    if type(um) is not int or abs(um) > 1_000_000_000:
        raise ExportError("Coordinates must be signed integer micrometres within ±1e9")
    return format(Decimal(um) / 1_000, "f")


def _from_mm(text: str) -> int:
    try:
        raw = Decimal(text)
        scaled = raw * 1000
        if not raw.is_finite() or scaled != scaled.to_integral_value():
            raise ExportError("Length is not an exact integer micrometre")
        result = int(scaled)
        mm(result)
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ExportError("Invalid physical millimetre coordinate") from exc


def pixels(um: int, dpi: int) -> int:
    if type(dpi) is not int or not 72 <= dpi <= 600 or type(um) is not int or um <= 0:
        raise ExportError("DPI must be 72..600 and physical size positive integer µm")
    return int((Decimal(um) * dpi / 25_400).quantize(Decimal(1),
                                                      rounding=ROUND_HALF_UP))


def _rect(parent: ET.Element, x: int, y: int, w: int, h: int,
          *, stroke: str = "#000000", width_um: int = 700,
          kind: str = "") -> ET.Element:
    if min(w, h) <= 0:
        raise ExportError("Non-positive rectangle size")
    attrs = {"x": mm(x), "y": mm(y), "width": mm(w), "height": mm(h),
             "fill": "none", "stroke": stroke, "stroke-width": mm(width_um)}
    if kind:
        attrs["data-kind"] = kind
    return ET.SubElement(parent, S + "rect", attrs)


def _page_size(page: str, orientation: str) -> tuple[int, int]:
    if page not in PAGE_UM or orientation not in {"portrait", "landscape"}:
        raise ExportError("Invalid page format/orientation")
    w, h = PAGE_UM[page]
    return (w, h) if orientation == "portrait" else (h, w)


@dataclass(frozen=True, slots=True)
class ExportRequest:
    page: Literal["A4", "A3", "A2"] = "A3"
    orientation: Literal["portrait", "landscape"] = "landscape"
    dpi: int = 300
    # Pixel crop in page coordinates, NOT an inferred net/geometry selection.
    region_um: tuple[int, int, int, int] | None = None
    include_frame: bool = True
    include_title: bool = False
    background: Literal["white", "transparent"] = "white"
    strict_font: bool = True
    source_project_sha256: str | None = None
    # Explicit position translates existing source viewport without scaling.
    offset_um: tuple[int, int] | None = None
    # True v2 sheet coordinates; do NOT recenter imported CAD positions.
    page_coords: bool = False

    def __post_init__(self) -> None:
        page_w, page_h = _page_size(self.page, self.orientation)
        pixels(page_w, self.dpi)
        pixels(page_h, self.dpi)
        if self.background not in {"white", "transparent"}:
            raise ExportError("Invalid background")
        for flag in (self.include_frame, self.include_title, self.strict_font, self.page_coords):
            if type(flag) is not bool:
                raise ExportError("Export flags must be boolean")
        if self.source_project_sha256 is not None and not _SHA256.fullmatch(
            self.source_project_sha256
        ):
            raise ExportError("Project source SHA-256 must be lowercase hex")
        if self.offset_um is not None:
            if len(self.offset_um) != 2:
                raise ExportError("Offset is (x_um,y_um)")
            for n in self.offset_um:
                mm(n)
        if self.page_coords and self.offset_um not in (None, (0, 0)):
            raise ExportError("Page coordinates cannot have an additional content offset")
        if self.region_um is not None:
            if len(self.region_um) != 4:
                raise ExportError("Region must be (x,y,w,h) integer µm")
            for n in self.region_um:
                mm(n)
            x, y, w, h = self.region_um
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > page_w or y + h > page_h:
                raise ExportError("Selection region is outside page")
            if self.include_frame or self.include_title:
                raise ExportError("Region crop requires frame/title disabled")


@dataclass(frozen=True, slots=True)
class ExportResult:
    svg: bytes
    png: bytes
    size_um: tuple[int, int]
    pixels: tuple[int, int]
    input_svg_sha256: str
    svg_sha256: str
    png_sha256: str
    warnings: tuple[str, ...]
    # caller retains project's native gscad-project v2 file separately


def _check_source_ink_bounds(root: ET.Element, viewport: tuple[int, int, int, int]) -> None:
    """Reject SVG shapes outside their claimed viewBox, including painted strokes.

    Present Python engine emits Line/Rectangle/Circle/Semicircle. Check the
    exact basic-shape extents here; a general SVG path and text glyph-ink audit
    remains the responsibility of the source renderer/layout contract.
    """
    vx, vy, vw, vh = viewport
    parents = {child: parent for parent in root.iter() for child in parent}

    def stroke_padding(item: ET.Element) -> int:
        stroke, thickness = None, None
        cur: ET.Element | None = item
        while cur is not None:
            if stroke is None:
                stroke = cur.get("stroke")
            if thickness is None:
                thickness = cur.get("stroke-width")
            cur = parents.get(cur)
        if stroke is None or stroke == "none":
            return 0
        if thickness is None:
            raise ExportError("Painted source stroke lacks physical width")
        width = _from_mm(thickness)
        if width <= 0:
            raise ExportError("Painted source stroke width must be positive")
        return (width + 1) // 2

    for item in root.iter():
        kind = item.tag.rsplit("}", 1)[-1]
        if kind == "line":
            xs = [_from_mm(item.attrib[k]) for k in ("x1", "x2")]
            ys = [_from_mm(item.attrib[k]) for k in ("y1", "y2")]
        elif kind == "rect":
            x, y = _from_mm(item.attrib["x"]), _from_mm(item.attrib["y"])
            w, h = _from_mm(item.attrib["width"]), _from_mm(item.attrib["height"])
            if w <= 0 or h <= 0:
                raise ExportError("Source rectangle has non-positive dimensions")
            xs, ys = [x, x + w], [y, y + h]
        elif kind == "circle":
            x, y, r = (_from_mm(item.attrib[k]) for k in ("cx", "cy", "r"))
            if r <= 0:
                raise ExportError("Source circle has non-positive radius")
            xs, ys = [x - r, x + r], [y - r, y + r]
        elif kind == "polyline":
            chunks = re.split(r"[\s,]+", item.get("points", "").strip())
            if len(chunks) < 4 or len(chunks) % 2:
                raise ExportError("Invalid SVG polyline coordinates")
            coords = [_from_mm(v) for v in chunks]
            xs, ys = coords[::2], coords[1::2]
        elif kind == "path":
            # The Python UGO engine currently emits only true semicircular
            # 'M x y A r r 0 0 sweep x y' arcs. No arbitrary Beziers allowed
            # until exact stroked-ink bounds exist for them.
            chunks = item.get("d", "").replace(",", " ").split()
            if len(chunks) != 11 or chunks[0] != "M" or chunks[3] != "A":
                raise ExportError("UNVERIFIABLE_SVG_PATH")
            try:
                ax, ay, rx, ry = [_from_mm(v) for v in (
                    chunks[1], chunks[2], chunks[4], chunks[5])]
                ex, ey = _from_mm(chunks[9]), _from_mm(chunks[10])
            except (ValueError, KeyError) as exc:
                raise ExportError("UNVERIFIABLE_SVG_PATH") from exc
            if (chunks[6:8] != ["0", "0"] or chunks[8] not in {"0", "1"}
                    or rx != ry or rx <= 0):
                raise ExportError("UNVERIFIABLE_SVG_PATH")
            sweep = chunks[8]
            if ay == ey and ex - ax == 2 * rx:
                xs = [ax, ex]
                ys = [ay - rx, ay] if sweep == "1" else [ay, ay + rx]
            elif ax == ex and ey - ay == 2 * ry:
                xs = [ax, ax + rx] if sweep == "1" else [ax - rx, ax]
                ys = [ay, ey]
            else:
                raise ExportError("UNVERIFIABLE_SVG_PATH")
        else:
            continue
        pad = stroke_padding(item)
        if not (vx <= min(xs) - pad and max(xs) + pad <= vx + vw
                and vy <= min(ys) - pad and max(ys) + pad <= vy + vh):
            raise ExportError("SOURCE_VIEWBOX_CLIPS_INK: source shape exceeds viewBox")


def _check_xml(
    data: bytes, *, strict_font: bool
) -> tuple[ET.Element, tuple[int, int, int, int], bool]:
    if type(data) is not bytes or len(data) > _MAX_XML_BYTES:
        raise ExportError("Input must be bounded UTF-8 SVG bytes")
    lower = data.lower()
    if b"<!doctype" in lower or b"<!entity" in lower or b"<?xml-stylesheet" in lower:
        raise ExportError("DTD, entities and stylesheets are forbidden")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ExportError("Malformed SVG") from exc
    if root.tag != S + "svg":
        raise ExportError("Not an SVG root in the SVG namespace")
    dims = (root.get("viewBox") or "").split()
    if len(dims) != 4:
        raise ExportError("Engine SVG needs physical viewBox")
    x, y, w, h = map(_from_mm, dims)
    if w <= 0 or h <= 0:
        raise ExportError("Non-positive source viewBox")
    if root.get("width") != mm(w) + "mm" or root.get("height") != mm(h) + "mm":
        raise ExportError("SVG physical size and viewBox disagree")
    text_count = 0
    for index, element in enumerate(root.iter()):
        if index > _MAX_NODES:
            raise ExportError("SVG node limit exceeded")
        if element.tag not in {S + x for x in _ALLOWED_TAGS}:
            raise ExportError("Unsafe or unsupported SVG element")
        for attr, value in element.attrib.items():
            if attr not in _ALLOWED_ATTRS and not attr.startswith("data-"):
                raise ExportError(f"Unsafe SVG attribute: {attr}")
            if any(bad in value.lower() for bad in ("url(", "javascript:", "data:")):
                raise ExportError("External SVG resource/style reference forbidden")
            if attr in {"stroke", "fill"} and not _SAFE_COLOR.fullmatch(value):
                raise ExportError("Non-literal SVG paint forbidden")
            if attr == "d" and not _SVG_PATH.fullmatch(value):
                raise ExportError("Unapproved SVG path syntax")
        if element.attrib.get("data-layer") in _FORBIDDEN_LAYERS:
            raise ExportError("Diagnostic/editor layer cannot enter clean export")
        if element.tag == S + "text" and (element.text or "").strip():
            text_count += 1
            # The existing engine emits external SVG font-family. CairoSVG's
            # match to the exact SHA-256 *cannot* be proven by metadata alone.
            if strict_font:
                raise ExportError("FONT_NOT_OUTLINED: exact font rendering not verified")
    _check_source_ink_bounds(root, (x, y, w, h))
    return root, (x, y, w, h), bool(text_count)


def _title_grid(root: ET.Element, page_w: int, page_h: int) -> None:
    """Reuse the existing engine's DRAFT form-one geometry, not a fake title.

    If the Python engine is unavailable, fail closed instead of approximating
    GOST cells. Title values/captions need a later approved metrics adapter.
    """
    try:
        from gost_schematic.core.geometry import Box
        from gost_schematic.rendering.form_one import draw_form_one_geometry
    except ImportError as exc:
        raise ExportError("TITLE_BLOCK_ENGINE_UNAVAILABLE") from exc
    title = ET.SubElement(root, S + "g", {"data-layer": "title-block",
                                              "data-approval": "DRAFT"})
    draw_form_one_geometry(title, Box(page_w - 190_000, page_h - 60_000,
                                      page_w - 5_000, page_h - 5_000))


def compose_clean_svg(engine_svg: bytes, request: ExportRequest) -> tuple[bytes, tuple[str, ...]]:
    """Wrap existing authoritative UGO geometry at a true physical 1:1 scale.

    Explicit junction circles and source b-graphics (if already painted by
    engine adapter) survive verbatim. We never paint pins/junctions based on
    XY intersections or SVG renderer's visual crossing.
    """
    engine, (sx, sy, sw, sh), unverified_text = _check_xml(
        engine_svg, strict_font=request.strict_font
    )
    pw, ph = _page_size(request.page, request.orientation)
    # Based on current Python PageProfile, conservative content zone: left 20,
    # other margins 5; 2mm clearance; bottom title only if requested.
    x_min, y_min = 22_000, 7_000
    x_max = pw - 7_000
    y_max = ph - (62_000 if request.include_title else 7_000)
    if request.page_coords:
        # Absolute sheet geometry is already in physical mm from page (0,0).
        # In particular source b continuations near paper edges must NOT
        # disappear merely because they are outside the framed content zone.
        dx, dy = 0, 0
        x_min, y_min, x_max, y_max = 0, 0, pw, ph
    elif request.offset_um is None:
        dx = x_min + (x_max - x_min - sw) // 2 - sx
        dy = y_min + (y_max - y_min - sh) // 2 - sy
    else:
        dx, dy = request.offset_um
    x1, y1 = sx + dx, sy + dy
    if x1 < x_min or y1 < y_min or x1 + sw > x_max or y1 + sh > y_max:
        raise ExportError("SCHEMATIC_PAGE_OVERFLOW: no auto scale or clipping")

    rx, ry, rw, rh = request.region_um or (0, 0, pw, ph)
    root = ET.Element(S + "svg", {"width": mm(rw) + "mm", "height": mm(rh) + "mm",
                                  "viewBox": " ".join(map(mm, (rx, ry, rw, rh))),
                                  "data-export-profile": "clean",
                                  "data-source-svg-sha256": hashlib.sha256(engine_svg).hexdigest(),
                                  "data-approval-status": "DRAFT"})
    if request.source_project_sha256 is not None:
        root.set("data-source-project-sha256", request.source_project_sha256)
    ET.SubElement(root, S + "title").text = "GOST Schematic — unapproved clean export"
    ET.SubElement(root, S + "desc").text = (
        "1:1 mm engineering source. No electrical connectivity inferred from image."
    )
    if request.background == "white":
        paper = ET.SubElement(root, S + "g", {"data-layer": "page-background"})
        ET.SubElement(paper, S + "rect", {"x": mm(rx), "y": mm(ry),
                                              "width": mm(rw), "height": mm(rh),
                                              "fill": "#ffffff", "stroke": "none"})
    if request.include_frame:
        group = ET.SubElement(root, S + "g", {"data-layer": "frame"})
        _rect(group, 20_000, 5_000, pw - 25_000, ph - 10_000,
              kind="inner-frame")
    if request.include_title:
        _title_grid(root, pw, ph)
    content = ET.SubElement(root, S + "g", {"data-layer": "schematic-content",
                                               "data-scale": "1:1",
                                               "transform": f"translate({mm(dx)} {mm(dy)})"})
    for node in list(engine):
        if node.tag not in {S + "title", S + "desc"}:
            content.append(node)
    warnings = ("FONT_RENDER_UNVERIFIED",) if unverified_text else ()
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n", warnings


def _validate_output_dimensions(svg: bytes) -> tuple[int, int]:
    try:
        root = ET.fromstring(svg)
        w_text, h_text = root.attrib["width"], root.attrib["height"]
        if not w_text.endswith("mm") or not h_text.endswith("mm"):
            raise ExportError("Exported SVG physical units missing")
        w, h = _from_mm(w_text[:-2]), _from_mm(h_text[:-2])
        if w <= 0 or h <= 0:
            raise ExportError("Invalid exported SVG size")
        dims = (root.attrib.get("viewBox") or "").split()
        if len(dims) != 4 or (_from_mm(dims[2]), _from_mm(dims[3])) != (w, h):
            raise ExportError("Exported SVG dimensions disagree with viewBox")
        return w, h
    except (ET.ParseError, KeyError) as exc:
        raise ExportError("Invalid exported SVG") from exc


def rasterize_svg(svg: bytes, request: ExportRequest) -> tuple[bytes, tuple[int, int]]:
    """Single raster path; explicit pixel dimensions and pHYs resolution.

    Optional CairoSVG/Pillow are installed in the renderer worker, not the
    mandatory Python engine dependency. A resvg Rust adapter may replace this.
    """
    w_um, h_um = _validate_output_dimensions(svg)
    width, height = pixels(w_um, request.dpi), pixels(h_um, request.dpi)
    if min(width, height) < 1 or width * height > _MAX_PIXELS:
        raise ExportError("PNG exceeds approved pixel budget")
    try:
        import cairosvg
        from PIL import Image
    except ImportError as exc:
        raise ExportError("PNG_BACKEND_UNAVAILABLE: CairoSVG + Pillow needed") from exc
    source_png = cairosvg.svg2png(bytestring=svg, output_width=width,
                                  output_height=height,
                                  background_color=("#ffffff" if request.background == "white"
                                                    else None))
    with Image.open(io.BytesIO(source_png)) as image:
        if image.size != (width, height):
            raise ExportError("PNG backend returned incorrect raster size")
        target = io.BytesIO()
        # Pillow emits PNG pHYs with integer pixels/metre, therefore 300 DPI
        # round-trips as approximately 299.9994, never as precisely 300.0000.
        image.save(target, format="PNG", dpi=(request.dpi, request.dpi),
                   optimize=False, compress_level=6)
    png = target.getvalue()
    if b"pHYs" not in png:
        raise ExportError("PNG backend omitted pHYs resolution metadata")
    return png, (width, height)


def export(engine_svg: bytes, request: ExportRequest) -> ExportResult:
    svg, warnings = compose_clean_svg(engine_svg, request)
    png, size_px = rasterize_svg(svg, request)
    width_um, height_um = _validate_output_dimensions(svg)
    return ExportResult(
        svg=svg, png=png, size_um=(width_um, height_um), pixels=size_px,
        input_svg_sha256=hashlib.sha256(engine_svg).hexdigest(),
        svg_sha256=hashlib.sha256(svg).hexdigest(),
        png_sha256=hashlib.sha256(png).hexdigest(), warnings=warnings,
    )
