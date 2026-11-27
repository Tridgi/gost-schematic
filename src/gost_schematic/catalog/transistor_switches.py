"""Source-reviewed JFET and N-IGBT layout definitions, DRAFT."""
from dataclasses import dataclass
from enum import Enum
from itertools import product

from gost_schematic.catalog.transistors import TerminalExit
from gost_schematic.core.geometry import (
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


class SwitchKind(str, Enum):
    JFET_N = "jfet_n"
    JFET_P = "jfet_p"
    IGBT_N = "igbt_n"


@dataclass(frozen=True, slots=True)
class SwitchSpec:
    kind: SwitchKind
    upper_exit: TerminalExit = TerminalExit.VERTICAL
    lower_exit: TerminalExit = TerminalExit.VERTICAL
    with_case: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SwitchKind):
            raise TypeError("SwitchKind required")
        if not all(isinstance(exit_style, TerminalExit)
                   for exit_style in (self.upper_exit, self.lower_exit)):
            raise TypeError("TerminalExit required")
        if type(self.with_case) is not bool:
            raise TypeError("with_case must be boolean")

    @property
    def identifier(self) -> str:
        case = "case" if self.with_case else "bare"
        return (
            f"transistor.{self.kind.value}.layout_"
            f"{self.upper_exit.value}{self.lower_exit.value}.{case}"
        )


@dataclass(frozen=True, slots=True)
class SwitchDefinition:
    spec: SwitchSpec
    part: PartDefinition
    symbol: SymbolDefinition


def build_switch(spec: SwitchSpec) -> SwitchDefinition:
    if not isinstance(spec, SwitchSpec):
        raise TypeError("SwitchSpec required")
    igbt = spec.kind == SwitchKind.IGBT_N
    roles = ("G", "C", "E") if igbt else ("G", "D", "S")
    gate_end = Point(-2400, 4000) if igbt else Point(0, 3000)
    pins = [GraphicPin("1", Point(-12000, gate_end.y), Side.LEFT, "G")]
    graphics: list[Primitive] = [Line(pins[0].at, gate_end)]
    internal: list[Primitive] = []
    if igbt:
        gate = Line(gate_end, Point(-2400, -3500))
        graphics.append(gate)
        internal.append(gate)
    for number, name, sign, exit_style in (
        ("2", roles[1], -1, spec.upper_exit),
        ("3", roles[2], 1, spec.lower_exit),
    ):
        elbow = Point(3000, sign * 4000) if igbt else Point(4000, sign * 3000)
        joint = Point(-1000, sign * 1500) if igbt else Point(0, sign * 3000)
        branch = Line(joint, elbow)
        if exit_style == TerminalExit.VERTICAL:
            at = Point(elbow.x, sign * 12000)
            side = Side.BOTTOM if sign > 0 else Side.TOP
        else:
            at = Point(12000, elbow.y)
            side = Side.RIGHT
        graphics.extend((branch, Line(elbow, at)))
        internal.append(branch)
        pins.append(GraphicPin(number, at, side, name))
    indices = tuple(range(len(graphics)))
    if igbt:
        electrode = Line(Point(-1000, -3500), Point(-1000, 3500))
        tip = Point(3000, 4000)
        tails = (Point(1000, 3800), Point(1600, 2100))
        refs = (
            "Infineon IGB20N60H3 datasheet, rev 2.3, p. 2, G/C/E circuit symbol",
            "EDITORIAL_ADAPTATION: open arrow and optional case; not a certified GOST IGBT plate.",
        )
    else:
        electrode = Line(Point(0, -3800), Point(0, 3800))
        if spec.kind == SwitchKind.JFET_N:
            tip = Point(0, 3000)
            tails = (Point(-2000, 2400), Point(-2000, 3600))
        else:
            tip = Point(-2000, 3000)
            tails = (Point(0, 2400), Point(0, 3600))
        refs = (
            "ГОСТ 2.730-73, таблица 8, позиции 1–2, PDF page 9; note on case",
            "EDITORIAL_ADAPTATION: user photo 19; project dimensions and lead extensions.",
        )
    marks = (electrode, *(Line(tail, tip) for tail in tails))
    graphics.extend(marks)
    internal.extend(marks)
    if spec.with_case:
        circle = Circle(Point(0, 0), 5000)
        graphics.append(circle)
        internal.append(circle)
    body = enclosing_box(tuple(primitive_stroked_bounds(g, 300) for g in internal))
    slots = (
        AnnotationSlot("refdes", AnnotationRole.REFDES, (
            Anchor(Point(0, -15000)),
            Anchor(Point(-15000, -7000), HorizontalAlign.RIGHT),
        ), required=True),
        AnnotationSlot("value", AnnotationRole.VALUE, (
            Anchor(Point(0, 15000), vertical=VerticalAlign.TOP),
        )),
    )
    # JFET G and S artwork meet at one point in the source symbol. Do not
    # select the entire S electrode in the ideal conductor graph: the gate
    # junction is a semiconductor junction, not a short.
    if not igbt:
        indices = (0, 1, 2, 4)
    symbol = SymbolDefinition(
        identifier=spec.identifier,
        revision=1,
        graphics=tuple(graphics),
        pins=tuple(pins),
        body_keepout=body,
        line_width_um=300,
        status=SymbolStatus.DRAFT,
        standard_refs=refs,
        annotation_slots=slots,
        conductor_topology=ConductorTopology(
            conductor_indices=indices, junctions=(),
            pin_groups=(("1",), ("2",), ("3",)),
        ),
        routing_keepouts=(body.expanded(200),),
    )
    part = PartDefinition(spec.identifier, "VT", spec.identifier, tuple(
        PhysicalPin(str(i), name, ElectricalType.PASSIVE)
        for i, name in enumerate(roles, start=1)
    ))
    return SwitchDefinition(spec, part, symbol)


def switch_review_variants(kind: SwitchKind) -> tuple[SwitchDefinition, ...]:
    return tuple(
        build_switch(SwitchSpec(kind, upper, lower, case))
        for upper, lower in product(TerminalExit, repeat=2)
        for case in (True, False)
    )
