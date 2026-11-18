"""Clean vs review SVG must not share diagnostic geometry."""

from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.layout import (
    obstacles_for_component,
    place_annotations,
    requests_for_component,
)
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.rendering.annotation_svg import render_annotation_svg


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1800, len(text) * 550, 1), len(text) * 550)


SVG = "{http://www.w3.org/2000/svg}"


def test_annotation_svg_renders_clean_text_and_debug_only_in_overlay(resistor):
    instance = ComponentInstance("R1", "generic")
    style = TextStyle("mock-font.ttf", "Mock Face", 2500, 400)
    requests = requests_for_component(resistor, instance, style, {"value": "10 k"})
    result = place_annotations(requests, Metrics(), boxes=obstacles_for_component(resistor, instance))
    assert result.valid
    clean = ET.fromstring(render_annotation_svg(resistor, instance, result.placements))
    review = ET.fromstring(render_annotation_svg(
        resistor, instance, result.placements, review_overlay=True,
    ))
    clean_labels = clean.findall(f".//{SVG}text")
    assert [label.text for label in clean_labels] == ["R1", "10 k"]
    assert clean.find(f".//{SVG}g[@data-layer='geometry-review']") is None
    assert review.find(f".//{SVG}g[@data-layer='geometry-review']") is not None
    assert len(review.findall(f".//{SVG}rect")) > len(clean.findall(f".//{SVG}rect"))
    assert all("transform" not in node.attrib for node in clean_labels)
