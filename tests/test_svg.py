from xml.etree import ElementTree as ET

from gost_schematic.rendering.svg import render_symbol_svg

NAMESPACE = "{http://www.w3.org/2000/svg}"


def test_inspection_svg_has_primitives_and_metric_viewbox(resistor):
    svg = render_symbol_svg(resistor)
    root = ET.fromstring(svg)
    assert root.tag == f"{NAMESPACE}svg"
    assert root.attrib["width"].endswith("mm")
    assert len(root.findall(f".//{NAMESPACE}line")) == 2
    assert len(root.findall(f".//{NAMESPACE}rect")) == 1
    assert root.find(f"{NAMESPACE}title").text == "resistor.fixed"


def test_review_overlay_is_separate_from_standard_geometry(resistor):
    normal = ET.fromstring(render_symbol_svg(resistor))
    review = ET.fromstring(render_symbol_svg(resistor, review_overlay=True))
    assert len(normal.findall(f".//{NAMESPACE}circle")) == 0
    assert len(review.findall(f".//{NAMESPACE}circle")) == 2
    assert len(review.findall(f".//{NAMESPACE}rect")) == 2
