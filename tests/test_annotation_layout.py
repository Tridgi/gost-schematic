"""Regression tests for text hitboxes, collision handling and preferred anchors."""

from dataclasses import replace

import pytest

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.collision import (
    BoxObstacle,
    WireObstacle,
    segment_intersects_box,
    wire_intersects_box,
)
from gost_schematic.engines.annotation.layout import (
    obstacles_for_component,
    place_annotations,
    requests_for_component,
)
from gost_schematic.model.annotations import (
    Anchor,
    AnnotationRequest,
    AnnotationRole,
    AnnotationSlot,
    HorizontalAlign,
    MeasuredText,
    TextStyle,
    VerticalAlign,
)
from gost_schematic.model.circuit import ComponentInstance


class DeterministicMetrics:
    """Stable synthetic glyph model for layout unit tests; no fonts required."""

    def measure(self, text, style):
        width = len(text) * style.em_height_um // 3
        return MeasuredText(Box(0, -style.em_height_um, width, 1), width)


@pytest.fixture
def style():
    return TextStyle("does-not-need-to-exist-in-unit-tests.ttf", "Test Face", 2000, 250)


def test_catalog_loads_reference_and_value_slots(resistor):
    assert [item.key for item in resistor.annotation_slots] == ["refdes", "value"]
    assert resistor.annotation_slots[0].required
    assert len(resistor.annotation_slots[0].candidates) == 2


def test_instance_reference_and_value_are_separate_from_symbol(resistor, style):
    instance = ComponentInstance("R1234", "generic.resistor")
    requests = requests_for_component(resistor, instance, style, {"value": "100 кОм"})
    assert [item.text for item in requests] == ["R1234", "100 кОм"]
    obstacles = obstacles_for_component(resistor, instance)
    result = place_annotations(requests, DeterministicMetrics(), boxes=obstacles)
    assert result.valid
    assert len(result.placements) == 2
    refdes = result.placements[0]
    assert refdes.ink_bounds.max_x - refdes.ink_bounds.min_x > 3000
    assert refdes.collision_bounds.min_y < refdes.ink_bounds.min_y
    assert result.placements[1].collision_bounds.min_y > 2000


def test_longer_text_recalculates_ink_and_collision(resistor, style):
    instance = ComponentInstance("R1", "generic.resistor")
    obstacles = obstacles_for_component(resistor, instance)
    def measure(value):
        request = requests_for_component(resistor, instance, style, {"value": value})[1]
        result = place_annotations((request,), DeterministicMetrics(), boxes=obstacles)
        assert result.valid
        return result.placements[0].collision_bounds

    short = measure("1 Ом")
    long = measure("100000 кОм")
    assert long.max_x - long.min_x > short.max_x - short.min_x


def test_alternate_position_is_used_if_first_is_blocked(resistor, style):
    instance = ComponentInstance("R1", "resistor")
    req = requests_for_component(resistor, instance, style)[0]
    blocked_above = BoxObstacle("nearby", Box(-10000, -9000, 10000, -3000))
    result = place_annotations(
        (req,), DeterministicMetrics(),
        boxes=obstacles_for_component(resistor, instance) + (blocked_above,),
    )
    assert result.valid
    assert result.placements[0].candidate_index == 1


def test_locked_label_must_not_move_silently(resistor, style):
    instance = ComponentInstance("R1", "resistor")
    request = replace(requests_for_component(resistor, instance, style)[0], locked=True)
    block = BoxObstacle("nearby", Box(-10000, -9000, 10000, -3000))
    result = place_annotations(
        (request,), DeterministicMetrics(),
        boxes=obstacles_for_component(resistor, instance) + (block,),
    )
    assert not result.valid
    assert result.diagnostics[0].code == "ANNOTATION_UNPLACEABLE"


def test_text_text_collision_reports_error(style):
    slot = AnnotationSlot(
        "x", AnnotationRole.NOTE,
        (Anchor(Point(0, 0), HorizontalAlign.CENTER, VerticalAlign.BOTTOM),),
    )
    requests = (
        AnnotationRequest("A", slot, "FIRST", style),
        AnnotationRequest("B", slot, "SECOND", style),
    )
    result = place_annotations(requests, DeterministicMetrics())
    assert len(result.placements) == 1
    assert result.diagnostics[0].code == "ANNOTATION_UNPLACEABLE"
    assert "annotation:A.x" in result.diagnostics[0].message


def test_text_symbol_collision_reports_error(style):
    slot = AnnotationSlot(
        "x", AnnotationRole.NOTE,
        (Anchor(Point(0, 0)),),
    )
    request = AnnotationRequest("A", slot, "TEXT", style)
    result = place_annotations(
        (request,), DeterministicMetrics(),
        boxes=(BoxObstacle("B.body", Box(-5000, -5000, 5000, 5000)),),
    )
    assert not result.valid
    assert "symbol:B.body" in result.diagnostics[0].message


def test_text_wire_collision_uses_actual_segment(style):
    slot = AnnotationSlot("x", AnnotationRole.NOTE, (Anchor(Point(0, 0)),))
    request = AnnotationRequest("A", slot, "TEXT", style)
    crossing = WireObstacle("N1", Line(Point(-5000, -1000), Point(5000, -1000)), 300)
    result = place_annotations((request,), DeterministicMetrics(), wires=(crossing,))
    assert not result.valid
    assert "wire:N1" in result.diagnostics[0].message


def test_wire_segment_box_exact_for_diagonal_and_outside():
    box = Box(0, 0, 100, 100)
    assert segment_intersects_box(Line(Point(-10, -10), Point(110, 110)), box)
    assert not segment_intersects_box(Line(Point(-10, 110), Point(110, 230)), box)
    assert wire_intersects_box(
        WireObstacle("edge", Line(Point(-10, -10), Point(110, 110))), box,
    )


def test_reserved_region_is_independent_collision_region(style):
    slot = AnnotationSlot(
        "x", AnnotationRole.NOTE,
        (Anchor(Point(0, -6000)),),
        reserved_region=Box(-5000, 3000, 5000, 5000),
    )
    request = AnnotationRequest("A", slot, "TEXT", style)
    obstruction = BoxObstacle("reserved-block", Box(0, 3500, 1000, 4500))
    result = place_annotations((request,), DeterministicMetrics(), boxes=(obstruction,))
    assert not result.valid


def test_rotation_mirror_moves_anchor_but_not_orientation(resistor, style):
    instance = ComponentInstance("R1", "resistor", Point(50000, 7000),
                                 Transform(90, True))
    request = requests_for_component(resistor, instance, style)[0]
    layout = place_annotations(
        (request,), DeterministicMetrics(),
        boxes=obstacles_for_component(resistor, instance),
    )
    assert layout.valid
    assert layout.placements[0].baseline.x > 50000
    assert layout.placements[0].ink_bounds.min_x > 50000


def test_duplicate_owner_key_fails_instead_of_rendering_twice(resistor, style):
    instance = ComponentInstance("R1", "resistor")
    request = requests_for_component(resistor, instance, style)[0]
    result = place_annotations((request, request), DeterministicMetrics())
    assert "DUPLICATE_ANNOTATION" in {item.code for item in result.diagnostics}


def test_missing_required_annotation_reports_error(resistor, style):
    instance = ComponentInstance("R1", "resistor")
    required_slot = replace(resistor.annotation_slots[0], key="custom_required")
    symbol = replace(resistor, annotation_slots=(required_slot,))
    with pytest.raises(ValueError, match="Missing mandatory"):
        requests_for_component(symbol, instance, style)
