"""Independent C3 source-symbol, pin/viewport and revision provenance regression."""
import hashlib
from xml.etree import ElementTree as ET

from gost_schematic.agent_api.specimen import load_specimen
from gost_schematic.agent_api.vision import (
    diagnostics,
    inspect_component,
    inspect_region,
    render_overview,
)
from gost_schematic.rendering.primitives import draw_primitive

NS = "http://www.w3.org/2000/svg"


def _symbol_group(svg: str, reference: str) -> ET.Element:
    root = ET.fromstring(svg)
    group = root.find(f".//{{{NS}}}g[@data-reference='{reference}']")
    assert group is not None
    return group


def _lines(group: ET.Element) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (node.get("x1"), node.get("y1"), node.get("x2"), node.get("y2"))
        for node in group if node.tag.split("}")[-1] == "line"
    )


def test_c3_exact_specialized_electrolytic_primitives_not_polarized():
    scene = load_specimen("six-part")
    component = next(x for x in scene.circuit.components if x.reference == "C3")
    part = scene.parts[component.part_id]
    symbol = scene.symbols[part.symbol_id]
    assert (part.identifier, symbol.identifier, symbol.revision) == (
        "capacitor.electrolytic", "capacitor.electrolytic", 1,
    )
    assert len(symbol.graphics) == 12
    assert len(scene.symbols["capacitor.polarized"].graphics) == 6
    viewport = inspect_component("six-part", "C3", target_dpi=500)
    actual = _symbol_group(viewport.svg, "C3")
    expected = ET.Element("g")
    for item in symbol.graphics:
        draw_primitive(expected, component.transform.primitive(item, component.origin))
    # Compare every authored stroke, not an image-recognized approximation.
    assert _lines(actual) == _lines(expected)
    assert len(_lines(actual)) == 12
    assert _lines(actual) != _lines(_symbol_group(viewport.svg, "C2"))
    assert _lines(actual)[2] == ("97.75", "76", "99.25", "76")
    assert _lines(actual)[10] == ("96", "75.5", "97", "75.5")


def test_c3_pin_numbers_polarity_and_mm_bbox_are_authoritative():
    scene = load_specimen("six-part")
    c3 = next(c for c in scene.circuit.components if c.reference == "C3")
    part = scene.parts[c3.part_id]
    assert [(p.number, p.name, p.polarity.value) for p in part.pins] == [
        ("1", "PLUS", "positive"), ("2", "MINUS", "negative"),
    ]
    symbol = scene.symbols[part.symbol_id]
    assert {k: (p.x, p.y) for k, p in c3.pin_positions(symbol).items()} == {
        "1": (91000, 80000), "2": (109000, 80000),
    }
    view = inspect_component("six-part", "C3", target_dpi=500)
    identity = view.metadata["selected_component"]
    assert identity["part_id"] == identity["symbol_id"] == "capacitor.electrolytic"
    assert identity["graphics_primitive_count"] == 12
    assert [p["position_mm"] for p in identity["physical_pins"]] == [
        ["91", "80"], ["109", "80"],
    ]
    assert view.metadata["bbox_mm"] == ["87.999", "64.5", "112.001", "87.5"]
    crop = list(map(float, view.metadata["bbox_mm"]))
    for node in _symbol_group(view.svg, "C3"):
        if node.tag.endswith("line"):
            for x, y in (
                (float(node.get("x1")), float(node.get("y1"))),
                (float(node.get("x2")), float(node.get("y2"))),
            ):
                assert crop[0] < x < crop[2] and crop[1] < y < crop[3]
    assert view.metadata["pixels"] == [472, 453]
    assert view.metadata["effective_dpi"][0] >= 499
    pin_crop = inspect_region(
        "six-part", {"pin": {"component": "C3", "number": "1"}}
    )
    assert pin_crop.metadata["selected_component"]["reference"] == "C3"


def test_revision_and_raster_are_identical_on_repeated_requests():
    a = inspect_component("six-part", "C3", target_dpi=500)
    b = inspect_component("six-part", "C3", target_dpi=500)
    overview = render_overview("six-part", mode="clean")
    report = diagnostics("six-part", "all")
    assert a.png == b.png
    assert a.svg == b.svg
    assert a.metadata == b.metadata
    assert a.metadata["project_revision"] == overview.metadata["project_revision"]
    assert a.metadata["project_revision"] == report["project_revision"]
    assert a.metadata["catalog_sha256"] == report["catalog_sha256"]
    assert a.metadata["schema_version"] == report["schema_version"] == 1
    assert a.metadata["view_svg_sha256"] == hashlib.sha256(a.svg.encode()).hexdigest()
    assert a.metadata["png_sha256"] == hashlib.sha256(a.png).hexdigest()
    assert a.metadata["view_id"] == b.metadata["view_id"]
