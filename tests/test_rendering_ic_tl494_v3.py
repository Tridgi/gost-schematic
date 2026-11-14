"""Issue #110 TL494 true bottom-to-top and immutable manufacturer aliases."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_tl494_cycle7 import specimen
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.core.geometry import Box
from gost_schematic.rendering.ic_rectangular import (
    IcFunctionReading,
    IcTypographyProfile,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_tl494_profile import (
    TI_TL494_PIN_NAMES,
    apply_tl494_portrait_profile,
)

STYLE = TextStyle("/synthetic/nonfont.ttf", "Deterministic Unit Metrics", 3500, 500)
SVG = "{http://www.w3.org/2000/svg}"


class FixedInk:
    def measure(self, text, style):
        if not text:
            raise ValueError("Empty text")
        return MeasuredText(Box(0, -3500, 650 * len(text), 1), 650 * len(text))


@pytest.mark.parametrize("rot,mirrored", (
    (0, False), (90, False), (180, False), (270, False),
    (0, True), (90, True), (180, True), (270, True),
))
def test_real_ti_16_pin_alias_default_btt_toggle_same_anchor_d4(rot, mirrored):
    source, _ = specimen(STYLE, FixedInk(), Transform(rot, mirrored))
    assert source.typography_profile is IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT
    assert source.function_rotation == 270
    assert source.function_text_reading is IcFunctionReading.BOTTOM_TO_TOP
    assert len(source.pins) == 16
    assert {p.number for p in source.pins} == set(TI_TL494_PIN_NAMES)
    assert {p.label for p in source.pins if p.number in ("3", "13")} == {
        "FEEDBACK", "OUTPUT CTRL",
    }
    variants = {}
    for reading in IcFunctionReading:
        shown = source.select_function_text_reading(reading)
        assert shown.body == source.body
        assert shown.pins == source.pins
        assert all(
            len(p.visible_label) <= 6 for p in shown.pins
        )
        rendered = render_resolved_ic(shown, STYLE, FixedInk())
        variants[reading] = rendered
        root = ET.fromstring(rendered.svg)
        assert root.get("data-function-reading-local") == reading.value
        assert "editor-connection-targets" not in rendered.svg
        texts = root.findall(f".//{SVG}text[@data-kind='pin-label']")
        assert len(texts) == 16
        by_pin = {el.get("data-physical-pin-number"): el for el in texts}
        assert by_pin["3"].text == "FB"
        assert by_pin["3"].get("data-full-manufacturer-name") == "FEEDBACK"
        assert by_pin["13"].text == "OC"
        assert by_pin["13"].get("data-full-manufacturer-name") == "OUTPUT CTRL"
        assert len(root.findall(f".//{SVG}text[@data-kind='pin-number']")) == 16
        assert tuple((p.pin_id, p.anchor) for p in source.pins) == (
            rendered.pin_anchors
        )
    assert variants[IcFunctionReading.BOTTOM_TO_TOP].body_world == (
        variants[IcFunctionReading.HORIZONTAL].body_world
    )
    a = ET.fromstring(variants[IcFunctionReading.BOTTOM_TO_TOP].svg)
    b = ET.fromstring(variants[IcFunctionReading.TOP_TO_BOTTOM].svg)
    c = ET.fromstring(variants[IcFunctionReading.HORIZONTAL].svg)
    for layer in ("ic-outline", "ic-physical-pin-leads"):
        selector = f".//{SVG}g[@data-layer='{layer}']"
        assert ET.tostring(a.find(selector)) == ET.tostring(b.find(selector))
        assert ET.tostring(a.find(selector)) == ET.tostring(c.find(selector))
    if rot == 0 and not mirrored:
        assert a.find(
            f".//{SVG}text[@data-kind='function']"
        ).get("transform", "").startswith("matrix(0 -1 1 0")
        assert b.find(
            f".//{SVG}text[@data-kind='function']"
        ).get("transform", "").startswith("matrix(0 1 -1 0")
        assert "transform" not in c.find(
            f".//{SVG}text[@data-kind='function']"
        ).attrib


def test_tl494_source_alias_name_wrong_number_7char_and_duplicate_are_rejected():
    source, _ = specimen(STYLE, FixedInk())
    physical = next(p for p in source.pins if p.number == "3")
    assert physical.label == "FEEDBACK"
    assert physical.visible_label == "FB"
    with pytest.raises(ValueError, match="IC_TL494_MANUFACTURER_PIN_LABEL_MISMATCH"):
        apply_tl494_portrait_profile(replace(
            source, pins=tuple(
                replace(p, label="FAKE") if p.number == "3" else p
                for p in source.pins
            ),
        ))
    with pytest.raises(ValueError, match="IC_VISIBLE_PIN_ALIAS_OVER_6"):
        replace(source, pins=tuple(
            replace(p, display_alias="FEEDBACK") if p.number == "3" else p
            for p in source.pins
        ))
    with pytest.raises(ValueError, match="IC_VISIBLE_PIN_ALIAS_DUPLICATE"):
        replace(source, pins=tuple(
            replace(p, display_alias="FB") if p.number == "13" else p
            for p in source.pins
        ))
    with pytest.raises(ValueError, match="IC_TL494_EXACT_16_PHYSICAL_PINS_REQUIRED"):
        apply_tl494_portrait_profile(replace(
            source.select_typography_profile(IcTypographyProfile.LEGACY_V1),
            pins=source.pins[:-1],
        ))


def test_tl494_function_direction_typed_and_conflict_rejected_without_moving_point():
    base, _ = specimen(STYLE, FixedInk())
    assert base.function_rotation == 270
    with pytest.raises(ValueError, match="IC_FUNCTION_READING_ROTATION_CONFLICT"):
        replace(base, function_rotation=90)
    with pytest.raises(TypeError, match="IC_FUNCTION_READING_TYPED_REQUIRED"):
        base.select_function_text_reading("bottom_to_top")
    rotated = base.select_function_text_reading(IcFunctionReading.TOP_TO_BOTTOM)
    assert all(a.anchor == b.anchor for a, b in zip(
        base.pins, rotated.pins, strict=True,
    ))
    changed = list(base.pins)
    changed[0] = replace(changed[0], anchor=Point(
        changed[0].anchor.x + 1, changed[0].anchor.y,
    ))
    with pytest.raises(ValueError, match="IC_PIN_ANCHOR_MISMATCH"):
        render_resolved_ic(
            replace(base, pins=tuple(changed)), STYLE, FixedInk(),
        )
