"""Catalog-owned Cu-note fallback for expanded, rotated DRAFT galleries.

This regression tests an *annotation* candidate, not altered winding ink,
physical terminals, or a normative ГОСТ dimension.
"""

from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.layout import place_annotations
from gost_schematic.model.annotations import (
    AnnotationRequest,
    MeasuredText,
    TextStyle,
)
from gost_schematic.model.obstacles import BoxObstacle


class _MeasuredCu:
    def measure(self, text, style):
        assert text == "Cu"
        return MeasuredText(Box(0, -500, 2000, 500), 2000)


def test_rotated_copper_note_uses_safe_third_candidate_when_first_two_blocked():
    path = files("gost_schematic").joinpath(
        "catalog/inductors/inductor.trim_copper.json",
    )
    variant = load_inductor(Path(str(path)))
    symbol = variant.symbol
    note = next(slot for slot in symbol.annotation_slots
                if slot.key == "core_material")

    # Preserve both old candidates, adding only an editorial fallback.
    assert [anchor.at for anchor in note.candidates] == [
        Point(12000, -3600),
        Point(12000, -7600),
        Point(18000, -3600),
    ]
    assert symbol.constant_annotations == (("core_material", "Cu"),)

    request = AnnotationRequest(
        "L13", note, "Cu", TextStyle("test.ttf", "Test", 3500, 500),
        Point(0, 0), Transform(rotation=180),
    )
    # In 180° view the first two candidates are inside the constrained
    # nominal-label area, but the distant third anchor remains readable.
    obstacle = BoxObstacle(
        "nominal.hitbox", Box(-14000, 0, -9000, 10000),
        "annotation", "L13",
    )
    result = place_annotations((request,), _MeasuredCu(), (obstacle,))
    assert result.valid, result.diagnostics
    assert len(result.placements) == 1
    assert result.placements[0].candidate_index == 2
    assert result.placements[0].text == "Cu"
