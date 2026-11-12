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
from gost_schematic.core.geometry import Box, Point, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.sheet_layout import SheetLayout, layout_sheet
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.obstacles import WireObstacle, wire_intersects_box
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.rendering.sheet_svg import render_sheet_svg

_SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")


@dataclass(frozen=True, slots=True)
class ReviewScene:
    circuit: Circuit
    symbols_by_part: dict[str, SymbolDefinition]


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


def build_catalog_review_scene() -> ReviewScene:
    """Load all currently checked-in catalog variants, never synthesize UGO paint."""
    root = files("gost_schematic").joinpath("catalog")
    symbols = {
        "resistor": load_symbol(Path(str(root.joinpath("symbols/resistors/fixed.json")))),
        "capacitor": load_symbol(Path(str(root.joinpath("symbols/capacitors/fixed.json")))),
        "polarized": load_symbol(Path(str(root.joinpath("symbols/capacitors/polarized.json")))),
    }
    entries: list[tuple[str, str, Quantity]] = [
        ("R1", "resistor", Quantity.from_unit("2,3", Unit.KOHM)),
        ("C1", "capacitor", Quantity.from_unit("100", Unit.NANOFARAD)),
        ("C2", "polarized", Quantity.from_unit("470", Unit.MICROFARAD)),
    ]
    paths = sorted(
        (item for item in root.joinpath("inductors").iterdir()
         if item.name.endswith(".json")),
        key=lambda item: item.name,
    )
    for index, path in enumerate(paths, start=1):
        variant = load_inductor(Path(str(path)))
        key = variant.part.identifier
        if key in symbols:
            raise ValueError(f"Duplicate part id in review catalog: {key}")
        symbols[key] = variant.symbol
        entries.append((
            f"L{index}", key,
            Quantity.from_unit(str(33 + index), Unit.MICROHENRY),
        ))
    if len(entries) != 18 or len(symbols) != 18:
        raise ValueError(f"Expected 18 current draft catalog entries, got {len(entries)}")
    if any(symbol.status != SymbolStatus.DRAFT for symbol in symbols.values()):
        raise ValueError("This specimen is restricted to DRAFT symbols")
    components = tuple(
        ComponentInstance(
            reference, part_id,
            Point(40000 + (index % 4) * 70000, 25000 + (index // 4) * 52000),
            Transform(rotation=(index % 4) * 90, mirror_x=index % 5 == 4),
            nominal=nominal,
        )
        for index, (reference, part_id, nominal) in enumerate(entries)
    )
    return ReviewScene(Circuit(components, ()), symbols)


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
        "components": [
            {
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
            for item in scene.circuit.components
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
