"""QA-only reference metrics for Issue #44: route aesthetics, NOT a placer.

Measured lengths use exact integer micrometres. A safe netlist and clearance
validation are mandatory gates BEFORE any aesthetic score comparison.
"""

from dataclasses import dataclass

from gost_schematic.core.geometry import Point


@dataclass(frozen=True, slots=True)
class RouteQuality:
    length_um: int
    endpoint_manhattan_um: int
    detour_um: int
    backtrack_um: int
    bend_count: int
    axial_reversals: int
    short_legs: int
    redundant_vertices: int
    closed_loop: bool


def measure_route(points: tuple[Point, ...], *, short_leg_um: int = 8000) -> RouteQuality:
    """Evaluate one ordered simple terminal-to-terminal polyline.

    U-shaped doglegs are detected by signs changing on the same axis, even
    when an intervening orthogonal segment hides the direction reversal.
    Same-net branches must be evaluated as separate ordered paths.
    """
    if len(points) < 2 or any(not isinstance(p, Point) for p in points):
        raise ValueError("At least two typed route vertices are required")
    if type(short_leg_um) is not int or short_leg_um <= 0:
        raise ValueError("short_leg_um must be a positive integer")
    length = 0
    bends = 0
    short_count = 0
    redundant = 0
    previous_axis = None
    signs: dict[str, list[int]] = {"x": [], "y": []}
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b.x - a.x, b.y - a.y
        if (dx == 0) == (dy == 0):
            raise ValueError("Every route edge must be nonzero and orthogonal")
        axis = "x" if dx else "y"
        value = dx if dx else dy
        distance = abs(value)
        length += distance
        short_count += distance < short_leg_um
        if previous_axis == axis:
            redundant += 1
        elif previous_axis is not None:
            bends += 1
        previous_axis = axis
        signs[axis].append(1 if value > 0 else -1)
    direct = abs(points[-1].x - points[0].x) + abs(points[-1].y - points[0].y)
    detour = length - direct
    assert detour >= 0 and detour % 2 == 0
    reversals = sum(
        left != right
        for values in signs.values()
        for left, right in zip(values, values[1:], strict=False)
    )
    return RouteQuality(
        length_um=length,
        endpoint_manhattan_um=direct,
        detour_um=detour,
        backtrack_um=detour // 2,
        bend_count=bends,
        axial_reversals=reversals,
        short_legs=short_count,
        redundant_vertices=redundant,
        closed_loop=points[0] == points[-1],
    )


def illustration_cost_um(
    branches: tuple[RouteQuality, ...], *,
    moved_um: int = 0,
    bend_weight_um: int = 5000,
    detour_weight: int = 2,
    axial_reversal_weight_um: int = 5000,
    movement_weight: int = 1,
) -> int:
    """Example deterministic scalar score, not a ГОСТ/ESKD rule.

    All inputs must first pass electrical and collision hard constraints. The
    penalty values are illustrative until calibrated on reviewed examples.
    """
    params = (
        moved_um, bend_weight_um, detour_weight,
        axial_reversal_weight_um, movement_weight,
    )
    if any(type(value) is not int or value < 0 for value in params):
        raise ValueError("Quality weights and relocation must be nonnegative ints")
    return (
        sum(
            branch.length_um
            + bend_weight_um * branch.bend_count
            + detour_weight * branch.detour_um
            + axial_reversal_weight_um * branch.axial_reversals
            for branch in branches
        )
        + movement_weight * moved_um
    )
