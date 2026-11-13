"""Graph and straight-chord inspection diagnostics for the isolated E1 model.

Chords are conservative *validation geometry*, not a routed wire graph.
Intersections never connect structural links, and cannot short electrical nets.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import combinations

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.structural.model import (
    BlockPort,
    FunctionalBlock,
    FunctionalLink,
    PortDirection,
    PortRef,
    StructuralDiagram,
)


def _error(code: str, message: str, subject: str) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, message, subject)


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    return (
        _cross(a, b, point) == 0
        and min(a.x, b.x) <= point.x <= max(a.x, b.x)
        and min(a.y, b.y) <= point.y <= max(a.y, b.y)
    )


def _cross(a: Point, b: Point, c: Point) -> int:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _segment_intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    s1, s2 = _cross(a, b, c), _cross(a, b, d)
    t1, t2 = _cross(c, d, a), _cross(c, d, b)
    if s1 == s2 == t1 == t2 == 0:
        return (
            max(min(a.x, b.x), min(c.x, d.x))
            <= min(max(a.x, b.x), max(c.x, d.x))
            and max(min(a.y, b.y), min(c.y, d.y))
            <= min(max(a.y, b.y), max(c.y, d.y))
        )
    return (
        (s1 * s2 < 0 and t1 * t2 < 0)
        or (s1 == 0 and _point_on_segment(c, a, b))
        or (s2 == 0 and _point_on_segment(d, a, b))
        or (t1 == 0 and _point_on_segment(a, c, d))
        or (t2 == 0 and _point_on_segment(b, c, d))
    )


def _positive_collinear_overlap(a: Point, b: Point, c: Point, d: Point) -> bool:
    if _cross(a, b, c) != 0 or _cross(a, b, d) != 0:
        return False
    if a.x != b.x:
        return max(min(a.x, b.x), min(c.x, d.x)) < min(
            max(a.x, b.x), max(c.x, d.x)
        )
    return max(min(a.y, b.y), min(c.y, d.y)) < min(
        max(a.y, b.y), max(c.y, d.y)
    )


def _segment_through_block_interior(a: Point, b: Point, box: Box) -> bool:
    """Exact open-rectangle segment intersection, no float/tangency ambiguity."""
    low, high = Fraction(0), Fraction(1)
    for start, delta, lower, upper in (
        (a.x, b.x - a.x, box.min_x, box.max_x),
        (a.y, b.y - a.y, box.min_y, box.max_y),
    ):
        if delta == 0:
            if not lower < start < upper:
                return False
            continue
        first, second = Fraction(lower - start, delta), Fraction(upper - start, delta)
        low = max(low, min(first, second))
        high = min(high, max(first, second))
    return low < high


def _anchor(block: FunctionalBlock, side: Side, fraction: Fraction) -> Point:
    bounds = block.bounds
    length = block.height_um if side in (Side.LEFT, Side.RIGHT) else block.width_um
    coordinate = fraction * length
    if coordinate.denominator != 1:
        raise ValueError("relative port position is not integral in micrometres")
    index = coordinate.numerator
    if side == Side.LEFT:
        return Point(bounds.min_x, bounds.min_y + index)
    if side == Side.RIGHT:
        return Point(bounds.max_x, bounds.min_y + index)
    if side == Side.TOP:
        return Point(bounds.min_x + index, bounds.min_y)
    return Point(bounds.min_x + index, bounds.max_y)


def _port_geometry(
    diagram: StructuralDiagram, blocks: dict[str, FunctionalBlock],
) -> tuple[dict[PortRef, Point], tuple[Diagnostic, ...]]:
    issues: list[Diagnostic] = []
    groups: dict[tuple[str, Side], list[BlockPort]] = defaultdict(list)
    for port in diagram.ports:
        groups[(port.block_id, port.side)].append(port)
    positions: dict[PortRef, Point] = {}
    owners: dict[str, dict[Point, PortRef]] = defaultdict(dict)
    seen: set[PortRef] = set()
    for (block_id, side), group in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        block = blocks.get(block_id)
        for index, port in enumerate(group):
            ref = port.ref
            if ref in seen:
                issues.append(_error(
                    "E1_DUPLICATE_PORT", f"Duplicated port {block_id}.{port.id}", block_id
                ))
                continue
            seen.add(ref)
            if block is None:
                issues.append(_error(
                    "E1_PORT_BLOCK_UNKNOWN",
                    f"Port {block_id}.{port.id} refers to missing block", block_id,
                ))
                continue
            fraction = (
                port.position if port.position is not None
                else Fraction(index + 1, len(group) + 1)
            )
            try:
                point = _anchor(block, side, fraction)
            except ValueError:
                issues.append(_error(
                    "E1_PORT_OFF_GRID",
                    f"Port {block_id}.{port.id} at {fraction} is off the 1µm grid",
                    block_id,
                ))
                continue
            positions[ref] = point
            previous = owners[block_id].get(point)
            if previous is not None:
                issues.append(_error(
                    "E1_PORT_COLLISION",
                    f"Ports {previous.port_id} and {port.id} coincide at {point}",
                    block_id,
                ))
            else:
                owners[block_id][point] = ref
    return positions, tuple(issues)


def resolve_port_positions(diagram: StructuralDiagram) -> dict[PortRef, Point]:
    """Return exactly computed declared anchors; reject invalid port inventory."""
    blocks = {b.id: b for b in diagram.blocks}
    if len(blocks) != len(diagram.blocks):
        raise ValueError("Duplicate block ID; cannot resolve port coordinates")
    points, issues = _port_geometry(diagram, blocks)
    if issues:
        raise ValueError("; ".join(f"{d.code}:{d.message}" for d in issues))
    return points


def _invalid_link(
    link: FunctionalLink,
    ports: dict[PortRef, BlockPort],
    positions: dict[PortRef, Point],
    issues: list[Diagnostic],
) -> bool:
    bad = False
    for ref in (link.source, link.target):
        if ref not in ports or ref not in positions:
            issues.append(_error(
                "E1_LINK_PORT_UNKNOWN",
                f"Link {link.id} has missing or invalid port {ref.block_id}.{ref.port_id}",
                link.id,
            ))
            bad = True
    if bad:
        return True
    if link.source.block_id == link.target.block_id:
        issues.append(_error("E1_SELF_LINK", f"Link {link.id} joins its own block", link.id))
        bad = True
    if ports[link.source].direction == PortDirection.INPUT:
        issues.append(_error(
            "E1_SOURCE_DIRECTION", f"Source {link.source} is input-only", link.id,
        ))
        bad = True
    if ports[link.target].direction == PortDirection.OUTPUT:
        issues.append(_error(
            "E1_TARGET_DIRECTION", f"Target {link.target} is output-only", link.id,
        ))
        bad = True
    if positions[link.source] == positions[link.target]:
        issues.append(_error(
            "E1_ZERO_LENGTH_LINK", f"Link {link.id} has coincident anchors", link.id,
        ))
        bad = True
    return bad


def validate_structural_diagram(diagram: StructuralDiagram) -> tuple[Diagnostic, ...]:
    """Fail closed on illegal E1 references, directions, and straight geometry.

    Inspection chords are NOT autoroutes and NOT conductive wires. Directed
    cycles are permitted as intentional process feedback; no electrical shorts
    or junctions are inferred at crossings.
    """
    if not isinstance(diagram, StructuralDiagram):
        raise TypeError("Expected StructuralDiagram")
    issues: list[Diagnostic] = []
    blocks: dict[str, FunctionalBlock] = {}
    for block in sorted(diagram.blocks, key=lambda item: item.id):
        if block.id in blocks:
            issues.append(_error(
                "E1_DUPLICATE_BLOCK", f"Block ID {block.id} repeats", block.id,
            ))
        else:
            blocks[block.id] = block

    for first, second in combinations(sorted(blocks.values(), key=lambda b: b.id), 2):
        if first.bounds.overlaps(second.bounds):
            issues.append(_error(
                "E1_BLOCK_OVERLAP",
                f"Rectangles {first.id} and {second.id} overlap in area",
                f"{first.id}/{second.id}",
            ))

    positions, port_issues = _port_geometry(diagram, blocks)
    issues.extend(port_issues)
    port_map: dict[PortRef, BlockPort] = {}
    for item in diagram.ports:
        port_map.setdefault(item.ref, item)

    seen_ids: set[str] = set()
    seen_pairs: set[tuple[PortRef, PortRef]] = set()
    chords: list[tuple[FunctionalLink, Point, Point]] = []
    for link in sorted(diagram.links, key=lambda item: item.id):
        if link.id in seen_ids:
            issues.append(_error(
                "E1_DUPLICATE_LINK", f"Link ID {link.id} repeats", link.id,
            ))
            continue
        seen_ids.add(link.id)
        pair = (link.source, link.target)
        if pair in seen_pairs:
            issues.append(_error(
                "E1_DUPLICATE_CONNECTION", f"Connection {pair} repeats", link.id,
            ))
            continue
        seen_pairs.add(pair)
        if _invalid_link(link, port_map, positions, issues):
            continue
        a, b = positions[link.source], positions[link.target]
        chords.append((link, a, b))
        for block in sorted(blocks.values(), key=lambda item: item.id):
            if _segment_through_block_interior(a, b, block.bounds):
                issues.append(_error(
                    "E1_LINK_THROUGH_BLOCK",
                    f"Link {link.id} crosses block {block.id} interior",
                    link.id,
                ))
        for ref, point in sorted(
            positions.items(), key=lambda item: (item[0].block_id, item[0].port_id)
        ):
            if ref not in (link.source, link.target) and _point_on_segment(point, a, b):
                issues.append(_error(
                    "E1_LINK_THROUGH_PORT",
                    f"Link {link.id} passes undeclared port {ref.block_id}.{ref.port_id}",
                    link.id,
                ))

    for (first, a, b), (second, c, d) in combinations(chords, 2):
        if not _segment_intersects(a, b, c, d):
            continue
        shared = {first.source, first.target} & {second.source, second.target}
        if shared and not _positive_collinear_overlap(a, b, c, d):
            # Same explicitly declared anchor: legitimate output fan-out,
            # never an inferred conductive T or node.
            continue
        issues.append(_error(
            "E1_LINK_CROSSING",
            f"Inspection chords {first.id} and {second.id} touch/cross without "
            "a unique shared declared endpoint",
            f"{first.id}/{second.id}",
        ))

    return tuple(sorted(
        issues, key=lambda item: (item.code, item.subject or "", item.message)
    ))
