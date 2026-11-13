"""Cycle7 #88 contract tests: no virtual pin creation, real text ink/frames."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcRenderingPolicy,
    IcResolvedUnit,
    ResolvedIcPin,
    propose_ic_dimensions,
    render_resolved_ic,
)

STYLE = TextStyle("/synthetic/nonfont.ttf", "Deterministic Unit Metrics", 3500, 500)
NS = "{http://www.w3.org/2000/svg}"


class FixedInk:
    """Deterministic unit metrics only; OpenGost is used by the gallery CI."""

    def measure(self, text, style):
        if not text:
            raise ValueError("Empty glyph text")
        # Only deterministic tests use uniform widths; never use for gallery.
        return MeasuredText(Box(0, -3500, 650 * len(text), 1),
                            650 * len(text))


def specimen(
    count: int,
    *,
    long_name: bool = False,
    transform: Transform | None = None,
    function: str = "AND",
    extra_rows: tuple[str, ...] = (),
    labels: bool = True,
    columns: tuple[str, ...] = (),
):
    transform = transform or Transform()
    if count % 2:
        raise ValueError("Only symmetrical *synthetic fixtures*")
    pins = []
    for i in range(count):
        side = Side.LEFT if i < count // 2 else Side.RIGHT
        row = i % (count // 2) + 1
        name = (f"ДЛИННОЕ_ИМЯ_{i:03d}" if long_name else
                ("A" if side == Side.LEFT else "Q")) if labels else ""
        pins.append(ResolvedIcPin(
            f"TEST.{i+1}", str(i+1), name, side, row,
            Point(i * 100 + 1, i * 100 + 2),
            "in" if side == Side.LEFT else "out",
        ))
    content = IcFieldContent(
        function, extra_rows, columns, (),
        left_zone_after=(2,) if count >= 8 and labels else (),
    )
    plan = propose_ic_dimensions(content, tuple(pins), STYLE, FixedInk())
    origin = Point(100000, 90000)
    body = Box(0, 0, plan.width_um, plan.height_um)
    real = []
    for p in pins:
        x = 0 if p.side == Side.LEFT else plan.width_um
        y = (p.row * plan.row_pitch_um + plan.row_pitch_um // 2)
        world = transform.apply(Point(x, y)) + origin
        real.append(replace(p, anchor=world))
    return IcResolvedUnit(
        "DD1", body, tuple(real), content, origin, transform,
    ), plan


@pytest.mark.parametrize("count", (4, 8, 14, 40, 64))
def test_five_stress_counts_satisfy_grid_and_keep_all_authoritative_pins(count):
    source, plan = specimen(count)
    built = render_resolved_ic(source, STYLE, FixedInk())
    root = ET.fromstring(built.svg)
    links = root.findall(f".//{NS}g[@data-layer='ic-physical-pin-leads']/{NS}line")
    assert len(links) == count
    assert built.proposed == plan
    assert len({x.get("data-pin-number") for x in links}) == count
    assert built.pin_anchors == tuple((p.pin_id, p.anchor) for p in source.pins)
    assert all(
        (x.get("x1"), x.get("y1")) == (
            str(pin.anchor.x / 1000).rstrip("0").rstrip("."),
            str(pin.anchor.y / 1000).rstrip("0").rstrip("."),
        ) or x.get("data-real-anchor") == "true"
        for x, pin in zip(links, source.pins, strict=True)
    )
    assert root.get("data-pin-anchor-authority") == "external-resolved-only"
    assert root.get("data-document-kind") == "E3-physical-IC"
    assert root.get("data-approval") == "DRAFT"
    assert plan.width_um % plan.module_um == 0
    assert plan.height_um % plan.row_pitch_um == 0
    assert len(root.findall(f".//{NS}text[@data-kind='pin-number']")) == count


def test_long_cyrillic_grows_fields_not_font_or_truncation():
    _, dim_short = specimen(14)
    long, dim_long = specimen(14, long_name=True)
    assert dim_long.width_um > dim_short.width_um
    render = render_resolved_ic(long, STYLE, FixedInk())
    root = ET.fromstring(render.svg)
    labels = root.findall(f".//{NS}text[@data-kind='pin-label']")
    assert len(labels) == 14
    assert any("ДЛИННОЕ" in t.text for t in labels)
    assert all(t.get("font-size") == "3.5" for t in labels)
    assert not any(t.get("textLength") for t in labels)


def test_long_main_row_forces_width_growth_without_arbitrary_character_cutoff():
    small, _ = specimen(4)
    long, plan = specimen(4, function="RAM/EEPROM_ПАМЯТЬ_64×16")
    assert plan.main_width_um > 15000
    assert plan.width_um > small.body.max_x
    out = render_resolved_ic(long, STYLE, FixedInk())
    assert "RAM/EEPROM_ПАМЯТЬ_64×16" in out.svg


def test_main_and_aux_field_rows_and_zone_separator():
    sample, _ = specimen(14, extra_rows=("ПРОВЕРКА", "ТЕСТ"), columns=("NC",))
    svg = render_resolved_ic(sample, STYLE, FixedInk()).svg
    root = ET.fromstring(svg)
    assert "ПРОВЕРКА" in svg and "ТЕСТ" in svg
    assert root.findall(f".//{NS}line[@data-kind='zone-divider']")
    assert root.findall(f".//{NS}line[@data-kind='field-divider']")


def test_number_1_10_40_and_no_number_inside_main_field():
    unit, _ = specimen(40)
    result = render_resolved_ic(unit, STYLE, FixedInk())
    numbers = {i.owner: i.box for i in result.ink if i.kind == "pin-number"}
    assert all(f"TEST.{n}" in numbers for n in (1, 10, 40))
    body = result.body_world
    assert all(not body.overlaps(box) for box in numbers.values())


def test_duplicate_physical_pin_and_duplicate_side_row_refused():
    unit, _ = specimen(8)
    p = list(unit.pins)
    p[1] = replace(p[1], number=p[0].number)
    with pytest.raises(ValueError, match="IC_DUPLICATE_PHYSICAL_NUMBER"):
        replace(unit, pins=tuple(p))
    p = list(unit.pins)
    p[1] = replace(p[1], row=p[0].row)
    with pytest.raises(ValueError, match="IC_DUPLICATE_PIN_ROW"):
        replace(unit, pins=tuple(p))


def test_off_by_one_um_authoritative_pin_is_error_no_snap():
    unit, _ = specimen(8)
    p = list(unit.pins)
    p[0] = replace(p[0], anchor=Point(p[0].anchor.x + 1, p[0].anchor.y))
    with pytest.raises(ValueError, match="IC_PIN_ANCHOR_MISMATCH"):
        render_resolved_ic(replace(unit, pins=tuple(p)), STYLE, FixedInk())


def test_pin_never_silently_relaxes_source_body_to_autosize():
    unit, plan = specimen(8, long_name=True)
    reduced = Box(0, 0, plan.width_um - plan.module_um, plan.height_um)
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW"):
        render_resolved_ic(replace(unit, body=reduced), STYLE, FixedInk())


def test_page_overflow_and_foreign_obstacle_fail_closed():
    unit, _ = specimen(8)
    with pytest.raises(ValueError, match="IC_PAGE_OVERFLOW"):
        render_resolved_ic(
            unit, STYLE, FixedInk(), page_bounds=Box(0, 0, 50000, 50000),
        )
    with pytest.raises(ValueError, match="IC_OBSTACLE_COLLISION"):
        render_resolved_ic(
            unit, STYLE, FixedInk(),
            other_obstacles=(Box(100000, 90000, 105000, 95000),),
        )


def test_side_field_row_conflict_is_never_silently_overwritten():
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW: conflict left row"):
        specimen(8, columns=("LEFT-FIELD", "DIFFERENT"))


def test_empty_additional_fields_are_optional_and_no_fake_header():
    unit, _ = specimen(4, function="1", labels=False)
    rendered = render_resolved_ic(unit, STYLE, FixedInk())
    assert rendered.proposed.left_width_um == 0
    assert rendered.proposed.right_width_um == 0
    assert "data-kind=\"field-divider\"" not in rendered.svg


def test_excessively_small_pitch_resolved_from_ink_height_upwards():
    unit, _ = specimen(4)
    policy = IcRenderingPolicy(pitch_modules=1)
    plan = propose_ic_dimensions(unit.content, unit.pins, STYLE, FixedInk(), policy)
    assert plan.row_pitch_um >= 5000
    assert plan.row_pitch_um % policy.module_um == 0


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_eight_transforms_never_mutate_authoritative_anchors(rotation, mirror):
    transform = Transform(rotation, mirror)
    unit, _ = specimen(4, transform=transform, function="1", labels=False)
    try:
        rendered = render_resolved_ic(unit, STYLE, FixedInk())
    except ValueError as exc:
        # A transformed narrow row can be too small for upright text.
        # Fail closed, never rotate letters, clip or shift PinRef.
        assert "IC_INK_COLLISION" in str(exc) or "IC_TEXT_OVERFLOW" in str(exc)
        return
    assert rendered.pin_anchors == tuple(
        (p.pin_id, p.anchor) for p in unit.pins
    )
    assert "rotate(" not in rendered.svg
    assert len(ET.fromstring(rendered.svg).findall(
        f".//{NS}g[@data-layer='ic-physical-pin-leads']/{NS}line"
    )) == 4


def test_transform_bad_real_anchor_is_rejected_even_if_one_micrometre():
    unit, _ = specimen(4, transform=Transform(90, True))
    p = list(unit.pins)
    p[-1] = replace(p[-1], anchor=p[-1].anchor + Point(0, 1))
    with pytest.raises(ValueError, match="IC_PIN_ANCHOR_MISMATCH"):
        render_resolved_ic(replace(unit, pins=tuple(p)), STYLE, FixedInk())


def test_no_vertical_ports_without_normative_attachment_profile():
    unit, _ = specimen(4)
    p = list(unit.pins)
    p[0] = replace(p[0], side=Side.TOP, role="power")
    with pytest.raises(ValueError, match="IC_UNSUPPORTED_VERTICAL_PORT"):
        render_resolved_ic(replace(unit, pins=tuple(p)), STYLE, FixedInk())


def test_main_field_cannot_be_indiscriminately_used_for_pin_number():
    unit, _ = specimen(8)
    xml = ET.fromstring(render_resolved_ic(unit, STYLE, FixedInk()).svg)
    numbering = xml.findall(f".//{NS}text[@data-kind='pin-number']")
    for node in numbering:
        ink = tuple(int(x) for x in node.get("data-ink-um").split(","))
        assert ink[3] < unit.origin.y + unit.body.max_y or (
            ink[0] < unit.origin.x or ink[2] > unit.origin.x + unit.body.max_x
        )
