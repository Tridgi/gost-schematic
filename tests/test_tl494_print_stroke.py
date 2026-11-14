"""Measured finite segment and circle stroke clearances, Issue #108."""
import pytest

from scripts.review_tl494_print_readability import (
    _circle_circle_gap,
    _parallel,
    _segment_circle_gap,
    _segment_gap,
)


def test_parallel_wire_stroke_boundary_299_300_mm():
    first = ((0.0, 0.0), (20.0, 0.0), 0.3)
    pass_300 = ((1.0, 3.30), (19.0, 3.30), 0.3)
    fail_299 = ((1.0, 3.29), (19.0, 3.29), 0.3)
    assert _parallel(first, pass_300)
    assert _segment_gap(first, pass_300) == pytest.approx(3.0)
    assert _segment_gap(first, fail_299) == pytest.approx(2.99)
    assert _segment_gap(first, pass_300) >= 3.0 - 1e-8
    assert _segment_gap(first, fail_299) < 3.0


def test_true_stroke_width_changes_ugo_to_wire_proximity():
    wire = ((0.0, 0.0), (10.0, 0.0), 0.3)
    plate = ((2.0, 1.2), (8.0, 1.2), 0.3)
    assert _segment_gap(wire, plate) == pytest.approx(0.9)
    fat = ((2.0, 1.2), (8.0, 1.2), 0.4)
    assert _segment_gap(wire, fat) == pytest.approx(0.85)


def test_mosfet_internal_dot_true_circle_stroke_geometry():
    wire = ((0.0, 0.0), (10.0, 0.0), 0.3)
    dot = ((5.0, 1.0), 0.25, 0.3)
    assert _segment_circle_gap(wire, dot) == pytest.approx(0.45)
    touching = ((5.0, .25), .25, .3)
    assert _segment_circle_gap(wire, touching) < 0
    circle_b = ((5.0, 2.0), 0.25, .3)
    assert _circle_circle_gap(dot, circle_b) == pytest.approx(.2)


def test_perpendicular_ungrounded_cross_has_zero_stroke_gap_not_a_net():
    horizontal = ((0., 5.), (10., 5.), .3)
    vertical = ((5., 0.), (5., 10.), .3)
    assert not _parallel(horizontal, vertical)
    assert _segment_gap(horizontal, vertical) < 0
    # Geometry reports an ink crossing. It MUST NEVER infer circuit Net
    # equality or a physical junction without typed electrical authority.
