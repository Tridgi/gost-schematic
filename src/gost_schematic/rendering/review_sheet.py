"""Reproducible DRAFT sheet specimens; diagnostic geometry is never an ERC netlist.

Review rectangles are *conservative axis-aligned bounds*. They highlight
potential clashes, not proven pixel/curve intersections or GOST compliance.
"""
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Box, Point, enclosing_box, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm, mm
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.sheet_layout import SheetLayout, layout_sheet
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.obstacles import WireObstacle, wire_intersects_box
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.rendering.sheet_svg import render_sheet_svg

_SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")


@dataclass(frozen=True, slots=True)
class ReviewScene:
    circuit: Circuit
    symbols_by_part: dict[str, SymbolDefinition]
    source_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewCollision:
    kind: str
    first: str
    second: str
    bounds: Box


def _overlap(first: Box, second: Box) -> Box | None:
    min_x, min_y = max(first.min_x, second.min_x), max(first.min_y, second.min_y)
    max_x, max_y = min(first.max_x, second.max_x), min(first.max_y, second.max_y)
    if min_x >= max_x or min_y >= max_y:
        return None
    return Box(min_x, min_y, max_x, max_y)


class CatalogReviewError(ValueError):
    """Fail visibly when a catalog source cannot be shown without corrupting identity."""


@dataclass(frozen=True, slots=True)
class ReviewCatalogEntry:
    source: str
    symbol: SymbolDefinition
    part: PartDefinition


_SAMPLE_NOMINALS: dict[QuantityKind, tuple[str, Unit]] = {
    QuantityKind.RESISTANCE: ("2,3", Unit.KOHM),
    QuantityKind.CAPACITANCE: ("100", Unit.NANOFARAD),
    QuantityKind.INDUCTANCE: ("33", Unit.MICROHENRY),
}
_CELL_PADDING_UM = mm(25)


def discover_catalog_entries(
    catalog_root: Path | None = None,
) -> tuple[ReviewCatalogEntry, ...]:
    """Scan every versioned symbol and winding profile, matching audit source scope.

    Static symbols require a *real* matching physical passport at the
    corresponding path under parts/. Neither numeric values nor pin roles
    are inferred from painted symbols.
    """
    root = (
        Path(catalog_root) if catalog_root is not None
        else Path(str(files("gost_schematic").joinpath("catalog")))
    )
    paths = [
        (item, False) for item in sorted((root / "symbols").rglob("*.json"))
    ] + [
        (item, True) for item in sorted((root / "inductors").glob("*.json"))
    ]
    if not paths:
        raise CatalogReviewError(f"No versioned UGO sources in {root}")

    entries: list[ReviewCatalogEntry] = []
    seen_parts: dict[str, str] = {}
    seen_symbols: dict[tuple[str, int], str] = {}
    for path, is_winding in paths:
        source = "catalog/" + path.relative_to(root).as_posix()
        try:
            if is_winding:
                variant = load_inductor(path)
                symbol, part = variant.symbol, variant.part
            else:
                symbol = load_symbol(path)
                part_path = root / "parts" / path.relative_to(root / "symbols")
                part = load_part(part_path)
        except (OSError, ValueError) as error:
            raise CatalogReviewError(f"{source}: missing or invalid UGO/part: {error}") from error
        if symbol.status != SymbolStatus.DRAFT:
            raise CatalogReviewError(
                f"{source}: expected DRAFT UGO, got {symbol.status.value}"
            )
        if part.symbol_id != symbol.identifier:
            raise CatalogReviewError(
                f"{source}: part {part.identifier!r} points to "
                f"{part.symbol_id!r}, not {symbol.identifier!r}"
            )
        if {pin.number for pin in part.pins} != {pin.number for pin in symbol.pins}:
            raise CatalogReviewError(
                f"{source}: physical and graphic terminal numbers disagree"
            )
        if not part.reference_prefix.strip() or (
            part.reference_prefix != part.reference_prefix.strip()
        ):
            raise CatalogReviewError(f"{source}: invalid reference prefix")
        if part.identifier in seen_parts:
            raise CatalogReviewError(
                f"{source}: duplicate physical part ID {part.identifier!r}; "
                f"already in {seen_parts[part.identifier]}"
            )
        symbol_key = (symbol.identifier, symbol.revision)
        if symbol_key in seen_symbols:
            raise CatalogReviewError(
                f"{source}: duplicate UGO {symbol_key!r}; "
                f"already in {seen_symbols[symbol_key]}"
            )
        seen_parts[part.identifier] = source
        seen_symbols[symbol_key] = source
        entries.append(ReviewCatalogEntry(source, symbol, part))

    # Avoid ordering based on OS directory enumeration or incidental filenames.
    return tuple(sorted(
        entries, key=lambda item: (
            item.symbol.identifier, item.symbol.revision, item.part.identifier, item.source
        ),
    ))


def _example_nominal(part: PartDefinition) -> Quantity | None:
    if part.nominal_kind is None:
        return None  # Unknown is not a license to invent a physical characteristic.
    try:
        value, unit = _SAMPLE_NOMINALS[part.nominal_kind]
    except KeyError as error:
        raise CatalogReviewError(
            f"{part.identifier}: unsupported nominal kind {part.nominal_kind}"
        ) from error
    return Quantity.from_unit(value, unit)


def build_catalog_review_scene(
    catalog_root: Path | None = None,
    *,
    columns: int = 4,
) -> ReviewScene:
    """Fit all discovered DRAFT UGO in content-sized cells, no fixed catalog count.

    The width and height of each column/row are determined by real transformed
    strokes, body keepouts and terminal-escape corridors. Padding reserves
    space for labels, but any unplaceable text remains a diagnostic failure.
    """
    if type(columns) is not int or columns < 1:
        raise ValueError("columns must be a positive integer")
    entries = discover_catalog_entries(catalog_root)
    symbols = {entry.part.identifier: entry.symbol for entry in entries}

    references: set[str] = set()
    counters: dict[str, int] = {}
    frames: list[tuple[str, ReviewCatalogEntry, Transform, Box]] = []
    # Give existing catalogue symbols their old D4 poses even after XP/XS
    # additions, to preserve validated text clearance and manual comparisons.
    legacy_index = 0
    connector_index = 0
    for index, entry in enumerate(entries):
        is_connector = entry.symbol.identifier.startswith("connector.")
        pose_index = connector_index if is_connector else legacy_index
        if is_connector:
            connector_index += 1
        else:
            legacy_index += 1
        prefix = entry.part.reference_prefix
        number = counters.get(prefix, 0)
        while True:
            number += 1
            reference = f"{prefix}{number}"
            if reference not in references:
                break
        counters[prefix] = number
        references.add(reference)
        transform = Transform(rotation=(pose_index % 4) * 90, mirror_x=(not is_connector and pose_index % 5 == 4))
        originless = ComponentInstance(
            reference, entry.part.identifier, Point(0, 0), transform,
        )
        bounds = enclosing_box((
            transform.box(entry.symbol.stroked_bounds),
            transform.box(entry.symbol.body_keepout),
            *(port.box for port in pin_corridors_for_component(
                entry.symbol, originless,
            )),
        ))
        frames.append((reference, entry, transform, bounds))

    row_count = (len(frames) + columns - 1) // columns
    col_widths = [0] * columns
    row_heights = [0] * row_count
    for index, (_, _, _, bounds) in enumerate(frames):
        col = index % columns
        row = index // columns
        col_widths[col] = max(
            col_widths[col], bounds.max_x - bounds.min_x + 2 * _CELL_PADDING_UM,
        )
        row_heights[row] = max(
            row_heights[row], bounds.max_y - bounds.min_y + 2 * _CELL_PADDING_UM,
        )
    col_starts = [0] * columns
    row_starts = [0] * row_count
    for i in range(1, columns):
        col_starts[i] = col_starts[i - 1] + col_widths[i - 1]
    for i in range(1, row_count):
        row_starts[i] = row_starts[i - 1] + row_heights[i - 1]

    components: list[ComponentInstance] = []
    for index, (reference, entry, transform, bounds) in enumerate(frames):
        col, row = index % columns, index // columns
        origin = Point(
            col_starts[col] + (col_widths[col] - (bounds.max_x - bounds.min_x)) // 2
            - bounds.min_x,
            row_starts[row] + (row_heights[row] - (bounds.max_y - bounds.min_y)) // 2
            - bounds.min_y,
        )
        components.append(ComponentInstance(
            reference, entry.part.identifier, origin, transform,
            nominal=_example_nominal(entry.part),
        ))
    return ReviewScene(
        Circuit(tuple(components), ()), symbols,
        tuple(entry.source for entry in entries),
    )


def build_overlap_review_scene() -> ReviewScene:
    """An explicitly INVALID control specimen, never presented as a valid sheet."""
    root = files("gost_schematic").joinpath("catalog/symbols/resistors/fixed.json")
    symbol = load_symbol(Path(str(root)))
    return ReviewScene(Circuit((
        ComponentInstance("R1", "resistor", Point(15000, 15000),
                          nominal=Quantity.from_unit("1", Unit.KOHM)),
        ComponentInstance("R2", "resistor", Point(18000, 15000),
                          nominal=Quantity.from_unit("2", Unit.KOHM)),
    ), ()), {"resistor": symbol})


def layout_review_scene(scene: ReviewScene, style: TextStyle, measurer) -> SheetLayout:
    """Place text using the existing authoritative collision-aware layout."""
    return layout_sheet(scene.circuit, scene.symbols_by_part, style, measurer)


def review_collisions(
    scene: ReviewScene,
    layout: SheetLayout,
    *,
    wires: tuple[WireObstacle, ...] = (),
) -> tuple[ReviewCollision, ...]:
    """Independent overlay geometry; annotations, graphics and ports stay distinct.

    Each marker is a rectangular intersection, not a proof of painted-stroke
    collision. No net membership, physical values or symbol definition is changed.
    """
    graphics: list[tuple[str, Box]] = []
    strokes: list[tuple[str, Box]] = []
    corridors: list[tuple[str, str, Box]] = []
    for component in scene.circuit.components:
        symbol = scene.symbols_by_part[component.part_id]
        graphics.append((
            component.reference,
            component.transform.box(symbol.stroked_bounds).translated(component.origin),
        ))
        for index, primitive in enumerate(symbol.graphics):
            box = component.transform.box(
                primitive_stroked_bounds(primitive, symbol.line_width_um)
            ).translated(component.origin)
            strokes.append((f"{component.reference}.graphic.{index}", box))
        for port in pin_corridors_for_component(symbol, component):
            corridors.append((component.reference, port.identifier, port.box))

    findings: list[ReviewCollision] = []

    def add(kind: str, first: str, second: str, a: Box, b: Box) -> None:
        common = _overlap(a, b)
        if common is not None:
            findings.append(ReviewCollision(kind, first, second, common))

    for index, (name, bounds) in enumerate(graphics):
        for other_name, other_bounds in graphics[index + 1:]:
            add("symbol-aabb", name, other_name, bounds, other_bounds)
    for owner, name, corridor in corridors:
        for other_name, bounds in graphics:
            if owner != other_name:
                add("pin-exit-aabb", name, other_name, corridor, bounds)

    for index, label in enumerate(layout.placements):
        owner_key = f"{label.owner}.{label.key}"
        for other in layout.placements[index + 1:]:
            add("text-text", owner_key, f"{other.owner}.{other.key}",
                label.collision_bounds, other.collision_bounds)
        for name, box in strokes:
            add("text-stroke-aabb", owner_key, name, label.collision_bounds, box)
        for component in scene.circuit.components:
            symbol = scene.symbols_by_part[component.part_id]
            for obstacle in obstacles_for_component(symbol, component):
                if obstacle.kind == "pin_escape":
                    add("text-pin-exit", owner_key, obstacle.identifier,
                        label.collision_bounds, obstacle.box)
        for wire in wires:
            if wire_intersects_box(wire, label.collision_bounds):
                wire_box = primitive_stroked_bounds(wire.line, wire.stroke_um)
                add("text-wire-aabb", owner_key, wire.identifier,
                    label.collision_bounds, wire_box)

    return tuple(sorted(findings, key=lambda item: (
        item.kind, item.first, item.second,
        item.bounds.min_x, item.bounds.min_y,
    )))


def render_review_svg(
    scene: ReviewScene,
    layout: SheetLayout,
    *,
    diagnostic: bool,
    wires: tuple[WireObstacle, ...] = (),
) -> str:
    """Build clean or diagnostic vector SVG using existing genuine UGO primitives."""
    root = ET.fromstring(render_sheet_svg(
        scene.circuit, scene.symbols_by_part, layout,
        wires=wires, review_overlay=diagnostic,
    ))
    root.set("data-approval-status", "DRAFT")
    root.set("data-specimen", "invalid-overlap" if not layout.valid else "catalog")
    root.set("data-view", "diagnostic" if diagnostic else "clean")
    ET.SubElement(root, f"{_SVG}desc").text = (
        "DRAFT geometry preview, not verified GOST/ESKD approval. "
        "Diagnostic rectangles are conservative AABBs; not physical connections."
    )
    if diagnostic:
        markers = ET.SubElement(root, f"{_SVG}g", {
            "data-layer": "collision-markers",
            "stroke": "#e11d48",
            "stroke-width": "0.22",
            "fill": "#e11d48",
            "fill-opacity": "0.18",
        })
        for issue in review_collisions(scene, layout, wires=wires):
            region = issue.bounds
            marker = ET.SubElement(markers, f"{_SVG}rect", {
                "x": format_mm(region.min_x),
                "y": format_mm(region.min_y),
                "width": format_mm(region.max_x - region.min_x),
                "height": format_mm(region.max_y - region.min_y),
                "data-kind": issue.kind,
                "data-first": issue.first,
                "data-second": issue.second,
            })
            ET.SubElement(marker, f"{_SVG}title").text = (
                f"{issue.kind}: {issue.first} vs {issue.second} "
                "(conservative bounding-box intersection)"
            )
        diagnostics = ET.SubElement(root, f"{_SVG}metadata", {
            "data-layer": "layout-diagnostics",
        })
        diagnostics.text = "; ".join(
            f"{item.severity.value}:{item.code}:{item.subject or ''}"
            for item in layout.diagnostics
        )
    return ET.tostring(root, encoding="unicode") + "\n"


def review_manifest(scene: ReviewScene, layout: SheetLayout) -> dict[str, object]:
    """Exact µm contact coordinates and original SI quantities for human review."""
    collisions = review_collisions(scene, layout)
    return {
        "schema_version": 1,
        "approval": "DRAFT",
        "not_gost_certified": True,
        "source": "current versioned catalog",
        "catalog_size": len(scene.circuit.components),
        "example_nominals_only": True,
        "components": [
            {
                "catalog_source": (
                    scene.source_paths[index] if index < len(scene.source_paths) else None
                ),
                "symbol_revision": scene.symbols_by_part[item.part_id].revision,
                "reference": item.reference,
                "part_id": item.part_id,
                "symbol_id": scene.symbols_by_part[item.part_id].identifier,
                "symbol_status": scene.symbols_by_part[item.part_id].status.value,
                "origin_um": [item.origin.x, item.origin.y],
                "rotation_clockwise_deg": item.transform.rotation,
                "mirror_x": item.transform.mirror_x,
                "nominal_si": item.nominal.to_record() if item.nominal else None,
                "pins": [
                    {"number": number, "x_um": point.x, "y_um": point.y}
                    for number, point in item.pin_positions(
                        scene.symbols_by_part[item.part_id]
                    ).items()
                ],
            }
            for index, item in enumerate(scene.circuit.components)
        ],
        "labels": [
            {
                "owner": label.owner,
                "key": label.key,
                "text": label.text,
                "baseline_um": [label.baseline.x, label.baseline.y],
                "hitbox_um": [
                    label.collision_bounds.min_x, label.collision_bounds.min_y,
                    label.collision_bounds.max_x, label.collision_bounds.max_y,
                ],
            }
            for label in layout.placements
        ],
        "layout_valid": layout.valid,
        "diagnostics": [
            {"code": item.code, "severity": item.severity.value,
             "subject": item.subject, "message": item.message}
            for item in layout.diagnostics
        ],
        "aabb_collisions": [
            {"kind": item.kind, "first": item.first, "second": item.second,
             "box_um": [
                 item.bounds.min_x, item.bounds.min_y,
                 item.bounds.max_x, item.bounds.max_y,
             ]}
            for item in collisions
        ],
    }
