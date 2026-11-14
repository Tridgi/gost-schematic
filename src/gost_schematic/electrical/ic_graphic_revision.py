"""Strict DRAFT IC view revision gate; neither Circuit nor wires are modified.

Source and candidate are both immutable IcLibraryRecords. The two-phase
PAINT bridge may *propose* an enlarged body and re-resolved outer anchors,
but ONLY this explicit, typed acceptance gate may authorize that proposal.
A caller must handle ExternalWireGraph rerouting separately before commit.
"""
import hashlib
from dataclasses import dataclass, replace

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.ic import IcTextAngle, resolve_ic_pin_positions
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_to_json
from gost_schematic.model.circuit import Circuit, PinRef


@dataclass(frozen=True, slots=True)
class IcGeometryConsent:
    """Source-fingerprint-bound permit with exact named movable PinRefs.

    Connected contacts require a second independent exact set of authorized
    members; this records intent, not proof that a wire was rerouted.
    """

    source_sha256: str
    movable_pinrefs: tuple[PinRef, ...]
    connected_reroute_pinrefs: tuple[PinRef, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.source_sha256) is not str
            or len(self.source_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.source_sha256)
        ):
            raise ValueError("IC_SOURCE_FINGERPRINT_INVALID")
        if any(not isinstance(x, PinRef) for x in (
            *self.movable_pinrefs, *self.connected_reroute_pinrefs,
        )):
            raise TypeError("IC_CONSENT_REQUIRES_PHYSICAL_PINREF")
        if (
            len(set(self.movable_pinrefs)) != len(self.movable_pinrefs)
            or len(set(self.connected_reroute_pinrefs))
            != len(self.connected_reroute_pinrefs)
            or not set(self.connected_reroute_pinrefs) <= set(self.movable_pinrefs)
        ):
            raise ValueError("IC_GEOMETRY_CONSENT_DUPLICATE_OR_FOREIGN")


@dataclass(frozen=True, slots=True)
class IcGraphicRevisionDelta:
    """Validated PREVIEW only, no wire routing or Circuit mutation."""

    old_pin_points: tuple[tuple[PinRef, Point], ...]
    new_pin_points: tuple[tuple[PinRef, Point], ...]
    moved: tuple[PinRef, ...]
    connected_moved: tuple[PinRef, ...]


def ic_record_fingerprint(record: IcLibraryRecord) -> str:
    if not isinstance(record, IcLibraryRecord):
        raise TypeError("Expected IcLibraryRecord")
    return hashlib.sha256(ic_to_json(record).encode("utf-8")).hexdigest()


def revise_ic_text_orientation(
    record: IcLibraryRecord,
    function_angle: IcTextAngle,
    *,
    other_text_angle: IcTextAngle | None = None,
    unit_ids: tuple[str, ...] | None = None,
) -> IcLibraryRecord:
    """Explicit textual-only revision; all original physical points remain.

    E.g. 'PWM' 0→90 under LEFT_RIGHT is a valid ELECTRICAL model. An older
    PAINT renderer may still return a named BLOCKED error for this view.
    """
    if not isinstance(record, IcLibraryRecord):
        raise TypeError("Expected IcLibraryRecord")
    if not isinstance(function_angle, IcTextAngle):
        raise TypeError("IC_TEXT_ANGLE_TYPED_REQUIRED")
    if other_text_angle is not None and not isinstance(other_text_angle, IcTextAngle):
        raise TypeError("IC_TEXT_ANGLE_TYPED_REQUIRED")
    valid = {s.unit_id for s in record.specs}
    selected = valid if unit_ids is None else set(unit_ids)
    if not selected or not selected <= valid or (
        unit_ids is not None and len(selected) != len(unit_ids)
    ):
        raise ValueError("IC_UNKNOWN_OR_DUPLICATE_UNIT")
    result = []
    for spec in record.specs:
        if spec.unit_id not in selected:
            result.append(spec)
            continue
        profile = replace(
            spec.profile, function_angle=function_angle,
            other_text_angle=(
                spec.profile.other_text_angle
                if other_text_angle is None else other_text_angle
            ),
        )
        result.append(replace(spec, profile=profile, revision=spec.revision + 1))
    new = IcLibraryRecord(record.device, tuple(result), record.placements)
    before = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    after = resolve_ic_pin_positions(new.device, new.specs, new.placements)
    if before != after:
        raise ValueError("IC_TEXT_REVISION_MUTATED_PHYSICAL_ENDPOINT")
    return new


def validate_ic_graphic_revision(
    source: IcLibraryRecord,
    candidate: IcLibraryRecord,
    *,
    circuit: Circuit | None = None,
    consent: IcGeometryConsent | None = None,
) -> IcGraphicRevisionDelta:
    """Reject any unapproved movement, especially already wired IC contacts.

    No source mutation, no hidden edit to Circuit.Net or ExternalWireGraph.
    Same-body/text-only revisions can pass without a movement permit.
    """
    if not isinstance(source, IcLibraryRecord) or not isinstance(
        candidate, IcLibraryRecord,
    ):
        raise TypeError("IC_REVISION_REQUIRES_TYPED_RECORDS")
    if candidate.device != source.device or candidate.placements != source.placements:
        raise ValueError("IC_REVISION_PHYSICAL_IDENTITY_CHANGED")
    old_specs = {s.unit_id: s for s in source.specs}
    new_specs = {s.unit_id: s for s in candidate.specs}
    if set(old_specs) != set(new_specs):
        raise ValueError("IC_REVISION_UNIT_OWNERSHIP_CHANGED")
    for unit_id, old in old_specs.items():
        new = new_specs[unit_id]
        if new.revision <= old.revision:
            raise ValueError("IC_GRAPHIC_REVISION_NOT_INCREMENTED")
        old_metadata = tuple(
            (p.number, p.label, p.row_key, p.field, p.visual_row)
            for p in old.rows
        )
        new_metadata = tuple(
            (p.number, p.label, p.row_key, p.field, p.visual_row)
            for p in new.rows
        )
        if old_metadata != new_metadata:
            raise ValueError("IC_REVISION_PIN_PRESENTATION_IDENTITY_CHANGED")
    old_points = resolve_ic_pin_positions(
        source.device, source.specs, source.placements,
    )
    new_points = resolve_ic_pin_positions(
        candidate.device, candidate.specs, candidate.placements,
    )
    if set(old_points) != set(new_points):
        raise ValueError("IC_REVISION_PINREF_CHANGED")
    ordered = tuple(sorted(old_points, key=lambda p: (p.reference, p.number)))
    moved = tuple(p for p in ordered if old_points[p] != new_points[p])
    connected: set[PinRef] = set()
    if circuit is not None:
        if not isinstance(circuit, Circuit):
            raise TypeError("IC_REVISION_REQUIRES_TYPED_CIRCUIT")
        from gost_schematic.electrical.ic import validate_ic_circuit

        reference = source.placements[0].component_ref
        validate_ic_circuit(source.device, circuit, reference)
        connected = {p for net in circuit.nets for p in net.members if p in old_points}
    connected_moved = tuple(p for p in moved if p in connected)
    if consent is not None:
        if not isinstance(consent, IcGeometryConsent):
            raise TypeError("IC_GEOMETRY_CONSENT_TYPED_REQUIRED")
        if consent.source_sha256 != ic_record_fingerprint(source):
            raise ValueError("IC_GEOMETRY_CONSENT_SOURCE_STALE")
        if set(consent.movable_pinrefs) != set(moved):
            raise ValueError("IC_GEOMETRY_CONSENT_PINREF_MISMATCH")
        if set(consent.connected_reroute_pinrefs) != set(connected_moved):
            raise ValueError("IC_CONNECTED_REROUTE_CONSENT_MISMATCH")
    elif moved:
        raise ValueError("IC_GEOMETRY_REAUTHORIZATION_REQUIRED")
    return IcGraphicRevisionDelta(
        tuple((p, old_points[p]) for p in ordered),
        tuple((p, new_points[p]) for p in ordered),
        moved, connected_moved,
    )
