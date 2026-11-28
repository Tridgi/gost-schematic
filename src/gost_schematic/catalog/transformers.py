"""Parametric Form-II transformer profiles (GOST 2.723-68, DRAFT).

Each winding has its own authored conducting island. Magnetic coupling is
represented by the common graphic core, not by a conductive bridge or a
numerical simulation model. Drawn lobe counts do not specify turns ratio.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from gost_schematic.catalog.inductors import CoreKind
from gost_schematic.catalog.loader import CatalogError
from gost_schematic.core.geometry import (
    Box,
    Circle,
    Line,
    Point,
    Primitive,
    Semicircle,
    Side,
    StyledLine,
    enclosing_box,
    primitive_stroked_bounds,
)
from gost_schematic.core.units import mm
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRole,
    AnnotationSlot,
    HorizontalAlign,
    VerticalAlign,
)
from gost_schematic.model.conductor_topology import ConductorTopology
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin, TerminalFunction
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


@dataclass(frozen=True, slots=True)
class WindingSpec:
    lobes: int = 4
    taps: tuple[int, ...] = ()
    start_bottom: bool = False

    def __post_init__(self) -> None:
        if type(self.lobes) is not int or not 1 <= self.lobes <= 12:
            raise ValueError("Winding supports 1–12 drawn lobes")
        if not isinstance(self.taps, tuple) or any(
            type(i) is not int or not 1 <= i < self.lobes for i in self.taps
        ) or tuple(sorted(set(self.taps))) != self.taps:
            raise ValueError("Taps must be unique sorted internal boundaries")
        if type(self.start_bottom) is not bool:
            raise TypeError("start_bottom must be boolean")


@dataclass(frozen=True, slots=True)
class TransformerSpec:
    identifier: str
    windings: tuple[WindingSpec, ...]
    core: CoreKind = CoreKind.FERROMAGNETIC
    radius_um: int = 2000
    lead_um: int = 4000
    line_width_um: int = 300
    revision: int = 1
    mark_starts: bool = False
    normative_basis: str = "ГОСТ 2.723-68, таблицы 1, 2; проектная компоновка"

    def __post_init__(self) -> None:
        if not self.identifier.startswith("transformer."):
            raise ValueError("Transformer identifier required")
        if not isinstance(self.windings, tuple) or len(self.windings) not in (2, 3):
            raise ValueError("Expected two or three windings")
        if any(not isinstance(w, WindingSpec) for w in self.windings):
            raise TypeError("WindingSpec required")
        if self.core not in (CoreKind.NONE, CoreKind.FERROMAGNETIC,
                             CoreKind.FERRITE, CoreKind.MAGNETODIELECTRIC):
            raise ValueError("Unsupported transformer core")
        if type(self.radius_um) is not int or not 1500 <= self.radius_um <= 4000:
            raise ValueError("Draft radius must be 1.5–4 mm")
        if type(self.lead_um) is not int or self.lead_um < 3000:
            raise ValueError("Terminal leads must be at least 3 mm")
        if type(self.line_width_um) is not int or not 200 <= self.line_width_um <= 500:
            raise ValueError("Draft line width must be 0.2–0.5 mm")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("Positive revision required")
        if type(self.mark_starts) is not bool:
            raise TypeError("mark_starts must be boolean")
        if not isinstance(self.normative_basis, str) or not self.normative_basis.strip():
            raise ValueError("Documented normative basis required")


@dataclass(frozen=True, slots=True)
class TransformerDefinition:
    spec: TransformerSpec
    symbol: SymbolDefinition
    part: PartDefinition


def build_transformer(spec: TransformerSpec) -> TransformerDefinition:
    r = spec.radius_um
    # The facing arcs leave 2 mm on each side of the common core.
    axis = r + mm(2)
    gap = mm(4)
    lengths = [2 * r * w.lobes for w in spec.windings]
    secondary_span = sum(lengths[1:]) + gap * (len(lengths) - 2)
    tops = [-lengths[0] // 2, -secondary_span // 2]
    if len(lengths) == 3:
        tops.append(tops[1] + lengths[1] + gap)
    graphics: list[Primitive] = []
    conductors: list[int] = []
    joints: list[Point] = []
    pins: list[GraphicPin] = []
    physical: list[PhysicalPin] = []
    groups: list[tuple[str, ...]] = []
    body_ink: list[Box] = []

    def add(shape: Primitive, *, conductive: bool = False, body: bool = False) -> None:
        if conductive:
            conductors.append(len(graphics))
        graphics.append(shape)
        if body:
            body_ink.append(primitive_stroked_bounds(shape, spec.line_width_um))

    for i, (w, top, length) in enumerate(zip(spec.windings, tops, lengths, strict=True)):
        left = i == 0
        x = -axis if left else axis
        side = Side.LEFT if left else Side.RIGHT
        bulge = Side.RIGHT if left else Side.LEFT
        outer = x - spec.lead_um if left else x + spec.lead_um
        bottom = top + length
        for j in range(w.lobes):
            add(Semicircle(Point(x, top + (2 * j + 1) * r), r, bulge),
                conductive=True, body=True)
        group: list[str] = []
        # Winding START and END identities are stable even with reversed phase marks.
        ends = (bottom, top) if w.start_bottom else (top, bottom)
        contacts = [(ends[0], TerminalFunction.WINDING_START, "START"),
                    (ends[1], TerminalFunction.WINDING_END, "END")]
        contacts.extend((top + 2 * r * tap, TerminalFunction.WINDING_TAP, f"TAP{j + 1}")
                        for j, tap in enumerate(w.taps))
        for y, role, name in contacts:
            at = Point(outer, y)
            joint = Point(x, y)
            add(Line(joint, at), conductive=True)
            if role == TerminalFunction.WINDING_TAP:
                joints.append(joint)
            number = str(len(pins) + 1)
            pins.append(GraphicPin(number, at, side))
            physical.append(PhysicalPin(number, f"W{i + 1}_{name}",
                                        ElectricalType.PASSIVE, function=role))
            group.append(number)
        groups.append(tuple(sorted(group)))
        if spec.mark_starts:
            # Radius equal to half inherited stroke: a solid circular mark,
            # separate from conductor indices and from physical contact circles.
            dot_y = ends[0] + (mm(1) if w.start_bottom else -mm(1))
            dot_x = x + (mm(1) if left else -mm(1))
            add(Circle(Point(dot_x, dot_y), spec.line_width_um // 2), body=True)

    if spec.core != CoreKind.NONE:
        core_top = min(tops)
        core_bottom = max(t + length for t, length in zip(tops, lengths, strict=True))
        width = spec.line_width_um * (2 if spec.core == CoreKind.FERRITE else 1)
        dash = (mm(2), mm(1)) if spec.core == CoreKind.MAGNETODIELECTRIC else ()
        add(StyledLine(Point(0, core_top), Point(0, core_bottom), width, dash), body=True)
    body = enclosing_box(tuple(body_ink)).expanded(mm("0.3"))
    zone = body.expanded(mm("0.2"))
    if any(zone.expanded(mm("0.55")).includes(p.at) for p in pins):
        raise ValueError("Functional zone traps a terminal")
    labels = (
        AnnotationSlot("refdes", AnnotationRole.REFDES, (
            Anchor(Point(0, body.min_y - mm(3)), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),
            Anchor(Point(0, body.max_y + mm(3)), HorizontalAlign.CENTER, VerticalAlign.TOP),
        ), required=True),
        AnnotationSlot("value", AnnotationRole.VALUE, (
            Anchor(Point(0, body.max_y + mm(3)), HorizontalAlign.CENTER, VerticalAlign.TOP),
            Anchor(Point(0, body.min_y - mm(3)), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),
        )),
    )
    symbol = SymbolDefinition(
        identifier=spec.identifier, revision=spec.revision, graphics=tuple(graphics),
        pins=tuple(pins), body_keepout=body, line_width_um=spec.line_width_um,
        status=SymbolStatus.DRAFT, annotation_slots=labels,
        standard_refs=(spec.normative_basis,
                       "EDITORIAL_ASSUMPTION: dimensions and abstract terminal numbering; DRAFT"),
        conductor_topology=ConductorTopology(
            conductor_indices=tuple(conductors), junctions=tuple(joints),
            pin_groups=tuple(sorted(groups, key=lambda group: group[0])),
        ),
        routing_keepouts=(zone,),
    )
    part = PartDefinition(spec.identifier, "T", spec.identifier, tuple(physical))
    return TransformerDefinition(spec, symbol, part)


def parse_transformer_spec(data: dict) -> TransformerSpec:
    try:
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported transformer schema")
        return TransformerSpec(
            identifier=data["id"],
            windings=tuple(WindingSpec(
                item.get("lobes", 4), tuple(item.get("taps", [])),
                item.get("start_bottom", False),
            ) for item in data["windings"]),
            core=CoreKind(data.get("core", "ferromagnetic")),
            radius_um=mm(data.get("radius_mm", "2")),
            lead_um=mm(data.get("lead_mm", "4")),
            line_width_um=mm(data.get("line_width_mm", "0.3")),
            revision=data.get("revision", 1),
            mark_starts=data.get("mark_starts", False),
            normative_basis=data["normative_basis"],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise CatalogError(f"Invalid transformer spec: {error}") from error


def load_transformer(path: str | Path) -> TransformerDefinition:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CatalogError(f"Cannot load transformer {path}: {error}") from error
    return build_transformer(parse_transformer_spec(data))
