"""Parametric, versioned ГОСТ 2.723-68 winding family.

This is an EXPERIMENTAL Form-II expanded-symbol generator: the nominal
component is never represented by a pre-rendered bitmap or a polyline
imitation of a semicircle. A separate JSON spec describes each variant.
All geometry uses exact integer micrometres.

Reference: ГОСТ 2.723-68 §§4–6, table 1 and table 2 (changes 1–3).
The standard explicitly does not fix the semicircle count. Selected radius,
lead length and text clearance are reviewable draft style parameters.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from gost_schematic.catalog.loader import CatalogError
from gost_schematic.core.geometry import Box, Line, Point, Semicircle, Side, StyledLine
from gost_schematic.core.units import mm
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRole,
    AnnotationSlot,
    HorizontalAlign,
    VerticalAlign,
)
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import (
    ElectricalType,
    GraphicPin,
    PhysicalPin,
    TerminalFunction,
)
from gost_schematic.model.quantities import QuantityKind
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


class CoreKind(str, Enum):
    NONE = "none"
    FERROMAGNETIC = "ferromagnetic"
    GAPPED_FERROMAGNETIC = "gapped_ferromagnetic"
    FERRITE = "ferrite"
    MAGNETODIELECTRIC = "magnetodielectric"
    NONMAGNETIC_COPPER = "nonmagnetic_copper"


class AdjustmentKind(str, Enum):
    FIXED = "fixed"
    CORE_TRIM = "core_trim"
    VARIABLE = "variable"


class NormativeRelation(str, Enum):
    """Relationship to the original GOST drawings, not an approval certificate."""

    TABLE_2_EXAMPLE = "table_2_example"
    TABLE_1_COMPOSITION = "table_1_composition"
    EDITORIAL_ADAPTATION = "editorial_adaptation"


@dataclass(frozen=True, slots=True)
class InductorSpec:
    identifier: str
    core: CoreKind = CoreKind.NONE
    adjustment: AdjustmentKind = AdjustmentKind.FIXED
    turns: int = 4
    tap_turns: tuple[int, ...] = ()
    slider_turns: tuple[int, ...] = ()
    radius_um: int = 2000
    lead_um: int = 4000
    line_width_um: int = 300
    revision: int = 1
    normative_relation: NormativeRelation = NormativeRelation.EDITORIAL_ADAPTATION
    normative_basis: str = "User-defined, unverified geometry"

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.startswith(
            ("inductor.", "choke.")
        ):
            raise ValueError("A winding variant needs an inductor.* or choke.* ID")
        if not isinstance(self.core, CoreKind) or not isinstance(
            self.adjustment, AdjustmentKind
        ):
            raise TypeError("Core and adjustment must be typed enums")
        if type(self.turns) is not int or not 3 <= self.turns <= 12:
            raise ValueError("Draft winding supports 3–12 half-circle lobes")
        for name, value in (
            ("radius", self.radius_um),
            ("lead length", self.lead_um),
            ("line width", self.line_width_um),
        ):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive integer µm")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("Revision must be positive")
        if not isinstance(self.normative_relation, NormativeRelation):
            raise TypeError("normative_relation must be a NormativeRelation")
        if not isinstance(self.normative_basis, str) or not self.normative_basis.strip():
            raise ValueError("Normative basis must be a documented non-empty source")
        if self.radius_um < 1500 or self.radius_um > 4000:
            raise ValueError("Draft radius must remain within 1.5–4 mm")
        for selections in (self.tap_turns, self.slider_turns):
            if len(selections) != len(set(selections)):
                raise ValueError("Duplicate winding contact location")
            if any(type(index) is not int or not 0 <= index < self.turns for index in selections):
                raise ValueError("Winding contact index outside the lobe range")
        if set(self.tap_turns) & set(self.slider_turns):
            raise ValueError("Fixed taps and sliders cannot occupy the same lobe")
        if self.core != CoreKind.NONE and (self.tap_turns or self.slider_turns):
            raise ValueError(
                "Core + exposed contacts need a separate verified route over core symbol"
            )
        if self.adjustment == AdjustmentKind.CORE_TRIM and self.core == CoreKind.NONE:
            raise ValueError("Core trim requires a physical core")
        if self.adjustment == AdjustmentKind.VARIABLE and self.core != CoreKind.NONE:
            raise ValueError("Variable-winding symbol must not silently imply core tuning")


@dataclass(frozen=True, slots=True)
class InductorDefinition:
    spec: InductorSpec
    symbol: SymbolDefinition
    part: PartDefinition


def parse_inductor_spec(payload: dict[str, object]) -> InductorSpec:
    if not isinstance(payload, dict):
        raise CatalogError("Inductor spec must be a JSON object")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise CatalogError("Unsupported inductor variant schema version")
    try:
        return InductorSpec(
            identifier=payload["id"],
            core=CoreKind(payload.get("core", "none")),
            adjustment=AdjustmentKind(payload.get("adjustment", "fixed")),
            turns=payload.get("turns", 4),
            tap_turns=tuple(payload.get("tap_turns", [])),
            slider_turns=tuple(payload.get("slider_turns", [])),
            radius_um=mm(payload.get("radius_mm", "2")),
            lead_um=mm(payload.get("lead_mm", "4")),
            line_width_um=mm(payload.get("line_width_mm", "0.3")),
            revision=payload.get("revision", 1),
            normative_relation=NormativeRelation(
                payload.get("normative_relation", "editorial_adaptation")
            ),
            normative_basis=payload.get(
                "normative_basis", "User-defined, unverified geometry"
            ),
        )
    except (TypeError, ValueError, KeyError) as error:
        raise CatalogError(f"Invalid inductor spec: {error}") from error


def load_inductor(path: str | Path) -> InductorDefinition:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CatalogError(f"Cannot load inductor variant {path}: {error}") from error
    return build_inductor(parse_inductor_spec(data))


def _arrowhead(tip: Point, *, direction: str, unit: int) -> tuple[Line, Line]:
    """Vector arrowhead with no graphical pin semantics."""
    if direction == "up_right":
        return (
            Line(tip, Point(tip.x - unit, tip.y)),
            Line(tip, Point(tip.x, tip.y + unit)),
        )
    if direction == "down":
        return (
            Line(tip, Point(tip.x - unit, tip.y - unit)),
            Line(tip, Point(tip.x + unit, tip.y - unit)),
        )
    raise ValueError("Invalid arrow direction")


def build_inductor(spec: InductorSpec) -> InductorDefinition:
    """Compose one immutable winding, its distinct physical part and text slots."""
    r = spec.radius_um
    span = spec.turns * 2 * r
    first = -span // 2
    last = first + span
    lead_start = first - spec.lead_um
    lead_end = last + spec.lead_um

    graphics: list[Line | Semicircle | StyledLine] = [
        Line(Point(lead_start, 0), Point(first, 0)),
    ]
    for index in range(spec.turns):
        graphics.append(Semicircle(Point(first + (2 * index + 1) * r, 0), r, Side.TOP))
    graphics.append(Line(Point(last, 0), Point(lead_end, 0)))

    pins = [
        GraphicPin("1", Point(lead_start, 0), Side.LEFT),
        GraphicPin("2", Point(lead_end, 0), Side.RIGHT),
    ]
    physical = [
        PhysicalPin("1", "START", ElectricalType.PASSIVE, function=TerminalFunction.WINDING_START),
        PhysicalPin("2", "END", ElectricalType.PASSIVE, function=TerminalFunction.WINDING_END),
    ]
    core_y = -r - mm("1.6")
    core_left, core_right = first - r // 2, last + r // 2
    width = spec.line_width_um

    if spec.core == CoreKind.FERROMAGNETIC:
        graphics.append(StyledLine(
            Point(core_left, core_y), Point(core_right, core_y), width,
        ))
    elif spec.core == CoreKind.GAPPED_FERROMAGNETIC:
        gap = mm("1.5")
        graphics.extend((
            StyledLine(Point(core_left, core_y), Point(-gap // 2, core_y), width),
            StyledLine(Point(gap // 2, core_y), Point(core_right, core_y), width),
        ))
    elif spec.core == CoreKind.FERRITE:
        # ГОСТ 2.723-68 table 1: ferrite core uses an emphasized line.
        graphics.append(StyledLine(
            Point(core_left, core_y), Point(core_right, core_y), width * 2,
        ))
    elif spec.core in (CoreKind.MAGNETODIELECTRIC, CoreKind.NONMAGNETIC_COPPER):
        graphics.append(StyledLine(
            Point(core_left, core_y), Point(core_right, core_y),
            width, (mm("2"), mm("1.1")),
        ))

    if spec.adjustment != AdjustmentKind.FIXED:
        tip = Point(r * 2, -r - mm("3.5"))
        tail = Point(-r * 2, mm("2"))
        graphics.append(Line(tail, tip))
        graphics.extend(_arrowhead(tip, direction="up_right", unit=mm("1.3")))

    for offset, index in enumerate(spec.tap_turns):
        x = first + (2 * index + 1) * r
        number = str(3 + offset)
        pos = Point(x, -r - mm("7"))
        graphics.append(Line(Point(x, -r), pos))
        pins.append(GraphicPin(number, pos, Side.TOP))
        physical.append(PhysicalPin(number, f"TAP{offset + 1}", ElectricalType.PASSIVE, function=TerminalFunction.WINDING_TAP))

    for offset, index in enumerate(spec.slider_turns):
        x = first + (2 * index + 1) * r
        number = str(3 + len(spec.tap_turns) + offset)
        pos = Point(x, -r - mm("7"))
        tip = Point(x, -r)
        graphics.append(Line(pos, tip))
        graphics.extend(_arrowhead(tip, direction="down", unit=mm("1")))
        pins.append(GraphicPin(number, pos, Side.TOP))
        physical.append(PhysicalPin(number, f"SLIDER{offset + 1}", ElectricalType.PASSIVE, function=TerminalFunction.WINDING_SLIDER))

    top_y = min(core_y - mm("1"), -r - mm("1"))
    if spec.tap_turns or spec.slider_turns:
        top_y = min(top_y, -r - mm("5"))
    if spec.adjustment != AdjustmentKind.FIXED:
        top_y = min(top_y, -r - mm("4"))
    body = Box(first - mm("0.5"), top_y, last + mm("0.5"), mm("1.2"))
    # Routed wire exit is protected independently from this central body keepout.
    labels: list[AnnotationSlot] = [
        AnnotationSlot("refdes", AnnotationRole.REFDES, (
            Anchor(Point(0, top_y - mm("3")), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),
            Anchor(Point(lead_end + mm("2"), top_y), HorizontalAlign.LEFT, VerticalAlign.BOTTOM),
        ), required=True),
        AnnotationSlot("value", AnnotationRole.VALUE, (
            Anchor(Point(0, mm("4")), HorizontalAlign.CENTER, VerticalAlign.TOP),
            Anchor(Point(lead_end + mm("2"), mm("4")), HorizontalAlign.LEFT, VerticalAlign.TOP),
        )),
    ]
    constants: tuple[tuple[str, str], ...] = ()
    if spec.core == CoreKind.NONMAGNETIC_COPPER:
        labels.append(AnnotationSlot(
            "core_material", AnnotationRole.NOTE,
            (
                Anchor(Point(core_right + mm("3"), core_y), HorizontalAlign.LEFT,
                       VerticalAlign.CENTER),
                Anchor(Point(core_right + mm("3"), core_y - mm("4")),
                       HorizontalAlign.LEFT, VerticalAlign.CENTER),
            ), required=True,
        ))
        constants = (("core_material", "Cu"),)

    symbol = SymbolDefinition(
        identifier=spec.identifier, revision=spec.revision,
        graphics=tuple(graphics), pins=tuple(pins),
        body_keepout=body, line_width_um=width,
        status=SymbolStatus.DRAFT,
        standard_refs=(
            "ГОСТ 2.723-68, таблица 1 (обмотка, магнитопровод)",
            spec.normative_basis,
            f"review_relation={spec.normative_relation.value}; approval=draft",
        ),
        annotation_slots=tuple(labels), constant_annotations=constants,
    )
    part = PartDefinition(
        identifier=spec.identifier, reference_prefix="L", symbol_id=symbol.identifier,
        pins=tuple(physical), nominal_kind=QuantityKind.INDUCTANCE,
    )
    return InductorDefinition(spec, symbol, part)
