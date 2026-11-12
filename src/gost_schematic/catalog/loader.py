"""Parse versioned JSON symbol fixtures into immutable domain objects."""
import json
from pathlib import Path
from typing import Any

from gost_schematic.core.geometry import (
    Box,
    Circle,
    Line,
    Point,
    Rectangle,
    Semicircle,
    Side,
    StyledLine,
)
from gost_schematic.core.units import mm
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRole,
    AnnotationSlot,
    HorizontalAlign,
    VerticalAlign,
)
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


class CatalogError(ValueError):
    """Schema, format or geometry error in a symbol catalog entry."""


def _point(values: list[int | float]) -> Point:
    if not isinstance(values, list) or len(values) != 2:
        raise CatalogError("Point must be an [x, y] millimetre pair")
    return Point(mm(values[0]), mm(values[1]))


def _box(values: list[int | float]) -> Box:
    if not isinstance(values, list) or len(values) != 4:
        raise CatalogError("Box must be [min_x, min_y, max_x, max_y] in mm")
    return Box(*(mm(number) for number in values))


def parse_symbol(data: dict[str, Any]) -> SymbolDefinition:
    if not isinstance(data, dict):
        raise CatalogError("Symbol document must be an object")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CatalogError("Unsupported symbol catalog schema_version")
    try:
        shapes = data["geometry"]
        geometry = (
            tuple(Rectangle(_box(rect)) for rect in shapes.get("rectangles", []))
            + tuple(Line(_point(line[0]), _point(line[1]))
                    for line in shapes.get("lines", []))
            + tuple(Circle(_point(circle["center_mm"]), mm(circle["radius_mm"]))
                    for circle in shapes.get("circles", []))
            + tuple(
                Semicircle(
                    _point(item["center_mm"]), mm(item["radius_mm"]), Side(item["bulge"])
                )
                for item in shapes.get("semicircles", [])
            )
            + tuple(
                StyledLine(
                    _point(item["start_mm"]), _point(item["end_mm"]),
                    mm(item["stroke_width_mm"]),
                    tuple(mm(value) for value in item.get("dash_pattern_mm", [])),
                )
                for item in shapes.get("styled_lines", [])
            )
        )
        pins = tuple(
            GraphicPin(
                number=str(item["number"]),
                at=_point(item["at_mm"]),
                side=Side(item["side"]),
                label=str(item.get("label", "")),
            )
            for item in data["pins"]
        )
        slots = tuple(
            AnnotationSlot(
                key=str(item["key"]),
                role=AnnotationRole(item["role"]),
                candidates=tuple(
                    Anchor(
                        at=_point(candidate["at_mm"]),
                        horizontal=HorizontalAlign(candidate.get("horizontal", "center")),
                        vertical=VerticalAlign(candidate.get("vertical", "bottom")),
                    )
                    for candidate in item["candidates"]
                ),
                reserved_region=(
                    _box(item["reserved_region_mm"])
                    if "reserved_region_mm" in item
                    else None
                ),
                required=bool(item.get("required", False)),
            )
            for item in data.get("annotations", [])
        )
        return SymbolDefinition(
            identifier=str(data["id"]),
            revision=data["revision"],
            graphics=geometry,
            pins=pins,
            body_keepout=_box(data["body_keepout_mm"]),
            line_width_um=mm(data["line_width_mm"]),
            status=SymbolStatus(data.get("status", "draft")),
            standard_refs=tuple(data.get("standard_refs", [])),
            annotation_slots=slots,
            constant_annotations=tuple(
                (str(key), str(value))
                for key, value in data.get("constant_annotations", {}).items()
            ),
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise CatalogError(f"Invalid symbol {data.get('id', '<unknown>')}: {error}") from error


def load_symbol(path: str | Path) -> SymbolDefinition:
    try:
        content = Path(path).read_text(encoding="utf-8")
        document = json.loads(content)
    except (OSError, ValueError) as error:
        raise CatalogError(f"Cannot load symbol from {path}: {error}") from error
    return parse_symbol(document)
