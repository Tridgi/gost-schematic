"""EXPERIMENTAL ROUTING: bounded deterministic orthogonal path geometry.

This low-level helper has no Circuit or complete pin list. Safe sheet-level
routing MUST use two_pin_sheet.route_circuit_two_pins instead. No implicit
junction, net inference or mutation of the shared model and graphics APIs.
"""

from dataclasses import dataclass
from heapq import heappop, heappush

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.obstacles import WireObstacle
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
        """Never create a partially calculated connection after failure."""
        if not self.ok:
            raise ValueError("No completed two-pin route")
        return ExternalWireGraph(tuple(
            WireSegment(a, b, net_name)
            for a, b in zip(self.points, self.points[1:], strict=False)
        ))


def _fail(code: str, message: str) -> TwoPinRoute:
    return TwoPinRoute((), (Diagnostic(code, Severity.ERROR, message, "two-pin"),))


def _foreign_box(wire: WireObstacle, margin_um: int) -> Box:
    """Conservative bounding rectangle around actual foreign centerline/ink.

    The wire's own half-stroke is included in margin_um by the caller.
    This is deliberately restrictive around diagonal lines and intersections.
    """
    a, b = wire.line.start, wire.line.end
    return Box(
        min(a.x, b.x), min(a.y, b.y),
        max(a.x, b.x) + 1, max(a.y, b.y) + 1,
    ).expanded(margin_um)


def _window(start: Point, end: Point, grid_um: int, pad_cells: int) -> Box:
    """Endpoint-local search region; remote hazards NEVER enlarge the grid."""
    margin = grid_um * pad_cells
    return Box(
        min(start.x, end.x) - margin, min(start.y, end.y) - margin,
        max(start.x, end.x) + margin, max(start.y, end.y) + margin,
    )


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


def _search(
    start: Point, end: Point, hazards: tuple[Box, ...],
    grid_um: int, window: Box, max_cells: int,
) -> TwoPinRoute:
    """Run the original four-way Dijkstra inside one bounded search window."""
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

    # Closed-boundary filtering. A distant hazard is harmless to this attempt.
    local_hazards = tuple(box for box in hazards if (
        box.max_x >= window.min_x and box.min_x <= window.max_x
        and box.max_y >= window.min_y and box.min_y <= window.max_y
    ))
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
            edge = Line(at, Point(nx * grid_um, ny * grid_um))
            if any(segment_intersects_box(edge, box) for box in local_hazards):
                continue
            new_state = (nx, ny, side)
            cost = (length + 1, bends + (direction not in (-1, side)))
            if cost < best.get(new_state, (float("inf"), float("inf"))):
                best[new_state] = cost
                previous[new_state] = state
                heappush(queue, (cost[0], cost[1], ny, nx, side))
    return _fail("ROUTE_NO_PATH", "No free route exists inside bounded grid")


def route_two_pins(
    start: Point,
    end: Point,
    *,
    keepouts: tuple[Box, ...] = (),
    existing_wires: tuple[WireSegment, ...] = (),
    foreign_wires: tuple[WireObstacle, ...] = (),
    grid_um: int = 1000,
    clearance_um: int = 400,
    stroke_um: int = 300,
    bounds: Box | None = None,
    max_cells: int = 50000,
) -> TwoPinRoute:
    """Route two on-grid points around explicitly supplied hazards.

    GEOMETRY-ONLY: this function has no complete catalog/pin membership and
    cannot guarantee safety against unprovided contacts. The typed sheet
    adapter must be used for physical-pin-safe circuit routing.

    The previous widthless `existing_wires` parameter remains accepted, but
    refuses nonempty inputs (ROUTE_FOREIGN_WIDTH_REQUIRED). Use the typed
    `foreign_wires` with explicit actual WireObstacle.stroke_um instead.
    Stroke-edge exclusion margin for foreign ink is
    clearance + ceil(new_stroke/2) + ceil(foreign_stroke/2).
    All rectangles are closed; even tangency is forbidden.

    Search is deterministic (fewest grid steps then bends, stable Y/X/side)
    with bounded endpoint-local adaptive windows (4, 8, 12, ... grid cells
    padded around the two contacts). Only retry after a NO_PATH result; the
    next window must satisfy max_cells. Explicit bounds keep one-shot behavior.
    A cell-limit failure means no permitted larger search, not a global proof.
    """
    if not isinstance(start, Point) or not isinstance(end, Point):
        return _fail("ROUTE_COORDINATE_INVALID", "Both contacts must be Points")
    if start == end:
        return _fail("ROUTE_COINCIDENT_PINS", "The two contacts coincide")
    if type(grid_um) is not int or grid_um <= 0:
        return _fail("ROUTE_GRID_INVALID", "Grid step must be positive integer µm")
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
            or any(not isinstance(item, WireSegment) for item in existing_wires)
            or not isinstance(foreign_wires, tuple)
            or any(not isinstance(item, WireObstacle) for item in foreign_wires)):
        return _fail("ROUTE_OBSTACLE_INVALID", "Invalid obstacle collection")
    if existing_wires:
        return _fail(
            "ROUTE_FOREIGN_WIDTH_REQUIRED",
            "WireSegment has no stroke width; supply typed foreign_wires instead",
        )
    if any(item.stroke_um <= 0 for item in foreign_wires):
        return _fail(
            "ROUTE_FOREIGN_WIDTH_REQUIRED", "Actual foreign stroke must be positive",
        )
    if bounds is not None and not isinstance(bounds, Box):
        return _fail("ROUTE_WINDOW_INVALID", "Bounds must be a Box or None")

    half_new = (stroke_um + 1) // 2
    hazards = tuple(sorted(
        (
            *(box.expanded(clearance_um + half_new) for box in keepouts),
            *(_foreign_box(
                wire, clearance_um + half_new + (wire.stroke_um + 1) // 2
            ) for wire in foreign_wires),
        ),
        key=lambda box: (box.min_x, box.min_y, box.max_x, box.max_y),
    ))
    if any(box.includes(start) or box.includes(end) for box in hazards):
        return _fail("ROUTE_PORT_BLOCKED", "Contact intersects a forbidden area")

    if bounds is not None:
        return _search(start, end, hazards, grid_um, bounds, max_cells)
    pad = 4
    while True:
        candidate = _search(
            start, end, hazards, grid_um, _window(start, end, grid_um, pad),
            max_cells,
        )
        if candidate.ok or candidate.diagnostics[0].code != "ROUTE_NO_PATH":
            return candidate
        pad += 4
