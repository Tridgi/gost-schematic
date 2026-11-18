"""Private A4/A3 page compositor for a validated, already-rendered schematic.

A 1:1 sheet wrapper: never scale, crop, reorder, or reinterpret the source
Circuit/ExternalWireGraph. Geometry and form-1 cells are experimental DRAFT.
Sources: docs/standards/issue-35-full-sheet.md and GOST R 2.104-2023 B.1.
"""
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box
from gost_schematic.core.units import format_mm, mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.model.annotations import TextStyle
from gost_schematic.rendering.external_wire_sheet import ExternalWireSheet
from gost_schematic.rendering.form_one import (
    draw_form_one_geometry,
    write_form_one_fields,
)

_URI = "http://www.w3.org/2000/svg"
_SVG = "{" + _URI + "}"
ET.register_namespace("", _URI)

# GOST R 2.104-2023, annex B.1: first-sheet graphic-document title, 185x55.
_TITLE_WIDTH = 185000
_TITLE_HEIGHT = 55000
_LEFT = 20000
_EDGE = 5000
_ALLOWED_PATH_ARC = re.compile(
    r"\s*M\s+(-?[\d.]+)\s+(-?[\d.]+)\s+"
    r"A\s+([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+"
    r"([01])\s+([01])\s+(-?[\d.]+)\s+(-?[\d.]+)\s*"
)


@dataclass(frozen=True, slots=True)
class PageProfile:
    """Page dimensions are integer µm; A4 landscape is not a first-sheet form."""

    format: str = "A4"
    orientation: str = "portrait"
    mode: str = "paper_first_sheet"
    electronic_title_block: bool = False
    safe_gap_um: int = 2000

    def __post_init__(self) -> None:
        if self.format not in {"A4", "A3"}:
            raise ValueError("Unsupported paper format: choose A4 or A3")
        if self.orientation not in {"portrait", "landscape"}:
            raise ValueError("Orientation must be portrait or landscape")
        if self.format == "A4" and self.orientation != "portrait":
            raise ValueError("A4 first-sheet form must be portrait (B.5)")
        if self.mode not in {"paper_first_sheet", "electronic_layout"}:
            raise ValueError("Unsupported document mode")
        if type(self.electronic_title_block) is not bool:
            raise TypeError("electronic_title_block must be boolean")
        if self.mode == "paper_first_sheet" and self.electronic_title_block:
            raise ValueError("The electronic exception is not a paper setting")
        if type(self.safe_gap_um) is not int or self.safe_gap_um < 0:
            raise ValueError("safe_gap_um must be a nonnegative integer")

    @property
    def dimensions_um(self) -> tuple[int, int]:
        if self.format == "A4":
            return 210000, 297000
        if self.orientation == "portrait":
            return 297000, 420000
        return 420000, 297000

    @property
    def frame_um(self) -> Box:
        width, height = self.dimensions_um
        return Box(_LEFT, _EDGE, width - _EDGE, height - _EDGE)

    @property
    def has_title_block(self) -> bool:
        return self.mode == "paper_first_sheet" or self.electronic_title_block

    @property
    def title_um(self) -> Box | None:
        if not self.has_title_block:
            return None
        frame = self.frame_um
        return Box(
            frame.max_x - _TITLE_WIDTH,
            frame.max_y - _TITLE_HEIGHT,
            frame.max_x,
            frame.max_y,
        )

    @property
    def content_zone_um(self) -> Box:
        """Conservative full-width strip above the title; never overlaps it."""
        frame = self.frame_um
        title = self.title_um
        bottom = title.min_y if title is not None else frame.max_y
        left, top = frame.min_x + self.safe_gap_um, frame.min_y + self.safe_gap_um
        right, lower = frame.max_x - self.safe_gap_um, bottom - self.safe_gap_um
        if left >= right or top >= lower:
            raise ValueError("SCHEMATIC_PAGE_OVERFLOW: margins exhaust content zone")
        return Box(left, top, right, lower)


@dataclass(frozen=True, slots=True)
class FormattedSheet:
    """Review-only SVG and exact 1:1 offset of the unchanged source content."""

    svg: str
    profile: PageProfile
    source_viewport_um: Box
    placed_viewport_um: Box
    offset_um: tuple[int, int]


def _rect(parent: ET.Element, box: Box, **attrs: str) -> ET.Element:
    return ET.SubElement(parent, _SVG + "rect", {
        "x": format_mm(box.min_x),
        "y": format_mm(box.min_y),
        "width": format_mm(box.max_x - box.min_x),
        "height": format_mm(box.max_y - box.min_y),
        **attrs,
    })


def _parse_source(source: ExternalWireSheet) -> tuple[ET.Element, Box]:
    try:
        root = ET.fromstring(source.svg)
    except ET.ParseError as error:
        raise ValueError("Input schematic is not valid SVG") from error
    if root.tag != _SVG + "svg":
        raise ValueError("Input must be an SVG root")
    if root.get("data-approval-status") != "DRAFT":
        raise ValueError("Only annotated DRAFT authored wiring is accepted")
    view = (root.get("viewBox") or "").split()
    if len(view) != 4:
        raise ValueError("Input SVG must have a four-number viewBox in mm")
    try:
        sx, sy, sw, sh = (mm(part) for part in view)
        width = root.attrib["width"]
        height = root.attrib["height"]
        if not width.endswith("mm") or not height.endswith("mm"):
            raise ValueError("Source SVG dimensions must be millimetres")
        if mm(width[:-2]) != sw or mm(height[:-2]) != sh:
            raise ValueError("Input SVG physical size disagrees with viewBox")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid source SVG dimensions: {error}") from error
    if sw <= 0 or sh <= 0:
        raise ValueError("Source SVG viewport must be positive")
    viewport = Box(sx, sy, sx + sw, sy + sh)
    _audit_source_geometry(root, viewport, source)
    return root, viewport


def _inside(inner: Box, outer: Box) -> bool:
    return (outer.min_x <= inner.min_x <= inner.max_x <= outer.max_x
            and outer.min_y <= inner.min_y <= inner.max_y <= outer.max_y)


def _stroke_half_width(node: ET.Element,
                       parents: dict[ET.Element, ET.Element]) -> int:
    """Include inherited visible line thickness in the no-clipping proof."""
    stroke = None
    width = None
    current = node
    while current is not None:
        if stroke is None:
            stroke = current.get("stroke")
        if width is None:
            width = current.get("stroke-width")
        current = parents.get(current)
    if stroke is None or stroke == "none":
        return 0
    if width is None:
        raise ValueError("Source stroke width not specified; cannot prove no clipping")
    thickness = mm(width)
    if thickness <= 0:
        raise ValueError("Source stroke width must be positive")
    return (thickness + 1) // 2


def _audit_source_geometry(root: ET.Element, viewport: Box,
                           source: ExternalWireSheet) -> None:
    """Conservative visible-shape audit; never trust an undersized viewBox."""
    forbidden = {"clipPath", "mask", "image", "use", "foreignObject", "script"}
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1]
        if local in forbidden or "transform" in node.attrib:
            raise ValueError(f"Unsupported/clipping source SVG geometry: {local}")
        if local in {"line", "rect", "circle", "text"}:
            try:
                if local == "line":
                    xs = (mm(node.attrib["x1"]), mm(node.attrib["x2"]))
                    ys = (mm(node.attrib["y1"]), mm(node.attrib["y2"]))
                elif local == "rect":
                    x, y = mm(node.attrib["x"]), mm(node.attrib["y"])
                    xs = (x, x + mm(node.attrib["width"]))
                    ys = (y, y + mm(node.attrib["height"]))
                elif local == "circle":
                    cx, cy, rad = (
                        mm(node.attrib["cx"]), mm(node.attrib["cy"]),
                        mm(node.attrib["r"]),
                    )
                    xs, ys = (cx - rad, cx + rad), (cy - rad, cy + rad)
                else:
                    xs, ys = (mm(node.attrib["x"]),), (mm(node.attrib["y"]),)
            except (KeyError, ValueError, TypeError) as error:
                raise ValueError(f"Invalid source {local} coordinates") from error
            shape_coords = (min(xs), min(ys), max(xs), max(ys))
        elif local == "path":
            arc = _ALLOWED_PATH_ARC.fullmatch(node.get("d", ""))
            if arc is None:
                raise ValueError("Unsupported path geometry; cannot prove no clip")
            a, b, rx, ry, _, _, _, c, d = arc.groups()
            sx, sy, ex, ey = mm(a), mm(b), mm(c), mm(d)
            rad_x, rad_y = mm(rx), mm(ry)
            shape_coords = (
                min(sx, ex) - rad_x, min(sy, ey) - rad_y,
                max(sx, ex) + rad_x, max(sy, ey) + rad_y,
            )
        else:
            continue
        # The geometry AND the painted stroke must stay within the source
        # viewport. SVG's implicit clipping must not hide a 0.15-mm overrun.
        margin = 0 if local == "text" else _stroke_half_width(node, parents)
        x1, y1, x2, y2 = shape_coords
        if not (viewport.min_x <= x1 - margin <= x2 + margin <= viewport.max_x
                and viewport.min_y <= y1 - margin <= y2 + margin <= viewport.max_y):
            raise ValueError(f"Source viewport excludes {local} geometry")
    for label in source.layout.placements:
        if not _inside(label.collision_bounds, viewport):
            raise ValueError(f"Source viewport clips measured label {label.owner}")


def compose_formatted_sheet(
    source: ExternalWireSheet,
    profile: PageProfile,
    *,
    diagnostic: bool = False,
    offset_um: tuple[int, int] | None = None,
    title_values: dict[str, str] | None = None,
    title_text_style: TextStyle | None = None,
    title_measurer: TextMeasurer | None = None,
    title_cap_height_um: int = 2500,
    title_captions: bool = False,
) -> FormattedSheet:
    """Place source 1:1 on a page; error rather than crop/scale/overlap."""
    if title_values is not None or title_captions:
        if profile.title_um is None:
            raise ValueError("Title values require an explicit title-enabled profile")
        if title_text_style is None or title_measurer is None:
            raise ValueError("Title values require calibrated font style and measurer")
    if not source.layout.valid:
        raise ValueError("Cannot compose an invalid input annotation layout")
    root_source, viewport = _parse_source(source)
    width, height = profile.dimensions_um
    zone = profile.content_zone_um
    vw, vh = viewport.max_x - viewport.min_x, viewport.max_y - viewport.min_y
    if (vw > zone.max_x - zone.min_x
            or vh > zone.max_y - zone.min_y):
        raise ValueError("SCHEMATIC_PAGE_OVERFLOW: content exceeds safe page zone")
    if offset_um is None:
        destination_x = zone.min_x + (zone.max_x - zone.min_x - vw) // 2
        destination_y = zone.min_y + (zone.max_y - zone.min_y - vh) // 2
        dx, dy = destination_x - viewport.min_x, destination_y - viewport.min_y
    else:
        if len(offset_um) != 2 or any(type(number) is not int for number in offset_um):
            raise TypeError("offset_um must be (integer µm, integer µm)")
        dx, dy = offset_um
    placed = Box(
        viewport.min_x + dx, viewport.min_y + dy,
        viewport.max_x + dx, viewport.max_y + dy,
    )
    if not _inside(placed, zone):
        raise ValueError("SCHEMATIC_PAGE_OVERFLOW: explicit placement overlaps margin/title")

    root = ET.Element(_SVG + "svg", {
        "width": f"{format_mm(width)}mm",
        "height": f"{format_mm(height)}mm",
        "viewBox": f"0 0 {format_mm(width)} {format_mm(height)}",
        "data-page-format": profile.format,
        "data-orientation": profile.orientation,
        "data-document-mode": profile.mode,
        "data-approval-status": "DRAFT",
        "data-not-gost-approved": "true",
    })
    ET.SubElement(root, _SVG + "title").text = (
        "DRAFT first-sheet review: unapproved electrical principle diagram"
    )
    ET.SubElement(root, _SVG + "desc").text = (
        "1:1 mm sheet, not certified against an original print or KOMPAS. "
        "Font is external and not embedded. No signatures/approvals supplied."
    )
    page = ET.SubElement(root, _SVG + "g", {"data-layer": "page"})
    _rect(page, Box(0, 0, width, height), **{
        "data-kind": "paper-background", "fill": "#ffffff",
        "stroke": "none",
    })
    if profile.mode == "paper_first_sheet":
        frame = ET.SubElement(root, _SVG + "g", {"data-layer": "frame"})
        _rect(frame, profile.frame_um, **{
            "data-kind": "inner-frame", "stroke": "#000000",
            "stroke-width": "0.7", "fill": "none",
        })
    content = ET.SubElement(root, _SVG + "g", {
        "data-layer": "schematic-content",
        "transform": f"translate({format_mm(dx)} {format_mm(dy)})",
        "data-scale": "1:1",
        "data-source-viewport": " ".join(map(format_mm, (
            viewport.min_x, viewport.min_y, vw, vh,
        ))),
    })
    for node in root_source:
        if node.tag not in {_SVG + "title", _SVG + "desc"}:
            content.append(node)
    if profile.title_um is not None:
        title = ET.SubElement(root, _SVG + "g", {
            "data-layer": "title-block",
            "data-form": "1", "data-requisites": (
                "EXPLICIT_ONLY" if title_values else "NOT_FILLED"
            ),
        })
        draw_form_one_geometry(title, profile.title_um)
        if title_values is not None or title_captions:
            write_form_one_fields(
                title, profile.title_um, title_values or {},
                title_text_style, title_measurer,
                cap_height_um=title_cap_height_um, captions=title_captions,
            )
    if diagnostic:
        debug = ET.SubElement(root, _SVG + "g", {
            "data-layer": "page-diagnostics", "fill": "none",
            "stroke": "#b45309", "stroke-dasharray": "1,0.7",
            "stroke-width": "0.2",
        })
        _rect(debug, zone, **{"data-kind": "safe-content-zone"})
        _rect(debug, placed, **{"data-kind": "actual-source-viewport"})
        if profile.title_um is not None:
            _rect(debug, profile.title_um, **{"data-kind": "reserved-form-one"})
    return FormattedSheet(
        ET.tostring(root, encoding="unicode") + "\n",
        profile, viewport, placed, (dx, dy),
    )
