"""Issue #108: deterministic, fail-closed orthogonal E3 route preview.

No writes, no implied junction, no net merges, no automatic transformer
or part relocation. It is a two-physical-PinRef preview, NOT a full
multi-terminal industrial autorouter. Full 23/15 layout needs global
placement and explicit branch routing after independent QA acceptance.
"""
from dataclasses import dataclass
from heapq import heappop, heappush

from gost_schematic.core.geometry import Box, Line, Point, SIDE_VECTORS
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
)
from gost_schematic.validation.route_drc import (
    _seg_distance_sq,
    _symbol_boxes,
)

PAGES = (
    ("A4", 297000, 210000),
    ("A3", 420000, 297000),
    ("A2", 594000, 420000),
    ("A1", 841000, 594000),
    ("A0", 1189000, 841000),
)
FUNCTIONAL_GROUPS = {
    "input": ("X1", "L1"),
    "power_top": ("C1", "C2", "VD1", "L2", "FU1", "X2"),
    "pwm": ("DA1",),
    "control_left_lower": (
        "C3", "C4", "C7", "R1", "R2", "R3", "R4", "R5", "R6", "R7",
    ),
    "output_driver_right": ("R8", "VT1"),
}


@dataclass(frozen=True, slots=True)
class PlacementFinding:
    code: str
    detail: str
    references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlacementReview:
    page: str
    min_size_um: tuple[int, int]
    source_bounds_um: tuple[int, int, int, int]
    required_area_um: tuple[int, int]
    suggested_page: str | None
    findings: tuple[PlacementFinding, ...]
    component_count: int
    net_count: int

    @property
    def feasible(self) -> bool:
        return not self.findings


@dataclass(frozen=True, slots=True)
class RoutePreview:
    net_name: str
    first: PinRef
    second: PinRef
    waypoints: tuple[Point, ...]
    length_um: int
    bends: int
    crossings: int
    diagnostics: tuple[str, ...]
    preview_only: bool = True

    @property
    def valid(self) -> bool:
        return not self.diagnostics and len(self.waypoints) >= 2


def _global_graphics(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
) -> tuple[Box, dict[str, Box]]:
    boxes = _symbol_boxes(circuit, symbols_by_part)
    if not boxes:
        raise ValueError("PLACE_EMPTY_CIRCUIT")
    outer = [x[0] for x in boxes.values()]
    return Box(
        min(x.min_x for x in outer), min(x.min_y for x in outer),
        max(x.max_x for x in outer), max(x.max_y for x in outer),
    ), {name: pair[0] for name, pair in boxes.items()}


def evaluate_placement(
    circuit: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    *,
    page: str = "A3",
    margin_um: int = 10000,
    functional_flow: bool = True,
) -> PlacementReview:
    """Evaluate PREEXISTING poses only, without mutating a component.

    A3 page size is print paper, not the SVG viewBox aspect. The suggested
    larger size is capacity-only, not a guaranteed collision-free placement.
    """
    if type(margin_um) is not int or margin_um < 0:
        raise ValueError("PLACE_MARGIN_INVALID")
    page_record = next((p for p in PAGES if p[0] == page), None)
    if page_record is None:
        raise ValueError("PLACE_UNSUPPORTED_PAGE")
    outer, boxes = _global_graphics(circuit, symbols_by_part)
    width = outer.max_x - outer.min_x
    height = outer.max_y - outer.min_y
    needed = width + 2 * margin_um, height + 2 * margin_um
    chosen = next((
        p[0] for p in PAGES if p[1] >= needed[0] and p[2] >= needed[1]
    ), None)
    findings: list[PlacementFinding] = []
    if needed[0] > page_record[1] or needed[1] > page_record[2]:
        findings.append(PlacementFinding(
            "ROUTE_PAGE_CAPACITY", "Existing complete component extents do not fit "
            "inside the requested sheet and margins; never downscale UGO",
            tuple(sorted(boxes)),
        ))
    for ref, left in boxes.items():
        for other, right in boxes.items():
            if ref >= other:
                continue
            dx = max(0, left.min_x - right.max_x, right.min_x - left.max_x)
            dy = max(0, left.min_y - right.max_y, right.min_y - left.max_y)
            if dx * dx + dy * dy < 2000 ** 2:
                findings.append(PlacementFinding(
                    "ROUTE_COMPONENT_GAP_2MM",
                    "Actual separate UGO stroked extents closer than 2mm",
                    (ref, other),
                ))
    if functional_flow:
        centers = {
            name: ((box.min_x + box.max_x) // 2, (box.min_y + box.max_y) // 2)
            for name, box in boxes.items()
        }
        def order(first: str, second: str, relation: str) -> None:
            if first not in centers or second not in centers:
                return
            a, b = centers[first], centers[second]
            broken = a[0] > b[0] if relation == "left" else a[1] > b[1]
            if broken:
                findings.append(PlacementFinding(
                    "ROUTE_FUNCTIONAL_FLOW_ORDER",
                    f"{first} must be {relation} of {second} in the TL494 functional plan",
                    (first, second),
                ))
        for first, second in (
            ("X1", "L1"), ("X1", "DA1"), ("DA1", "VT1"),
            ("DA1", "X2"), ("R8", "VT1"), ("L1", "L2"),
            ("L2", "FU1"), ("FU1", "X2"),
        ):
            order(first, second, "left")
        if "DA1" in centers:
            for ref in FUNCTIONAL_GROUPS["control_left_lower"]:
                if ref in centers:
                    order(ref, "DA1", "left")
        for ref in FUNCTIONAL_GROUPS["power_top"]:
            if ref in centers and "DA1" in centers and ref != "X2":
                order(ref, "DA1", "above")
    return PlacementReview(
        page, (page_record[1], page_record[2]),
        (outer.min_x, outer.min_y, outer.max_x, outer.max_y),
        needed, chosen, tuple(findings), len(circuit.components),
        len(circuit.nets),
    )


def _resolve_real_pin(
    circuit: Circuit, physical: PinRef,
    parts: dict[str, PartDefinition],
    symbols_by_part: dict[str, SymbolDefinition],
) -> tuple[Point, Point, ComponentInstance]:
    matches = [c for c in circuit.components if c.reference == physical.reference]
    if len(matches) != 1:
        raise ValueError("ROUTE_UNKNOWN_OR_DUPLICATED_REFERENCE")
    instance = matches[0]
    part = parts.get(instance.part_id)
    symbol = symbols_by_part.get(instance.part_id)
    if part is None or symbol is None or part.symbol_id != symbol.identifier:
        raise ValueError("ROUTE_UNVERIFIED_PHYSICAL_PART_SYMBOL")
    if {x.number for x in part.pins} != {x.number for x in symbol.pins}:
        raise ValueError("ROUTE_PHYSICAL_CATALOG_PIN_MISMATCH")
    if physical.number not in {x.number for x in part.pins}:
        raise ValueError("ROUTE_UNKNOWN_PHYSICAL_PIN")
    matching = next(x for x in symbol.pins if x.number == physical.number)
    anchor = instance.transform.apply(matching.at) + instance.origin
    normal = instance.transform.apply(SIDE_VECTORS[matching.side])
    return anchor, normal, instance


def _legality(
    first: Point, second: Point, *,
    bounds: Box, boxes: tuple[Box, ...], graph: ExternalWireGraph,
    wire_radius_um: int,
) -> bool:
    if first == second or not bounds.includes(first) or not bounds.includes(second):
        return False
    if first.x != second.x and first.y != second.y:
        return False
    line = Line(first, second)
    if any(segment_intersects_box(line, b) for b in boxes):
        return False
    candidate = WireSegment(first, second, "__PREVIEW_ONLY__")
    # Distances are exact squared Fractions from authored source lines;
    # no drawing intersection may silently become a real T or junction.
    threshold = wire_radius_um * 2 + 500
    return all(_seg_distance_sq(candidate, other) >= threshold ** 2
               for other in graph.segments)


def preview_orthogonal_route(
    circuit: Circuit,
    graph: ExternalWireGraph,
    first: PinRef,
    second: PinRef,
    net_name: str,
    parts: dict[str, PartDefinition],
    symbols_by_part: dict[str, SymbolDefinition],
    *,
    page_box: Box,
    margin_um: int = 1000,
    stroke_um: int = 300,
    obstacle_gap_um: int = 1000,
    max_grid_nodes: int = 12000,
    max_detour_ratio: float = 2.5,
) -> RoutePreview:
    """Costed visibility-grid H/V route with immutable net+pin provenance.

    No true node, branch, bridge, wire or Net change is performed by preview.
    Candidates touching existing wires are BLOCKED, even same-Net wires.
    """
    def refuse(code: str) -> RoutePreview:
        return RoutePreview(net_name, first, second, (), 0, 0, 0, (code,))

    if type(stroke_um) is not int or not 200 <= stroke_um <= 1000:
        raise ValueError("ROUTE_INVALID_STROKE")
    if type(obstacle_gap_um) is not int or obstacle_gap_um < 0:
        raise ValueError("ROUTE_INVALID_SYMBOL_GAP")
    if type(margin_um) is not int or margin_um < 0:
        raise ValueError("ROUTE_INVALID_MARGIN")
    if max_grid_nodes < 4 or not 1 <= max_detour_ratio <= 20:
        raise ValueError("ROUTE_INVALID_SEARCH_LIMIT")
    matching = [net for net in circuit.nets if net.name == net_name]
    if len(matching) != 1 or first == second:
        return refuse("ROUTE_NET_UNKNOWN_OR_SAME_PIN")
    if first not in matching[0].members or second not in matching[0].members:
        return refuse("ROUTE_NET_PIN_NOT_MEMBER")
    if any(p in other.members for n in circuit.nets for other in (n,)
           for p in (first, second) if n.name != net_name):
        return refuse("ROUTE_PHYSICAL_PIN_MULTI_NET")
    try:
        start, start_normal, start_owner = _resolve_real_pin(
            circuit, first, parts, symbols_by_part,
        )
        target, target_normal, target_owner = _resolve_real_pin(
            circuit, second, parts, symbols_by_part,
        )
    except ValueError as error:
        return refuse(str(error))
    inner = Box(
        page_box.min_x + margin_um, page_box.min_y + margin_um,
        page_box.max_x - margin_um, page_box.max_y - margin_um,
    )
    if not inner.includes(start) or not inner.includes(target):
        return refuse("ROUTE_TERMINALS_OUTSIDE_PAGE")
    if start == target:
        return refuse("ROUTE_AMBIGUOUS_COINCIDENT_PINS")
    if any(w.net_name not in {n.name for n in circuit.nets} for w in graph.segments):
        return refuse("ROUTE_FOREIGN_UNKNOWN_NET")
    obstacles: list[Box] = []
    for component in circuit.components:
        sym = symbols_by_part.get(component.part_id)
        if sym is None:
            return refuse("ROUTE_COMPONENT_SYMBOL_MISSING")
        # A pin's own outer graphic lead is a permissible exit, but the body
        # remains protected. Other symbols are fully protected including ink.
        shape = (sym.body_keepout
                 if component.reference in (start_owner.reference, target_owner.reference)
                 else sym.stroked_bounds)
        box = component.transform.box(shape).translated(component.origin)
        obstacles.append(box.expanded(obstacle_gap_um + (stroke_um + 1) // 2))
    source_pin_near_body = any(b.contains_interior(start) for b in obstacles)
    target_pin_near_body = any(b.contains_interior(target) for b in obstacles)
    if source_pin_near_body or target_pin_near_body:
        # A graphic pin trapped inside a keepout cannot be fixed by a route.
        return refuse("ROUTE_PIN_EXIT_TRAPPED_BY_KEEP_OUT")
    x_coords = {start.x, target.x, inner.min_x, inner.max_x}
    y_coords = {start.y, target.y, inner.min_y, inner.max_y}
    for box in obstacles:
        for x in (box.min_x - 1, box.max_x + 1):
            if inner.min_x <= x <= inner.max_x:
                x_coords.add(x)
        for y in (box.min_y - 1, box.max_y + 1):
            if inner.min_y <= y <= inner.max_y:
                y_coords.add(y)
    for w in graph.segments:
        for p in (w.start, w.end):
            if inner.min_x <= p.x - 1000 <= inner.max_x:
                x_coords.add(p.x - 1000)
            if inner.min_x <= p.x + 1000 <= inner.max_x:
                x_coords.add(p.x + 1000)
            if inner.min_y <= p.y - 1000 <= inner.max_y:
                y_coords.add(p.y - 1000)
            if inner.min_y <= p.y + 1000 <= inner.max_y:
                y_coords.add(p.y + 1000)
    xs = sorted(x_coords)
    ys = sorted(y_coords)
    if len(xs) * len(ys) > max_grid_nodes:
        return refuse("ROUTE_GRID_TOO_DENSE_USE_LARGER_PAGE_OR_SPLIT")
    xindex = {x: i for i, x in enumerate(xs)}
    yindex = {y: i for i, y in enumerate(ys)}
    start_cell = (xindex[start.x], yindex[start.y])
    end_cell = (xindex[target.x], yindex[target.y])
    # Dijkstra with deterministic tie breakers; first key weighs bends and
    # path length, second is bend count, third is exact Manhattan length.
    source_state = (start_cell[0], start_cell[1], -1)
    heap = [(0, 0, 0, *source_state)]
    best = {source_state: (0, 0, 0)}
    previous: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    winner = None
    while heap:
        penalty, bends, length, ix, iy, direction = heappop(heap)
        state = (ix, iy, direction)
        if best.get(state) != (penalty, bends, length):
            continue
        if (ix, iy) == end_cell:
            winner = state
            break
        for dx, dy, new_direction in (
            (-1, 0, 0), (1, 0, 0), (0, -1, 1), (0, 1, 1),
        ):
            ni, nj = ix + dx, iy + dy
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            a, b = Point(xs[ix], ys[iy]), Point(xs[ni], ys[nj])
            if state == source_state and (
                (b.x - a.x) * start_normal.x + (
                    b.y - a.y
                ) * start_normal.y <= 0
            ):
                continue
            if (ni, nj) == end_cell and (
                (a.x - b.x) * target_normal.x + (
                    a.y - b.y
                ) * target_normal.y <= 0
            ):
                continue
            if not _legality(
                a, b, bounds=inner, boxes=tuple(obstacles),
                graph=graph, wire_radius_um=(stroke_um + 1) // 2,
            ):
                continue
            increment = abs(b.x - a.x) + abs(b.y - a.y)
            turn = int(direction >= 0 and direction != new_direction)
            new_length, new_bends = length + increment, bends + turn
            new_penalty = new_length + new_bends * 50000
            next_state = (ni, nj, new_direction)
            score = (new_penalty, new_bends, new_length)
            if next_state not in best or score < best[next_state]:
                best[next_state] = score
                previous[next_state] = state
                heappush(heap, (*score, *next_state))
    if winner is None:
        return refuse("ROUTE_NO_CLEAR_ORTHOGONAL_PATH")
    sequence = []
    cursor = winner
    while cursor != source_state:
        sequence.append(Point(xs[cursor[0]], ys[cursor[1]]))
        cursor = previous[cursor]
    sequence.append(start)
    sequence.reverse()
    # Remove inline intermediate nodes; only TRUE bends survive.
    result = [sequence[0]]
    for current, nxt in zip(sequence[1:-1], sequence[2:]):
        previous_point = result[-1]
        if (
            (current.x - previous_point.x) * (nxt.y - current.y) ==
            (current.y - previous_point.y) * (nxt.x - current.x)
        ):
            continue
        result.append(current)
    result.append(sequence[-1])
    length_um = sum(
        abs(b.x - a.x) + abs(b.y - a.y) for a, b in zip(result, result[1:])
    )
    manhattan = abs(target.x - start.x) + abs(target.y - start.y)
    if manhattan and length_um > manhattan * max_detour_ratio:
        return refuse("ROUTE_EXCESSIVE_DETOUR_REPLACE_LAYOUT")
    # A preview may be EMPTY by refusal. It must never alter the underlying
    # Circuit or ExternalWireGraph, no matter how plausible its lines look.
    return RoutePreview(
        net_name, first, second, tuple(result),
        length_um, len(result) - 2, 0, (),
    )


def preview_metrics(preview: RoutePreview) -> dict:
    return {
        "status": "DRAFT_ROUTE_PREVIEW_NOT_COMMITTED",
        "valid": preview.valid,
        "net": preview.net_name,
        "physical_pin_refs": [
            preview.first.reference + "." + preview.first.number,
            preview.second.reference + "." + preview.second.number,
        ],
        "waypoints_um": [[p.x, p.y] for p in preview.waypoints],
        "length_um": preview.length_um,
        "bends": preview.bends, "crossings": preview.crossings,
        "diagnostics": list(preview.diagnostics),
        "electrical_modifications": 0,
    }
