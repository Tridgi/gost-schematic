"""End-to-end SVG line geometry for all eight transforms of both DRAFT diodes.

Pin positions alone are not sufficient: the rendered body, cathode bar and
Zener bends must transform with the two distinct physical terminals.
"""

from xml.etree import ElementTree as ET

import pytest

from examples.review_diodes_cycle4 import _entry
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("identifier", ("diode.general", "diode.zener"))
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_rendered_diode_strokes_and_A_K_markers_match_all_transforms(
    identifier, rotation, mirror,
):
    symbol, part = _entry(identifier)
    transform = Transform(rotation=rotation, mirror_x=mirror)
    instance = ComponentInstance(
        "VD17", part.identifier, Point(31000, 27000), transform,
    )
    circuit = Circuit((instance,), ())
    layout = SheetLayout((), ())
    svg = render_sheet_svg(
        circuit, {part.identifier: symbol}, layout, review_overlay=True,
    )
    root = ET.fromstring(svg)

    groups = root.findall(f".//{SVG}g[@data-layer='symbols']")
    assert len(groups) == 1
    assert groups[0].get("data-reference") == "VD17"
    rendered = groups[0].findall(f"{SVG}line")
    assert len(rendered) == (6 if identifier == "diode.general" else 8)

    # Check source-stroke order and exact physical-mm endpoints, not only
    # transformed pin positions or presence of an arbitrary SVG line.
    for ink, line in zip(rendered, symbol.graphics, strict=True):
        start = transform.apply(line.start) + instance.origin
        end = transform.apply(line.end) + instance.origin
        assert (
            ink.get("x1"), ink.get("y1"), ink.get("x2"), ink.get("y2"),
        ) == (
            format_mm(start.x), format_mm(start.y),
            format_mm(end.x), format_mm(end.y),
        )

    markers = root.findall(f".//{SVG}g[@data-layer='geometry-review']/{SVG}circle")
    assert len(markers) == 2
    real_pins = instance.pin_positions(symbol)
    assert set(real_pins) == {"1", "2"}
    assert real_pins["1"] != real_pins["2"]
    assert [
        (circle.get("cx"), circle.get("cy")) for circle in markers
    ] == [
        (format_mm(real_pins[number].x), format_mm(real_pins[number].y))
        for number in ("1", "2")
    ]

    # Graphic triangle/bar contact is not a new netlist short; no bitmap
    # substitute or fabricated electrical pin is permitted.
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",))
    assert not root.findall(f".//{SVG}image")
    assert svg == render_sheet_svg(
        circuit, {part.identifier: symbol}, layout, review_overlay=True,
    )
