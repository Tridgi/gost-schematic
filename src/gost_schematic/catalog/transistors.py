"""Parametric transistor artwork, first stage: bipolar transistors (DRAFT).

Variants are explicit review definitions, not silently installed replacements
for existing catalog IDs. Physical pin numbers do not depend on lead layout.
"""
from dataclasses import dataclass
from enum import Enum
from itertools import product

from gost_schematic.core.geometry import (
    Box,
    Circle,
    Line,
    Point,
    Primitive,
    Side,
    enclosing_box,
    primitive_stroked_bounds,
)
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRole,
    AnnotationSlot,
    HorizontalAlign,
    VerticalAlign,
)
from gost_schematic.model.conductor_topology import ConductorTopology
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


class BipolarKind(str, Enum):
    NPN = "npn"
    PNP = "pnp"


class TerminalExit(str, Enum):
    VERTICAL = "v"
    HORIZONTAL = "h"


@dataclass(frozen=True, slots=True)
class BipolarSpec:
    kind: BipolarKind
    collector_exit: TerminalExit = TerminalExit.VERTICAL
    emitter_exit: TerminalExit = TerminalExit.VERTICAL
    with_case: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BipolarKind):
            raise TypeError("BipolarKind required")
        if not isinstance(self.collector_exit, TerminalExit) or not isinstance(
            self.emitter_exit, TerminalExit
        ):
            raise TypeError("TerminalExit required")
        if type(self.with_case) is not bool:
            raise TypeError("with_case must be boolean")

    @property
    def identifier(self) -> str:
        # Distinguish alternate geometry in preview and any future versioned
        # persistence. Never reuse the installed legacy ID for a different pose.
        case = "case" if self.with_case else "bare"
        return (
            f"transistor.bjt_{self.kind.value}.layout_"
            f"{self.collector_exit.value}{self.emitter_exit.value}.{case}"
        )


@dataclass(frozen=True, slots=True)
class BipolarDefinition:
    spec: BipolarSpec
    part: PartDefinition
    symbol: SymbolDefinition


def build_bipolar(spec: BipolarSpec) -> BipolarDefinition:
    if not isinstance(spec, BipolarSpec):
        raise TypeError("BipolarSpec required")
    # Integer micrometres. The elbow (3, +/-4) lies exactly on a
    # 5 mm radius circle. All outer leads are cardinal and on a 1 mm grid.
    base = Point(-1000, 0)
    base_pin = GraphicPin("1", Point(-12000, 0), Side.LEFT, "B")
    graphics: list[Primitive] = [Line(base_pin.at, base)]
    pins = [base_pin]
    internal: list[Primitive] = []
    emitter_sign = 1 if spec.kind == BipolarKind.NPN else -1
    for number, name, sign, exit_style in (
        ("2", "C", -emitter_sign, spec.collector_exit),
        ("3", "E", emitter_sign, spec.emitter_exit),
    ):
        joint = Point(-1000, sign * 2000)
        elbow = Point(3000, sign * 4000)
        branch = Line(joint, elbow)
        if exit_style == TerminalExit.VERTICAL:
            at = Point(3000, sign * 12000)
            side = Side.BOTTOM if sign > 0 else Side.TOP
        else:
            at = Point(12000, sign * 4000)
            side = Side.RIGHT
        graphics.extend((branch, Line(elbow, at)))
        internal.append(branch)
        pins.append(GraphicPin(number, at, side, name))
    # The base electrode and arrows depict semiconductor structure, not
    # a metallic connection between all three external terminal islands.
    conductor_indices = tuple(range(len(graphics)))
    electrode = Line(Point(-1000, -3500), Point(-1000, 3500))
    if spec.kind == BipolarKind.NPN:
        tip = Point(3000, 4000)
        tails = (Point(1000, 3800), Point(1600, 2400))
    else:
        tip = Point(-1000, -2000)
        tails = (Point(1000, -2200), Point(400, -3600))
    internal.extend((electrode, *(Line(tail, tip) for tail in tails)))
    graphics.extend((electrode, *(Line(tail, tip) for tail in tails)))
    if spec.with_case:
        case = Circle(Point(0, 0), 5000)
        graphics.append(case)
        internal.append(case)
    body = enclosing_box(tuple(primitive_stroked_bounds(g, 300) for g in internal))
    zone = body.expanded(200)
    slots = (
        AnnotationSlot("refdes", AnnotationRole.REFDES, (
            Anchor(Point(0, -15000)),
            Anchor(Point(-15000, -7000), HorizontalAlign.RIGHT),
        ), required=True),
        AnnotationSlot("value", AnnotationRole.VALUE, (
            Anchor(Point(0, 15000), vertical=VerticalAlign.TOP),
            Anchor(Point(15000, 7000), HorizontalAlign.LEFT, VerticalAlign.TOP),
        )),
    )
    symbol = SymbolDefinition(
        identifier=spec.identifier,
        revision=1,
        graphics=tuple(graphics),
        pins=tuple(pins),
        body_keepout=body,
        line_width_um=300,
        status=SymbolStatus.DRAFT,
        standard_refs=(
            "ГОСТ 2.730-73, таблица 1, поз. 2; таблица 7, поз. 1а и примечание",
            "EDITORIAL_ADAPTATION: user photos 9–10; NPN derived from table 1 "
            "N-emitter, not table 7 shielded NPN. Project dimensions; DRAFT.",
        ),
        annotation_slots=slots,
        conductor_topology=ConductorTopology(
            conductor_indices=conductor_indices, junctions=(),
            pin_groups=(("1",), ("2",), ("3",)),
        ),
        routing_keepouts=(zone,),
    )
    part = PartDefinition(spec.identifier, "VT", spec.identifier, tuple(
        PhysicalPin(str(i), name, ElectricalType.PASSIVE)
        for i, name in enumerate(("B", "C", "E"), start=1)
    ))
    return BipolarDefinition(spec, part, symbol)


def bipolar_review_variants() -> tuple[BipolarDefinition, ...]:
    """16 variants, layout rows followed by polarity/case columns."""
    return tuple(
        build_bipolar(BipolarSpec(kind, collector, emitter, with_case))
        for collector, emitter in product(TerminalExit, repeat=2)
        for with_case in (True, False)
        for kind in BipolarKind
    )
