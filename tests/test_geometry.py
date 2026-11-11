from dataclasses import FrozenInstanceError

import pytest

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform


def test_box_overlap_and_touching_boundary():
    a = Box(0, 0, 100, 100)
    assert a.overlaps(Box(99, 0, 200, 100))
    assert not a.overlaps(Box(100, 0, 200, 100))
    assert a.expanded(1) == Box(-1, -1, 101, 101)


def test_orthogonal_transforms_and_direction():
    point = Point(2, 3)
    assert Transform(rotation=90).apply(point) == Point(-3, 2)
    assert Transform(rotation=180).apply(point) == Point(-2, -3)
    assert Transform(rotation=270).apply(point) == Point(3, -2)
    assert Transform(mirror_x=True).apply(point) == Point(-2, 3)
    assert Transform(rotation=90).side(Side.LEFT) == Side.TOP
    assert Transform(rotation=90, mirror_x=True).side(Side.LEFT) == Side.BOTTOM
    assert Transform(rotation=90).box(Box(-2, -1, 2, 1)) == Box(-1, -2, 1, 2)


def test_invalid_transform_or_mutation_is_rejected():
    with pytest.raises(ValueError):
        Transform(rotation=45)
    with pytest.raises(FrozenInstanceError):
        point = Point(1, 2)
        point.x = 7


def test_boolean_and_degenerate_geometry_rejected():
    with pytest.raises(TypeError):
        Point(True, 1)
    with pytest.raises(ValueError):
        Box(0, 0, 0, 10)
