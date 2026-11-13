"""Pure QA scoring reference for layout Issue #44 (not normative or production).

Hard electrical/net/clearance/label checks must pass before comparing scores.
Paths are ordered terminal-to-terminal polylines in exact integer micrometres.
"""
from dataclasses import dataclass
from itertools import pairwise

from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box


@dataclass(frozen=True, slots=True)
class QAMetrics:
    wire_length_um: int
    manhattan_lower_bound_um: int
    extra_length_um: int
    backtrack_um: int
    bends: int
    direction_reversals: int
    sub_8mm_legs: int


def score_path(points: tuple[Point, ...]) -> QAMetrics:
    if len(points) < 2:
        raise ValueError("At least two terminals required")
    total = 0
    bends = 0
    last_axis = None
    signs: dict[str, list[int]] = {"x": [], "y": []}
    stubs = 0
    for first, second in pairwise(points):
        x, y = second.x - first.x, second.y - first.y
        if (x == 0) == (y == 0):
            raise ValueError("Nondegenerate orthogonal conductors only")
        axis = "x" if x else "y"
        step = x if x else y
        total += abs(step)
        stubs += abs(step) < 8000
        if last_axis and last_axis != axis:
            bends += 1
        last_axis = axis
        signs[axis].append(1 if step > 0 else -1)
    lower = (
        abs(points[-1].x - points[0].x)
        + abs(points[-1].y - points[0].y)
    )
    excess = total - lower
    if excess < 0 or excess % 2:
        raise AssertionError("Incorrect Manhattan lower bound")
    reversals = sum(
        before != after
        for seq in signs.values() for before, after in pairwise(seq)
    )
    return QAMetrics(total, lower, excess, excess // 2, bends, reversals, stubs)


def count_x_crossings(
    path: tuple[Point, ...], foreign: tuple[Line, ...],
) -> int:
    """Count visual proper X crosses; not inferred electrical junctions."""
    result = 0
    for a, b in pairwise(path):
        own = Line(a, b)
        for other in foreign:
            x_vertical = own.start.x == own.end.x
            y_vertical = other.start.x == other.end.x
            if x_vertical == y_vertical:
                continue
            vertical = own if x_vertical else other
            horizontal = other if x_vertical else own
            at_x = vertical.start.x
            at_y = horizontal.start.y
            if (
                min(horizontal.start.x, horizontal.end.x)
                < at_x < max(horizontal.start.x, horizontal.end.x)
                and min(vertical.start.y, vertical.end.y)
                < at_y < max(vertical.start.y, vertical.end.y)
            ):
                result += 1
    return result


def count_visual_box_collisions(
    path: tuple[Point, ...],
    boxes: tuple[Box, ...],
    *,
    ink_half_width_um: int = 150,
) -> int:
    """Test bodies / annotation reservations by printed conductor geometry."""
    if ink_half_width_um < 0:
        raise ValueError("ink_half_width_um must be nonnegative")
    return sum(
        segment_intersects_box(Line(a, b), box.expanded(ink_half_width_um))
        for a, b in pairwise(path) for box in boxes
    )
