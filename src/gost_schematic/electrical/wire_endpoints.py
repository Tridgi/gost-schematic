"""Issue #90/#100: read-only physical E3 wire endpoint metadata.

A green diagnostic square is a projection of an independently verified
electrical target, never authority to connect, create, or merge a Circuit.Net.
No edits are made to ExternalWireGraph, Circuit or continuation models.
"""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import (
    NetContinuationProject,
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
)


class WireTermination(str, Enum):
    FREE = "free_wire_end"
    PHYSICAL_PIN = "physical_pin"
    CONNECTOR_CONTACT = "connector_contact"
    JOINED_WIRE = "joined_wire"
    JUNCTION = "authored_junction"
    CONTINUATION = "nonphysical_continuation"
    UNMARKED_TOUCH = "unmarked_touch"


class TargetState(str, Enum):
    AVAILABLE = "available"
    CONNECTED = "already_connected"
    BLOCKED = "blocked"
    NONPHYSICAL = "nonphysical"


class WireEndSide(str, Enum):
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class WireEndpoint:
    """Stable authored wire-end identity with exact prior source evidence.

    `wire_id` is assigned by the author, not reconstructed from SVG or a net
    label. Index is checked against the exact immutable source WireSegment.
    """
    id: str
    wire_id: str
    wire_index: int
    side: WireEndSide
    net_id: str
    point: Point
    termination: WireTermination
    state: TargetState
    can_accept_connection: bool
    attached_pin: PinRef | None = None
    continuation_id: str | None = None
    reason_code: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.wire_id or not self.net_id:
            raise ValueError("Stable endpoint, wire and Net IDs are required")
        if type(self.wire_index) is not int or self.wire_index < 0:
            raise ValueError("Endpoint wire index must be a nonnegative integer")
        if not isinstance(self.side, WireEndSide) or not isinstance(self.point, Point):
            raise TypeError("Wire endpoint needs a typed side and integer-um Point")
        if not isinstance(self.termination, WireTermination):
            raise TypeError("Wire termination must be typed")
        if not isinstance(self.state, TargetState) or type(self.can_accept_connection) is not bool:
            raise TypeError("Connection state and eligibility must be typed")
        if self.can_accept_connection and (
            self.termination is not WireTermination.FREE or
            self.state is not TargetState.AVAILABLE or
            self.attached_pin is not None or self.continuation_id is not None
        ):
            raise ValueError("Only an actually free and available endpoint can be eligible")
        if self.termination in (WireTermination.PHYSICAL_PIN, WireTermination.CONNECTOR_CONTACT):
            if not isinstance(self.attached_pin, PinRef):
                raise ValueError("Physical attachment requires exact PinRef")
        elif self.attached_pin is not None:
            raise ValueError("Only physical contact endpoint may carry PinRef")
        if self.termination is WireTermination.CONTINUATION:
            if not self.continuation_id or self.state is not TargetState.NONPHYSICAL:
                raise ValueError("Nonphysical continuation requires explicit endpoint ID")
        elif self.continuation_id is not None:
            raise ValueError("Continuation ID is only for nonphysical markers")


@dataclass(frozen=True, slots=True)
class PhysicalContactTarget:
    id: str
    pin: PinRef
    point: Point
    net_id: str | None
    connector: bool
    state: TargetState
    can_accept_connection: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class NonJoiningCrossing:
    """Graphic-only interior/interior X, never a conductive junction."""
    id: str
    point: Point
    first_wire_id: str
    second_wire_id: str
    first_net_id: str
    second_net_id: str


@dataclass(frozen=True, slots=True)
class WireEndpointSnapshot:
    """One immutable, validated view; all connection writes are out of scope."""
    circuit: Circuit
    graph: ExternalWireGraph
    nets: tuple[NetIdentity, ...]
    wire_ids: tuple[str, ...]
    wire_endpoints: tuple[WireEndpoint, ...]
    physical_contacts: tuple[PhysicalContactTarget, ...]
    nonjoining_crossings: tuple[NonJoiningCrossing, ...]
    continuation_ids: tuple[str, ...]
    schema_version: int = 1


def _source_point(wire: WireSegment, side: WireEndSide) -> Point:
    return wire.start if side is WireEndSide.START else wire.end


def _on(wire: WireSegment, point: Point) -> bool:
    return (
        (wire.end.x - wire.start.x) * (point.y - wire.start.y)
        == (wire.end.y - wire.start.y) * (point.x - wire.start.x)
        and min(wire.start.x, wire.end.x) <= point.x <= max(wire.start.x, wire.end.x)
        and min(wire.start.y, wire.end.y) <= point.y <= max(wire.start.y, wire.end.y)
    )


def _interior(wire: WireSegment, point: Point) -> bool:
    return _on(wire, point) and point not in (wire.start, wire.end)


def _positive_collinear_overlap(first: WireSegment, second: WireSegment) -> bool:
    # Check the two whole supporting lines, including partial overlap.
    # A single crossing endpoint is not evidence of collinearity.
    a, b = first.start, first.end
    for p in (second.start, second.end):
        if (b.x - a.x) * (p.y - a.y) != (b.y - a.y) * (p.x - a.x):
            return False
    axis = "x" if first.start.x != first.end.x else "y"
    f = sorted((getattr(first.start, axis), getattr(first.end, axis)))
    g = sorted((getattr(second.start, axis), getattr(second.end, axis)))
    return max(f[0], g[0]) < min(f[1], g[1])


def _crossing(first: WireSegment, second: WireSegment) -> Point | None:
    """Only proper orthogonal interior/interior intersections (no T or overlap)."""
    a_horizontal = first.start.y == first.end.y
    b_horizontal = second.start.y == second.end.y
    if a_horizontal == b_horizontal:
        return None
    h, v = (first, second) if a_horizontal else (second, first)
    if v.start.x != v.end.x:
        return None
    p = Point(v.start.x, h.start.y)
    return p if _interior(h, p) and _interior(v, p) else None


def _resolve_contacts(
    circuit: Circuit,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
) -> tuple[dict[PinRef, Point], frozenset[PinRef]]:
    positions: dict[PinRef, Point] = {}
    connector_pins: set[PinRef] = set()
    references: set[str] = set()
    for component in circuit.components:
        if component.reference in references:
            raise ValueError("WIRE_END_DUPLICATE_COMPONENT")
        references.add(component.reference)
        part = parts.get(component.part_id)
        if part is None or part.symbol_id not in symbols:
            raise ValueError("WIRE_END_UNKNOWN_PHYSICAL_PART_OR_SYMBOL")
        graphic = component.pin_positions(symbols[part.symbol_id])
        declared = {pin.number for pin in part.pins}
        if set(graphic) != declared:
            raise ValueError("WIRE_END_INCOMPLETE_PHYSICAL_PIN_MAP")
        for physical in part.pins:
            ref = PinRef(component.reference, physical.number)
            positions[ref] = graphic[physical.number]
            if part.reference_prefix in ("XP", "XS"):
                if not component.reference.startswith(part.reference_prefix):
                    raise ValueError("WIRE_END_CONNECTOR_REFERENCE_MISMATCH")
                connector_pins.add(ref)
    return positions, frozenset(connector_pins)


def _verify_nets(
    circuit: Circuit, bindings: tuple[NetIdentity, ...],
) -> dict[str, NetIdentity]:
    if len(set(item.id for item in bindings)) != len(bindings):
        raise ValueError("WIRE_END_DUPLICATE_NET_ID")
    if len(set(n.name for n in circuit.nets)) != len(circuit.nets):
        raise ValueError("WIRE_END_AMBIGUOUS_REAL_NET")
    by_name = {n.name: n for n in circuit.nets}
    if {b.net_name for b in bindings} != set(by_name) or len(bindings) != len(by_name):
        raise ValueError("WIRE_END_INCOMPLETE_NET_BINDING")
    owners: dict[PinRef, str] = {}
    for binding in bindings:
        real = by_name.get(binding.net_name)
        if real is None or real.members != binding.members:
            raise ValueError("WIRE_END_REAL_NET_MEMBERS_MISMATCH")
        for member in real.members:
            if member in owners and owners[member] != binding.id:
                raise ValueError("WIRE_END_PHYSICAL_PIN_MULTI_NET")
            owners[member] = binding.id
    if not set(m.reference for m in owners).issubset({
        p.reference for p in circuit.components
    }):
        raise ValueError("WIRE_END_UNKNOWN_COMPONENT")
    return {binding.net_name: binding for binding in bindings}


def collect_wire_endpoints(
    circuit: Circuit,
    graph: ExternalWireGraph,
    nets: tuple[NetIdentity, ...],
    wire_ids: tuple[str, ...],
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    continuations: NetContinuationProject | None = None,
    blocked_pins: frozenset[PinRef] = frozenset(),
    blocked_wire_ends: frozenset[tuple[str, WireEndSide]] = frozenset(),
) -> WireEndpointSnapshot:
    """Resolve exact physical metadata; never create connectivity or junctions.

    Eligibility is only an editor suggestion; connecting still needs an
    explicit, atomic, revision-checked, ERC-approved future transaction.
    """
    if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
        raise TypeError("Requires real Circuit and authored ExternalWireGraph")
    if type(nets) is not tuple or not all(isinstance(x, NetIdentity) for x in nets):
        raise TypeError("Expected tuple[NetIdentity]")
    if type(wire_ids) is not tuple or len(wire_ids) != len(graph.segments):
        raise ValueError("WIRE_END_WIRE_IDS_INCOMPLETE")
    if len(set(wire_ids)) != len(wire_ids) or any(
        type(x) is not str or not x or x.strip() != x for x in wire_ids
    ):
        raise ValueError("WIRE_END_WIRE_IDS_DUPLICATE_OR_INVALID")
    if not isinstance(blocked_pins, frozenset) or not isinstance(blocked_wire_ends, frozenset):
        raise TypeError("Blocked targets must be immutable frozensets")
    for pair in blocked_wire_ends:
        if type(pair) is not tuple or len(pair) != 2 or (
            pair[0] not in wire_ids or not isinstance(pair[1], WireEndSide)
        ):
            raise ValueError("WIRE_END_UNKNOWN_BLOCKED_END")
    binding_by_name = _verify_nets(circuit, nets)
    pin_positions, connector_pins = _resolve_contacts(circuit, parts, symbols)
    claimed_pins = {m for n in circuit.nets for m in n.members}
    if not claimed_pins.issubset(pin_positions):
        raise ValueError("WIRE_END_UNKNOWN_NET_PIN")
    if not blocked_pins.issubset(pin_positions):
        raise ValueError("WIRE_END_UNKNOWN_BLOCKED_PIN")
    wire_to_net: dict[str, str] = {}
    for wire_id, segment in zip(wire_ids, graph.segments, strict=True):
        binding = binding_by_name.get(segment.net_name)
        if binding is None:
            raise ValueError("WIRE_END_WIRE_NET_UNKNOWN")
        wire_to_net[wire_id] = binding.id

    marker_by_point: dict[Point, tuple[str, str, str]] = {}
    if continuations is not None:
        if not isinstance(continuations, NetContinuationProject) or (
            continuations.circuit != circuit
        ):
            raise ValueError("WIRE_END_FOREIGN_CONTINUATION_CIRCUIT")
        if validate_net_continuations(continuations):
            raise ValueError("WIRE_END_INVALID_CONTINUATIONS")
        if {(n.id, n.net_name, n.members) for n in continuations.nets} != {
            (n.id, n.net_name, n.members) for n in nets
        }:
            raise ValueError("WIRE_END_FOREIGN_CONTINUATION_NETS")
        stub_by_end = {s.endpoint_id: s for s in continuations.stubs}
        for marker in continuations.endpoints:
            stub = stub_by_end[marker.id]
            matching = [
                wire_id for wire_id, wire in zip(wire_ids, graph.segments, strict=True)
                if {wire.start, wire.end} == {stub.start, stub.end}
                and wire_to_net[wire_id] == marker.net_id
            ]
            if len(matching) != 1 or marker.anchor in marker_by_point:
                raise ValueError("WIRE_END_CONTINUATION_STUB_UNRESOLVED")
            if marker.anchor in pin_positions.values():
                raise ValueError("WIRE_END_CONTINUATION_IS_NOT_A_PHYSICAL_PIN")
            marker_by_point[marker.anchor] = (marker.id, marker.net_id, matching[0])

    # Two foreign nets must never be silently accepted as overlapping copper.
    # This is a read-only diagnostic rejection, NOT an automatic net repair.
    for i, first in enumerate(graph.segments):
        for second in graph.segments[:i]:
            if first.net_name == second.net_name:
                continue
            if _positive_collinear_overlap(first, second):
                raise ValueError("WIRE_END_CROSS_NET_COLLINEAR_SHORT")

    for junction in graph.junctions:
        touching = [segment.net_name for segment in graph.segments if _on(segment, junction)]
        if len(touching) < 2 or len(set(touching)) != 1:
            raise ValueError("WIRE_END_INVALID_OR_CROSS_NET_JUNCTION")

    # A Net name on an orphan drawn segment is NOT evidence of an actual
    # physical connection. Determine same-net islands from AUTHORITATIVE
    # authored graph rules (shared endpoints, overlap, explicit junctions).
    # Unmarked T/X contacts do NOT union islands.
    parents = list(range(len(graph.segments)))

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(a: int, b: int) -> None:
        x, y = find(a), find(b)
        parents[max(x, y)] = min(x, y)

    for i, segment in enumerate(graph.segments):
        for j, earlier in enumerate(graph.segments[:i]):
            if segment.net_name != earlier.net_name:
                continue
            common_endpoint = any(
                p in (earlier.start, earlier.end)
                for p in (segment.start, segment.end)
            )
            common_junction = any(
                _on(segment, p) and _on(earlier, p) for p in graph.junctions
            )
            if common_endpoint or common_junction or _positive_collinear_overlap(
                segment, earlier,
            ):
                union(i, j)
    anchored_islands: set[int] = set()
    net_owners = {
        n.net_name: frozenset(n.members) for n in nets
    }
    for i, segment in enumerate(graph.segments):
        for pin, point in pin_positions.items():
            if pin not in net_owners[segment.net_name]:
                continue
            if point in (segment.start, segment.end) or (
                point in graph.junctions and _on(segment, point)
            ):
                anchored_islands.add(find(i))

    ids = set()
    ends: list[WireEndpoint] = []
    for index, (wire_id, segment) in enumerate(zip(wire_ids, graph.segments, strict=True)):
        net_id = wire_to_net[wire_id]
        for side in WireEndSide:
            point = _source_point(segment, side)
            attached = [
                pin for pin, pos in pin_positions.items() if pos == point
            ]
            attached_claimed = [
                pin for pin in attached if pin in binding_by_name[segment.net_name].members
            ]
            if len(attached) > 1 or (attached and not attached_claimed):
                termination, state, ref, cont, reason = (
                    WireTermination.UNMARKED_TOUCH, TargetState.BLOCKED,
                    None, None, "FOREIGN_OR_AMBIGUOUS_PHYSICAL_PIN",
                )
            elif attached_claimed:
                ref = attached_claimed[0]
                termination = (
                    WireTermination.CONNECTOR_CONTACT if ref in connector_pins
                    else WireTermination.PHYSICAL_PIN
                )
                state, cont, reason = TargetState.CONNECTED, None, "ALREADY_PIN_CONNECTED"
            elif point in marker_by_point:
                marker_id, marker_net, marker_wire = marker_by_point[point]
                if marker_net != net_id or marker_wire != wire_id:
                    raise ValueError("WIRE_END_CONTINUATION_CROSS_NET_OR_WRONG_WIRE")
                termination, state, ref, cont, reason = (
                    WireTermination.CONTINUATION, TargetState.NONPHYSICAL,
                    None, marker_id, "NONPHYSICAL_CONTINUATION",
                )
            elif point in graph.junctions:
                termination, state, ref, cont, reason = (
                    WireTermination.JUNCTION, TargetState.CONNECTED,
                    None, None, "EXPLICIT_JUNCTION",
                )
            else:
                other_end = any(
                    j != index and point in (other.start, other.end)
                    and other.net_name == segment.net_name
                    for j, other in enumerate(graph.segments)
                )
                foreign_end = any(
                    j != index and point in (other.start, other.end)
                    and other.net_name != segment.net_name
                    for j, other in enumerate(graph.segments)
                )
                other_interior = any(
                    j != index and _interior(other, point)
                    for j, other in enumerate(graph.segments)
                )
                if other_interior or foreign_end:
                    termination, state, ref, cont, reason = (
                        WireTermination.UNMARKED_TOUCH, TargetState.BLOCKED,
                        None, None,
                        "FOREIGN_NET_COINCIDENT_ENDPOINT" if foreign_end
                        else "T_TOUCH_REQUIRES_EXPLICIT_JUNCTION",
                    )
                elif other_end:
                    termination, state, ref, cont, reason = (
                        WireTermination.JOINED_WIRE, TargetState.CONNECTED,
                        None, None, "WIRE_ENDPOINT_JOIN",
                    )
                else:
                    blocked = (
                        (wire_id, side) in blocked_wire_ends
                        or find(index) not in anchored_islands
                    )
                    reason = (
                        "UNANCHORED_CONDUCTOR_ISLAND" if find(index) not in anchored_islands
                        else "POLICY_BLOCKED" if (wire_id, side) in blocked_wire_ends
                        else "FREE_WIRE_END"
                    )
                    termination, state, ref, cont = (
                        WireTermination.FREE,
                        TargetState.BLOCKED if blocked else TargetState.AVAILABLE,
                        None, None,
                    )
            eligible = termination is WireTermination.FREE and state is TargetState.AVAILABLE
            end_id = f"{wire_id}:{side.value}"
            if end_id in ids:
                raise ValueError("WIRE_END_DUPLICATE_ENDPOINT_ID")
            ids.add(end_id)
            ends.append(WireEndpoint(
                end_id, wire_id, index, side, net_id, point,
                termination, state, eligible, ref, cont, reason,
            ))

    contacts: list[PhysicalContactTarget] = []
    owner_net = {
        pin: n.id for n in nets for pin in n.members
    }
    for pin, point in sorted(
        pin_positions.items(), key=lambda pair: (pair[0].reference, pair[0].number)
    ):
        attached_segments = [
            s for s in graph.segments
            if point in (s.start, s.end) or (
                point in graph.junctions and _on(s, point)
            )
        ]
        unsafe = any(s.net_name != next(
            (n.net_name for n in nets if n.id == owner_net.get(pin)), None,
        ) for s in attached_segments)
        blocked = pin in blocked_pins or unsafe
        status = (
            TargetState.BLOCKED if blocked else
            TargetState.CONNECTED if attached_segments else TargetState.AVAILABLE
        )
        contacts.append(PhysicalContactTarget(
            f"pin:{pin.reference}.{pin.number}", pin, point,
            owner_net.get(pin), pin in connector_pins, status,
            not blocked and not attached_segments and pin in owner_net,
            "PIN_POLICY_BLOCKED" if pin in blocked_pins else
            "FOREIGN_WIRE_CONTACT" if unsafe else
            "ALREADY_CONNECTED" if attached_segments else
            "PHYSICAL_PIN_AVAILABLE" if pin in owner_net else
            "PIN_NOT_IN_DECLARED_NET",
        ))

    crossing_records = []
    for i, first in enumerate(graph.segments):
        for j in range(i):
            p = _crossing(first, graph.segments[j])
            if p is not None and p not in graph.junctions:
                crossing_records.append(NonJoiningCrossing(
                    f"X:{wire_ids[j]}:{wire_ids[i]}", p, wire_ids[j], wire_ids[i],
                    wire_to_net[wire_ids[j]], wire_to_net[wire_ids[i]],
                ))
    return WireEndpointSnapshot(
        circuit, graph, nets, wire_ids, tuple(ends), tuple(contacts),
        tuple(crossing_records),
        tuple(e.id for e in continuations.endpoints) if continuations else (),
    )


def validate_wire_endpoint_snapshot(snapshot: WireEndpointSnapshot) -> None:
    """Reject altered fields, misbound IDs and stale endpoint coordinates."""
    if not isinstance(snapshot, WireEndpointSnapshot) or snapshot.schema_version != 1:
        raise ValueError("WIRE_END_INVALID_SNAPSHOT")
    if len(snapshot.wire_endpoints) != len(snapshot.graph.segments) * 2:
        raise ValueError("WIRE_END_INCOMPLETE_ENDPOINTS")
    if len({e.id for e in snapshot.wire_endpoints}) != len(snapshot.wire_endpoints):
        raise ValueError("WIRE_END_DUPLICATE_ENDPOINT")
    by_name = _verify_nets(snapshot.circuit, snapshot.nets)
    for endpoint in snapshot.wire_endpoints:
        if endpoint.wire_index >= len(snapshot.graph.segments):
            raise ValueError("WIRE_END_UNKNOWN_SEGMENT")
        wire = snapshot.graph.segments[endpoint.wire_index]
        if snapshot.wire_ids[endpoint.wire_index] != endpoint.wire_id:
            raise ValueError("WIRE_END_SEGMENT_ID_MISMATCH")
        if endpoint.point != _source_point(wire, endpoint.side):
            raise ValueError("WIRE_END_POINT_MISMATCH")
        if by_name[wire.net_name].id != endpoint.net_id:
            raise ValueError("WIRE_END_NET_ID_MISMATCH")
        if endpoint.id != f"{endpoint.wire_id}:{endpoint.side.value}":
            raise ValueError("WIRE_END_ID_MISMATCH")
        if endpoint.can_accept_connection != (
            endpoint.termination is WireTermination.FREE
            and endpoint.state is TargetState.AVAILABLE
        ):
            raise ValueError("WIRE_END_ELIGIBILITY_MISMATCH")
