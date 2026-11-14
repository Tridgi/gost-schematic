"""Issue #108 G2 — deterministic, source-PinRef multi-terminal E3 net-tree router.

A tree is assembled from real physical terminal coordinates and exact authored
T junctions. It is always a read-only preview; no semantic Circuit.Net, component
placement, or physical PartDefinition is modified. A failed route returns a
partial *nonprintable* graph and explicit reason. DO NOT claim ESKD APPROVED.
"""
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from itertools import pairwise

from gost_schematic.core.geometry import Box, Line, Point
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
            "not_gost_approved": True,
        }


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
    boxes: tuple[Box, ...],
    page: Box,
    stroke_um: int,
    search_node_cap: int,
    grid_um: int,
    max_detour_ratio: float,
) -> tuple[tuple[Point, ...], str | None]:
    """Deterministic multi-goal Dijkstra with explicit T candidates.

    A candidate ending on own tree is checked with that exact proposed dot,
    but intermediate crossings cannot silently acquire new dot authority.
    """
    if not goals:
        return (), "ROUTE_NO_TREE_TARGET"
    # Source's long COMMON and GATE_DRIVE require a SPARSE visibility grid.
    # A full Cartesian grid from every source wire endpoint can exceed 25k
    # nodes after just 5 nets. Keep closest genuine branch targets first;
    # retaining all pre-existing physical obstacles in edge validity checks.
    reachable_goals = tuple(sorted(
        set(goals),
        key=lambda p: (
            abs(p.x - source.x) + abs(p.y - source.y), p.x, p.y,
        ),
    ))[:24]
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
    if len(xs) * len(ys) > search_node_cap:
        return (), "ROUTE_GRID_TOO_DENSE"
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
            if not page.includes(to) or any(
                segment_intersects_box(Line(here, to), box) for box in boxes
            ):
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
        return (), "ROUTE_NO_CLEAR_ORTHOGONAL_TREE_PATH"
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
    order = terminal_order if terminal_order is not None else pins
    if len(order) != len(pins) or set(order) != set(pins):
        raise ValueError("ROUTE_TERMINAL_ORDER_MUST_MATCH_REAL_SOURCE_PINREF")
    locations = _pin_catalog(circuit, net, parts, symbols)
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
        path, reason = _visibility_path(
            current, outward, goals, net_name=net.name,
            occupied=occupied, tree=tuple(branches),
            existing_dots=dots,
            goal_pin_normals={
                at: normal for ref in connected
                for at, normal in (locations[ref],)
                if at in goals
            },
            boxes=boxes, page=page_box,
            stroke_um=stroke_um, grid_um=grid_um,
            search_node_cap=search_node_cap,
            max_detour_ratio=max_detour_ratio,
        )
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
        result = audit_route_drc(circuit, trial, stroke_um=stroke_um)
        if not result.valid:
            reasons = tuple(sorted({f.code for f in result.findings
                                    if f.severity == "error"}))
            return NetTreePreview(
                net.name, pins, tuple(branches), dots, total_bends,
                sum(abs(w.end.x-w.start.x)+abs(w.end.y-w.start.y)
                    for w in branches), total_crossings,
                ("ROUTE_POST_DRC_ERROR:" + ",".join(reasons),),
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
            alternate_orders = (
                tuple(sorted(known[name].members, key=lambda p: (
                    positions[p][0].x, positions[p][0].y,
                    p.reference, p.number,
                ))),
                tuple(sorted(known[name].members, key=lambda p: (
                    positions[p][0].y, positions[p][0].x,
                    p.reference, p.number,
                ))),
                tuple(reversed(known[name].members)),
            )
            attempts = 0
            for order in alternate_orders:
                if attempts >= max_order_restarts:
                    break
                if order == known[name].members:
                    continue
                attempts += 1
                other = route_multi_terminal_net(
                    circuit, known[name], parts, symbols,
                    page_box=page_box, occupied_graph=graph,
                    annotation_placements=annotation_placements,
                    stroke_um=stroke_um, search_node_cap=search_node_cap,
                    max_detour_ratio=max_detour_ratio,
                    grid_um=5000 if attempts == 1 else 10000,
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
