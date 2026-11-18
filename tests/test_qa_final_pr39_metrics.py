"""Issue #44: exact measurement of C3 dogleg and crossings (QA only)."""

import pytest

from gost_schematic.core.geometry import Box, Line, Point
from scripts.qa_final_pr39_metrics import (
    count_visual_box_collisions,
    count_x_crossings,
    score_path,
)


def _route(*coords):
    return tuple(Point(x * 1000, y * 1000) for x, y in coords)


def test_c3_equal_wire_length_but_reduces_bends_reversals_and_backtrack():
    old_top = score_path(_route(
        (40, 40), (40, 80), (84, 80), (84, 75), (91, 75),
    ))
    old_right = score_path(_route(
        (120, 40), (120, 75), (109, 75),
    ))
    new_top = score_path(_route((40, 40), (40, 80), (91, 80)))
    new_right = score_path(_route((120, 40), (120, 80), (109, 80)))
    assert old_top.wire_length_um + old_right.wire_length_um == 142000
    assert new_top.wire_length_um + new_right.wire_length_um == 142000
    assert old_top.bends + old_right.bends == 4
    assert new_top.bends + new_right.bends == 2
    assert old_top.extra_length_um == 10000
    assert new_top.extra_length_um == 0
    assert old_top.backtrack_um == 5000
    assert new_top.backtrack_um == 0
    assert old_top.direction_reversals == 1
    assert new_top.direction_reversals == 0


def test_proper_non_junction_x_crossings_and_one_micrometre_near_miss():
    horizontal = _route((0, 0), (20, 0))
    crossing = (Line(Point(10000, -10000), Point(10000, 10000)),)
    near_miss = (Line(Point(20001, -10000), Point(20001, 10000)),)
    assert count_x_crossings(horizontal, crossing) == 1
    assert count_x_crossings(horizontal, near_miss) == 0
    # Intersection count is a SOFT visual metric; it is not an ERC short.
    assert count_x_crossings(
        horizontal, (Line(Point(0, -5000), Point(0, 5000)),),
    ) == 0


def test_annotation_and_ugo_ink_overlap_must_be_a_hard_gate_before_aesthetics():
    path = _route((0, 0), (20, 0))
    annotation = Box(9000, -200, 11000, 200)
    clear_box = Box(9000, 301, 11000, 800)
    assert count_visual_box_collisions(path, (annotation,)) == 1
    assert count_visual_box_collisions(path, (clear_box,)) == 0
    with pytest.raises(ValueError):
        count_visual_box_collisions(path, (), ink_half_width_um=-1)
    with pytest.raises(ValueError):
        score_path(_route((0, 0), (1, 1)))
    with pytest.raises(ValueError):
        score_path((Point(0, 0),))
