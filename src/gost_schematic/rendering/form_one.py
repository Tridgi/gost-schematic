"""DRAFT first-sheet form-1 geometry and separately measured field content.

Source of principal dimensions: ГОСТ Р 2.104-2023, obligatory annex Б.1,
form 1 (2024-09 edition). Source graphics require 1:1 human verification
before any approved production release. No credentials are fabricated.
"""
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.model.annotations import TextStyle

_SVG = "{http://www.w3.org/2000/svg}"
WIDTH_UM = 185000
HEIGHT_UM = 55000
# Project-level title field identifiers; field numbers follow annex Б.1.
# The rectangles are intentionally separate from the drawing of the frame.
CELLS = {
    "designation": Box(65000, 0, 175000, 15000),  # (2)
    "name": Box(65000, 15000, 135000, 40000),  # (1)
    "material": Box(65000, 40000, 135000, 50000),  # (3)
    "letter": Box(135000, 20000, 150000, 35000),  # (4)
    "mass": Box(150000, 20000, 167000, 35000),  # (5)
    "scale": Box(167000, 20000, 185000, 35000),  # (6)
    "sheet": Box(135000, 40000, 155000, 50000),  # (7)
    "sheets": Box(155000, 40000, 185000, 50000),  # (8)
    "organization": Box(135000, 50000, 185000, 55000),  # (9)
    "developed": Box(0, 30000, 17000, 35000),  # role (10)
    "checked": Box(0, 35000, 17000, 40000),
    "tech_control": Box(0, 40000, 17000, 45000),
    "norm_control": Box(0, 45000, 17000, 50000),
    "approved": Box(0, 50000, 17000, 55000),
}
# Only confirmed printed headings in the original annex, no document values.
# Small role fields have 17 mm width, NOT the 7 mm "Изм." column.
CAPTIONS = {
    "developed": "Разраб.",
    "checked": "Пров.",
    "tech_control": "Т. контр.",
    "norm_control": "Н. контр.",
    "approved": "Утв.",
}
# Revision and auxiliary table headings are separate cells above the role rows.
CAPTION_CELLS = {
    "rev_change": Box(0, 15000, 7000, 20000),
    "rev_sheet": Box(7000, 15000, 17000, 20000),
    "rev_document": Box(17000, 15000, 40000, 20000),
    "rev_sign": Box(40000, 15000, 55000, 20000),
    "rev_date": Box(55000, 15000, 65000, 20000),
    "letter_caption": Box(135000, 15000, 150000, 20000),
    "mass_caption": Box(150000, 15000, 167000, 20000),
    "scale_caption": Box(167000, 15000, 185000, 20000),
    "sheet_caption": Box(135000, 35000, 155000, 40000),
    "sheets_caption": Box(155000, 35000, 185000, 40000),
}
CAPTION_TEXT = {
    "rev_change": "Изм.",
    "rev_sheet": "Лист",
    "rev_document": "№ докум.",
    "rev_sign": "Подп.",
    "rev_date": "Дата",
    "letter_caption": "Лит.",
    "mass_caption": "Масса",
    "scale_caption": "Масштаб",
    "sheet_caption": "Лист",
    "sheets_caption": "Листов",
}


def _abs(local: Box, bounds: Box) -> Box:
    return local.translated(Point(bounds.min_x, bounds.min_y))


def _line(parent: ET.Element, a: int, b: int, c: int, d: int, section: str,
          bounds: Box) -> None:
    ET.SubElement(parent, _SVG + "line", {
        "x1": format_mm(bounds.min_x + a),
        "y1": format_mm(bounds.min_y + b),
        "x2": format_mm(bounds.min_x + c),
        "y2": format_mm(bounds.min_y + d),
        "data-grid-section": section,
    })


def draw_form_one_geometry(parent: ET.Element, bounds: Box) -> None:
    """Keep vector cells independent of any text, requisites or font files."""
    if (bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y) != (
        WIDTH_UM, HEIGHT_UM,
    ):
        raise ValueError("FORM_ONE_GEOMETRY: expected exactly 185x55 mm")
    group = ET.SubElement(parent, _SVG + "g", {
        "data-layer": "title-block-grid",
        "data-form": "1",
        "data-standard": "GOST-R-2.104-2023-B.1",
        "data-approval": "DRAFT_MANUAL_1_TO_1_REVIEW",
        "fill": "none", "stroke": "#000000", "stroke-width": "0.25",
    })
    ET.SubElement(group, _SVG + "rect", {
        "x": format_mm(bounds.min_x), "y": format_mm(bounds.min_y),
        "width": "185", "height": "55", "stroke-width": "0.7",
        "data-kind": "form-one-outline",
    })
    # Principal horizontal and vertical sizes explicitly dimensioned in B.1.
    # 7+10+23+15+10 + 110+10 = 185 mm, total height 55 mm.
    _line(group, 65000, 0, 65000, 55000, "revision-columns", bounds)
    for x, y0, y1 in (
        (7000, 15000, 30000), (17000, 15000, 55000),
        (40000, 15000, 55000), (55000, 15000, 55000),
    ):
        _line(group, x, y0, x, y1, "revision-columns", bounds)
    for y in (15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000):
        _line(group, 0, y, 65000, y, "revision-rows", bounds)

    _line(group, 175000, 0, 175000, 15000, "title-columns", bounds)
    _line(group, 65000, 15000, 185000, 15000, "title-rows", bounds)
    # Four-column metadata upper-right of the main name field.
    for x in (135000, 150000, 167000):
        y0, y1 = (15000, 55000) if x == 135000 else (15000, 35000)
        _line(group, x, y0, x, y1, "title-columns", bounds)
    _line(group, 135000, 20000, 185000, 20000, "title-rows", bounds)
    _line(group, 135000, 35000, 185000, 35000, "title-rows", bounds)
    _line(group, 155000, 35000, 155000, 50000, "title-columns", bounds)
    _line(group, 65000, 40000, 185000, 40000, "title-rows", bounds)
    _line(group, 65000, 50000, 185000, 50000, "title-rows", bounds)


@dataclass(frozen=True, slots=True)
class PlacedField:
    key: str
    text: str
    cell: Box
    ink: Box
    baseline: Point


def write_form_one_fields(
    parent: ET.Element,
    bounds: Box,
    fields: dict[str, str],
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    cap_height_um: int = 2500,
    padding_um: int = 400,
    captions: bool = False,
) -> tuple[PlacedField, ...]:
    """Explicit user fields; fixed cap-height, no auto-shrink or ellipsis.

    True glyph ink bounds are measured in integer µm; centre the ink on both
    axes and enforce a padded interior. Reject an overflow, do not clip.
    """
    if cap_height_um not in (2500, 3500):
        raise ValueError("Only calibrated Type A 2.5/3.5 mm text is supported")
    if type(padding_um) is not int or padding_um < 0:
        raise ValueError("padding_um must be a nonnegative integer")
    if any(not isinstance(k, str) or k not in CELLS for k in fields):
        raise ValueError("Unknown form-1 field identifier")
    if any(not isinstance(v, str) or "\n" in v or "\r" in v for v in fields.values()):
        raise ValueError("Form-1 fields must be single-line strings")
    selections = {k: v for k, v in fields.items() if v}
    positions = {k: CELLS[k] for k in selections}
    if captions:
        # Structural official captions, not application-specific requisites.
        selections.update({k: v for k, v in CAPTIONS.items() if k not in selections})
        selections.update(CAPTION_TEXT)
        positions.update({k: CELLS[k] for k in CAPTIONS})
        positions.update(CAPTION_CELLS)
    if not selections:
        return ()
    group = ET.SubElement(parent, _SVG + "g", {
        "data-layer": "title-block-fields",
        "data-title-source": "explicit-only",
        "data-approval": "DRAFT",
        "data-font-sha256": style.font_sha256 or "unverified",
    })
    placed: list[PlacedField] = []
    for key, value in selections.items():
        cell = _abs(positions[key], bounds)
        # Font metrics are authoritative, not SVG CSS text-anchor heuristics.
        metrics = measurer.measure(value, style)
        tx = (cell.min_x + cell.max_x
              - metrics.ink_box.min_x - metrics.ink_box.max_x) // 2
        ty = (cell.min_y + cell.max_y
              - metrics.ink_box.min_y - metrics.ink_box.max_y) // 2
        ink = metrics.ink_box.translated(Point(tx, ty))
        if not (cell.min_x + padding_um <= ink.min_x
                and ink.max_x <= cell.max_x - padding_um
                and cell.min_y + padding_um <= ink.min_y
                and ink.max_y <= cell.max_y - padding_um):
            raise ValueError(f"TITLE_FIELD_OVERFLOW: {key} at {cap_height_um} um")
        node = ET.SubElement(group, _SVG + "text", {
            "x": format_mm(tx), "y": format_mm(ty),
            "font-family": style.font_family,
            "font-size": format_mm(style.em_height_um),
            "font-style": style.font_style,
            "data-cap-height-mm": format_mm(cap_height_um),
            "data-graph": key,
            "data-cell-bounds-um": ",".join(
                str(n) for n in (cell.min_x, cell.min_y, cell.max_x, cell.max_y)
            ),
            "data-ink-bounds-um": ",".join(
                str(n) for n in (ink.min_x, ink.min_y, ink.max_x, ink.max_y)
            ),
            "fill": "#000000", "stroke": "none",
        })
        node.text = value
        placed.append(PlacedField(key, value, cell, ink, Point(tx, ty)))
    return tuple(placed)
