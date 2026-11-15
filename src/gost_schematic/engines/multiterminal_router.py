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
    ripup_trials: tuple[tuple[str, str, int, str], ...] = ()
    group_ripup_trials: tuple[tuple[str, str, int, str], ...] = ()

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
            "ripup_trials": [
                {"blocked_net": blocked, "ripped_net": removed,
                 "complete_nets": count, "status": status}
                for blocked, removed, count, status in self.ripup_trials
            ],
            "physical_conflict_dependencies": {
                name: list(owners) for name, owners in
                _physical_conflict_dependencies(self.net_trees).items()
            },
            "group_ripup_trials": [
                {"blocked_net": blocked, "removed_real_nets": owners,
                 "complete_nets": complete, "status": status}
                for blocked, owners, complete, status
                in self.group_ripup_trials
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
    *,
    root: PinRef | None = None,
) -> tuple[PinRef, ...]:
    """Deterministic Prim order from actual physical PinRefs.

    By default the first source-owned contact stays root. Explicit ALT roots
    must be members of this exact immutable Net: only order changes, not
    physical anchor, name, topology or contact membership.
    """
    if not pins or len(set(pins)) != len(pins):
        raise ValueError("ROUTE_PRIM_INVALID_SOURCE_PINREFS")
    first = pins[0] if root is None else root
    if first not in pins or set(pins) - set(positions):
        raise ValueError("ROUTE_PRIM_UNKNOWN_ROOT_OR_PHYSICAL_CONTACT")
    visited = [first]
    remaining = set(pins) - {first}
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
    prefer_astar: bool = False,
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
    # Source-real GraphicPin lead strokes can extend beyond the rectangular
    # body keepout. In a tight 7.5mm physical DA1 lead fanout the safe aisle
    # may be only hundreds of µm beyond a printed stroke cap; a 5mm sample
    # grid omits that aisle entirely. Add conservative exact SOURCE-INK
    # boundaries for leads within 16mm of the current real endpoints.
    # This is a SEARCH lane only; the original strokes, final candidate
    # collision veto and global full DRC remain unchanged. Do not add an
    # imagined physical PinRef, wire, dot, or exemption.
    for lead in ink_obstacles:
        if lead.permitted_pin is None or not overlaps_window(
            lead.collision_bounds
        ):
            continue
        bound = lead.collision_bounds
        # Include lead-cap lanes intersecting the actual source-to-goal
        # corridor, even when both endpoints are more than 16mm from the
        # obstruction. Endpoint-only proximity incorrectly skipped the ink
        # exactly halfway along a long straight run.
        if not (
            bound.max_x + 16000 >= x0
            and bound.min_x - 16000 <= x1
            and bound.max_y + 16000 >= y0
            and bound.min_y - 16000 <= y1
        ):
            continue
        x_set.update((bound.min_x - 1, bound.max_x + 1))
        y_set.update((bound.min_y - 1, bound.max_y + 1))
    xs = sorted(x for x in x_set if window.min_x <= x <= window.max_x)
    ys = sorted(y for y in y_set if window.min_y <= y <= window.max_y)
    # The Cartesian visibility lattice is sparse in practice: only states
    # actually expanded from the source allocate nodes. Reject enormous
    # lattices but do not confuse potential cells with 25k actual visits.
    if len(xs) * len(ys) > search_node_cap * 8:
        if search_node_cap < 16:
            return (), "ROUTE_GRID_TOO_DENSE"
        # The full potential Cartesian product is NOT the visited Dijkstra
        # budget. Earlier we rejected R5.2 and distant power terminals
        # without testing a single genuine wire candidate. Downsample ONLY
        # search coordinates, never source physical ink, copper or the DRC
        # obstacles. Every proposed edge still checks ALL original boxes,
        # real lead strokes, wire-veto and post-route full graph DRC.
        # Source/goal coordinates are non-negotiable. The compressed grid
        # keeps nearby verified lane boundaries where it is most likely
        # to find a short escape. If no path is found, report that honestly
        # rather than converting the failure to a synthetic connection.
        max_cells = search_node_cap * 8
        side = max(8, int(max_cells ** 0.5))
        keep_x = {window.min_x, window.max_x, source.x}
        keep_y = {window.min_y, window.max_y, source.y}
        keep_x.update(point.x for point in reachable_goals)
        keep_y.update(point.y for point in reachable_goals)

        def sampled_axis(
            values: list[int], required: set[int], endpoints: tuple[int, ...],
            limit: int,
        ) -> list[int]:
            mandatory = {value for value in required if value in values}
            if len(mandatory) >= limit:
                return sorted(mandatory)
            available = [value for value in values if value not in mandatory]
            available.sort(key=lambda value: (
                min(abs(value - pivot) for pivot in endpoints),
                value,
            ))
            chosen = mandatory | set(available[:limit - len(mandatory)])
            return sorted(chosen)

        # Two dimensions are trimmed together. Any axis smaller than side
        # retains every legitimate source candidate, allocating remaining
        # grid capacity to the longer axis instead of wasting budget.
        nx = min(len(xs), side)
        ny = min(len(ys), max_cells // nx)
        nx = min(len(xs), max_cells // ny)
        xs = sampled_axis(
            xs, keep_x, (source.x, *(p.x for p in reachable_goals)), nx,
        )
        ys = sampled_axis(
            ys, keep_y, (source.y, *(p.y for p in reachable_goals)), ny,
        )
        if len(xs) * len(ys) > max_cells:
            return (), "ROUTE_SPARSE_GRID_EXCEEDED_NODE_BUDGET"
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
    # Physical T/pin fast path is a *strictly legal* geometry check, NOT a
    # routing/DRC exception. New lead-cap visibility grid lanes can make a
    # much longer detour look attractive before reaching an already printed
    # same-Net T on the very same axis. The shortest direct wire is allowed
    # only if it exits the source pin outward, reaches a true original PinRef
    # from its exterior when applicable, and clears all actual native UGO,
    # measured Type A text and existing full-graph wires. Any crossing with
    # warning is deferred to the normal Dijkstra search. The same
    # bounded detour ratio that governs Dijkstra also governs this shortcut.
    shortest_goal_distance = min(
        abs(source.x - target.x) + abs(source.y - target.y)
        for target in reachable_goals
    )
    for goal in reachable_goals:
        candidate_distance = (
            abs(source.x - goal.x) + abs(source.y - goal.y)
        )
        if (
            goal == source
            or shortest_goal_distance and candidate_distance > (
                max_detour_ratio * shortest_goal_distance
            )
            or not (source.x == goal.x or source.y == goal.y)
        ):
            continue
        if (
            (goal.x - source.x) * normal.x
            + (goal.y - source.y) * normal.y
        ) <= 0:
            continue
        goal_normal = goal_pin_normals.get(goal)
        if goal_normal is not None and (
            (source.x - goal.x) * goal_normal.x
            + (source.y - goal.y) * goal_normal.y
        ) <= 0:
            continue
        wire = WireSegment(source, goal, net_name)
        graphic = Line(source, goal)
        guard_boxes = (
            boxes_by_y[source.y] if source.y == goal.y
            else boxes_by_x[source.x]
        )
        guard_ink = (
            ink_by_y[source.y] if source.y == goal.y
            else ink_by_x[source.x]
        )
        if any(segment_intersects_box(graphic, box) for box in guard_boxes):
            continue
        if _source_ink_collision(
            wire, guard_ink, authorized_pins=authorized_pins,
        ) is not None:
            continue
        junctions = frozenset((
            *occupied.junctions, *existing_dots, goal,
        ))
        checks = tuple(
            candidate_wire_clearance(
                wire, old,
                candidate_stroke_um=stroke_um,
                existing_stroke_um=stroke_um,
                explicit_junctions=junctions,
            ) for old in (*occupied.segments, *tree)
        )
        if all(check.valid and not check.warnings for check in checks):
            return (source, goal), None
    start = (x_idx[source.x], y_idx[source.y], -1)
    active = (*occupied.segments, *tree)
    permanent_dots = frozenset((*occupied.junctions, *existing_dots))
    current_score = {start: (0, 0, 0, 0)}
    predecessor: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    # A* Manhattan lower bound is admissible even with positive bend and
    # foreign-crossing penalties. Dijkstra's zero heuristic needlessly
    # expanded thousands of unrelated rows before trying the real target.
    # Only SEARCH order changes; every old physical veto/DRC is preserved.
    def remaining_distance(at: Point) -> int:
        return min(
            abs(at.x - goal.x) + abs(at.y - goal.y)
            for goal in reachable_goals
        )

    heap = [(
        remaining_distance(source) if prefer_astar else 0,
        0, 0, 0, 0, *start,
    )]
    reached = None
    visited = 0
    # A goal-window retry must use only its selected real T candidates.
    # Earlier unreachable goals outside the window cannot impose their
    # shorter distance as a false detour bound on a farther physical T.
    best_direct = min(
        abs(source.x - goal.x) + abs(source.y - goal.y)
        for goal in reachable_goals
    )
    cache: dict[tuple[Point, Point, bool], tuple[bool, int]] = {}
    ink_rejections: dict[tuple[str, int, str], tuple[Point, Point]] = {}
    wire_rejections: dict[
        tuple[str, str, Point, Point], tuple[Point, Point]
    ] = {}
    while heap:
        _, score, bends, crossings, length, ix, iy, direction = heappop(heap)
        state = (ix, iy, direction)
        if current_score.get(state) != (score, bends, crossings, length):
            continue
        visited += 1
        if visited > search_node_cap * 3:
            if not prefer_astar:
                # Preserve every successful Dijkstra route. Only a failed
                # bounded exploration receives one admissible A* retry.
                # This is a SEARCH restart, not permission to cross UGO ink,
                # bypass a PinRef, or relax a single physical DRC rule.
                return _visibility_path(
                    source, normal, goals,
                    net_name=net_name, occupied=occupied, tree=tree,
                    existing_dots=existing_dots,
                    goal_pin_normals=goal_pin_normals,
                    ink_obstacles=ink_obstacles,
                    authorized_pins=authorized_pins, boxes=boxes,
                    page=page, stroke_um=stroke_um,
                    search_node_cap=search_node_cap, grid_um=grid_um,
                    max_detour_ratio=max_detour_ratio,
                    goal_offset=goal_offset, prefer_astar=True,
                )
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
                heappush(heap, (
                    n_score + (remaining_distance(to) if prefer_astar else 0),
                    *improved, *next_state,
                ))
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
            # Preserve the same-source detour retry, then try the actual
            # physical medoid as root for multi-contact Nets. COMMON's photo
            # first PinRef X1.2 is at a distant sheet boundary; reversing
            # the source list is NOT a Steiner/Prim search and can route
            # another 300mm unnecessary early trunk. A medoid root minimizes
            # real Manhattan distance to the OTHER physical terminals, then
            # Prim grows its actual sourced tree (no fake point or Net).
            members = known[name].members
            if len(members) > 2:
                medoid = min(members, key=lambda pin: (
                    sum(
                        abs(positions[pin][0].x - positions[peer][0].x)
                        + abs(positions[pin][0].y - positions[peer][0].y)
                        for peer in members
                    ),
                    pin.reference, pin.number,
                ))
                centered = _nearest_net_order(
                    members, positions, root=medoid,
                )
            else:
                centered = tuple(reversed(members))
            retries = (
                (None, 5000, 1.6),
                (centered, 5000, 2.0),
                (tuple(reversed(members)), 5000, 2.0),
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



def _accepted_tree_graph(trees: tuple[NetTreePreview, ...]) -> ExternalWireGraph:
    """Rebuild copper AND same-Net dots only from independently complete trees.

    Never retain an old ripped-up junction (it could falsely connect a new
    conductor), or include partially constructed but rejected branch wires.
    """
    completed = tuple(tree for tree in trees if tree.complete)
    if len({tree.net_name for tree in completed}) != len(completed):
        raise ValueError("ROUTE_RIPUP_DUPLICATED_SOURCE_NET_TREE")
    return ExternalWireGraph(
        tuple(w for tree in completed for w in tree.segments),
        tuple(sorted(
            {point for tree in completed for point in tree.junctions},
            key=lambda point: (point.x, point.y),
        )),
    )


def _observed_ripup_pairs(
    trees: tuple[NetTreePreview, ...],
) -> tuple[tuple[str, str], ...]:
    """Use only an actual foreign-Net physical WIRE_VETO as repair evidence."""
    complete = frozenset(tree.net_name for tree in trees if tree.complete)
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for failed in trees:
        if failed.complete:
            continue
        for diagnostic in failed.diagnostics:
            if ":WIRE_VETO=" not in diagnostic:
                continue
            for record in diagnostic.split(":WIRE_VETO=", 1)[1].split(";"):
                owner = record.split(":", 1)[0]
                key = (failed.net_name, owner)
                if (
                    owner not in complete or owner == failed.net_name
                    or key in seen
                ):
                    continue
                seen.add(key)
                result.append(key)
    return tuple(result)


def _reroute_real_net(
    circuit: Circuit,
    net: Net,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    occupied_graph: ExternalWireGraph,
    page_box: Box,
    annotation_placements: tuple,
    stroke_um: int,
    search_node_cap: int,
    max_detour_ratio: float,
) -> NetTreePreview:
    """Rebuild a sourced physical tree, optionally trying its true reverse.

    Neither the physical source PinRefs nor its nominal/UGO/clearance changes.
    Every candidate passes the same strict per-segment, ink and DRC gates.
    """
    first = route_multi_terminal_net(
        circuit, net, parts, symbols,
        page_box=page_box, occupied_graph=occupied_graph,
        annotation_placements=annotation_placements,
        stroke_um=stroke_um, search_node_cap=search_node_cap,
        max_detour_ratio=max_detour_ratio,
    )
    if first.complete or len(net.members) < 2:
        return first
    reverse = route_multi_terminal_net(
        circuit, net, parts, symbols,
        page_box=page_box, occupied_graph=occupied_graph,
        annotation_placements=annotation_placements,
        stroke_um=stroke_um, search_node_cap=search_node_cap,
        max_detour_ratio=max_detour_ratio,
        terminal_order=tuple(reversed(net.members)),
    )
    if reverse.complete or len(reverse.completed_pins) > len(first.completed_pins):
        return reverse
    return first


def _conflict_directed_ripup(
    source: GlobalRoutePreview,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    annotation_placements: tuple,
    stroke_um: int,
    search_node_cap: int,
    max_detour_ratio: float,
    budget: int,
) -> GlobalRoutePreview:
    """Bounded physical rip-up/rebuild search, never a DRC or topology waiver.

    On an observed failed Net / foreign accepted copper collision, remove
    exactly that real foreign tree, keep all independently valid other trees,
    route the blocked Net, then reroute the removed real Net. One attempt may
    exchange which source Net is blocked, allowing the next attempt to free
    a different corridor. The return value is always globally rescanned;
    candidates that do not improve the full-connected-Net count cannot
    replace the caller's result, and partial routes remain NOT PRINT PASS.
    """
    if type(budget) is not int or not 0 <= budget <= 4:
        raise ValueError("ROUTE_INVALID_PHYSICAL_RIPUP_BUDGET")
    if budget == 0 or source.print_pass:
        return source
    circuit = source.source_circuit
    original = {net.name: net for net in circuit.nets}
    if (
        len(original) != len(circuit.nets)
        or len(source.net_trees) != len(circuit.nets)
        or {tree.net_name for tree in source.net_trees} != set(original)
        or any(tree.pin_refs != original[tree.net_name].members
               for tree in source.net_trees)
    ):
        raise ValueError("ROUTE_RIPUP_UNTRUSTED_SOURCE_PREVIEW")
    # Derive candidate copper from actual complete tree data, not blindly
    # trust a serialized/handcrafted graph that may omit hidden foreign wire.
    if _accepted_tree_graph(source.net_trees) != source.graph:
        raise ValueError("ROUTE_RIPUP_GRAPH_TREE_MISMATCH")

    best = source
    best_count = sum(tree.complete for tree in source.net_trees)
    frontier = [source]
    seen: set[ExternalWireGraph] = {source.graph}
    history: list[tuple[str, str, int, str]] = []
    while frontier and len(history) < budget:
        current = frontier.pop(0)
        for blocked, blocker in _observed_ripup_pairs(current.net_trees):
            if len(history) >= budget:
                break
            retained = tuple(
                tree for tree in current.net_trees
                if tree.complete and tree.net_name != blocker
            )
            retained_graph = _accepted_tree_graph(retained)
            restored = _reroute_real_net(
                circuit, original[blocked], parts, symbols,
                occupied_graph=retained_graph, page_box=page_box,
                annotation_placements=annotation_placements,
                stroke_um=stroke_um, search_node_cap=search_node_cap,
                max_detour_ratio=max_detour_ratio,
            )
            if not restored.complete:
                history.append((blocked, blocker, best_count, "BLOCKED_PIN_OR_INK"))
                continue
            next_occupied = _accepted_tree_graph((*retained, restored))
            rebuilt = _reroute_real_net(
                circuit, original[blocker], parts, symbols,
                occupied_graph=next_occupied, page_box=page_box,
                annotation_placements=annotation_placements,
                stroke_um=stroke_um, search_node_cap=search_node_cap,
                max_detour_ratio=max_detour_ratio,
            )
            replacements = {blocked: restored, blocker: rebuilt}
            new_trees = tuple(
                replacements.get(tree.net_name, tree)
                for tree in current.net_trees
            )
            candidate_graph = _accepted_tree_graph(new_trees)
            drc = audit_route_drc(
                circuit, candidate_graph, stroke_um=stroke_um,
                symbols_by_part=symbols,
                annotation_placements=annotation_placements,
            )
            if not drc.valid:
                history.append((blocked, blocker, best_count, "REJECTED_GLOBAL_DRC"))
                continue
            diagnostic = [
                f"{tree.net_name}:{code}"
                for tree in new_trees if not tree.complete
                for code in tree.diagnostics
            ]
            if all(tree.complete for tree in new_trees):
                found = validate_external_wires(
                    circuit, candidate_graph, parts,
                    {symbol.identifier: symbol for symbol in symbols.values()},
                )
                physical_errors = tuple(
                    issue.code for issue in found
                    if issue.severity.value == "error"
                )
                if physical_errors:
                    history.append((
                        blocked, blocker, best_count, "REJECTED_PHYSICAL_ERC",
                    ))
                    continue
            candidate = GlobalRoutePreview(
                circuit, candidate_graph, new_trees, tuple(diagnostic), drc,
                current.routing_strategy, current.route_order_trials,
            )
            new_count = sum(tree.complete for tree in new_trees)
            history.append((
                blocked, blocker, new_count,
                "BOTH_REBUILT" if rebuilt.complete else "RIPPED_NET_BLOCKED",
            ))
            # A candidate can be retained on the temporary bounded frontier
            # even if its complete-Net count is equal, but only an actual
            # improvement replaces the returned best. Old copper is never
            # silently substituted into a different independent graph.
            if new_count > best_count:
                best, best_count = candidate, new_count
            if candidate_graph not in seen and len(frontier) < budget:
                seen.add(candidate_graph)
                frontier.append(candidate)
    return replace(
        best, ripup_trials=tuple(history),
        routing_strategy=(
            "CONFLICT_DIRECTED_PHYSICAL_RIPUP"
            if best is not source else source.routing_strategy
        ),
    )



def _physical_conflict_dependencies(
    trees: tuple[NetTreePreview, ...],
) -> dict[str, tuple[str, ...]]:
    """Reported real copper dependency graph of BLOCKED -> accepted foreign Nets.

    Include no guessed blocker on INK, grid-budget or pin-escape errors.
    Source net tree identities are preserved even when no witness exists.
    """
    accepted = {tree.net_name for tree in trees if tree.complete}
    result: dict[str, tuple[str, ...]] = {}
    for tree in trees:
        if tree.complete:
            continue
        blockers: list[str] = []
        for diagnosis in tree.diagnostics:
            for marker in diagnosis.split(":WIRE_VETO=")[1:]:
                for token in marker.split(";"):
                    owner = token.split(":", 1)[0]
                    if (
                        owner in accepted and owner != tree.net_name
                        and owner not in blockers
                    ):
                        blockers.append(owner)
        result[tree.net_name] = tuple(blockers)
    return result


def _conflict_group_reroute(
    source: GlobalRoutePreview,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    annotation_placements: tuple,
    stroke_um: int,
    search_node_cap: int,
    max_detour_ratio: float,
    attempts: int,
) -> GlobalRoutePreview:
    """Bounded 2+1 Net simultaneous genuine physical copper re-planning.

    A blocked tree's actual veto owners form its measured conflict component;
    remove no more than TWO accepted foreign trees at once. Build blocked
    first, then reconstruct both removed authentic trees in either order.
    Candidate graph consists ONLY of freshly independently DRC-cleared,
    completed trees. Never invent a terminal, copper stroke, or terminal T.
    """
    if type(attempts) is not int or not 0 <= attempts <= 3:
        raise ValueError("ROUTE_INVALID_CONFLICT_GROUP_ATTEMPTS")
    if attempts == 0 or source.print_pass:
        return source
    circuit = source.source_circuit
    known = {n.name: n for n in circuit.nets}
    if (
        len(known) != len(circuit.nets)
        or len(source.net_trees) != len(circuit.nets)
        or {tree.net_name for tree in source.net_trees} != set(known)
        or any(tree.pin_refs != known[tree.net_name].members
               for tree in source.net_trees)
        or _accepted_tree_graph(source.net_trees) != source.graph
    ):
        raise ValueError("ROUTE_GROUP_RIPUP_UNTRUSTED_PREVIEW")
    best = source
    best_complete = sum(t.complete for t in source.net_trees)
    history = []
    dependencies = _physical_conflict_dependencies(source.net_trees)
    for blocked, owners in dependencies.items():
        if len(history) >= attempts:
            break
        if len(owners) < 2:
            continue
        removing = owners[:2]
        rest = tuple(
            tree for tree in source.net_trees
            if tree.complete and tree.net_name not in removing
        )
        start = _accepted_tree_graph(rest)
        for chosen_order in (removing, tuple(reversed(removing))):
            if len(history) >= attempts:
                break
            candidate_trees = {
                tree.net_name: tree for tree in rest
            }
            blocked_tree = _reroute_real_net(
                circuit, known[blocked], parts, symbols,
                occupied_graph=start, page_box=page_box,
                annotation_placements=annotation_placements,
                stroke_um=stroke_um, search_node_cap=search_node_cap,
                max_detour_ratio=max_detour_ratio,
            )
            if not blocked_tree.complete:
                history.append((
                    blocked, "+".join(chosen_order), best_complete,
                    "PHYSICAL_PIN_OR_INK_BLOCKED",
                ))
                continue
            candidate_trees[blocked] = blocked_tree
            for owner in chosen_order:
                graph = _accepted_tree_graph(tuple(candidate_trees.values()))
                ret = _reroute_real_net(
                    circuit, known[owner], parts, symbols,
                    occupied_graph=graph, page_box=page_box,
                    annotation_placements=annotation_placements,
                    stroke_um=stroke_um, search_node_cap=search_node_cap,
                    max_detour_ratio=max_detour_ratio,
                )
                if ret.complete:
                    candidate_trees[owner] = ret
                else:
                    candidate_trees[owner] = ret
            trial_trees = tuple(
                candidate_trees.get(tree.net_name, tree)
                for tree in source.net_trees
            )
            graph = _accepted_tree_graph(trial_trees)
            drc = audit_route_drc(
                circuit, graph, stroke_um=stroke_um,
                symbols_by_part=symbols,
                annotation_placements=annotation_placements,
            )
            if not drc.valid:
                history.append((
                    blocked, "+".join(chosen_order), best_complete,
                    "REJECTED_FULL_GRAPH_DRC",
                ))
                continue
            complete = sum(tree.complete for tree in trial_trees)
            notes = tuple(
                f"{tree.net_name}:{diagnostic}"
                for tree in trial_trees if not tree.complete
                for diagnostic in tree.diagnostics
            )
            if complete == len(known):
                faults = validate_external_wires(
                    circuit, graph, parts,
                    {sym.identifier: sym for sym in symbols.values()},
                )
                if any(f.severity.value == "error" for f in faults):
                    history.append((
                        blocked, "+".join(chosen_order), complete,
                        "REJECTED_PHYSICAL_ERC",
                    ))
                    continue
            candidate = GlobalRoutePreview(
                circuit, graph, trial_trees, notes, drc,
                source.routing_strategy, source.route_order_trials,
                source.ripup_trials,
            )
            history.append((
                blocked, "+".join(chosen_order), complete,
                "REBUILT" if all(
                    candidate_trees[o].complete for o in chosen_order
                ) else "SOME_REMOVED_NET_INCOMPLETE",
            ))
            if complete > best_complete:
                best, best_complete = candidate, complete
    return replace(
        best,
        group_ripup_trials=tuple(history),
        routing_strategy=(
            "CONFLICT_COMPONENT_PHYSICAL_REBUILD"
            if best is not source else source.routing_strategy
        ),
    )


def _source_priority_name_view(
    original: tuple[str, ...],
    actual_names: frozenset[str],
) -> tuple[str, ...]:
    """Choose REAL source names, not fabricated alias Nets, for route order.

    The user photo records a_INPUT_PLUS / TRANSFER / b_NEGATIVE_OUTPUT,
    while older RECON display art called these INPUT_POS /
    ENERGY_TRANSFER / OUTPUT_NEG. All three pairs have the same original
    *physical PinRef tuples*. The source-typed graph MUST retain whichever
    actual Circuit.Net.name was provided, never rewrite or merge the Net.
    """
    aliases = {
        "INPUT_POS": "a_INPUT_PLUS",
        "ENERGY_TRANSFER": "TRANSFER",
        "OUTPUT_NEG": "b_NEGATIVE_OUTPUT",
    }
    if len(set(original)) != len(original):
        raise ValueError("ROUTE_DUPLICATE_SOURCE_ORDER_LABEL")
    translated = tuple(
        name if name in actual_names else aliases.get(name, name)
        for name in original
    )
    if len(set(translated)) != len(translated):
        raise ValueError("ROUTE_SOURCE_ALIAS_PRIORITY_COLLISION")
    return translated


def _physical_wire_veto_priority_trials(
    priority: tuple[str, ...],
    trees: tuple[NetTreePreview, ...],
    *,
    limit: int,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Promote only REAL failed Net before a prior REAL blocking-wire owner.

    Each source diagnosis is an observed invalid trial against already
    accepted *foreign* physical copper. The resulting order is a candidate
    to rerun from EMPTY; this helper never edits or combines routed graphs.
    A symbol-ink veto by itself provides no evidence for reordering.
    """
    if type(limit) is not int or not 0 <= limit <= 4:
        raise ValueError("ROUTE_INVALID_PHYSICAL_VETO_TRIAL_LIMIT")
    if len(set(priority)) != len(priority):
        raise ValueError("ROUTE_PHYSICAL_VETO_DUPLICATE_NET_PRIORITY")
    if limit == 0:
        return ()
    positions = {name: i for i, name in enumerate(priority)}
    # Sort proposals by the number of existing source-Nets displaced.
    # Relocating OSCILLATOR_RT before OSCILLATOR_CT is a bounded local
    # repair, unlike moving GATE_DRIVE across half the source power graph.
    # This is scheduling only, not a physical geometry or DRC waiver.
    outcomes: list[tuple[int, int, str, tuple[str, ...]]] = []
    seen: set[tuple[str, ...]] = {priority}
    for tree in trees:
        blocked = tree.net_name
        if tree.complete or blocked not in positions:
            continue
        for diagnostic in tree.diagnostics:
            if ":WIRE_VETO=" not in diagnostic:
                continue
            entries = diagnostic.split(":WIRE_VETO=", 1)[1].split(";")
            for entry in entries:
                foreign = entry.split(":", 1)[0]
                if (
                    foreign not in positions
                    or foreign == blocked
                    or positions[foreign] >= positions[blocked]
                ):
                    continue
                # This is only an independent whole-graph priority proposal.
                # Never remove any Net, change membership or authorize the
                # failed foreign-Net contact. It must be routed anew and
                # independently pass symbol/text/wire DRC.
                move = tuple(name for name in priority if name != blocked)
                index = move.index(foreign)
                reordered = (
                    *move[:index], blocked, *move[index:],
                )
                if reordered in seen:
                    continue
                seen.add(reordered)
                outcomes.append((
                    positions[blocked] - positions[foreign],
                    len(outcomes),
                    f"VETO_REORDER_{blocked}_BEFORE_{foreign}",
                    reordered,
                ))
    outcomes.sort(key=lambda item: (item[0], item[1]))
    return tuple(
        (name, reordered) for _, _, name, reordered in outcomes[:limit]
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
    physical_veto_restarts: int = 0,
    physical_ripup_attempts: int = 0,
    physical_group_attempts: int = 0,
) -> GlobalRoutePreview:
    """Search independent functional route-order permutations without rewiring.

    Every attempt constructs its graph from EMPTY on the SAME Circuit source;
    a successful early Net cannot be substituted with a mismatched Net from
    another attempt. Deterministic ranking prefers more complete Nets, then
    fewer post-route DRC errors, fewer crossings/bends and shorter length.
    A partial graph always remains BLOCKED, even if geometric DRC is clean.
    """
    actual_net_names = frozenset(net.name for net in circuit.nets)
    original = _source_priority_name_view(
        SOURCE_TL494_ROUTE_PRIORITY, actual_net_names,
    )
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
            original[0], "SWITCH", "COMMON",
            *(p for p in original if p not in
              {original[0], "SWITCH", "COMMON"}),
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
    if (
        type(physical_veto_restarts) is not int
        or not 0 <= physical_veto_restarts <= 4
    ):
        raise ValueError("ROUTE_INVALID_PHYSICAL_VETO_TRIAL_LIMIT")
    if type(physical_ripup_attempts) is not int or not 0 <= physical_ripup_attempts <= 4:
        raise ValueError("ROUTE_INVALID_PHYSICAL_RIPUP_BUDGET")
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
    if physical_veto_restarts and not chosen.print_pass:
        chosen_priority = next(
            priority for label, priority in orders
            if label == chosen_strategy
        )
        actual = frozenset(net.name for net in circuit.nets)
        actual_priority = tuple(
            name for name in chosen_priority if name in actual
        )
        actual_priority += tuple(sorted(actual - set(actual_priority)))
        proposals = _physical_wire_veto_priority_trials(
            actual_priority, chosen.net_trees,
            limit=physical_veto_restarts,
        )
        for strategy, priority in proposals:
            independent = route_circuit_net_trees(
                circuit, parts, symbols,
                page_box=page_box, priority=priority,
                annotation_placements=annotation_placements,
                stroke_um=stroke_um, search_node_cap=search_node_cap,
                max_detour_ratio=max_detour_ratio,
                stop_on_first_failure=False,
                max_order_restarts=max_order_restarts,
            )
            count = sum(tree.complete for tree in independent.net_trees)
            errors = (
                sum(f.severity == "error" for f in independent.drc.findings)
                if independent.drc is not None else 1
            )
            history.append((strategy, count, errors))
            challenger = (strategy, independent)
            if ranking(challenger) < ranking((chosen_strategy, chosen)):
                chosen_strategy, chosen = challenger
            if chosen.print_pass:
                break
    chosen = replace(
        chosen, routing_strategy=chosen_strategy,
        route_order_trials=tuple(history),
    )
    paired = _conflict_directed_ripup(
        chosen, parts, symbols, page_box=page_box,
        annotation_placements=annotation_placements,
        stroke_um=stroke_um, search_node_cap=search_node_cap,
        max_detour_ratio=max_detour_ratio, budget=physical_ripup_attempts,
    )
    return _conflict_group_reroute(
        paired, parts, symbols, page_box=page_box,
        annotation_placements=annotation_placements,
        stroke_um=stroke_um, search_node_cap=search_node_cap,
        max_detour_ratio=max_detour_ratio, attempts=physical_group_attempts,
    )
