"""Read-only immutable physical UGO footprint contract for NET and PAINT.

All positions are exact integer micrometres after actual D4. The exported
per-primitive AABB includes stroke and is conservative (not an exact ink DRC).
A pin corridor is pin-specific and does NOT waive self-symbol collisions.
"""
from dataclasses import dataclass, replace

from gost_schematic.agent_project.catalog import value_digest
from gost_schematic.catalog.source_profiles import (
    SourceGlyphBinding,
    SymbolProfileMismatch,
    check_ink_contract,
    read_source_manifest,
)
from gost_schematic.core.geometry import (
    Box,
    Circle,
    Line,
    Point,
    StyledLine,
    primitive_stroke_width,
)
from gost_schematic.engines.ports import PinEscapeCorridor, pin_corridors_for_component
from gost_schematic.engines.sheet_layout import component_graphic_obstacles
from gost_schematic.model.circuit import PinRef
from gost_schematic.model.obstacles import BoxObstacle

FOOTPRINT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SourceLead:
    pin_ref: PinRef
    graphic_index: int
    segment: Line
    stroke_width_um: int
    obstacle: BoxObstacle


@dataclass(frozen=True, slots=True)
class SourceFootprint:
    reference: str
    part_id: str
    symbol_id: str
    revision: int
    part_sha256: str
    symbol_sha256: str
    origin: Point
    rotation: int
    mirror_x: bool
    body_keepout: Box
    rendered_ink_bounds: Box
    rendered_symbol_sha256: str
    ink_obstacles: tuple[BoxObstacle, ...]
    lead_obstacles: tuple[SourceLead, ...]
    pin_corridors: tuple[PinEscapeCorridor, ...]
    physical_pin_roles: tuple[tuple[PinRef, str], ...]


def source_reference_symbol(symbol, reference: str):
    """The one frozen photo-specific visual VT1 dot: ink, not a new net/pin.

    Reused by real gallery and obstacle export so their primitive indices and
    bounds cannot drift from one another.
    """
    if reference != "VT1":
        return symbol
    point = Point(0, 5000)
    if symbol.identifier != "transistor.mosfet_n_enh" or len(symbol.pins) != 3:
        raise SymbolProfileMismatch("VT1 source variant requires three-pin MOS")
    if not any(
        getattr(shape, "start", None) == point
        or getattr(shape, "end", None) == point
        for shape in symbol.graphics
    ):
        raise SymbolProfileMismatch("VT1 dot must lie on true source channel ink")
    return replace(symbol, graphics=(*symbol.graphics, Circle(point, 250)))


def source_footprint(binding: SourceGlyphBinding) -> SourceFootprint:
    """Fail closed if any actual physical pin has no exactly attached lead."""
    symbol, part, instance = binding.symbol, binding.part, binding.instance
    check_ink_contract(symbol, part)
    row = next(
        (item for item in read_source_manifest()["profiles"]
         if item["reference"] == binding.reference), None
    )
    if (row is None or row["symbol_id"] != symbol.identifier
        or [p.name for p in part.pins] != row["expected_physical_roles"]
        or [p.label for p in symbol.pins] != row["expected_graphic_labels"]):
        raise SymbolProfileMismatch("Footprint violates source-locked ID/roles")
    rendered_symbol = source_reference_symbol(symbol, binding.reference)
    if (binding.reference != instance.reference
        or instance.part_id != part.identifier
        or part.symbol_id != symbol.identifier):
        raise SymbolProfileMismatch("Footprint changed source part/symbol identity")
    numbers = tuple(pin.number for pin in part.pins)
    if (tuple(ref.number for ref in binding.pin_refs) != numbers
        or any(ref.reference != instance.reference for ref in binding.pin_refs)):
        raise SymbolProfileMismatch("Footprint physical PinRef inventory mismatched")
    positions = instance.pin_positions(symbol)
    if tuple(positions[n] for n in numbers) != binding.pin_positions:
        raise SymbolProfileMismatch("Footprint true D4 endpoint mismatch")
    ink = component_graphic_obstacles(rendered_symbol, instance)
    corridors = pin_corridors_for_component(symbol, instance)
    if len(ink) != len(rendered_symbol.graphics) or len(corridors) != len(part.pins):
        raise SymbolProfileMismatch("Missing ink obstacle or pin corridor")
    conducting = (symbol.conductor_topology.conductor_indices
                  if symbol.conductor_topology is not None else ())
    leads = []
    for number in numbers:
        local_at = next(p.at for p in symbol.pins if p.number == number)
        matches = [
            (index, symbol.graphics[index]) for index in conducting
            if isinstance(symbol.graphics[index], (Line, StyledLine))
            and local_at in (
                symbol.graphics[index].start, symbol.graphics[index].end
            )
        ]
        if len(matches) != 1:
            raise SymbolProfileMismatch(
                f"{instance.reference}.{number}: expected exactly one true lead, "
                f"found {len(matches)}"
            )
        index, primitive = matches[0]
        a = instance.transform.apply(primitive.start) + instance.origin
        b = instance.transform.apply(primitive.end) + instance.origin
        if positions[number] not in (a, b):
            raise SymbolProfileMismatch("D4 changed lead-to-pin contact")
        leads.append(SourceLead(
            PinRef(instance.reference, number), index, Line(a, b),
            primitive_stroke_width(primitive, symbol.line_width_um), ink[index],
        ))
    if tuple(c.pin for c in corridors) != binding.pin_refs:
        raise SymbolProfileMismatch("Wrong escape PinRefs")
    if tuple(c.contact for c in corridors) != binding.pin_positions:
        raise SymbolProfileMismatch("Escape corridor not on physical pin end")
    return SourceFootprint(
        reference=instance.reference,
        part_id=part.identifier, symbol_id=symbol.identifier,
        revision=symbol.revision, part_sha256=value_digest(part),
        symbol_sha256=value_digest(symbol), origin=instance.origin,
        rotation=instance.transform.rotation, mirror_x=instance.transform.mirror_x,
        body_keepout=instance.transform.box(symbol.body_keepout).translated(
            instance.origin
        ),
        rendered_ink_bounds=instance.transform.box(
            rendered_symbol.stroked_bounds
        ).translated(instance.origin),
        rendered_symbol_sha256=value_digest(rendered_symbol),
        ink_obstacles=ink,
        lead_obstacles=tuple(leads), pin_corridors=corridors,
        physical_pin_roles=tuple(
            (PinRef(instance.reference, pin.number), pin.name) for pin in part.pins
        ),
    )


def footprint_record(footprint: SourceFootprint) -> dict:
    """Frozen, machine-readable geometry with canonical SHA256."""
    def xy(p: Point) -> list[int]:
        return [p.x, p.y]

    def bounds(b: Box) -> list[int]:
        return [b.min_x, b.min_y, b.max_x, b.max_y]

    data = {
        "schema_version": FOOTPRINT_SCHEMA_VERSION,
        "reference": footprint.reference,
        "part_id": footprint.part_id,
        "symbol_id": footprint.symbol_id,
        "symbol_revision": footprint.revision,
        "status": "DRAFT_NOT_GOST_CERTIFIED",
        "part_sha256": footprint.part_sha256,
        "symbol_sha256": footprint.symbol_sha256,
        "rendered_symbol_sha256": footprint.rendered_symbol_sha256,
        "origin_um": xy(footprint.origin),
        "rotation": footprint.rotation,
        "mirror_x": footprint.mirror_x,
        "body_keepout_um": bounds(footprint.body_keepout),
        "rendered_ink_bounds_um": bounds(footprint.rendered_ink_bounds),
        "graphic_ink": [
            {"id": o.identifier, "primitive_index": i,
             "box_um": bounds(o.box), "kind": o.kind}
            for i, o in enumerate(footprint.ink_obstacles)
        ],
        "real_leads": [
            {"ref": lead.pin_ref.reference, "number": lead.pin_ref.number,
             "graphic_index": lead.graphic_index,
             "segment_um": [xy(lead.segment.start), xy(lead.segment.end)],
             "stroke_um": lead.stroke_width_um,
             "obstacle_um": bounds(lead.obstacle.box)}
            for lead in footprint.lead_obstacles
        ],
        "pin_escape": [
            {"ref": c.pin.reference, "number": c.pin.number,
             "contact_um": xy(c.contact), "side": c.side.value,
             "reserved_box_um": bounds(c.box),
             "rule": "EXACT_PIN_OUTWARD_ONLY_NO_SELF_INK_WAIVER"}
            for c in footprint.pin_corridors
        ],
        "physical_pin_roles": [
            {"ref": pin.reference, "number": pin.number, "name": name}
            for pin, name in footprint.physical_pin_roles
        ],
        "geometry_relation": "CONSERVATIVE_STROKE_AABB_NOT_EXACT_INK_DRC",
        "normative_source_status": "BLOCKED_INDEPENDENT_CALIBRATED_1TO1",
    }
    data["footprint_sha256"] = value_digest(data)
    return data


def verify_footprint_record(footprint: SourceFootprint, supplied: dict) -> None:
    """Reject stale part lock, wrong D4, moved lead and tampered hash."""
    if not isinstance(supplied, dict) or supplied != footprint_record(footprint):
        raise SymbolProfileMismatch(
            f"{footprint.reference}: immutable footprint/digest mismatch"
        )
