"""Post-routing checks and router-obstacle export."""

from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.engines.annotation.collision import BoxObstacle, WireObstacle
from gost_schematic.engines.annotation.layout import place_annotations
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRequest,
    AnnotationRole,
    AnnotationSlot,
    MeasuredText,
    TextStyle,
)
from gost_schematic.validation.annotation_checks import (
    annotation_obstacles,
    validate_annotation_scene,
)


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1000, 2500, 1), 2500)


def _label(owner, x):
    slot = AnnotationSlot(f"slot-{owner}", AnnotationRole.NOTE, (Anchor(Point(x, 0)),))
    return AnnotationRequest(owner, slot, "LABEL", TextStyle("mock.ttf", "Mock", 2000, 250))


def test_router_receives_annotation_hitbox_obstacles():
    layout = place_annotations((_label("R1", 0),), Metrics())
    assert layout.valid
    obstacles = annotation_obstacles(layout.placements)
    assert len(obstacles) == 1
    assert obstacles[0].kind == "annotation"
    assert obstacles[0].box == layout.placements[0].collision_bounds


def test_post_routing_catches_wire_inserted_after_layout():
    layout = place_annotations((_label("R1", 0),), Metrics())
    route = WireObstacle("GND", Line(Point(-2000, -500), Point(2000, -500)))
    diagnostics = validate_annotation_scene(layout.placements, wires=(route,))
    assert [item.code for item in diagnostics] == ["ANNOTATION_WIRE_OVERLAP"]


def test_post_routing_catches_symbol_and_pin_escape_invasion():
    layout = place_annotations((_label("R1", 0),), Metrics())
    obstacle = BoxObstacle("DA1.1", Box(-1000, -3000, 1000, 1000), "pin_escape")
    issues = validate_annotation_scene(layout.placements, boxes=(obstacle,))
    assert [item.code for item in issues] == ["ANNOTATION_OBSTACLE_OVERLAP"]
    assert "pin_escape" in issues[0].message


def test_post_routing_detects_text_text_overlap():
    one = place_annotations((_label("R1", 0),), Metrics()).placements[0]
    two = place_annotations((_label("R2", 0),), Metrics()).placements[0]
    issues = validate_annotation_scene((one, two))
    assert [item.code for item in issues] == ["ANNOTATION_TEXT_OVERLAP"]


def test_distant_labels_have_no_overlap():
    layout = place_annotations((_label("R1", 0), _label("R2", 10000)), Metrics())
    assert layout.valid
    assert validate_annotation_scene(layout.placements) == ()
