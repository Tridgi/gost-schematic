"""Issue #108 G2 — deterministic, source-PinRef multi-terminal E3 net-tree router.

A tree is assembled from real physical terminal coordinates and exact authored
T junctions. It is always a read-only preview; no semantic Circuit.Net, component
placement, or physical PartDefinition is modified. A failed route returns a
partial *nonprintable* graph and explicit reason. DO NOT claim ESKD APPROVED.
"""
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from itertools import pairwise

from gost_schematic.core.geometry import (
    SIDE_VECTORS,
    Box,
    Line,
    Point,
    StyledLine,
    primitive_stroke_width,
    primitive_stroked_bounds,
)
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.engines.orthogonal_route_planner import _resolve_real_pin
from gost_schematic.model.circuit import Circuit, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)
from gost_schematic.validation.route_drc import (
    RouteDRCReport,
    _on,
    _seg_distance_sq,
    _symbol_boxes,
    audit_route_drc,
    candidate_wire_clearance,
)

# A priority list is an editorial routing order, never electrical authority.
SOURCE_TL494_ROUTE_PRIORITY = (
    "INPUT_POS", "SWITCH", "ENERGY_TRANSFER", "OUT_BEFORE_FUSE",
    "OUTPUT_NEG", "GATE_DRIVE", "CONTROL_REFERENCE", "SOFT_START",
    "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK", "ADJUSTED_DIVIDER",
    "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
)


@dataclass(frozen=True, slots=True)
class NetTreePreview:
    net_name: str
    pin_refs: tuple[PinRef, ...]
    segments: tuple[WireSegment, ...]
    junctions: tuple[Point, ...]
    bend_count: int
    length_um: int
    crossing_count: int
    diagnostics: tuple[str, ...]
    completed_pins: tuple[PinRef, ...]
    search_restarts: int = 0

    @property
    def complete(self) -> bool:
        return not self.diagnostics and self.completed_pins == self.pin_refs

    def as_dict(self) -> dict:
        return {
            "net": self.net_name,
            "pin_refs": [p.reference + "." + p.number for p in self.pin_refs],
            "connected_pin_refs": [
                p.reference + "." + p.number for p in self.completed_pins
            ],
            "segments": len(self.segments),
            "junctions_um": [[p.x, p.y] for p in self.junctions],
            "bends": self.bend_count,
            "length_um": self.length_um,
            "crossings": self.crossing_count,
            "diagnostics": list(self.diagnostics),
            "complete": self.complete,
            "search_restarts": self.search_restarts,
            "print_pass": False,
        }


@dataclass(frozen=True, slots=True)
class GlobalRoutePreview:
    source_circuit: Circuit
    graph: ExternalWireGraph
    net_trees: tuple[NetTreePreview, ...]
    diagnostics: tuple[str, ...]
    drc: RouteDRCReport | None
    routing_strategy: str = "SOURCE_FUNCTIONAL"
    route_order_trials: tuple[tuple[str, int, int], ...] = ()

    @property
    def complete(self) -> bool:
        return (
            len(self.net_trees) == len(self.source_circuit.nets)
            and all(t.complete for t in self.net_trees)
            and not self.diagnostics
        )

    @property
    def print_pass(self) -> bool:
        return (
            self.complete and self.drc is not None
            and self.drc.valid
            and self.drc.checked_symbol_geometry
            and self.drc.checked_measured_text
        )

    def as_dict(self) -> dict:
        return {
            "status": "DRAFT_ROUTING_PREVIEW",
            "complete": self.complete,
            "print_pass": self.print_pass,
            "source_net_count": len(self.source_circuit.nets),
            "routed_net_count": sum(t.complete for t in self.net_trees),
            "source_pin_count": sum(len(n.members) for n in self.source_circuit.nets),
            "net_diff": {
                "added": [], "removed": [],
                "modified_physical_PinRef": [],
            },
            "graph_segments": len(self.graph.segments),
            "graph_junctions": len(self.graph.junctions),
            "net_trees": [tree.as_dict() for tree in self.net_trees],
            "diagnostics": list(self.diagnostics),
            "drc": self.drc.as_dict() if self.drc else None,
            "blocked_release": not self.print_pass,
            "routing_strategy": self.routing_strategy,
            "route_order_trials": [
                {"strategy": name, "complete_nets": count,
                 "drc_errors": errors}
                for name, count, errors in self.route_order_trials
            ],
            "not_gost_approved": True,
        }


@dataclass(frozen=True, slots=True)
class _SourceInk:
    """Actual transformed stroked UGO primitive; never a guessed pin lane."""

    owner: str
    primitive_index: int
    primitive_kind: str
    collision_bounds: Box
    permitted_pin: PinRef | None = None
    contact: Point | None = None
    normal: Point | None = None
    ink_line: WireSegment | None = None
    graphic_stroke_um: int = 0
    wire_stroke_um: int = 0


def _source_ink_obstacles(
    circuit: Circuit,
    symbols: dict[str, SymbolDefinition],
    *,
    stroke_um: int,
) -> tuple[_SourceInk, ...]:
    """Transform every symbol primitive to world coordinates at true D4 pose.

    Native physical leads are matched by actual GraphicPin endpoints, not
    assumed DA1 pin pitch. Only that one exact lead may touch its own
    conductor, and only at its sourced outward endpoint.
    """
    obstacles: list[_SourceInk] = []
    for component in circuit.components:
        symbol = symbols.get(component.part_id)
        if symbol is None:
            raise ValueError("ROUTE_NATIVE_SYMBOL_MISSING:" + component.part_id)
        actual_pins = component.pin_positions(symbol)
        vectors = {
            pin.number: component.transform.apply(
                SIDE_VECTORS[pin.side],
            )
            for pin in symbol.pins
        }
        contact_by_point = {
            pos: (PinRef(component.reference, number), vectors[number])
            for number, pos in actual_pins.items()
        }
        for i, primitive in enumerate(symbol.graphics):
            world = component.transform.primitive(primitive, component.origin)
            touched = None
            if isinstance(world, (Line, StyledLine)):
                matches = tuple(
                    contact_by_point[p] for p in (world.start, world.end)
                    if p in contact_by_point
                )
                if len(matches) == 1:
                    touched = matches[0]
            obstacles.append(_SourceInk(
                component.reference, i, type(world).__name__,
                primitive_stroked_bounds(
                    world, symbol.line_width_um,
                ).expanded((stroke_um + 1) // 2),
                touched[0] if touched else None,
                (world.start if world.start in contact_by_point else
                 world.end if world.end in contact_by_point else None)
                if touched else None,
                touched[1] if touched else None,
                WireSegment(
                    world.start, world.end, "__NATIVE_SYMBOL_INK__",
                ) if isinstance(world, (Line, StyledLine)) else None,
                primitive_stroke_width(world, symbol.line_width_um),
                stroke_um,
            ))
    return tuple(obstacles)


def _source_ink_collision(
    candidate: WireSegment,
    obstacles: tuple[_SourceInk, ...],
    *,
    authorized_pins: frozenset[PinRef],
) -> _SourceInk | None:
    """Prevent the DA1 right-lead fanout overprint *during* graph search.

    An outward segment from its OWN physical lead tip can touch that lead's
    stroked cap. It cannot use the same exemption for any other pin, a body,
    a label or a second segment merely on the same component reference.
    """
    segment = Line(candidate.start, candidate.end)
    for ink in obstacles:
        if not segment_intersects_box(segment, ink.collision_bounds):
            continue
        if ink.ink_line is not None:
            # A diagonal line's AABB can contain large areas of empty paper.
            # Compare source line and candidate *actual* printed strokes
            # using exact rational squared distances, never their AABBs.
            dist_sq = _seg_distance_sq(candidate, ink.ink_line)
            if 4 * dist_sq > (
                ink.wire_stroke_um + ink.graphic_stroke_um
            ) ** 2:
                continue
        if (
            ink.permitted_pin in authorized_pins
            and ink.contact is not None
            and ink.normal is not None
        ):
            # A legal outward pin escape can be split by the visibility
            # lattice inside the *same real stroke cap*. The second small
            # segment no longer contains the PinRef coordinate; requiring
            # endpoint == contact here would wrongly forbid the same physical
            # continuous conductor solely because a grid knot was inserted.
            #
            # Permit ONLY the one-dimensional exterior ray of THAT exact
            # physical contact, including its subsegments; never permit a
            # move behind the tip into the IC lead forest or any off-axis
            # crossing of another lead. All wire-to-wire and DRC checks
            # still run afterwards, and this does not author a junction.
            first_offset = candidate.start - ink.contact
            second_offset = candidate.end - ink.contact
            if (
                first_offset.x * ink.normal.y
                == first_offset.y * ink.normal.x
                and second_offset.x * ink.normal.y
                == second_offset.y * ink.normal.x
                and (
                    first_offset.x * ink.normal.x
                    + first_offset.y * ink.normal.y
                ) >= 0
                and (
                    second_offset.x * ink.normal.x
                    + second_offset.y * ink.normal.y
                ) >= 0
            ):
                continue
        return ink
    return None


def _nearest_net_order(
    pins: tuple[PinRef, ...],
    positions: dict[PinRef, tuple[Point, Point]],
) -> tuple[PinRef, ...]:
    """Deterministic Prim order from physical PinRef, not Net-list order.

    The first contact stays source-owned. Each next real contact minimizes
    Manhattan distance to ANY already selected contact, avoiding a 400mm
    X1.2→X2.2 initial trunk for COMMON.
    """
    visited = [pins[0]]
    remaining = set(pins[1:])
    while remaining:
        next_pin = min(remaining, key=lambda candidate: (
            min(
                abs(positions[candidate][0].x - positions[old][0].x)
                + abs(positions[candidate][0].y - positions[old][0].y)
                for old in visited
            ),
            candidate.reference, candidate.number,
        ))
        visited.append(next_pin)
        remaining.remove(next_pin)
    return tuple(visited)


def _empty_graph() -> ExternalWireGraph:
    return ExternalWireGraph(())


def _pin_catalog(
    circuit: Circuit,
    net: Net,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
) -> dict[PinRef, tuple[Point, Point]]:
    if len(net.members) != len(set(net.members)):
        raise ValueError("ROUTE_DUPLICATE_PHYSICAL_PIN_IN_NET")
    mapping: dict[PinRef, tuple[Point, Point]] = {}
    for ref in net.members:
        point, outward, _ = _resolve_real_pin(circuit, ref, parts, symbols)
        if outward.x == outward.y == 0:
            raise ValueError("ROUTE_PIN_DIRECTION_INVALID")
        mapping[ref] = (point, outward)
    if len({point for point, _ in mapping.values()}) != len(mapping):
        raise ValueError("ROUTE_MULTIPLE_PINS_SAME_PHYSICAL_POINT")
    return mapping


def _pin_is_attached(point: Point, segments: tuple[WireSegment, ...],
                     junctions: tuple[Point, ...]) -> bool:
    return any(
        point == w.start or point == w.end
        or point in junctions and _on(w, point)
        for w in segments
    )


def _junctions_for(
    segments: tuple[WireSegment, ...],
    existing: tuple[Point, ...] = (),
) -> tuple[Point, ...]:
    """Explicitly mark T and 3+ branches, not arbitrary foreign X crossings."""
    dot = set(existing)
    endpoints = {p for w in segments for p in (w.start, w.end)}
    for point in endpoints:
        incident = tuple(w for w in segments if _on(w, point))
        if len(incident) >= 3 or any(
            point != w.start and point != w.end for w in incident
        ):
            dot.add(point)
    return tuple(sorted(dot, key=lambda p: (p.x, p.y)))


def _join_targets(
    branches: tuple[WireSegment, ...],
    from_point: Point,
    *,
    grid_um: int,
    page: Box,
    protected: tuple[Box, ...],
) -> tuple[Point, ...]:
    """Include real interior T candidates, never invented PinRef coordinates."""
    points = {p for wire in branches for p in (wire.start, wire.end)}
    for wire in branches:
        a, b = wire.start, wire.end
        if a.y == b.y:
            low, high = sorted((a.x, b.x))
            values = [from_point.x]
            values += [
                low + k * grid_um
                for k in range(1, (high - low) // grid_um + 1)
            ]
            for x in values:
                if low <= x <= high:
                    points.add(Point(x, a.y))
        elif a.x == b.x:
            low, high = sorted((a.y, b.y))
            values = [from_point.y]
            values += [
                low + k * grid_um
                for k in range(1, (high - low) // grid_um + 1)
            ]
            for y in values:
                if low <= y <= high:
                    points.add(Point(a.x, y))
        else:
            raise ValueError("ROUTE_TREE_NONORTHOGONAL_EXISTING_BRANCH")
    return tuple(sorted((
        p for p in points
        if page.includes(p) and not any(
            box.contains_interior(p) for box in protected
        )
    ), key=lambda p: (
        abs(p.x - from_point.x) + abs(p.y - from_point.y), p.x, p.y,
    )))


def _boxes_for(
    circuit: Circuit, symbols: dict[str, SymbolDefinition],
    *,
    pin_owners: frozenset[str], stroke_um: int, clearance_um: int,
    annotations: tuple,
) -> tuple[Box, ...]:
    native = _symbol_boxes(circuit, symbols)
    buffer = clearance_um + (stroke_um + 1) // 2
    boxes = [
        (body if name in pin_owners else graphic).expanded(buffer)
        for name, (graphic, body) in native.items()
    ]
    boxes += [
        placement.collision_bounds.expanded(buffer)
        for placement in annotations
    ]
    return tuple(boxes)


def _visibility_path(
    source: Point,
    normal: Point,
    goals: tuple[Point, ...],
    *,
    net_name: str,
    occupied: ExternalWireGraph,
    tree: tuple[WireSegment, ...],
    existing_dots: tuple[Point, ...],
    goal_pin_normals: dict[Point, Point],
    ink_obstacles: tuple[_SourceInk, ...],
    authorized_pins: frozenset[PinRef],
    boxes: tuple[Box, ...],
    page: Box,
    stroke_um: int,
    search_node_cap: int,
    grid_um: int,
    max_detour_ratio: float,
    goal_offset: int = 0,
) -> tuple[tuple[Point, ...], str | None]:
    """Deterministic multi-goal Dijkstra with explicit T candidates.

    A candidate ending on own tree is checked with that exact proposed dot,
    but intermediate crossings cannot silently acquire new dot authority.
    """
    if type(goal_offset) is not int or goal_offset < 0:
        raise ValueError("ROUTE_INVALID_GOAL_WINDOW_OFFSET")
    if not goals:
        return (), "ROUTE_NO_TREE_TARGET"
    # Source's long COMMON and GATE_DRIVE require a SPARSE visibility grid.
    # A full Cartesian grid from every source wire endpoint can exceed 25k
    # nodes after just 5 nets. Keep closest genuine branch targets first;
    # retaining all pre-existing physical obstacles in edge validity checks.
    sorted_goals = tuple(sorted(
        set(goals),
        key=lambda p: (
            abs(p.x - source.x) + abs(p.y - source.y), p.x, p.y,
        ),
    ))
    reachable_goals = sorted_goals[goal_offset:goal_offset + 24]
    if not reachable_goals:
        return (), "ROUTE_NO_TREE_TARGET_IN_WINDOW"
    targets = frozenset(reachable_goals)
    x0 = min(source.x, *(p.x for p in reachable_goals))
    x1 = max(source.x, *(p.x for p in reachable_goals))
    y0 = min(source.y, *(p.y for p in reachable_goals))
    y1 = max(source.y, *(p.y for p in reachable_goals))
    detour_window = max(40000, min(
        160000, max(x1 - x0, y1 - y0) // 2,
    ))
    window = Box(
        max(page.min_x, x0 - detour_window),
        max(page.min_y, y0 - detour_window),
        min(page.max_x, x1 + detour_window),
        min(page.max_y, y1 + detour_window),
    )
    x_set = {window.min_x, window.max_x, source.x}
    y_set = {window.min_y, window.max_y, source.y}
    x_set.update(p.x for p in reachable_goals)
    y_set.update(p.y for p in reachable_goals)

    def overlaps_window(box: Box, *, cushion: int = 3300) -> bool:
        return (
            box.max_x + cushion >= window.min_x
            and box.min_x - cushion <= window.max_x
            and box.max_y + cushion >= window.min_y
            and box.min_y - cushion <= window.max_y
        )

    for box in boxes:
        if overlaps_window(box):
            x_set.update((box.min_x - 1, box.max_x + 1))
            y_set.update((box.min_y - 1, box.max_y + 1))
    for old in (*occupied.segments, *tree):
        bounds = Box(
            min(old.start.x, old.end.x), min(old.start.y, old.end.y),
            max(old.start.x, old.end.x) + 1,
            max(old.start.y, old.end.y) + 1,
        )
        if not overlaps_window(bounds):
            continue
        if old.start.y == old.end.y:
            x_set.update((old.start.x - 3300, old.start.x,
                          old.end.x, old.end.x + 3300))
            y_set.update((old.start.y - 3300, old.start.y + 3300))
        else:
            x_set.update((old.start.x - 3300, old.start.x + 3300))
            y_set.update((old.start.y - 3300, old.start.y,
                          old.end.y, old.end.y + 3300))
    for point in (source, *reachable_goals):
        x_set.update((point.x - grid_um, point.x + grid_um))
        y_set.update((point.y - grid_um, point.y + grid_um))
    xs = sorted(x for x in x_set if window.min_x <= x <= window.max_x)
    ys = sorted(y for y in y_set if window.min_y <= y <= window.max_y)
    # The Cartesian visibility lattice is sparse in practice: only states
    # actually expanded from the source allocate nodes. Reject enormous
    # lattices but do not confuse potential cells with 25k actual visits.
    if len(xs) * len(ys) > search_node_cap * 8:
        return (), "ROUTE_GRID_TOO_DENSE"
    # Every candidate is strictly horizontal or vertical. A rectangle can
    # intersect such a candidate only if its perpendicular projection
    # contains the fixed row/column coordinate (including its boundary).
    # Hoist this exact necessary test out of the inner Dijkstra edge loop:
    # PAINT's 16 lead strokes and 72 measured text guards otherwise each
    # incur tens of thousands of redundant box checks per routed Net.
    boxes_by_y = {
        y: tuple(box for box in boxes if box.min_y <= y <= box.max_y)
        for y in ys
    }
    boxes_by_x = {
        x: tuple(box for box in boxes if box.min_x <= x <= box.max_x)
        for x in xs
    }
    ink_by_y = {
        y: tuple(ink for ink in ink_obstacles
                 if ink.collision_bounds.min_y <= y
                 <= ink.collision_bounds.max_y)
        for y in ys
    }
    ink_by_x = {
        x: tuple(ink for ink in ink_obstacles
                 if ink.collision_bounds.min_x <= x
                 <= ink.collision_bounds.max_x)
        for x in xs
    }
    x_idx = {x: i for i, x in enumerate(xs)}
    y_idx = {y: i for i, y in enumerate(ys)}
    start = (x_idx[source.x], y_idx[source.y], -1)
    active = (*occupied.segments, *tree)
    permanent_dots = frozenset((*occupied.junctions, *existing_dots))
    current_score = {start: (0, 0, 0, 0)}
    predecessor: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    heap = [(0, 0, 0, 0, *start)]
    reached = None
    visited = 0
    best_direct = min(
        abs(source.x - goal.x) + abs(source.y - goal.y)
        for goal in goals
    )
    cache: dict[tuple[Point, Point, bool], tuple[bool, int]] = {}
    ink_rejections: dict[tuple[str, int, str], tuple[Point, Point]] = {}
    wire_rejections: dict[
        tuple[str, str, Point, Point], tuple[Point, Point]
    ] = {}
    while heap:
        score, bends, crossings, length, ix, iy, direction = heappop(heap)
        state = (ix, iy, direction)
        if current_score.get(state) != (score, bends, crossings, length):
            continue
        visited += 1
        if visited > search_node_cap * 3:
            return (), "ROUTE_SEARCH_EXPANSION_LIMIT"
        here = Point(xs[ix], ys[iy])
        if here in targets and here != source:
            reached = state
            break
        for dx, dy, ndir in ((-1, 0, 0), (1, 0, 0), (0, -1, 1), (0, 1, 1)):
            ni, nj = ix + dx, iy + dy
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            to = Point(xs[ni], ys[nj])
            axis_boxes = (
                boxes_by_y[here.y] if ndir == 0 else boxes_by_x[here.x]
            )
            if not page.includes(to) or any(
                segment_intersects_box(Line(here, to), box)
                for box in axis_boxes
            ):
                continue
            axis_ink = (
                ink_by_y[here.y] if ndir == 0 else ink_by_x[here.x]
            )
            ink_error = _source_ink_collision(
                WireSegment(here, to, net_name),
                axis_ink, authorized_pins=authorized_pins,
            )
            if ink_error is not None:
                key = (
                    ink_error.owner,
                    ink_error.primitive_index,
                    (f"{ink_error.permitted_pin.reference}."
                     f"{ink_error.permitted_pin.number}"
                     if ink_error.permitted_pin else "UGO_BODY"),
                )
                if key not in ink_rejections:
                    ink_rejections[key] = (here, to)
                continue
            if state == start and (
                (to.x - here.x) * normal.x
                + (to.y - here.y) * normal.y <= 0
            ):
                continue
            is_goal = to in targets
            if is_goal and to in goal_pin_normals:
                outward = goal_pin_normals[to]
                if ((here.x - to.x) * outward.x
                        + (here.y - to.y) * outward.y <= 0):
                    # Last segment must reach a REAL physical pin from
                    # outside its own graphics, never through the body.
                    continue
            key = (here, to, is_goal)
            saved = cache.get(key)
            if saved is None:
                trial = WireSegment(here, to, net_name)
                dots = (permanent_dots | {to}) if is_goal else permanent_dots
                bad = False
                seen_crossings = 0
                for old in active:
                    result = candidate_wire_clearance(
                        trial, old, candidate_stroke_um=stroke_um,
                        existing_stroke_um=stroke_um,
                        explicit_junctions=dots,
                    )
                    if not result.valid:
                        bad = True
                        # Preserve exact two conductor endpoints and scoped
                        # 3mm/same-Net T/foreign-Net contact reason. A
                        # no-route condition is often a WIRE constraint even
                        # when some other candidate also hit IC lead ink.
                        for code in result.errors:
                            witness = (
                                old.net_name, code, old.start, old.end,
                            )
                            if witness not in wire_rejections:
                                wire_rejections[witness] = (here, to)
                        break
                    seen_crossings += (
                        "DRC_UNMARKED_DIFFERENT_NET_X" in result.warnings
                    )
                saved = (not bad, seen_crossings)
                cache[key] = saved
            legal, crosses = saved
            if not legal:
                continue
            advance = abs(to.x - here.x) + abs(to.y - here.y)
            new_len = length + advance
            if best_direct and new_len > max_detour_ratio * best_direct:
                continue
            nbends = bends + int(direction >= 0 and direction != ndir)
            n_crosses = crossings + crosses
            # Each turn and foreign-X ambiguity is expensive; no net mutation.
            n_score = new_len + nbends * 20000 + n_crosses * 10000
            next_state = (ni, nj, ndir)
            improved = (n_score, nbends, n_crosses, new_len)
            if (next_state not in current_score
                    or improved < current_score[next_state]):
                current_score[next_state] = improved
                predecessor[next_state] = state
                heappush(heap, (*improved, *next_state))
    if reached is None:
        # Route-search diagnostics retain the actual source primitive and
        # candidate coordinates; never call the reject a successful Net.
        details = tuple(
            f"{owner}#{index}:{pin}:{a.x},{a.y}->{b.x},{b.y}"
            for (owner, index, pin), (a, b) in sorted(ink_rejections.items())
        )
        reason = "ROUTE_NO_CLEAR_ORTHOGONAL_TREE_PATH"
        if details:
            reason += ":INK_VETO=" + ";".join(details[:6])
        if wire_rejections:
            route_evidence = tuple(
                f"{net}:{code}:existing={a.x},{a.y}->"
                f"{b.x},{b.y}:trial={p.x},{p.y}->{q.x},{q.y}"
                for (net, code, a, b), (p, q)
                in sorted(wire_rejections.items(), key=lambda item: (
                    item[0][0], item[0][1],
                    item[0][2].x, item[0][2].y,
                    item[0][3].x, item[0][3].y,
                ))
            )
            reason += ":WIRE_VETO=" + ";".join(route_evidence[:6])
        return (), reason
    points = []
    state = reached
    while state != start:
        points.append(Point(xs[state[0]], ys[state[1]]))
        state = predecessor[state]
    points.append(source)
    points.reverse()
    reduced = [points[0]]
    for cur, nxt in pairwise(points[1:]):
        old = reduced[-1]
        if ((cur.x - old.x) * (nxt.y - cur.y)
                != (cur.y - old.y) * (nxt.x - cur.x)):
            reduced.append(cur)
    reduced.append(points[-1])
    return tuple(reduced), None


def route_multi_terminal_net(
    circuit: Circuit,
    net: Net,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    occupied_graph: ExternalWireGraph | None = None,
    annotation_placements: tuple = (),
    stroke_um: int = 300,
    symbol_gap_um: int = 1000,
    grid_um: int = 5000,
    search_node_cap: int = 25000,
    max_detour_ratio: float = 3.0,
    terminal_order: tuple[PinRef, ...] | None = None,
) -> NetTreePreview:
    """Route all real pins of ONE declared net to an explicit branched tree."""
    if net not in circuit.nets:
        raise ValueError("ROUTE_NET_NOT_FROM_SOURCE_CIRCUIT")
    if not 200 <= stroke_um <= 1000 or grid_um <= 0:
        raise ValueError("ROUTE_INVALID_STROKE_OR_GRID")
    pins = net.members
    locations = _pin_catalog(circuit, net, parts, symbols)
    order = (
        terminal_order if terminal_order is not None else
        _nearest_net_order(pins, locations) if len(pins) >= 5 else pins
    )
    if len(order) != len(pins) or set(order) != set(pins):
        raise ValueError("ROUTE_TERMINAL_ORDER_MUST_MATCH_REAL_SOURCE_PINREF")
    if any(not page_box.includes(point) for point, _ in locations.values()):
        return NetTreePreview(
            net.name, pins, (), (), 0, 0, 0,
            ("ROUTE_PHYSICAL_PIN_OUTSIDE_SELECTED_PAGE",), (),
        )
    occupied = occupied_graph if occupied_graph is not None else _empty_graph()
    for wire in occupied.segments:
        if wire.net_name == net.name:
            raise ValueError("ROUTE_ALREADY_HAS_NET_USE_SEPARATE_PREVIEW")
    if len(pins) == 1:
        return NetTreePreview(net.name, pins, (), (), 0, 0, 0, (), pins)
    if len(pins) < 1:
        raise ValueError("ROUTE_EMPTY_NET")
    # Physically anchored root. Route each subsequent terminal to the union
    # of already connected physical contacts and actual conductor segments.
    root = order[0]
    connected = [root]
    branches: list[WireSegment] = []
    dots: tuple[Point, ...] = ()
    total_bends = 0
    total_crossings = 0
    full_boxes = _boxes_for(
        circuit, symbols,
        pin_owners=frozenset(p.reference for p in pins),
        stroke_um=stroke_um, clearance_um=symbol_gap_um,
        annotations=annotation_placements,
    )
    source_ink = _source_ink_obstacles(
        circuit, symbols, stroke_um=stroke_um,
    )
    for pin in order[1:]:
        current, outward = locations[pin]
        if branches and _pin_is_attached(current, tuple(branches), dots):
            connected.append(pin)
            continue
        goals = (
            _join_targets(
                tuple(branches), current, grid_um=grid_um,
                page=page_box, protected=full_boxes,
            ) if branches else (locations[root][0],)
        )
        boxes = full_boxes
        # One single box per part can wrongly obstruct its own *tip*; the
        # full source model must show the pin exiting all installed keepouts.
        if any(box.contains_interior(current) for box in boxes):
            return NetTreePreview(
                net.name, pins, tuple(branches), dots, total_bends,
                sum(abs(w.end.x-w.start.x)+abs(w.end.y-w.start.y)
                    for w in branches), total_crossings,
                ("ROUTE_PIN_TRAPPED_BY_SYMBOL_OR_TEXT:" + pin.reference
                 + "." + pin.number,), tuple(p for p in pins if p in connected),
            )
        # A tree with dozens of real interior T points can have its nearest
        # 24 candidates blocked by another routed Net or actual UGO ink. An
        # immutable point 25+ may be legal; previously it was NEVER tried.
        # Search non-overlapping source-authored target windows in a bounded
        # progression and accept ONLY a path to a real existing conductor.
        # No synthetic electrical joint, no mixing independent route graphs.
        path: tuple[Point, ...] = ()
        reason: str | None = None
        target_windows = 0
        for target_offset in range(0, min(len(goals), 72), 24):
            target_windows += 1
            path, reason = _visibility_path(
                current, outward, goals, net_name=net.name,
                occupied=occupied, tree=tuple(branches),
                existing_dots=dots,
                ink_obstacles=source_ink,
                authorized_pins=frozenset(pins),
                goal_pin_normals={
                    at: normal for ref in connected
                    for at, normal in (locations[ref],)
                    if at in goals
                },
                boxes=boxes, page=page_box,
                stroke_um=stroke_um, grid_um=grid_um,
                search_node_cap=search_node_cap,
                max_detour_ratio=max_detour_ratio,
                goal_offset=target_offset,
            )
            if reason is None:
                break
        if reason is not None and target_windows > 1:
            reason += f":REAL_TREE_TARGET_WINDOWS_TRIED={target_windows}"
        if reason is not None:
            return NetTreePreview(
                net.name, pins, tuple(branches), dots, total_bends,
                sum(abs(w.end.x-w.start.x)+abs(w.end.y-w.start.y)
                    for w in branches), total_crossings,
                (reason + ":" + pin.reference + "." + pin.number,),
                tuple(p for p in pins if p in connected),
            )
        new = tuple(WireSegment(a, b, net.name) for a, b in pairwise(path))
        updated = (*branches, *new)
        new_dots = _junctions_for(updated, dots)
        # No source circuit writes; check for 3mm rule and true same-net
        # branch dots in the assembled graph, not only local edge preflight.
        trial = ExternalWireGraph(
            (*occupied.segments, *updated),
            tuple(sorted(
                {*occupied.junctions, *new_dots},
                key=lambda p: (p.x, p.y),
            )),
        )
        result = audit_route_drc(
            circuit, trial, stroke_um=stroke_um,
            symbols_by_part=symbols,
            annotation_placements=annotation_placements,
        )
        if not result.valid:
            failures = tuple(
                f for f in result.findings if f.severity == "error"
            )
            # Fail on the EXACT committed candidate segment, never collapse
            # real owner+coordinates into a bare code. The inspector remains
            # the normative authority; this is source-identity provenance.
            reasons = []
            for finding in failures:
                location = ""
                if finding.first.startswith("W") and finding.first[1:].isdigit():
                    index = int(finding.first[1:])
                    if index < len(trial.segments):
                        wire = trial.segments[index]
                        location = (
                            f":W{index}:{wire.start.x},{wire.start.y}->"
                            f"{wire.end.x},{wire.end.y}:owner={finding.second}"
                        )
                        collision = _source_ink_collision(
                            wire, source_ink,
                            authorized_pins=frozenset(pins),
                        )
                        if collision is not None:
                            location += (
                                f":primitive={collision.primitive_index}/"
                                f"{collision.primitive_kind}"
                            )
                            if collision.permitted_pin is not None:
                                location += (
                                    f":physical_lead="
                                    f"{collision.permitted_pin.reference}."
                                    f"{collision.permitted_pin.number}"
                                )
                reasons.append(finding.code + location)
            return NetTreePreview(
                net.name, pins, tuple(branches), dots, total_bends,
                sum(abs(w.end.x-w.start.x)+abs(w.end.y-w.start.y)
                    for w in branches), total_crossings,
                tuple("ROUTE_POST_DRC_ERROR:" + message for message in reasons),
                tuple(p for p in pins if p in connected),
            )
        total_bends += max(0, len(path) - 2)
        total_crossings += sum(
            1 for wire in new for previous in occupied.segments
            if candidate_wire_clearance(
                wire, previous, explicit_junctions=frozenset(trial.junctions),
            ).warnings
        )
        branches = list(updated)
        dots = new_dots
        connected.append(pin)
    return NetTreePreview(
        net.name, pins, tuple(branches), dots, total_bends,
        sum(abs(w.end.x - w.start.x) + abs(w.end.y - w.start.y)
            for w in branches),
        total_crossings, (), pins,
    )


def route_circuit_net_trees(
    circuit: Circuit,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    annotation_placements: tuple = (),
    stroke_um: int = 300,
    priority: tuple[str, ...] = SOURCE_TL494_ROUTE_PRIORITY,
    search_node_cap: int = 25000,
    max_detour_ratio: float = 3.0,
    stop_on_first_failure: bool = True,
    max_order_restarts: int = 1,
) -> GlobalRoutePreview:
    """Route all original Nets; release only after full DRC+physical connectivity.

    If any net fails, the preview is kept diagnosable and is ALWAYS NOT
    PRINT PASS. The actual circuit, real Net, and component position stay
    byte-for-byte unchanged.
    """
    if len({n.name for n in circuit.nets}) != len(circuit.nets):
        raise ValueError("ROUTE_DUPLICATE_CIRCUIT_NET")
    if type(max_order_restarts) is not int or not 0 <= max_order_restarts <= 5:
        raise ValueError("ROUTE_INVALID_MAX_RESTARTS")
    if (
        type(priority) is not tuple
        or any(type(name) is not str for name in priority)
        or len(set(priority)) != len(priority)
    ):
        raise ValueError("ROUTE_INVALID_DUPLICATED_NET_PRIORITY")
    known = {net.name: net for net in circuit.nets}
    names = tuple(x for x in priority if x in known)
    names += tuple(sorted(set(known) - set(names)))
    tree_results = []
    graph = _empty_graph()
    diagnostics = []
    for name in names:
        tree = route_multi_terminal_net(
            circuit, known[name], parts, symbols,
            page_box=page_box, occupied_graph=graph,
            annotation_placements=annotation_placements,
            stroke_um=stroke_um, search_node_cap=search_node_cap,
            max_detour_ratio=max_detour_ratio,
        )
        if not tree.complete and max_order_restarts:
            positions = _pin_catalog(circuit, known[name], parts, symbols)
            sorted_x = tuple(sorted(known[name].members, key=lambda p: (
                positions[p][0].x, positions[p][0].y,
                p.reference, p.number,
            )))
            sorted_y = tuple(sorted(known[name].members, key=lambda p: (
                positions[p][0].y, positions[p][0].x,
                p.reference, p.number,
            )))
            # The previous restart loop SKIPPED an unchanged pin ordering.
            # Consequently a two-terminal route could never retry its legal
            # original outward corridor with a larger detour, even when a
            # nearby ink/annotation obstacle required just such a turn.
            # First retry the SAME sourced PinRef order at a larger bounded
            # detour, then independently reverse its physical root; only
            # later try geometric terminal orders and coarser search.
            retries = (
                (None, 5000, 1.6),
                (tuple(reversed(known[name].members)), 5000, 2.0),
                (sorted_x, 5000, 2.0),
                (sorted_y, 10000, 2.0),
            )
            attempts = 0
            for order, grid, scale in retries:
                if attempts >= max_order_restarts:
                    break
                if order == known[name].members and attempts != 0:
                    continue
                attempts += 1
                other = route_multi_terminal_net(
                    circuit, known[name], parts, symbols,
                    page_box=page_box, occupied_graph=graph,
                    annotation_placements=annotation_placements,
                    stroke_um=stroke_um, search_node_cap=search_node_cap,
                    max_detour_ratio=min(max_detour_ratio * scale, 6.0),
                    grid_um=grid,
                    terminal_order=order,
                )
                if (other.complete or
                        len(other.completed_pins) > len(tree.completed_pins)):
                    tree = other
                if tree.complete:
                    break
            tree = replace(tree, search_restarts=attempts)
        tree_results.append(tree)
        if not tree.complete:
            diagnostics.extend(f"{name}:{d}" for d in tree.diagnostics)
            if stop_on_first_failure:
                break
            continue
        graph = ExternalWireGraph(
            (*graph.segments, *tree.segments),
            tuple(sorted(
                {*graph.junctions, *tree.junctions},
                key=lambda p: (p.x, p.y),
            )),
        )
    full_drc = audit_route_drc(
        circuit, graph, stroke_um=stroke_um,
        symbols_by_part=symbols,
        annotation_placements=annotation_placements,
    )
    if all(tree.complete for tree in tree_results) and len(tree_results) == len(known):
        physical = validate_external_wires(circuit, graph, parts, {
            sym.identifier: sym for sym in symbols.values()
        })
        errors = tuple(d.code for d in physical if d.severity.value == "error")
        diagnostics.extend(errors)
    if not full_drc.valid:
        diagnostics.append("ROUTE_POST_GLOBAL_DRC_FAIL")
    return GlobalRoutePreview(
        circuit, graph, tuple(tree_results), tuple(diagnostics), full_drc,
    )


def route_circuit_with_order_fallback(
    circuit: Circuit,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    annotation_placements: tuple = (),
    stroke_um: int = 300,
    search_node_cap: int = 25000,
    max_detour_ratio: float = 3.0,
    max_order_restarts: int = 2,
    try_priorities: int = 3,
    priority_offset: int = 0,
) -> GlobalRoutePreview:
    """Search independent functional route-order permutations without rewiring.

    Every attempt constructs its graph from EMPTY on the SAME Circuit source;
    a successful early Net cannot be substituted with a mismatched Net from
    another attempt. Deterministic ranking prefers more complete Nets, then
    fewer post-route DRC errors, fewer crossings/bends and shorter length.
    A partial graph always remains BLOCKED, even if geometric DRC is clean.
    """
    original = SOURCE_TL494_ROUTE_PRIORITY
    congested = (
        "FEEDBACK", "OSCILLATOR_RT", "CONTROL_REFERENCE",
        "GATE_DRIVE", "COMMON",
    )
    # A rejected net may reserve a scarce physical IC pin lane only if its
    # successfully routed *previous* Nets already occupy that corridor.
    # Test independent whole-graph orders, never splice wires between trials.
    # In particular, front-load the five real current SOURCE bottlenecks:
    # the default order put FEEDBACK/RT/COMMON after many other Net trunks.
    # These are routing search heuristics, not modified electrical Nets.
    orders = (
        ("SOURCE_FUNCTIONAL", original),
        ("COMMON_FIRST", ("COMMON", *(p for p in original if p != "COMMON"))),
        ("POWER_THEN_COMMON", (
            "INPUT_POS", "SWITCH", "COMMON",
            *(p for p in original if p not in
              {"INPUT_POS", "SWITCH", "COMMON"}),
        )),
        ("CONGESTED_PIN_FANOUT_FIRST", (
            *congested, *(p for p in original if p not in congested),
        )),
        ("CONGESTED_REVERSE_ROOTS", (
            *reversed(congested),
            *(p for p in original if p not in congested),
        )),
        ("SOURCE_REVERSE", tuple(reversed(original))),
    )
    if (
        type(try_priorities) is not int
        or type(priority_offset) is not int
        or not 1 <= try_priorities <= len(orders)
        or not 0 <= priority_offset < len(orders)
        or priority_offset + try_priorities > len(orders)
    ):
        raise ValueError("ROUTE_INVALID_FUNCTIONAL_ORDER_TRIAL_COUNT")
    orders = orders[priority_offset:priority_offset + try_priorities]
    history: list[tuple[str, int, int]] = []
    candidate_results: list[tuple[str, GlobalRoutePreview]] = []
    for strategy, priority in orders:
        preview = route_circuit_net_trees(
            circuit, parts, symbols,
            page_box=page_box, priority=priority,
            annotation_placements=annotation_placements,
            stroke_um=stroke_um, search_node_cap=search_node_cap,
            max_detour_ratio=max_detour_ratio,
            stop_on_first_failure=False,
            max_order_restarts=max_order_restarts,
        )
        accepted = sum(tree.complete for tree in preview.net_trees)
        errors = (
            sum(f.severity == "error" for f in preview.drc.findings)
            if preview.drc is not None else 1
        )
        history.append((strategy, accepted, errors))
        candidate_results.append((strategy, preview))
        if preview.print_pass:
            break

    def ranking(item: tuple[str, GlobalRoutePreview]) -> tuple:
        _, draft = item
        completed = sum(t.complete for t in draft.net_trees)
        errors = (
            sum(f.severity == "error" for f in draft.drc.findings)
            if draft.drc is not None else 1
        )
        lengths = sum(t.length_um for t in draft.net_trees)
        bends = sum(t.bend_count for t in draft.net_trees)
        crossings = sum(t.crossing_count for t in draft.net_trees)
        return (
            -int(draft.print_pass), -completed, errors,
            crossings, bends, lengths,
        )

    chosen_strategy, chosen = min(candidate_results, key=ranking)
    return replace(
        chosen, routing_strategy=chosen_strategy,
        route_order_trials=tuple(history),
    )
