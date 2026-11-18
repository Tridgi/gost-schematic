"""Regression gates: no floating pins, reversed lead stubs or clipped core strokes."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import (
    Box,
    Line,
    Point,
    Side,
    StyledLine,
    primitive_stroked_bounds,
)
from gost_schematic.engines.sheet_layout import (
    component_graphic_obstacles,
    layout_sheet,
)
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.symbol_checks import validate_symbol


def _resistor():
    root = files("gost_schematic").joinpath("catalog/symbols/resistors/fixed.json")
    return load_symbol(Path(str(root)))


@pytest.mark.parametrize(
    "path",
    [
        "catalog/symbols/resistors/fixed.json",
        "catalog/symbols/capacitors/fixed.json",
        "catalog/symbols/capacitors/polarized.json",
    ],
)
def test_base_catalog_graphic_pins_are_drawn_and_inward(path):
    symbol = load_symbol(Path(str(files("gost_schematic").joinpath(path))))
    codes = {issue.code for issue in validate_symbol(symbol)}
    assert "PIN_GRAPHIC_DISCONNECTED" not in codes
    assert "PIN_LEAD_NOT_INWARD" not in codes


def test_floating_graphic_connector_rejected_even_when_outside_body():
    symbol = _resistor()
    first = replace(symbol.pins[0], at=Point(-9000, 0))
    candidate = replace(symbol, pins=(first, *symbol.pins[1:]))
    codes = {issue.code for issue in validate_symbol(candidate)}
    assert "PIN_GRAPHIC_DISCONNECTED" in codes
    assert "PIN_NOT_EXPOSED" not in codes


@pytest.mark.parametrize("end", [Point(-9000, 0), Point(-8000, 1000)])
def test_outward_or_tangent_contact_stub_not_accepted(end):
    symbol = _resistor()
    bad_line = Line(symbol.pins[0].at, end)
    retained = tuple(
        item for item in symbol.graphics
        if not (
            isinstance(item, Line)
            and symbol.pins[0].at in (item.start, item.end)
        )
    )
    candidate = replace(symbol, graphics=(bad_line, *retained))
    codes = {issue.code for issue in validate_symbol(candidate)}
    assert "PIN_LEAD_NOT_INWARD" in codes


def _thick_core_symbol():
    return SymbolDefinition(
        identifier="test.thick",
        revision=1,
        body_keepout=Box(-1000, -1000, 1000, 1000),
        line_width_um=100,
        pins=(
            GraphicPin("1", Point(-4000, 0), Side.LEFT),
            GraphicPin("2", Point(4000, 0), Side.RIGHT),
        ),
        graphics=(
            Line(Point(-4000, 0), Point(-1000, 0)),
            Line(Point(1000, 0), Point(4000, 0)),
            StyledLine(Point(-500, -2500), Point(500, -2500), 1500),
        ),
    )


def test_stroked_bounds_protect_thick_core_without_changing_legacy_bounds():
    symbol = _thick_core_symbol()
    assert symbol.bounds.min_y == -2500
    assert symbol.stroked_bounds.min_y == -3250
    assert primitive_stroked_bounds(symbol.graphics[2], 100).min_y == -3250

    instance = ComponentInstance("L1", symbol.identifier)
    obstacles = component_graphic_obstacles(symbol, instance)
    assert obstacles[2].box.min_y == -3250
    assert obstacles[2].box.max_y >= -1750  # +1 µm from nondegenerate Line bbox

    svg = ET.fromstring(render_symbol_svg(symbol))
    viewbox = tuple(float(item) for item in svg.attrib["viewBox"].split())
    assert viewbox[1] == -6.25  # -3250 µm minus 3 mm preview margin


def test_two_symbols_with_unstroked_gap_are_flagged_when_ink_overlaps():
    symbol = _thick_core_symbol()
    first = ComponentInstance("L1", symbol.identifier, Point(0, 0))
    second = ComponentInstance("L2", symbol.identifier, Point(0, 3700))
    assert not symbol.bounds.overlaps(symbol.bounds.translated(second.origin))
    assert symbol.stroked_bounds.overlaps(
        symbol.stroked_bounds.translated(second.origin)
    )
    result = layout_sheet(
        Circuit((first, second), ()), {symbol.identifier: symbol},
        TextStyle("never-read.ttf", "Mock"),
        _UnusedMeasurer(),
    )
    assert "SYMBOL_GEOMETRY_OVERLAP" in {
        item.code for item in result.diagnostics
    }


class _UnusedMeasurer:
    def measure(self, text, style):
        raise AssertionError("No labels were requested in this fixture")


@pytest.mark.parametrize(
    "name", ["inductor.sliding_contact", "inductor.double_sliding"]
)
def test_slider_contact_stem_meets_arrow_tip_and_winding_apex(name):
    path = files("gost_schematic").joinpath(f"catalog/inductors/{name}.json")
    item = load_inductor(Path(str(path)))
    r = item.spec.radius_um
    first = -(item.spec.turns * 2 * r) // 2
    for index, turn in enumerate(item.spec.slider_turns):
        x = first + (2 * turn + 1) * r
        contact = item.symbol.pins[2 + len(item.spec.tap_turns) + index].at
        apex = Point(x, -r)
        assert Line(contact, apex) in item.symbol.graphics
        # The stem and the two arrow lines terminate at the SAME apex.
        assert sum(
            isinstance(g, Line) and (g.start == apex or g.end == apex)
            for g in item.symbol.graphics
        ) >= 3


@pytest.mark.parametrize(
    "name", ["inductor.air_core", "inductor.tapped", "inductor.double_sliding",
             "choke.ferrite"],
)
def test_parametric_coils_pass_connection_integrity_gate(name):
    path = files("gost_schematic").joinpath(f"catalog/inductors/{name}.json")
    symbol = load_inductor(Path(str(path))).symbol
    codes = {item.code for item in validate_symbol(symbol)}
    assert not {"PIN_GRAPHIC_DISCONNECTED", "PIN_LEAD_NOT_INWARD"} & codes
