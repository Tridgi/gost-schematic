"""Regression: drawn connector stubs are hard annotation obstacles."""

from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.sheet_layout import (
    component_graphic_obstacles,
    layout_sheet,
)
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2400, len(text) * 680, 1), len(text) * 680)


def _cap():
    return load_symbol(Path(str(files("gost_schematic").joinpath(
        "catalog/symbols/capacitors/fixed.json"
    ))))


def _instance():
    return ComponentInstance(
        "C3", "capacitor", Point(30000, 28000),
        Transform(rotation=90),
        nominal=Quantity.from_unit("47", Unit.PICOFARAD),
    )


def test_vertical_capacitor_labels_cannot_cross_own_leads():
    cap = _cap()
    instance = _instance()
    strokes = component_graphic_obstacles(cap, instance)
    assert len(strokes) == len(cap.graphics)
    result = layout_sheet(
        Circuit((instance,), ()), {"capacitor": cap},
        TextStyle("mock.ttf", "Demo", 3500, 500), Metrics(),
    )
    assert result.valid
    assert [p.text for p in result.placements] == ["C3", "47"]
    assert all(p.candidate_index != 0 for p in result.placements)
    for label in result.placements:
        assert not any(label.collision_bounds.overlaps(o.box) for o in strokes)


def test_full_units_does_not_reintroduce_vertical_lead_collision():
    cap = _cap()
    instance = _instance()
    result = layout_sheet(
        Circuit((instance,), ()), {"capacitor": cap},
        TextStyle("mock.ttf", "Demo", 3500, 500), Metrics(),
        configuration=NominalDisplayConfiguration(
            NominalDisplaySettings(mode=NominalDisplayMode.FULL_UNITS)
        ),
    )
    assert result.valid
    assert result.placements[-1].text == "47 пФ"
    assert not any(
        label.collision_bounds.overlaps(obstacle.box)
        for label in result.placements
        for obstacle in component_graphic_obstacles(cap, instance)
    )


def test_global_graphic_strokes_block_foreign_component_label():
    cap = _cap()
    instance = _instance()
    blockers = component_graphic_obstacles(cap, instance)
    assert all(obstacle.kind == "graphic" for obstacle in blockers)
    assert all(obstacle.owner == "C3" for obstacle in blockers)
