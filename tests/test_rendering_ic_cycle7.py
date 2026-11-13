"""Cycle7 #88 contract tests: no virtual pin creation, real text ink/frames."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcOrientation,
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
        frame = transform.apply(Point(x, y)) + origin
        outward = SIDE_VECTORS[transform.side(p.side)]
        world = Point(
            frame.x + outward.x * plan.lead_length_um,
            frame.y + outward.y * plan.lead_length_um,
        )
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
        (x.get("x2"), x.get("y2")) == (
            format_mm(pin.anchor.x), format_mm(pin.anchor.y),
        ) and x.get("data-real-anchor") == "true"
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



def test_same_logical_row_key_may_contain_two_distinct_physical_pin_rows():
    unit, _ = specimen(8)
    pins = list(unit.pins)
    pins[0] = replace(pins[0], row_key="BUS_A")
    pins[1] = replace(pins[1], row_key="BUS_A")
    changed = replace(unit, pins=tuple(pins))
    assert pins[0].row_key == pins[1].row_key
    assert pins[0].row != pins[1].row
    built = render_resolved_ic(changed, STYLE, FixedInk())
    assert len(built.pin_anchors) == 8


def test_true_text_ink_one_micrometre_from_frame_is_rejected_not_clipped():
    from gost_schematic.rendering.ic_rectangular import (
        IcRenderingPolicy,
        _text_placement,
    )

    text_box = FixedInk().measure("A", STYLE).ink_box
    nearly_touching = Box(0, 0, text_box.max_x + 1, 5000)
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW"):
        _text_placement(
            "unit", "A", nearly_touching, "center", STYLE, FixedInk(),
            IcRenderingPolicy(), "main-text",
        )


def test_three_digit_number_is_outside_box_without_crossing_pin_lead():
    unit, original_plan = specimen(8)
    pins = list(unit.pins)
    pins[-1] = replace(pins[-1], number="100")
    candidate = replace(unit, pins=tuple(pins))
    spec = propose_ic_dimensions(candidate.content, candidate.pins, STYLE, FixedInk())
    # Source currently contains geometry for the previous proposed lead;
    # if number requires more space the electrical owner must re-resolve it.
    if spec.lead_length_um != original_plan.lead_length_um:
        with pytest.raises(ValueError, match="IC_PIN_ANCHOR_MISMATCH"):
            render_resolved_ic(candidate, STYLE, FixedInk())
    else:
        render = render_resolved_ic(candidate, STYLE, FixedInk())
        box = next(x.box for x in render.ink
                   if x.kind=="pin-number" and x.owner==pins[-1].pin_id)
        assert box.min_x >= render.body_world.max_x



def test_sixty_four_pin_actual_stroke_footprint_requires_larger_than_a4_zone():
    unit, _ = specimen(64)
    with pytest.raises(ValueError, match="IC_PAGE_OVERFLOW"):
        render_resolved_ic(
            unit, STYLE, FixedInk(),
            page_bounds=Box(20000, 5000, 205000, 237000),
        )
    permitted = render_resolved_ic(
        unit, STYLE, FixedInk(),
        page_bounds=Box(20000, 5000, 292000, 415000),
    )
    assert len(permitted.pin_anchors) == 64
    assert permitted.proposed.height_um > 200000


def test_function_and_side_fields_preserve_all_stress_special_unicode():
    sample, _ = specimen(14, long_name=True, function="RG/≤64×16")
    out = render_resolved_ic(sample, STYLE, FixedInk())
    assert "RG/≤64×16" in out.svg
    assert "ДЛИННОЕ_ИМЯ_" in out.svg
    assert not any("ellipsis" in x or "textLength=" in x for x in (out.svg,))


def vertical_specimen(
    count: int, *,
    transform: Transform | None = None,
    function_rotation: int = 90,
    field_rotation: int = 90,
):
    """Real TOP/BOTTOM source port labels/Points; no D4-only shortcut."""
    source, _ = specimen(count, function="&")
    candidates = tuple(
        replace(p, side=Side.TOP if p.side is Side.LEFT else Side.BOTTOM)
        for p in source.pins
    )
    policy = IcRenderingPolicy()
    plan = propose_ic_dimensions(
        source.content, candidates, STYLE, FixedInk(), policy,
        orientation=IcOrientation.TOP_BOTTOM,
    )
    pose = transform or Transform()
    body = Box(0, 0, plan.width_um, plan.height_um)
    maxcol = max(p.row for p in candidates)
    real = []
    for p in candidates:
        virtual_row = maxcol + 1 - p.row
        x = plan.width_um - (virtual_row * plan.row_pitch_um
                             + plan.row_pitch_um // 2)
        y = 0 if p.side is Side.TOP else plan.height_um
        direction = SIDE_VECTORS[p.side]
        local = Point(x + direction.x * plan.lead_length_um,
                      y + direction.y * plan.lead_length_um)
        real.append(replace(
            p, anchor=pose.apply(local) + Point(100000, 90000),
        ))
    return IcResolvedUnit(
        "DD1", body, tuple(real), source.content,
        Point(100000, 90000), pose,
        IcOrientation.TOP_BOTTOM, function_rotation, field_rotation,
    ), plan


@pytest.mark.parametrize("count", (4, 14, 40, 64))
@pytest.mark.parametrize("rotation,mirror", (
    (0,False), (90,False), (180,False), (270,False),
    (0,True), (90,True), (180,True), (270,True),
))
def test_true_top_bottom_8_d4_source_ports_no_physical_delta(
    count, rotation, mirror,
):
    unit, plan = vertical_specimen(count, transform=Transform(rotation,mirror))
    drawn = render_resolved_ic(unit, STYLE, FixedInk())
    assert drawn.proposed.width_um == plan.width_um
    assert drawn.proposed.height_um == plan.height_um
    assert drawn.pin_anchors == tuple((p.pin_id,p.anchor) for p in unit.pins)
    root = ET.fromstring(drawn.svg)
    assert root.get("data-orientation") == "top_bottom"
    lines = root.findall(f".//{NS}line[@data-pin-id]")
    assert len(lines)==count
    for lead, pin in zip(lines, unit.pins, strict=True):
        assert (lead.get("x2"),lead.get("y2")) == (
            format_mm(pin.anchor.x),format_mm(pin.anchor.y),
        )
    assert root.findall(f".//{NS}text[@data-kind='function']")
    assert any(n.get("transform","").startswith("matrix(")
               for n in root.findall(f".//{NS}text"))


def test_true_top_bottom_does_not_reinterpret_1um_external_pin():
    unit,_ = vertical_specimen(14)
    p = list(unit.pins)
    p[0] = replace(p[0], anchor=p[0].anchor+Point(1,0))
    with pytest.raises(ValueError,match="IC_PIN_ANCHOR_MISMATCH"):
        render_resolved_ic(replace(unit,pins=tuple(p)),STYLE,FixedInk())


def test_vertical_function_upright_independent_of_rotated_fields():
    unit,_ = vertical_specimen(4,function_rotation=0,field_rotation=90)
    drawn=render_resolved_ic(unit,STYLE,FixedInk())
    root=ET.fromstring(drawn.svg)
    function=root.find(f".//{NS}text[@data-kind='function']")
    assert function is not None
    assert "transform" not in function.attrib
    labels=root.findall(f".//{NS}text[@data-kind='pin-label']")
    assert labels and all("matrix(" in l.attrib.get("transform","") for l in labels)


def test_vertical_no_silent_270_function_rotation_without_eskd_profile():
    unit,_=vertical_specimen(4)
    with pytest.raises(ValueError,match="IC_TEXT_ROTATION_UNVERIFIED"):
        replace(unit,function_rotation=270)


def test_mixed_source_sides_no_fictitious_normalization():
    unit,_=vertical_specimen(4)
    p=list(unit.pins)
    p[-1]=replace(p[-1],side=Side.RIGHT,role="passive")
    with pytest.raises(ValueError,match="IC_MIXED_SIDE_PROFILE"):
        replace(unit,pins=tuple(p))


def test_svg_namespace_import_does_not_change_global_elementtree_state():
    # Importing ic_rectangular must NOT call global ET.register_namespace.
    root=ET.fromstring(render_resolved_ic(*(
        lambda u: (u,STYLE,FixedInk())
    )(vertical_specimen(4)[0])).svg)
    assert root.tag == f"{NS}svg"
    assert b"xmlns" in ET.tostring(root)
