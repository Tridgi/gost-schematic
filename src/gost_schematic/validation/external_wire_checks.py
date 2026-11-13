"""Experimental sheet-level wire connectivity, independent of symbol ink.

The semantic netlist belongs to Circuit. This module checks an explicitly
authored *external* conductor graph against it; it never synthesizes nets
from rendered SVG crossings or connects through component internals.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class WireSegment:
    """One straight, exact-µm external conductor with a declared net label."""

    start: Point
    end: Point
    net_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.start, Point) or not isinstance(self.end, Point):
            raise TypeError("WireSegment endpoints must be Points")
        if self.start == self.end:
            raise ValueError("Zero-length external wire is invalid")
        if not isinstance(self.net_name, str) or not self.net_name.strip():
            raise ValueError("External wire net_name must be non-empty")


@dataclass(frozen=True, slots=True)
class ExternalWireGraph:
    """Authored sheet wires; junctions are explicit conductive contacts.

    Coincident wire endpoints and positive-length collinear overlap connect.
    An isolated endpoint touching an interior, and an interior crossing, only
    connect when their exact coordinate is listed in `junctions`.
    """

    segments: tuple[WireSegment, ...]
    junctions: tuple[Point, ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(wire, WireSegment) for wire in self.segments):
            raise TypeError("ExternalWireGraph segments must be WireSegments")
        if any(not isinstance(point, Point) for point in self.junctions):
            raise TypeError("ExternalWireGraph junctions must be Points")
        if len(set(self.junctions)) != len(self.junctions):
            raise ValueError("Duplicate junction coordinate")


def _cross(a: Point, b: Point, p: Point) -> int:
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)


def _on_wire(wire: WireSegment, point: Point) -> bool:
    return (
        _cross(wire.start, wire.end, point) == 0
        and min(wire.start.x, wire.end.x) <= point.x <= max(wire.start.x, wire.end.x)
        and min(wire.start.y, wire.end.y) <= point.y <= max(wire.start.y, wire.end.y)
    )


def _overlap(a: WireSegment, b: WireSegment) -> bool:
    """Strictly positive collinear overlap, including diagonal segments."""
    if _cross(a.start, a.end, b.start) or _cross(a.start, a.end, b.end):
        return False
    if a.start.x != a.end.x:
        first = sorted((a.start.x, a.end.x))
        second = sorted((b.start.x, b.end.x))
    else:
        first = sorted((a.start.y, a.end.y))
        second = sorted((b.start.y, b.end.y))
    return max(first[0], second[0]) < min(first[1], second[1])


class _Disjoint:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        a, b = self.find(first), self.find(second)
        self.parent[max(a, b)] = min(a, b)


def _endpoint_connected(
    point: Point,
    current: WireSegment,
    other: WireSegment,
    junctions: frozenset[Point],
) -> bool:
    return _on_wire(other, point) and (
        point == other.start
        or point == other.end
        or point in junctions
        or _overlap(current, other)
    )


def validate_external_wires(
    circuit: Circuit,
    graph: ExternalWireGraph,
    parts: Mapping[str, PartDefinition],
    symbols: Mapping[str, SymbolDefinition],
) -> tuple[Diagnostic, ...]:
    """Compare physical sheet contacts to the declared nets without mutating either.

    Returns deterministic diagnostics, not an inferred/persisted netlist.
    A single-member net need not have a drawn wire. Geometry is exact; no
    tolerance, pin-escape check, global labels, sheet ports or autorouting.
    """
    issues: list[Diagnostic] = []

    def error(code: str, message: str, subject: str | None = None) -> None:
        issues.append(Diagnostic(code, Severity.ERROR, message, subject))

    declared: dict[str, tuple[PinRef, ...]] = {}
    owners: dict[PinRef, set[str]] = defaultdict(set)
    for net in circuit.nets:
        if net.name in declared:
            error("WIRE_DUPLICATE_NET", f"Ambiguous duplicate net {net.name}", net.name)
        declared[net.name] = net.members
        for ref in net.members:
            owners[ref].add(net.name)
    for ref, names in sorted(owners.items(), key=lambda item: (item[0].reference, item[0].number)):
        if len(names) > 1:
            error("WIRE_PIN_MULTI_NET", f"{ref.reference}.{ref.number} has multiple nets", ref.reference)

    positions: dict[PinRef, Point] = {}
    seen: set[str] = set()
    for instance in circuit.components:
        if instance.reference in seen:
            error("WIRE_DUPLICATE_REFERENCE", f"Ambiguous {instance.reference}", instance.reference)
            continue
        seen.add(instance.reference)
        part = parts.get(instance.part_id)
        if part is None:
            error("WIRE_UNKNOWN_PART", f"Unknown part {instance.part_id}", instance.reference)
            continue
        symbol = symbols.get(part.symbol_id)
        if symbol is None:
            error("WIRE_UNKNOWN_SYMBOL", f"Unknown symbol {part.symbol_id}", instance.reference)
            continue
        graphic = instance.pin_positions(symbol)
        for physical in part.pins:
            if physical.number not in graphic:
                error(
                    "WIRE_PIN_UNMAPPED",
                    f"No graphic pin for {instance.reference}.{physical.number}",
                    instance.reference,
                )
            else:
                positions[PinRef(instance.reference, physical.number)] = graphic[physical.number]

    for ref in owners:
        if ref not in positions:
            error(
                "WIRE_UNKNOWN_PIN",
                f"Unresolved physical pin {ref.reference}.{ref.number}",
                ref.reference,
            )

    segments = graph.segments
    explicit = frozenset(graph.junctions)
    for i, wire in enumerate(segments):
        if wire.net_name not in declared:
            error("WIRE_UNKNOWN_NET", f"Wire {i} names missing net {wire.net_name}", str(i))

    connected = _Disjoint(len(segments))
    for i, first in enumerate(segments):
        for j in range(i):
            second = segments[j]
            if (
                _overlap(first, second)
                or first.start in (second.start, second.end)
                or first.end in (second.start, second.end)
            ):
                connected.union(i, j)

    for junction in graph.junctions:
        touching = [i for i, wire in enumerate(segments) if _on_wire(wire, junction)]
        if not touching or (len(touching) < 2 and junction not in positions.values()):
            error(
                "WIRE_JUNCTION_DANGLING",
                f"Junction {junction} has fewer than two wires and no pin",
                f"{junction.x},{junction.y}",
            )
        for index in touching[1:]:
            connected.union(touching[0], index)

    attachments: dict[PinRef, set[int]] = defaultdict(set)
    wires_with_pins: dict[int, set[PinRef]] = defaultdict(set)
    for ref, point in positions.items():
        interior_nets: set[str] = set()
        for i, wire in enumerate(segments):
            if point == wire.start or point == wire.end or (
                point in explicit and _on_wire(wire, point)
            ):
                attachments[ref].add(i)
                wires_with_pins[i].add(ref)
            elif _on_wire(wire, point):
                interior_nets.add(wire.net_name)
        # Issue #40: report an unmarked interior touching an unattached pin.
        # Issue #58: another legitimate endpoint attachment must NOT hide an
        # unmarked interior of a FOREIGN net at that physical contact.
        # Neither case implies a junction or electrically joins wire islands.
        if interior_nets and (
            not attachments[ref]
            or any(net not in owners.get(ref, ()) for net in interior_nets)
        ):
            error(
                "WIRE_PIN_CONTACT_UNDECLARED",
                f"{ref.reference}.{ref.number} touches a wire interior without junction",
                ref.reference,
            )
        if attachments[ref] and ref not in owners:
            error(
                "WIRE_PIN_UNASSIGNED",
                f"{ref.reference}.{ref.number} is wired but has no net",
                ref.reference,
            )

    # A physical wire island is a disjoint-set group of authored segments.
    wire_islands: dict[int, list[int]] = defaultdict(list)
    labels: dict[int, set[str]] = defaultdict(set)
    island_pins: dict[int, set[PinRef]] = defaultdict(set)
    for i, wire in enumerate(segments):
        root = connected.find(i)
        wire_islands[root].append(i)
        labels[root].add(wire.net_name)
        for ref in wires_with_pins[i]:
            island_pins[root].add(ref)
            labels[root].update(owners.get(ref, ()))
            if owners.get(ref) and wire.net_name not in owners[ref]:
                error(
                    "WIRE_PIN_NET_MISMATCH",
                    f"Wire {i} ({wire.net_name}) reaches {ref.reference}.{ref.number}",
                    ref.reference,
                )

    for root in sorted(wire_islands):
        if len(labels[root]) > 1:
            error(
                "WIRE_NET_SHORT",
                f"Conductors join distinct nets: {', '.join(sorted(labels[root]))}",
                str(root),
            )
        if not island_pins[root]:
            error(
                "WIRE_ORPHAN_CONDUCTOR",
                f"Wire island {root} has no physical pin",
                str(root),
            )

    for net_name, members in declared.items():
        unique = tuple(dict.fromkeys(members))
        if len(unique) < 2:
            continue
        roots = {
            connected.find(i)
            for ref in unique
            for i in attachments.get(ref, ())
        }
        unwired = [ref for ref in unique if ref in positions and not attachments[ref]]
        for ref in unwired:
            error(
                "WIRE_PIN_UNWIRED",
                f"{ref.reference}.{ref.number} of {net_name} has no conductor",
                ref.reference,
            )
        if len(roots) != 1 or unwired or any(ref not in positions for ref in unique):
            error(
                "WIRE_NET_DISCONNECTED",
                f"Net {net_name} does not form one physical wire island",
                net_name,
            )

    for i, wire in enumerate(segments):
        for end in (wire.start, wire.end):
            pinned = any(point == end for point in positions.values())
            joined = any(
                j != i and _endpoint_connected(end, wire, other, explicit)
                for j, other in enumerate(segments)
            )
            if not pinned and not joined:
                error(
                    "WIRE_DANGLING_END",
                    f"Wire {i} has an unconnected endpoint at {end.x},{end.y}",
                    str(i),
                )

    return tuple(issues)
