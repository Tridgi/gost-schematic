"""Issue #109: typed nonphysical 0V / chassis / PE reference labels.

These immutable view markers NEVER add a PartDefinition, conductor,
PinRef, electrical Net or protective-earth bond. A COMMON wire cannot
silently be reinterpreted as protective earth or equipment chassis.
Actual normative symbols remain an independent YGO/ESKD acceptance gate.
"""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import NetIdentity
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment


class ReferenceRole(str, Enum):
    COMMON_0V = "common_0v"
    CHASSIS = "equipment_chassis"
    PROTECTIVE_EARTH = "protective_earth_pe"


class ReferenceAnchor(str, Enum):
    PHYSICAL_PIN = "real_physical_pin"
    AUTHORED_WIRE = "authored_wire_segment"


@dataclass(frozen=True, slots=True)
class NetReferenceMarker:
    id: str
    net_id: str
    role: ReferenceRole
    point: Point
    anchor: ReferenceAnchor
    pin: PinRef | None = None
    wire_index: int | None = None
    source_evidence: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.net_id or not self.source_evidence.strip():
            raise ValueError("REFERENCE_MARKER_SOURCE_EVIDENCE_REQUIRED")
        if not isinstance(self.role, ReferenceRole) or not isinstance(
            self.anchor, ReferenceAnchor
        ) or not isinstance(self.point, Point):
            raise TypeError("Typed marker role, anchor and integer-um point required")
        if self.anchor is ReferenceAnchor.PHYSICAL_PIN:
            if not isinstance(self.pin, PinRef) or self.wire_index is not None:
                raise ValueError("REFERENCE_MARKER_PIN_ANCHOR_INCOMPLETE")
        elif self.pin is not None or type(self.wire_index) is not int or self.wire_index < 0:
            raise ValueError("REFERENCE_MARKER_WIRE_ANCHOR_INCOMPLETE")


def _on(wire: WireSegment, p: Point) -> bool:
    a, b = wire.start, wire.end
    return (
        (b.x - a.x) * (p.y - a.y) == (b.y - a.y) * (p.x - a.x)
        and min(a.x, b.x) <= p.x <= max(a.x, b.x)
        and min(a.y, b.y) <= p.y <= max(a.y, b.y)
    )


def validate_reference_markers(
    circuit: Circuit,
    graph: ExternalWireGraph,
    nets: tuple[NetIdentity, ...],
    markers: tuple[NetReferenceMarker, ...],
    *,
    authoritative_pin_positions: dict[PinRef, Point] | None = None,
) -> None:
    """Fail closed; no PE/chassis bridge or fake connection by displayed text."""
    if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
        raise TypeError("REFERENCE_MARKER_REAL_CIRCUIT_AND_GRAPH_REQUIRED")
    if not isinstance(nets, tuple) or not isinstance(markers, tuple):
        raise TypeError("REFERENCE_MARKER_IMMUTABLE_INVENTORY_REQUIRED")
    ids = [m.id for m in markers]
    if len(ids) != len(set(ids)):
        raise ValueError("REFERENCE_MARKER_DUPLICATE_ID")
    by_name = {n.name: n for n in circuit.nets}
    if len(by_name) != len(circuit.nets):
        raise ValueError("REFERENCE_MARKER_REAL_NET_NAME_AMBIGUOUS")
    identities = {b.id: b for b in nets}
    if len(identities) != len(nets):
        raise ValueError("REFERENCE_MARKER_NET_ID_DUPLICATE")
    for b in nets:
        real = by_name.get(b.net_name)
        if real is None or b.members != real.members:
            raise ValueError("REFERENCE_MARKER_NET_IDENTITY_MISMATCH")
    same_net_roles: dict[str, ReferenceRole] = {}
    for marker in markers:
        if not isinstance(marker, NetReferenceMarker):
            raise TypeError("REFERENCE_MARKER_TYPED_RECORD_REQUIRED")
        net = identities.get(marker.net_id)
        if net is None:
            raise ValueError("REFERENCE_MARKER_UNKNOWN_NET_ID")
        if marker.role is ReferenceRole.COMMON_0V and net.net_name not in (
            "COMMON", "0V", "GND", "SIGNAL_GND"
        ):
            raise ValueError("REFERENCE_MARKER_COMMON_WRONG_NET")
        if marker.role in (
            ReferenceRole.CHASSIS, ReferenceRole.PROTECTIVE_EARTH
        ) and net.net_name in ("COMMON", "0V", "GND", "SIGNAL_GND"):
            raise ValueError("REFERENCE_MARKER_NO_IMPLICIT_PE_TO_COMMON")
        prior = same_net_roles.setdefault(marker.net_id, marker.role)
        if prior != marker.role:
            raise ValueError("REFERENCE_MARKER_INCOMPATIBLE_ROLES_ON_ONE_NET")
        if marker.anchor is ReferenceAnchor.PHYSICAL_PIN:
            if marker.pin not in net.members:
                raise ValueError("REFERENCE_MARKER_FOREIGN_PHYSICAL_PIN")
            if authoritative_pin_positions is None:
                raise ValueError("REFERENCE_MARKER_EXACT_PIN_POSITION_REQUIRED")
            if authoritative_pin_positions.get(marker.pin) != marker.point:
                raise ValueError("REFERENCE_MARKER_PIN_POINT_MISMATCH")
        else:
            if marker.wire_index >= len(graph.segments):
                raise ValueError("REFERENCE_MARKER_UNKNOWN_WIRE")
            wire = graph.segments[marker.wire_index]
            if wire.net_name != net.net_name or not _on(wire, marker.point):
                raise ValueError("REFERENCE_MARKER_FOREIGN_NET_OR_OFF_WIRE")
        # A label is only a view of a net existing in Circuit.Net.
        # No additional Net identity, physical bond or Part is emitted.
