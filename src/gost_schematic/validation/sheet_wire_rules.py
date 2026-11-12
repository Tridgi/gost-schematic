"""Narrow, auditable ESKD check for external drawn conductor strokes.

No autorouting or netlist extraction. Diagonal wires are warnings because
GOST 2.701-2008 §5.5.2 permits limited exceptional diagonal segments.
The 3 mm clearance is checked analytically for parallel, overlapping
orthogonal spans only, at the printed stroke edges (never centerlines).
"""

from collections.abc import Iterable

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Line
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.validation.dimensional_checks import load_requirements


def _orientation(line: Line) -> str:
    if line.start.y == line.end.y:
        return "horizontal"
    if line.start.x == line.end.x:
        return "vertical"
    return "diagonal"


def _project(line: Line, orientation: str) -> tuple[int, int]:
    coords = (line.start.x, line.end.x) if orientation == "horizontal" else (
        line.start.y, line.end.y
    )
    return min(coords), max(coords)


def validate_sheet_wire_rules(
    wires: Iterable[WireObstacle], *,
    requirements: dict[str, object] | None = None,
) -> tuple[Diagnostic, ...]:
    """Validate source-backed width and strict parallel clearance constraints.

    Does not check symbol gaps, dot/junction usage, precise diagonal
    distances, or full netlist identity. Coincident collinear fragments
    require explicit matching net names and are only warned as redundant.
    """
    rules = (requirements if requirements is not None else load_requirements())["layout_rules"]
    wires = tuple(wires)
    issues: list[Diagnostic] = []

    for wire in wires:
        if not (rules["connection_stroke_min_um"]
                <= wire.stroke_um <= rules["connection_stroke_max_um"]):
            issues.append(Diagnostic(
                "ESKD_WIRE_WIDTH_OUT_OF_RANGE", Severity.ERROR,
                f"{wire.identifier}: stroke must be 0.2–1.0 mm (ГОСТ 2.701-2008 §5.5.1)",
                wire.identifier,
            ))
        if _orientation(wire.line) == "diagonal":
            issues.append(Diagnostic(
                "ESKD_WIRE_DIAGONAL_REVIEW", Severity.WARNING,
                f"{wire.identifier}: diagonal requires justification under §5.5.2",
                wire.identifier,
            ))

    for index, left in enumerate(wires):
        direction = _orientation(left.line)
        if direction == "diagonal":
            continue
        for right in wires[index + 1:]:
            if _orientation(right.line) != direction:
                continue
            first, last = _project(left.line, direction)
            other_first, other_last = _project(right.line, direction)
            if min(last, other_last) <= max(first, other_first):
                # Parallel segments do not overlap along their running axis.
                continue
            axis_a = left.line.start.y if direction == "horizontal" else left.line.start.x
            axis_b = right.line.start.y if direction == "horizontal" else right.line.start.x
            if axis_a == axis_b:
                # Two authored fragments on the same centerline make ONE
                # printed wire when explicitly assigned to the same net.
                # This must not be mistaken for two adjacent parallel wires.
                if (
                    left.net_name is not None
                    and left.net_name == right.net_name
                ):
                    issues.append(Diagnostic(
                        "ESKD_COLLINEAR_WIRE_REDUNDANT", Severity.WARNING,
                        f"{left.identifier} and {right.identifier}: overlapping "
                        "fragments of the same net should be normalized into one route",
                        left.identifier,
                    ))
                else:
                    issues.append(Diagnostic(
                        "ESKD_COLLINEAR_WIRE_AMBIGUOUS", Severity.ERROR,
                        f"{left.identifier} and {right.identifier}: coincident "
                        "strokes with different or unknown net ownership",
                        left.identifier,
                    ))
                continue
            # 2 × centerline gap < 2 × required clear gap + widths.
            # Equality is compliant; integer arithmetic avoids rounding.
            if 2 * abs(axis_a - axis_b) < (
                2 * rules["min_clearance_parallel_connection_lines_um"]
                + left.stroke_um + right.stroke_um
            ):
                issues.append(Diagnostic(
                    "ESKD_PARALLEL_WIRE_CLEARANCE", Severity.ERROR,
                    f"{left.identifier} and {right.identifier}: printed parallel "
                    "line-edge clearance must be at least 3 mm "
                    "(ГОСТ 2.701-2008 §5.3.4)",
                    left.identifier,
                ))
    return tuple(issues)
