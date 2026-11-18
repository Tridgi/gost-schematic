"""Draft capacitor geometry, pins and annotation constraints."""

from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
)
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.validation.symbol_checks import validate_symbol


def _symbol(kind):
    path = files("gost_schematic").joinpath(f"catalog/symbols/capacitors/{kind}.json")
    return load_symbol(Path(str(path)))


class Font:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


@pytest.mark.parametrize("kind", ["fixed", "polarized"])
def test_capacitor_is_a_separate_draft_symbol(kind):
    symbol = _symbol(kind)
    assert symbol.identifier == f"capacitor.{kind}"
    assert [pin.number for pin in symbol.pins] == ["1", "2"]
    assert [pin.side for pin in symbol.pins] == [Side.LEFT, Side.RIGHT]
    assert all(isinstance(shape, Line) for shape in symbol.graphics)
    assert not any(issue.severity.value == "error" for issue in validate_symbol(symbol))
    assert [slot.key for slot in symbol.annotation_slots] == ["refdes", "value"]


@pytest.mark.parametrize("kind", ["fixed", "polarized"])
def test_plate_dimensions_are_8mm_and_gap_is_1_5mm(kind):
    symbol = _symbol(kind)
    plates = [
        item for item in symbol.graphics
        if item.start.x == item.end.x
        and abs(item.start.y - item.end.y) == 8000
    ]
    assert len(plates) == 2
    assert {item.start.x for item in plates} == {-750, 750}
    assert abs(plates[0].start.x - plates[1].start.x) == 1500


def test_polylines_never_connect_capacitor_plates():
    for kind in ("fixed", "polarized"):
        symbol = _symbol(kind)
        assert not any(
            item.start.x < 0 < item.end.x
            and item.start.y == item.end.y == 0
            for item in symbol.graphics
        )


def test_polarized_cap_has_positive_marker_on_first_pin_side():
    symbol = _symbol("polarized")
    assert symbol.pins[0].label == "+"
    assert symbol.pins[1].label == "-"
    marker = [
        item for item in symbol.graphics
        if item.start.y == item.end.y == -4000
        and item.start.x >= -4000 and item.end.x < -2000
    ]
    assert marker
    assert symbol.body_keepout.includes(Point(-3000, -4000))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_pin_identity_remains_stable(rotation):
    symbol = _symbol("polarized")
    part = ComponentInstance("C4", "capacitor", Point(20000, 12000),
                             Transform(rotation))
    ports = pin_corridors_for_component(symbol, part)
    assert [port.pin for port in ports] == [PinRef("C4", "1"), PinRef("C4", "2")]
    assert ports[0].side == part.transform.side(Side.LEFT)
    assert ports[1].side == part.transform.side(Side.RIGHT)


@pytest.mark.parametrize("kind", ["fixed", "polarized"])
def test_capacitor_nominals_generate_correct_eskd_and_full_labels(kind):
    symbol = _symbol(kind)
    c = ComponentInstance(
        "C1", "capacitor", nominal=Quantity.from_unit("100", Unit.NANOFARAD)
    )
    style = TextStyle("/fake/type-a.ttf", "OpenGost Type A", 3500, 500)
    compact = bind_component_annotations(symbol, c, style)
    full = bind_component_annotations(
        symbol, c, style,
        NominalDisplayConfiguration(NominalDisplaySettings(
            mode=NominalDisplayMode.FULL_UNITS,
        )),
    )
    assert [x.text for x in compact.requests] == ["C1", "0,1мк"]
    assert [x.text for x in full.requests] == ["C1", "100 нФ"]
    placed = place_annotations(
        compact.requests, Font(), boxes=obstacles_for_component(symbol, c)
    )
    assert placed.valid


def test_capacitor_hitbox_is_separate_from_protected_leads():
    symbol = _symbol("fixed")
    c = ComponentInstance("C1", "capacitor")
    obstacles = obstacles_for_component(symbol, c)
    assert obstacles[0].kind == "symbol"
    assert [o.kind for o in obstacles[1:]] == ["pin_escape", "pin_escape"]
    assert not obstacles[1].box.overlaps(symbol.body_keepout)


def test_capacitor_instances_have_distinct_layouts_from_resistor(resistor):
    cap = _symbol("fixed")
    assert cap.identifier != resistor.identifier
    assert cap.body_keepout != resistor.body_keepout
    instances = Circuit((
        ComponentInstance("R1", "resistor"),
        ComponentInstance("C1", "capacitor", Point(30000, 0)),
    ), ())
    assert len(instances.components) == 2
