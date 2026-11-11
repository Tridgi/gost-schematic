"""Independent post-layout checks for labels after later route or symbol changes."""

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box
from gost_schematic.model.obstacles import (
    BoxObstacle,
    WireObstacle,
    wire_intersects_box,
)
from gost_schematic.model.annotations import AnnotationPlacement


def _regions(label: AnnotationPlacement) -> tuple[Box, ...]:
    if label.reservation_bounds is None:
        return (label.collision_bounds,)
    return (label.collision_bounds, label.reservation_bounds)


def validate_annotation_scene(
    labels: tuple[AnnotationPlacement, ...],
    boxes: tuple[BoxObstacle, ...] = (),
    wires: tuple[WireObstacle, ...] = (),
) -> tuple[Diagnostic, ...]:
    """Check every label against symbols, pin escapes, other labels and wires."""
    issues: list[Diagnostic] = []
    for index, label in enumerate(labels):
        subject = f"{label.owner}.{label.key}"
        for obstacle in boxes:
            if any(region.overlaps(obstacle.box) for region in _regions(label)):
                issues.append(Diagnostic(
                    "ANNOTATION_OBSTACLE_OVERLAP", Severity.ERROR,
                    f"{subject} overlaps {obstacle.kind}:{obstacle.identifier}", subject,
                ))
        for wire in wires:
            if any(wire_intersects_box(wire, region) for region in _regions(label)):
                issues.append(Diagnostic(
                    "ANNOTATION_WIRE_OVERLAP", Severity.ERROR,
                    f"{subject} overlaps wire:{wire.identifier}", subject,
                ))
        for other in labels[index + 1:]:
            if any(a.overlaps(b) for a in _regions(label) for b in _regions(other)):
                issues.append(Diagnostic(
                    "ANNOTATION_TEXT_OVERLAP", Severity.ERROR,
                    f"{subject} overlaps annotation:{other.owner}.{other.key}",
                    subject,
                ))
    return tuple(issues)


def annotation_obstacles(
    labels: tuple[AnnotationPlacement, ...],
) -> tuple[BoxObstacle, ...]:
    """Stable router-facing obstacles; text cannot be crossed by later wires."""
    result: list[BoxObstacle] = []
    for item in labels:
        stem = f"{item.owner}.{item.key}"
        result.append(BoxObstacle(
            stem, item.collision_bounds, "annotation", item.owner,
        ))
        if item.reservation_bounds is not None:
            result.append(BoxObstacle(
                f"{stem}.reserved", item.reservation_bounds,
                "annotation_reserved", item.owner,
            ))
    return tuple(result)
