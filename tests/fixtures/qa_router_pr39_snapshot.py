"""EXPERIMENTAL ROUTING: bounded deterministic one-net orthogonal routing.

Exact integer-micrometre contacts only. No snapping, internal symbol topology
inference, multi-net routing, or mutation of shared electrical/graphics models.
"""
from dataclasses import dataclass
from heapq import heappop, heappush

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


@dataclass(frozen=True, slots=True)
class TwoPinRoute:
    points: tuple[Point, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def ok(self) -> bool:
        return len(self.points) >= 2 and not self.diagnostics

    def external_graph(self, net_name: str) -> ExternalWireGraph:
        """Never return a partially calculated connection after a failure."""
        if not self.ok:
            raise ValueError("No completed two-pin route")
        return ExternalWireGraph(tuple(
            WireSegment(a, b, net_name)
            for a, b in zip(self.points, self.points[1:], strict=False)
        ))


def _fail(code: str, message: str) -> TwoPinRoute:
    return TwoPinRoute((), (Diagnostic(code, Severity.ERROR, message, "two-pin"),))


def _foreign_box(wire: WireSegment, margin: int) -> Box:
    """Overapproximate an existing diagonal/orthogonal wire by its entire AABB."""
    return Box(
        min(wire.start.x, wire.end.x), min(wire.start.y, wire.end.y),
        max(wire.start.x, wire.end.x) + 1,
        max(wire.start.y, wire.end.y) + 1,
    ).expanded(margin)


def _window(start: Point, end: Point, hazards: tuple[Box, ...], grid: int) -> Box:
    xmin, xmax = min(start.x, end.x), max(start.x, end.x)
    ymin, ymax = min(start.y, end.y), max(start.y, end.y)
    for box in hazards:
        xmin, xmax = min(xmin, box.min_x), max(xmax, box.max_x)
        ymin, ymax = min(ymin, box.min_y), max(ymax, box.max_y)
    pad = 4 * grid
    return Box(xmin - pad, ymin - pad, xmax + pad, ymax + pad)


def _turns(nodes: list[Point]) -> tuple[Point, ...]:
    if len(nodes) < 3:
        return tuple(nodes)
    answer = [nodes[0]]
    for before, here, after in zip(nodes, nodes[1:], nodes[2:], strict=False):
        if (here.x - before.x, here.y - before.y) != (
            after.x - here.x, after.y - here.y
        ):
            answer.append(here)
    answer.append(nodes[-1])
    return tuple(answer)


def route_two_pins(
    start: Point,
    end: Point,
    *,
    keepouts: tuple[Box, ...] = (),
    existing_wires: tuple[WireSegment, ...] = (),
    grid_um: int = 1000,
    clearance_um: int = 400,
    stroke_um: int = 300,
    bounds: Box | None = None,
    max_cells: int = 50000,
) -> TwoPinRoute:
    """Route two pre-existing on-grid pin coordinates; no silent snap.

    Grid is globally zero-aligned, with four axis-aligned unit moves. Search
    minimizes (number of steps, number of right-angle bends). Heap ordering
    additionally fixes ties by Y, X and direction; obstacle ordering is sorted.
    Rectangles are closed (touch means collision). Body hazards expand by
    clearance plus half new stroke. Every pre-existing wire, regardless of its
    declared net, is excluded by a conservative AABB expanded by clearance
    plus both half-strokes. This forbids false shorts and any collinear overlap.
    Bounds are finite; a failed bounded search does not prove no global route.
    """
    if not isinstance(start, Point) or not isinstance(end, Point):
        return _fail("ROUTE_COORDINATE_INVALID", "Both contacts must be Points")
    if start == end:
        return _fail("ROUTE_COINCIDENT_PINS", "The two contacts coincide")
    if type(grid_um) is not int or grid_um <= 0:
        return _fail("ROUTE_GRID_INVALID", "Grid step must be a positive integer µm")
    if (
        type(clearance_um) is not int or clearance_um < 0
        or type(stroke_um) is not int or stroke_um <= 0
        or type(max_cells) is not int or max_cells <= 0
    ):
        return _fail("ROUTE_OPTIONS_INVALID", "Invalid clearance/stroke/cell limit")
    if any(coordinate % grid_um for coordinate in (
        start.x, start.y, end.x, end.y
    )):
        return _fail("ROUTE_OFF_GRID", "Off-grid endpoint; snapping is forbidden")
    if (not isinstance(keepouts, tuple)
            or any(not isinstance(item, Box) for item in keepouts)
            or not isinstance(existing_wires, tuple)
            or any(not isinstance(item, WireSegment) for item in existing_wires)):
        return _fail("ROUTE_OBSTACLE_INVALID", "Invalid obstacle collection")
    if bounds is not None and not isinstance(bounds, Box):
        return _fail("ROUTE_WINDOW_INVALID", "Bounds must be a Box or None")

    half_stroke = (stroke_um + 1) // 2
    hazards = tuple(sorted(
        (
            *(box.expanded(clearance_um + half_stroke) for box in keepouts),
            *(_foreign_box(wire, clearance_um + 2 * half_stroke)
              for wire in existing_wires),
        ),
        key=lambda box: (box.min_x, box.min_y, box.max_x, box.max_y),
    ))
    if any(box.includes(start) or box.includes(end) for box in hazards):
        return _fail("ROUTE_PORT_BLOCKED", "Contact intersects a forbidden area")
    window = bounds if bounds is not None else _window(start, end, hazards, grid_um)
    if not window.includes(start) or not window.includes(end):
        return _fail("ROUTE_WINDOW_INVALID", "Window does not contain both contacts")

    xmin = -(-window.min_x // grid_um)
    ymin = -(-window.min_y // grid_um)
    xmax = window.max_x // grid_um
    ymax = window.max_y // grid_um
    cells = (xmax - xmin + 1) * (ymax - ymin + 1)
    if cells <= 0:
        return _fail("ROUTE_WINDOW_INVALID", "No grid vertices within window")
    if cells > max_cells:
        return _fail("ROUTE_CELL_LIMIT", f"Grid needs {cells} cells (limit {max_cells})")

    source = (start.x // grid_um, start.y // grid_um, -1)
    target = (end.x // grid_um, end.y // grid_um)
    best = {source: (0, 0)}
    previous: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    queue = [(0, 0, source[1], source[0], -1)]
    while queue:
        length, bends, y, x, direction = heappop(queue)
        state = (x, y, direction)
        if best.get(state) != (length, bends):
            continue
        if (x, y) == target:
            nodes = [Point(x * grid_um, y * grid_um)]
            while state in previous:
                state = previous[state]
                nodes.append(Point(state[0] * grid_um, state[1] * grid_um))
            nodes.reverse()
            points = _turns(nodes)
            if points[0] != start or points[-1] != end:
                return _fail("ROUTE_INTERNAL_ERROR", "Route endpoints were modified")
            return TwoPinRoute(points, ())
        at = Point(x * grid_um, y * grid_um)
        for side, (dx, dy) in enumerate(_DIRECTIONS):
            nx, ny = x + dx, y + dy
            if not (xmin <= nx <= xmax and ymin <= ny <= ymax):
                continue
            candidate = Point(nx * grid_um, ny * grid_um)
            edge = Line(at, candidate)
            if any(segment_intersects_box(edge, box) for box in hazards):
                continue
            new_state = (nx, ny, side)
            cost = (length + 1, bends + (direction not in (-1, side)))
            if cost < best.get(new_state, (float("inf"), float("inf"))):
                best[new_state] = cost
                previous[new_state] = state
                heappush(queue, (cost[0], cost[1], ny, nx, side))
    return _fail("ROUTE_NO_PATH", "No free route exists inside bounded grid")
