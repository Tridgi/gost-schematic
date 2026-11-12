"""Multi-component clean SVG contains no diagnostic hitbox geometry."""

from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.sheet_svg import render_sheet_svg


SVG = "{http://www.w3.org/2000/svg}"


class Font:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1800, len(text) * 500, 1), len(text) * 500)


def test_sheet_clean_and_review_svg_have_expected_separate_layers(resistor):
    circuit = Circuit((
        ComponentInstance(
            "R1", "resistor", Point(0, 0),
            nominal=Quantity.from_unit("2300", Unit.OHM),
        ),
        ComponentInstance(
            "R2", "resistor", Point(30000, 0),
            nominal=Quantity.from_unit("470", Unit.KOHM),
        ),
    ), ())
    symbols = {"resistor": resistor}
    result = layout_sheet(
        circuit, symbols, TextStyle("font.ttf", "Demo", 3500, 400), Font()
    )
    assert result.valid
    clean = ET.fromstring(render_sheet_svg(circuit, symbols, result))
    review = ET.fromstring(render_sheet_svg(
        circuit, symbols, result, review_overlay=True,
    ))
    clean_text = clean.findall(f".//{SVG}text")
    assert [item.text for item in clean_text] == ["R1", "2,3к", "R2", "470к"]
    assert len(clean.findall(f".//{SVG}g[@data-layer='symbols']")) == 2
    assert clean.find(f".//{SVG}g[@data-layer='geometry-review']") is None
    assert review.find(f".//{SVG}g[@data-layer='geometry-review']") is not None
    assert len(review.findall(f".//{SVG}rect")) > len(clean.findall(f".//{SVG}rect"))
    assert len(review.findall(f".//{SVG}rect[@data-kind='text-hitbox']")) == 4
    assert "viewBox" in clean.attrib
