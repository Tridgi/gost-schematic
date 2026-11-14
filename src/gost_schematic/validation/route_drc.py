"""Issue #108: stroke-aware, read-only E3 print geometry DRC.

Covers exact segment geometry, explicit junctions, separate Circuit.Net
authority, graphic boxes and measured text keepouts. It NEVER joins nets
by proximity or alters an authored ExternalWireGraph. ГОСТ 2.701-2008
§5.3.4 requires a 3 mm gap for neighboring PARALLEL CONNECTION lines,
not for every perpendicular X crossing or a legal same-net junction.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import sqrt

from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

WIRE_PARALLEL_GAP_UM = 3000
SYMBOL_GAP_UM = 2000
SYMBOL_GRAPHIC_GAP_UM = 1000
WIRE_STROKE_MIN_UM = 200
WIRE_STROKE_MAX_UM = 1000


@dataclass(frozen=True, slots=True)
class RouteDRCFinding:
    code: str
    severity: str
    first: str
    second: str | None
    detail: str
    measured_edge_um: float | None = None
    required_um: int | None = None
    point_um: tuple[str, str] | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code, "severity": self.severity,
            "first": self.first, "second": self.second, "detail": self.detail,
            "measured_edge_um": self.measured_edge_um,
            "required_um": self.required_um, "point_um": self.point_um,
        }


@dataclass(frozen=True, slots=True)
class ParallelPairMeasurement:
    first_index: int
    second_index: int
    first_net: str
    second_net: str
    measured_edge_um: float
    required_um: int
    compliant: bool
    same_line: bool

    def as_dict(self) -> dict:
        return {
            "segments": [self.first_index, self.second_index],
            "nets": [self.first_net, self.second_net],
            "measured_edge_um": self.measured_edge_um,
            "required_um": self.required_um,
            "compliant": self.compliant, "same_line": self.same_line,
        }


@dataclass(frozen=True, slots=True)
class RouteDRCReport:
    wire_count: int
    component_count: int
    net_count: int
    explicit_junctions: int
    total_wire_length_um: float
    orthogonal_segments: int
    diagonal_segments: int
    bent_connection_pairs: int
    crossing_pairs: int
    crossing_different_net: int
    parallel_measurements: tuple[ParallelPairMeasurement, ...]
    findings: tuple[RouteDRCFinding, ...]
    checked_symbol_geometry: bool
    checked_measured_text: bool

    @property
    def valid(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    def as_dict(self) -> dict:
        return {
            "schema_version": 1, "status": "DRAFT_GEOMETRIC_DRC_NOT_GOST_APPROVED",
            "wire_count": self.wire_count,
            "component_count": self.component_count,
            "net_count": self.net_count,
            "explicit_junctions": self.explicit_junctions,
            "total_wire_length_um": self.total_wire_length_um,
            "orthogonal_segments": self.orthogonal_segments,
            "diagonal_segments": self.diagonal_segments,
            "bent_connection_pairs": self.bent_connection_pairs,
            "crossing_pairs": self.crossing_pairs,
            "crossing_different_net": self.crossing_different_net,
            "parallel_measurements": [x.as_dict() for x in self.parallel_measurements],
            "findings": [x.as_dict() for x in self.findings],
            "error_count": sum(x.severity == "error" for x in self.findings),
            "warning_count": sum(x.severity == "warning" for x in self.findings),
            "valid": self.valid,
            "checked_symbol_geometry": self.checked_symbol_geometry,
            "checked_measured_text": self.checked_measured_text,
            "restrictions": (
                "No net merge, no autoroute, no inferred junction. Parallel-wire "
                "3mm applies only when projections overlap; measured clearances "
                "include both real stroke widths. Unknown native symbol/text "
                "geometry must not be treated as a successful whole-sheet DRC."
            ),
        }


def _cross(dx: int, dy: int, ex: int, ey: int) -> int:
    return dx * ey - dy * ex


def _direction(wire: WireSegment) -> tuple[int, int]:
    return wire.end.x - wire.start.x, wire.end.y - wire.start.y


def _on(wire: WireSegment, p: Point) -> bool:
    a, b = wire.start, wire.end
    return (
        _cross(b.x - a.x, b.y - a.y, p.x - a.x, p.y - a.y) == 0
        and min(a.x, b.x) <= p.x <= max(a.x, b.x)
        and min(a.y, b.y) <= p.y <= max(a.y, b.y)
    )


def _interior(wire: WireSegment, p: Point) -> bool:
    return _on(wire, p) and p not in (wire.start, wire.end)


def _rational_xy(value: tuple[Fraction, Fraction]) -> tuple[str, str]:
    return tuple(str(coord) for coord in value)


def _strict_crossing(
    first: WireSegment, second: WireSegment,
) -> tuple[Fraction, Fraction] | None:
    a, b = first.start, second.start
    rx, ry = _direction(first)
    sx, sy = _direction(second)
    denominator = _cross(rx, ry, sx, sy)
    if not denominator:
        return None
    t = Fraction(_cross(b.x - a.x, b.y - a.y, sx, sy), denominator)
    u = Fraction(_cross(b.x - a.x, b.y - a.y, rx, ry), denominator)
    if not (0 < t < 1 and 0 < u < 1):
        return None
    return Fraction(a.x) + t * rx, Fraction(a.y) + t * ry


def _parallel_overlap(first: WireSegment, second: WireSegment) -> bool:
    dx, dy = _direction(first)
    ex, ey = _direction(second)
    if _cross(dx, dy, ex, ey) != 0:
        return False
    length2 = dx * dx + dy * dy
    start = (second.start.x - first.start.x) * dx + (
        second.start.y - first.start.y
    ) * dy
    end = (second.end.x - first.start.x) * dx + (
        second.end.y - first.start.y
    ) * dy
    return max(0, min(start, end)) < min(length2, max(start, end))


def _parallel_squared(first: WireSegment, second: WireSegment) -> Fraction:
    dx, dy = _direction(first)
    p = second.start
    cross = _cross(dx, dy, p.x - first.start.x, p.y - first.start.y)
    return Fraction(cross * cross, dx * dx + dy * dy)


def _point_line_sq(point: Point, wire: WireSegment) -> Fraction:
    a = wire.start
    dx, dy = _direction(wire)
    squared = dx * dx + dy * dy
    projected = (point.x - a.x) * dx + (point.y - a.y) * dy
    if projected <= 0:
        return Fraction((point.x - a.x) ** 2 + (point.y - a.y) ** 2)
    if projected >= squared:
        return Fraction(
            (point.x - wire.end.x) ** 2 + (point.y - wire.end.y) ** 2
        )
    cross = _cross(dx, dy, point.x - a.x, point.y - a.y)
    return Fraction(cross * cross, squared)


def _seg_distance_sq(first: WireSegment, second: WireSegment) -> Fraction:
    if _strict_crossing(first, second) is not None:
        return Fraction(0)
    if any(_on(second, p) for p in (first.start, first.end)):
        return Fraction(0)
    if any(_on(first, p) for p in (second.start, second.end)):
        return Fraction(0)
    return min(
        _point_line_sq(p, other)
        for p, other in (
            (first.start, second), (first.end, second),
            (second.start, first), (second.end, first),
        )
    )


def _edge_gap(square: Fraction | int, widths: int) -> float:
    return round(sqrt(float(square)) - widths / 2, 3)


def _box_gap_sq(left: Box, right: Box) -> int:
    dx = max(0, left.min_x - right.max_x, right.min_x - left.max_x)
    dy = max(0, left.min_y - right.max_y, right.min_y - left.max_y)
    return dx * dx + dy * dy


def _symbol_boxes(
    circuit: Circuit, symbols: dict[str, SymbolDefinition],
) -> dict[str, tuple[Box, Box]]:
    boxes = {}
    for part in circuit.components:
        symbol = symbols.get(part.part_id)
        if symbol is None:
            raise ValueError("DRC_MISSING_NATIVE_SYMBOL:" + part.part_id)
        drawn = part.transform.box(symbol.stroked_bounds).translated(part.origin)
        body = part.transform.box(symbol.body_keepout).translated(part.origin)
        boxes[part.reference] = (drawn, body)
    return boxes


def _validate_net_inventory(circuit: Circuit, graph: ExternalWireGraph) -> None:
    known = set()
    owners: dict[PinRef, str] = {}
    refs = [c.reference for c in circuit.components]
    if len(refs) != len(set(refs)):
        raise ValueError("DRC_DUPLICATE_PHYSICAL_COMPONENT_REF")
    for net in circuit.nets:
        if net.name in known:
            raise ValueError("DRC_DUPLICATE_CIRCUIT_NET")
        known.add(net.name)
        for pin in net.members:
            if pin.reference not in refs:
                raise ValueError("DRC_NET_MEMBER_NOT_IN_CIRCUIT")
            if pin in owners and owners[pin] != net.name:
                raise ValueError("DRC_CROSS_NET_PHYSICAL_PIN")
            owners[pin] = net.name
    if any(w.net_name not in known for w in graph.segments):
        raise ValueError("DRC_WIRE_UNKNOWN_SEMANTIC_NET")


def audit_route_drc(
    circuit: Circuit,
    graph: ExternalWireGraph,
    *,
    stroke_um: int = 300,
    symbols_by_part: dict[str, SymbolDefinition] | None = None,
    annotation_placements: tuple = (),
) -> RouteDRCReport:
    """Full source-preserving routing measurements (read-only).

    If symbols or actual measured text are absent, explicit coverage booleans
    remain false. Such a wire-only report cannot certify a whole E3 sheet.
    """
    if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
        raise TypeError("DRC requires actual immutable Circuit and ExternalWireGraph")
    if type(stroke_um) is not int or stroke_um <= 0:
        raise ValueError("DRC requires positive integral stroke in um")
    _validate_net_inventory(circuit, graph)
    violations: list[RouteDRCFinding] = []
    parallel: list[ParallelPairMeasurement] = []
    segments = graph.segments

    def issue(code: str, severity: str, i: str, j: str | None, detail: str,
              distance: float | None = None, required: int | None = None,
              point: tuple[str, str] | None = None) -> None:
        violations.append(RouteDRCFinding(
            code, severity, i, j, detail, distance, required, point,
        ))

    if not WIRE_STROKE_MIN_UM <= stroke_um <= WIRE_STROKE_MAX_UM:
        issue("DRC_WIRE_STROKE_RANGE", "error", "graph", None,
              "ГОСТ 2.701-2008 §5.5.1 wire stroke 0.2–1.0 mm")
    diagonal = sum(w.start.x != w.end.x and w.start.y != w.end.y for w in segments)
    if diagonal:
        issue("DRC_DIAGONAL_ROUTE_REVIEW", "warning", "graph", None,
              f"{diagonal} exceptional non-orthogonal segments, §5.5.2")
    crossings = 0
    foreign_crossings = 0
    bends = 0
    for i, a in enumerate(segments):
        for j in range(i):
            b = segments[j]
            same = a.net_name == b.net_name
            id1, id2 = f"W{j}", f"W{i}"
            intersection = _strict_crossing(a, b)
            if intersection is not None:
                crossings += 1
                if not same:
                    foreign_crossings += 1
                    issue("DRC_UNMARKED_DIFFERENT_NET_X", "warning", id1, id2,
                          "Printed crossing without net join; consider reroute to reduce ambiguity",
                          point=_rational_xy(intersection))
                else:
                    p = Point(int(intersection[0]), int(intersection[1])) if all(
                        coordinate.denominator == 1 for coordinate in intersection
                    ) else None
                    if p not in graph.junctions:
                        issue("DRC_SAME_NET_X_NO_JUNCTION", "error", id1, id2,
                              "Same-net interior X has no explicitly authored electrical dot",
                              point=_rational_xy(intersection))
            # Exact endpoint-to-interior T needs an explicit authored junction.
            touches = {
                p for p in (a.start, a.end) if _interior(b, p)
            } | {
                p for p in (b.start, b.end) if _interior(a, p)
            }
            for p in sorted(touches, key=lambda q: (q.x, q.y)):
                point = (str(p.x), str(p.y))
                if not same:
                    issue("DRC_FOREIGN_NET_T_TOUCH", "error", id1, id2,
                          "Different nets touch at an endpoint/interior without authorized connection",
                          point=point)
                elif p not in graph.junctions:
                    issue("DRC_SAME_NET_T_NO_DOT", "error", id1, id2,
                          "Same-net authored T requires a visible junction dot",
                          point=point)
            # Adjacent same-net noncollinear segment ends can form a legal bend.
            if (same and {a.start, a.end} & {b.start, b.end}
                    and _cross(*_direction(a), *_direction(b))):
                bends += 1
            if not _parallel_overlap(a, b):
                continue
            dist = _parallel_squared(a, b)
            painted_gap = _edge_gap(dist, 2 * stroke_um)
            on_same_line = dist == 0
            if on_same_line and same:
                # One continuous same-Net copper line is legal (no fictitious
                # 3mm requirement between its overlapping drawn fragments).
                parallel.append(ParallelPairMeasurement(
                    j, i, b.net_name, a.net_name, painted_gap,
                    0, True, True,
                ))
                continue
            limit = WIRE_PARALLEL_GAP_UM
            legal = 4 * dist >= (2 * limit + 2 * stroke_um) ** 2
            parallel.append(ParallelPairMeasurement(
                j, i, b.net_name, a.net_name, painted_gap,
                limit, legal, on_same_line,
            ))
            if not legal:
                issue(
                    "DRC_PARALLEL_STROKE_CLEARANCE", "error", id1, id2,
                    "ГОСТ 2.701-2008 §5.3.4: adjacent parallel connection strokes "
                    "must have 3mm clear printed edge-to-edge separation; "
                    "no implicit same-net side-by-side exemption",
                    painted_gap, limit,
                )
    # Authored dots are the ONLY evidence of a junction. They do not create
    # electric Net membership; a foreign-net dot is invalid.
    for p in graph.junctions:
        incident = [i for i, w in enumerate(segments) if _on(w, p)]
        if len(incident) < 2 or len({segments[i].net_name for i in incident}) > 1:
            issue("DRC_INVALID_AUTHORED_JUNCTION", "error",
                  f"{p.x},{p.y}", None, "Dot must touch at least two wires of ONE Net",
                  point=(str(p.x), str(p.y)))
    # Unmarked 3+ endpoint branch point visually resembles an unmarked T.
    shared_points = {p for w in segments for p in (w.start, w.end)}
    for p in sorted(shared_points, key=lambda q: (q.x, q.y)):
        incident = [w for w in segments if p in (w.start, w.end)]
        if len(incident) >= 3 and p not in graph.junctions:
            issue("DRC_UNMARKED_BRANCH_3PLUS", "error", f"{p.x},{p.y}", None,
                  "Three or more wires share an endpoint without an explicit dot",
                  point=(str(p.x), str(p.y)))
        if len({w.net_name for w in incident}) > 1:
            issue("DRC_FOREIGN_NET_SHARED_ENDPOINT", "error",
                  f"{p.x},{p.y}", None,
                  "Distinct Nets have coincident authored endpoints; not a valid join",
                  point=(str(p.x), str(p.y)))
    # Geometry of actual installed symbols; conservative ink-stroked envelopes.
    symbol_map = _symbol_boxes(circuit, symbols_by_part) if (
        symbols_by_part is not None
    ) else {}
    for (ref_a, (box_a, _)), (ref_b, (box_b, _)) in combinations(
        symbol_map.items(), 2,
    ):
        dist = _box_gap_sq(box_a, box_b)
        if dist < SYMBOL_GAP_UM ** 2:
            issue("DRC_SYMBOL_2MM", "error", ref_a, ref_b,
                  "Separate full UGO stroked footprints require >=2mm",
                  round(sqrt(dist), 3), SYMBOL_GAP_UM)
        if dist < SYMBOL_GRAPHIC_GAP_UM ** 2:
            issue("DRC_SYMBOL_GRAPHIC_1MM", "error", ref_a, ref_b,
                  "Adjacent distinct UGO lines require >=1mm; conservative stroke boxes",
                  round(sqrt(dist), 3), SYMBOL_GRAPHIC_GAP_UM)
    if symbol_map:
        attached_pin_by_net: dict[str, set[tuple[str, Point]]] = {}
        for net in circuit.nets:
            for member in net.members:
                instance = next(c for c in circuit.components
                                if c.reference == member.reference)
                symbol = symbols_by_part[instance.part_id]
                location = instance.pin_positions(symbol).get(member.number)
                if location is None:
                    raise ValueError("DRC_SYMBOL_PIN_MISSING:" + repr(member))
                attached_pin_by_net.setdefault(net.name, set()).add(
                    (member.reference, location)
                )
        for index, w in enumerate(segments):
            line = Line(w.start, w.end)
            for ref, (_, body) in symbol_map.items():
                if segment_intersects_box(line, body.expanded((stroke_um + 1) // 2)):
                    # Physical pin tip on a boundary does not authorize crossing
                    # the whole symbol body. Review pins via existing ERC.
                    issue("DRC_WIRE_SYMBOL_BODY", "error", f"W{index}", ref,
                          "Wire runs through a component body keepout", point=None)
                # Never globally waive clearances near the same reference;
                # a genuine pin exit can touch graphical lead ink but cannot
                # justify a foreign body's overlap.
                graphic = symbol_map[ref][0]
                if segment_intersects_box(line, graphic.expanded((stroke_um + 1) // 2)):
                    valid_pin_endpoint = any(
                        part_ref == ref and pin_point in (w.start, w.end)
                        for part_ref, pin_point in attached_pin_by_net.get(w.net_name, ())
                    )
                    if not valid_pin_endpoint:
                        issue("DRC_WIRE_SYMBOL_INK", "error", f"W{index}", ref,
                              "Wire overlaps other UGO stroke without a sourced PinRef exit")
    for index, w in enumerate(segments):
        line = Line(w.start, w.end)
        for position, label in enumerate(annotation_placements):
            box = label.collision_bounds
            if segment_intersects_box(line, box.expanded((stroke_um + 1) // 2)):
                issue("DRC_WIRE_TEXT_KEEP_OUT", "error", f"W{index}",
                      f"TEXT{position}:{label.owner}",
                      "Conductor touches measured protected text/annotation hitbox")
    total_length = sum(
        sqrt((w.end.x - w.start.x) ** 2 + (w.end.y - w.start.y) ** 2)
        for w in segments
    )
    return RouteDRCReport(
        len(segments), len(circuit.components), len(circuit.nets),
        len(graph.junctions), round(total_length, 3),
        len(segments) - diagonal, diagonal, bends, crossings, foreign_crossings,
        tuple(parallel), tuple(violations),
        symbols_by_part is not None, bool(annotation_placements),
    )
