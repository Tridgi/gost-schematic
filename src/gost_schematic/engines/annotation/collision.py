"""Exact integer segment-box and axis-aligned collision checks."""

from dataclasses import dataclass

from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.model.circuit import PinRef


@dataclass(frozen=True, slots=True)
class BoxObstacle:
    identifier: str
    box: Box
    kind: str = "symbol"
    owner: str | None = None


@dataclass(frozen=True, slots=True)
class WireObstacle:
    identifier: str
    line: Line
    stroke_um: int = 300
    attached_pin: PinRef | None = None
    net_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.stroke_um) is not int or self.stroke_um < 0:
            raise ValueError("Wire stroke must be non-negative micrometres")
        if self.net_name is not None and not self.net_name:
            raise ValueError("A wire net name must be non-empty when supplied")


def _cross(a: Point, b: Point, c: Point) -> int:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        _cross(a, b, c) == 0
        and min(a.x, b.x) <= c.x <= max(a.x, b.x)
        and min(a.y, b.y) <= c.y <= max(a.y, b.y)
    )


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    x = _cross(a, b, c)
    y = _cross(a, b, d)
    z = _cross(c, d, a)
    w = _cross(c, d, b)
    if (x > 0 > y or y > 0 > x) and (z > 0 > w or w > 0 > z):
        return True
    return (
        (x == 0 and _on_segment(a, b, c))
        or (y == 0 and _on_segment(a, b, d))
        or (z == 0 and _on_segment(c, d, a))
        or (w == 0 and _on_segment(c, d, b))
    )


def segment_intersects_box(line: Line, box: Box) -> bool:
    """Closed-boundary intersection. Works for diagonal and orthogonal segments."""
    a, b = line.start, line.end
    if max(a.x, b.x) < box.min_x or min(a.x, b.x) > box.max_x:
        return False
    if max(a.y, b.y) < box.min_y or min(a.y, b.y) > box.max_y:
        return False
    if box.includes(a) or box.includes(b):
        return True
    tl = Point(box.min_x, box.min_y)
    tr = Point(box.max_x, box.min_y)
    br = Point(box.max_x, box.max_y)
    bl = Point(box.min_x, box.max_y)
    return any(
        _segments_intersect(a, b, start, end)
        for start, end in ((tl, tr), (tr, br), (br, bl), (bl, tl))
    )


def wire_intersects_box(wire: WireObstacle, box: Box) -> bool:
    # Expand by ceil(stroke / 2) to avoid missing odd-width stroke edges.
    return segment_intersects_box(wire.line, box.expanded((wire.stroke_um + 1) // 2))
