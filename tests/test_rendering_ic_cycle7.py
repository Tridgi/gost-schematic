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
    unit, _ = vertical_specimen(4)
    root = ET.fromstring(render_resolved_ic(unit, STYLE, FixedInk()).svg)
    assert root.tag == f"{NS}svg"
    assert b"xmlns" in ET.tostring(root)


def test_connection_targets_immutable_pinref_and_editor_layer_opt_in():
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_hotspots import IcConnectionTarget

    unit, _ = specimen(4)
    target = IcConnectionTarget(
        pin_id=unit.pins[0].pin_id,
        pin_ref=PinRef("DD1", "1"),
        anchor=unit.pins[0].anchor,
        connectable=True,
        net_id="CLOCK",
    )
    result = render_resolved_ic(
        unit, STYLE, FixedInk(), editor_targets=(target,),
    )
    assert result.connection_targets == (target,)
    assert "editor-connection-targets" not in result.svg
    assert "#148645" not in result.svg
    visible = render_resolved_ic(
        unit, STYLE, FixedInk(), editor_targets=(target,),
        editor_overlay=True,
    )
    assert 'data-layer="editor-connection-targets"' in visible.svg
    assert 'data-pin-ref="DD1.1"' in visible.svg
    assert 'data-net-id="CLOCK"' in visible.svg
    assert result.pin_anchors == visible.pin_anchors


def test_invalid_editor_pinref_1um_and_nc_connection_rejected():
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_hotspots import IcConnectionTarget

    unit,_=specimen(4)
    bad=IcConnectionTarget(
        unit.pins[0].pin_id, PinRef("DD1","1"),
        unit.pins[0].anchor+Point(1,0),True,
    )
    with pytest.raises(ValueError,match="IC_EDITOR_PINREF_ENDPOINT_MISMATCH"):
        render_resolved_ic(unit,STYLE,FixedInk(),editor_targets=(bad,))

    p=list(unit.pins)
    p[0]=replace(p[0],role="nc")
    nc_unit=replace(unit,pins=tuple(p))
    illegal=IcConnectionTarget(
        p[0].pin_id, PinRef("DD1","1"),p[0].anchor,True,
    )
    with pytest.raises(ValueError,match="IC_EDITOR_NC_TARGET_CONNECTED"):
        render_resolved_ic(nc_unit,STYLE,FixedInk(),editor_targets=(illegal,))
    disabled=IcConnectionTarget(
        p[0].pin_id,PinRef("DD1","1"),p[0].anchor,False,reason="NC",
    )
    assert render_resolved_ic(
        nc_unit,STYLE,FixedInk(),editor_targets=(disabled,),
    ).connection_targets == (disabled,)


def test_editor_overlay_never_replaces_real_clean_pin_geometry():
    unit,_=vertical_specimen(4)
    with pytest.raises(ValueError,match="IC_EDITOR_OVERLAY_REQUIRES_EXPLICIT"):
        render_resolved_ic(unit,STYLE,FixedInk(),editor_overlay=True)


def test_vertical_64_pin_a4_page_zone_fails_instead_of_auto_scaling():
    unit, _ = vertical_specimen(64)
    with pytest.raises(ValueError, match="IC_PAGE_OVERFLOW"):
        render_resolved_ic(
            unit, STYLE, FixedInk(),
            page_bounds=Box(20000, 5000, 205000, 237000),
        )
    result = render_resolved_ic(
        unit, STYLE, FixedInk(),
        page_bounds=Box(20000, 5000, 412000, 290000),
    )
    assert len(result.pin_anchors) == 64
    assert result.proposed.width_um > 200000


def test_vertical_function_rotated_glyph_boxes_stay_on_frame_clearance():
    # Deterministic stub tests text-run geometry and invariants; real Type A
    # per-codepoint raster proof is exercised in independent gallery workflow.
    unit, _ = vertical_specimen(14)
    result = render_resolved_ic(unit, STYLE, FixedInk())
    function = next(x for x in result.ink if x.kind == "function")
    strokes = [x for x in result.ink if x.kind in (
        "outer-stroke", "field-divider", "zone-divider", "pin-lead",
    )]
    assert all(not function.box.expanded(1000).overlaps(x.box) for x in strokes)
    assert result.proposed.vertical_field_heights_um[1] > 0


# Independent center-function rotation — source L/R pins and physical nets
# are not re-resolved by PAINT. This is a DRAFT rendering candidate.
@pytest.mark.parametrize("count", (8, 14, 40, 64))
def test_lr_function_rotation_90_to_0_only_changes_function_ink(count):
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    initial, _ = specimen(count, function="PWM")
    portrait = initial.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    assert portrait.function_rotation == 90
    upright = replace(portrait, function_rotation=0)
    vertical = render_resolved_ic(portrait, STYLE, FixedInk())
    horizontal = render_resolved_ic(upright, STYLE, FixedInk())
    assert vertical.pin_anchors == horizontal.pin_anchors
    assert vertical.body_world == horizontal.body_world
    assert len(vertical.pin_anchors) == count
    r90, r0 = ET.fromstring(vertical.svg), ET.fromstring(horizontal.svg)
    assert r90.get("data-typography-profile") == "portrait_function_v2_draft"
    assert r0.get("data-typography-profile") == "portrait_function_v2_draft"
    assert r90.get("data-function-rotation-deg") == "90"
    assert r0.get("data-function-rotation-deg") is None
    f90 = r90.find(f".//{NS}text[@data-kind='function']")
    f0 = r0.find(f".//{NS}text[@data-kind='function']")
    assert f90 is not None and f0 is not None
    assert f90.text == f0.text == "PWM"
    assert f90.get("transform", "").startswith("matrix(0 1 -1 0")
    assert "transform" not in f0.attrib
    for layer in ("ic-outline", "ic-physical-pin-leads"):
        a = r90.find(f".//{NS}g[@data-layer='{layer}']")
        b = r0.find(f".//{NS}g[@data-layer='{layer}']")
        assert a is not None and b is not None
        assert ET.tostring(a) == ET.tostring(b)
    assert not any("editor-connection-targets" in svg for svg in
                   (horizontal.svg, vertical.svg))


def test_legacy_svg_profile_preserves_horizontal_function_default():
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    unit, plan = specimen(14, function="PWM")
    assert unit.typography_profile is IcTypographyProfile.LEGACY_V1
    assert unit.function_rotation == 0
    output = render_resolved_ic(unit, STYLE, FixedInk())
    assert output.proposed == plan
    assert "data-typography-profile" not in output.svg
    assert "data-function-rotation-deg" not in output.svg
    node = ET.fromstring(output.svg).find(f".//{NS}text[@data-kind='function']")
    assert node is not None and "transform" not in node.attrib


def test_vertical_word_reserves_multiple_real_rows_before_other_main_text():
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    unit, _ = specimen(
        64, function="МОДУЛЬ_УПРАВЛЕНИЯ_PWM",
        extra_rows=("FIRST", "SECOND"),
    )
    portrait = unit.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    sized = propose_ic_dimensions(
        unit.content, unit.pins, STYLE, FixedInk(), function_rotation=90,
    )
    assert sized.function_row_span >= 2
    drawn = render_resolved_ic(portrait, STYLE, FixedInk())
    function = next(i for i in drawn.ink if i.kind == "function")
    row1 = next(i for i in drawn.ink if i.owner == "main.1")
    row2 = next(i for i in drawn.ink if i.owner == "main.2")
    assert function.box.max_y + 1000 < row1.box.min_y < row2.box.min_y
    assert drawn.pin_anchors == tuple((p.pin_id, p.anchor) for p in unit.pins)


def test_rotation_requires_owner_revision_not_pin_move_when_body_too_short():
    unit, _ = specimen(
        4, function="ФУНКЦИОНАЛЬНАЯ_НАДПИСЬ_НЕ_ВЛЕЗАЕТ",
    )
    # Old 4-pin physical frame anchors remain authoritative, so drawing
    # cannot silently stretch a body or rewire the pins.
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW"):
        render_resolved_ic(
            replace(unit, function_rotation=90), STYLE, FixedInk(),
        )


def test_portrait_version_explicit_and_never_inferred_from_port_directions():
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    unit, _ = specimen(4, long_name=True, function="PWM")
    with pytest.raises(ValueError, match="IC_PORTRAIT_BODY_REQUIRED"):
        render_resolved_ic(
            unit.select_typography_profile(
                IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT),
            STYLE, FixedInk(),
        )
    with pytest.raises(ValueError, match="IC_FIELD_ROTATION_REQUIRES_TOP_BOTTOM"):
        replace(unit, field_text_rotation=90)


@pytest.mark.parametrize("angle,mirror", [
    (0, False), (90, False), (180, False), (270, False),
    (0, True), (90, True), (180, True), (270, True),
])
def test_d4_independent_function_turn_preserves_all_physical_leads(angle, mirror):
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    unit, _ = specimen(8, transform=Transform(angle, mirror), function="PWM")
    a = unit.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    turned = render_resolved_ic(a, STYLE, FixedInk())
    straight = render_resolved_ic(replace(a, function_rotation=0),
                                  STYLE, FixedInk())
    assert turned.pin_anchors == straight.pin_anchors
    assert turned.body_world == straight.body_world
    rotated_node = ET.fromstring(turned.svg).find(
        f".//{NS}text[@data-kind='function']",
    )
    assert rotated_node is not None
    assert rotated_node.text == "PWM"
    assert rotated_node.get("transform", "").startswith("matrix(")


def test_independent_rotation_1um_guard_and_actual_transform_bounds():
    from gost_schematic.rendering.ic_rectangular import (
        _rotated_function_placement,
    )

    ink = FixedInk().measure("A", STYLE).ink_box
    # 90-degree run size is 3501 x 650 um, allow <1000um on either
    # horizontal edge so no invisible tolerance may let the glyph through.
    too_narrow = Box(0, 0, (ink.max_y - ink.min_y) + 1999, 7500)
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW"):
        _rotated_function_placement(
            "main.0", "A", too_narrow, STYLE, FixedInk(), IcRenderingPolicy(),
        )


# New independent regressions: owner geometry stays frozen, no text/layout
# downgrade is permitted merely to make long PWM_CONTROLLER pass.
@pytest.mark.parametrize("word", ("PWM_CONTROLLER", "КОНТРОЛЛЕР_ШИМ"))
@pytest.mark.parametrize("count", (8, 14, 40, 64))
@pytest.mark.parametrize("pose,mirror", (
    (0, False), (90, False), (180, False), (270, False),
    (0, True), (90, True), (180, True), (270, True),
))
def test_long_center_word_common_0_90_envelope_all_d4(count, word, pose, mirror):
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    physical, _ = specimen(
        count, function=word, transform=Transform(pose, mirror),
        extra_rows=("ПИТАНИЕ_И_УПРАВЛЕНИЕ", "STATUS"),
    )
    candidate = physical.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    p90 = propose_ic_dimensions(
        candidate.content, candidate.pins, STYLE, FixedInk(),
        function_rotation=90, shared_function_envelope=True,
    )
    p0 = propose_ic_dimensions(
        candidate.content, candidate.pins, STYLE, FixedInk(),
        function_rotation=0, shared_function_envelope=True,
    )
    assert p0.function_row_span == p90.function_row_span
    assert p0.width_um == p90.width_um
    assert p0.height_um == p90.height_um
    # Author a NEW geometry revision before placing any real connections.
    # It is not a renderer-internal edit to an accepted/connected circuit.
    pitch = p90.row_pitch_um
    assert pitch == p0.row_pitch_um
    width = p90.width_um
    height = max(p90.height_um, width + pitch)
    height = ((height + pitch - 1) // pitch) * pitch
    body = Box(0, 0, width, height)
    new_pins = []
    for pin in candidate.pins:
        loc = Point(0 if pin.side is Side.LEFT else width,
                    pin.row * pitch + pitch // 2)
        frame = candidate.transform.apply(loc) + candidate.origin
        normal = SIDE_VECTORS[candidate.transform.side(pin.side)]
        new_pins.append(replace(
            pin, anchor=Point(
                frame.x + normal.x * p90.lead_length_um,
                frame.y + normal.y * p90.lead_length_um,
            ),
        ))
    resolved = replace(candidate, pins=tuple(new_pins), body=body)
    a = render_resolved_ic(resolved, STYLE, FixedInk())
    b = render_resolved_ic(
        replace(resolved, function_rotation=0), STYLE, FixedInk(),
    )
    assert a.pin_anchors == b.pin_anchors
    assert a.body_world == b.body_world
    assert p0.function_row_span >= 2
    for built in (a, b):
        ink = next(x.box for x in built.ink if x.kind == "function")
        separators = [
            x.box for x in built.ink
            if x.kind in ("field-divider", "zone-divider", "pin-lead", "outer-stroke")
        ]
        assert all(not ink.expanded(1000).overlaps(x) for x in separators)
        assert word in built.svg
    root90, root0 = ET.fromstring(a.svg), ET.fromstring(b.svg)
    func90 = root90.find(f".//{NS}text[@data-kind='function']")
    func0 = root0.find(f".//{NS}text[@data-kind='function']")
    assert func90 is not None and func0 is not None
    assert func90.get("transform", "").startswith("matrix(")
    assert func0.get("transform") is None
    for layer in ("ic-outline", "ic-physical-pin-leads"):
        assert ET.tostring(root90.find(f".//{NS}g[@data-layer='{layer}']")) == (
            ET.tostring(root0.find(f".//{NS}g[@data-layer='{layer}']"))
        )


def test_accepted_undersized_long_pwm_d4_must_request_electrik_revision():
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    sample, plan = specimen(
        14, transform=Transform(90, False), function="PWM_CONTROLLER",
    )
    portrait = sample.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    # Intentionally reject a newer view that was *not* reauthorized by
    # ELEKTRIK after reducing the original accepted module-height.
    short = replace(
        portrait, body=Box(
            portrait.body.min_x, portrait.body.min_y,
            portrait.body.max_x, portrait.body.max_y - plan.row_pitch_um,
        ),
        function_rotation=0,
    )
    with pytest.raises(ValueError, match="IC_TEXT_OVERFLOW"):
        render_resolved_ic(short, STYLE, FixedInk())


@pytest.mark.parametrize("count", (4, 8, 14, 40, 64))
def test_real_source_synthetic_nc_power_target_metadata_at_each_external_end(count):
    from decimal import Decimal

    from examples.review_ic_cycle7 import (
        _declared_synthetic_targets,
        _fixture,
    )

    kind = "analog" if count == 8 else "digital"
    unit, _ = _fixture(count, kind, STYLE, FixedInk())
    targets, circuit = _declared_synthetic_targets(unit)
    assert len(targets) == count
    assert all(t.pin_ref.number == p.number and t.anchor == p.anchor
               for t, p in zip(targets, unit.pins, strict=True))
    assert sum(not t.connectable for t in targets) == 1
    nc = next(pin for pin in unit.pins if pin.label == "NC")
    assert nc.role == "nc"
    assert next(t for t in targets if t.pin_id == nc.pin_id).reason
    assert any(pin.role == "power" for pin in unit.pins)
    names = {net.name for net in circuit.nets}
    assert {"TEST_SIGNAL", "TEST_SUPPLY"} <= names
    clean = render_resolved_ic(
        unit, STYLE, FixedInk(), editor_targets=targets,
    )
    visible = render_resolved_ic(
        unit, STYLE, FixedInk(), review_overlay=True,
        editor_targets=targets, editor_overlay=True,
    )
    assert clean.pin_anchors == visible.pin_anchors
    assert "editor-connection-targets" not in clean.svg
    assert "#148645" not in clean.svg and "#8b1e27" not in clean.svg
    svg = ET.fromstring(visible.svg)
    leaves = {
        element.get("data-pin-id"): element
        for element in svg.findall(f".//{NS}line[@data-pin-id]")
    }
    marks = svg.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect",
    )
    assert len(marks) == len(leaves) == count
    for target, mark in zip(targets, marks, strict=True):
        line = leaves[target.pin_id]
        assert mark.get("data-pin-ref") == (
            f"{target.pin_ref.reference}.{target.pin_ref.number}"
        )
        assert mark.get("data-pin-number") == target.pin_ref.number
        assert mark.get("data-net-id") == (target.net_id or "")
        assert mark.get("data-reason") == (target.reason or "")
        assert mark.get("data-pin-id") == target.pin_id
        assert mark.get("data-external-anchor-x-um") == str(target.anchor.x)
        assert mark.get("data-external-anchor-y-um") == str(target.anchor.y)
        assert (line.get("x2"), line.get("y2")) == (
            format_mm(target.anchor.x), format_mm(target.anchor.y),
        )
        # A true endpoint-centered square, never one drawn at the UGO body.
        assert int(Decimal(mark.get("x")) * 1000) + 350 == target.anchor.x
        assert int(Decimal(mark.get("y")) * 1000) + 350 == target.anchor.y
        assert mark.get("width") == mark.get("height") == "0.7"
        assert mark.get("fill") == (
            "#148645" if target.connectable else "#8b1e27"
        )


@pytest.mark.parametrize("angle,mirror", (
    (0, False), (90, False), (180, False), (270, False),
    (0, True), (90, True), (180, True), (270, True),
))
def test_hotspot_follows_d4_external_anchor_not_body_boundary(angle, mirror):
    from decimal import Decimal

    from examples.review_ic_cycle7 import _declared_synthetic_targets
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    original, _ = specimen(
        8, transform=Transform(angle, mirror), function="PWM",
    )
    unit = original.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    targets, _ = _declared_synthetic_targets(unit)
    svg = ET.fromstring(render_resolved_ic(
        unit, STYLE, FixedInk(),
        editor_targets=targets, editor_overlay=True,
    ).svg)
    squares = svg.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect",
    )
    assert len(squares) == len(targets) == 8
    for mark, target in zip(squares, targets, strict=True):
        assert int(Decimal(mark.get("x")) * 1000) + 350 == target.anchor.x
        assert int(Decimal(mark.get("y")) * 1000) + 350 == target.anchor.y


# Digital fig.6 a/b/c and analogue supply U/OV remain source-bound DRAFT.
# Selecting a layout never rewires or renumbers a physical component.
def test_power_side_profile_digital_vcc_gnd_and_analog_u_ov():
    from examples.review_ic_cycle7 import _fixture
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_power_profiles import (
        IcPowerLayout,
        IcPowerProfile,
        verify_ic_power_profile,
    )

    for kind in ("digital", "analog"):
        unit, _ = _fixture(8, kind, STYLE, FixedInk())
        power = tuple(p for p in unit.pins if p.role == "power")
        labels = {p.label for p in power}
        assert labels == ({"VCC", "GND"} if kind == "digital" else {"U", "OV"})
        profile = IcPowerProfile(
            IcPowerLayout.SIDE_PINS,
            tuple(PinRef(unit.reference, p.number) for p in power),
            unit.reference,
        )
        audit = verify_ic_power_profile(unit, profile)
        assert len(audit.external_points) == 2
        result = render_resolved_ic(
            unit, STYLE, FixedInk(), power_profile=profile,
        )
        root = ET.fromstring(result.svg)
        assert root.get("data-power-layout") == "ordinary_side_pins"
        assert "DRAFT" in root.get("data-power-normative")
        assert result.pin_anchors == tuple(
            (p.pin_id, p.anchor) for p in unit.pins
        )
        assert all(p.side in (Side.LEFT, Side.RIGHT) for p in power)


def test_power_fig6_one_split_unit_and_separate_outline_preserve_source_pinrefs():
    from examples.review_ic_cycle7 import _fixture
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_power_profiles import (
        IcPowerLayout,
        IcPowerProfile,
    )

    unit, _ = _fixture(8, "digital", STYLE, FixedInk())
    physical = tuple(p for p in unit.pins if p.role == "power")
    refs = tuple(PinRef("DD1", p.number) for p in physical)
    # One logical unit of a split physical component owns both power pins.
    split = replace(unit, reference="DD1.1")
    selection = IcPowerProfile(
        IcPowerLayout.ONE_SPLIT_UNIT, refs,
        "DD1.1", related_units=("DD1.2",),
    )
    shown = render_resolved_ic(
        split, STYLE, FixedInk(), power_profile=selection,
    )
    assert shown.pin_anchors == tuple(
        (p.pin_id, p.anchor) for p in unit.pins
    )
    assert "one_split_unit_fig6b" in shown.svg
    # A separate source-owned power view has ONLY actual power contacts.
    # It does not create an extra physical package or duplicate the nets.
    dedicated = replace(
        unit, pins=physical, content=IcFieldContent("PWR"),
    )
    profile = IcPowerProfile(
        IcPowerLayout.SEPARATE_CONTOUR, refs, "DD1",
    )
    isolated = render_resolved_ic(
        dedicated, STYLE, FixedInk(), power_profile=profile,
    )
    assert isolated.pin_anchors == tuple(
        (p.pin_id, p.anchor) for p in physical
    )
    assert "separate_power_contour_fig6c" in isolated.svg


def test_power_common_block_and_experimental_top_bottom_never_fake_normative():
    from examples.review_ic_cycle7 import _fixture
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_power_profiles import (
        IcPowerLayout,
        IcPowerProfile,
        verify_ic_power_profile,
    )

    unit, _ = _fixture(8, "digital", STYLE, FixedInk())
    refs = tuple(
        PinRef("DD1", pin.number) for pin in unit.pins
        if pin.role == "power"
    )
    common = IcPowerProfile(
        IcPowerLayout.COMMON_CONTROL_BLOCK, refs, "DD1",
    )
    audit = verify_ic_power_profile(unit, common)
    assert audit.requires_source_outline
    with pytest.raises(ValueError, match="IC_POWER_CONTROL_OUTLINE_SOURCE_REQUIRED"):
        render_resolved_ic(
            unit, STYLE, FixedInk(), power_profile=common,
        )
    proposal = IcPowerProfile(
        IcPowerLayout.EXPERIMENTAL_TOP_BOTTOM, refs, "DD1",
    )
    with pytest.raises(ValueError, match="IC_POWER_TOP_BOTTOM_REQUIRES_TYPED"):
        render_resolved_ic(
            unit, STYLE, FixedInk(), power_profile=proposal,
        )
    illegitimate = replace(unit.pins[-1], role="out")
    with pytest.raises(ValueError, match="IC_NONSTANDARD_OUTPUT_SIDE|IC_POWER"):
        invalid = replace(unit, pins=(*unit.pins[:-1], illegitimate))
        render_resolved_ic(
            invalid, STYLE, FixedInk(),
            power_profile=IcPowerProfile(
                IcPowerLayout.SIDE_PINS, refs, "DD1",
            ),
        )


def test_power_profile_rejects_duplicate_and_non_power_physical_pinrefs():
    from examples.review_ic_cycle7 import _fixture
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_power_profiles import (
        IcPowerLayout,
        IcPowerProfile,
    )

    unit, _ = _fixture(8, "digital", STYLE, FixedInk())
    first = PinRef("DD1", unit.pins[-1].number)
    with pytest.raises(ValueError, match="IC_POWER_DUPLICATE_PINREF"):
        IcPowerProfile(IcPowerLayout.SIDE_PINS, (first, first), "DD1")
    with pytest.raises(ValueError, match="IC_POWER_PINREF_COVERAGE_MISMATCH"):
        render_resolved_ic(
            unit, STYLE, FixedInk(),
            power_profile=IcPowerProfile(
                IcPowerLayout.SIDE_PINS, (PinRef("DD1", "1"),), "DD1",
            ),
        )


def test_editor_overlay_rejects_foreign_component_even_same_number_and_point():
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_hotspots import IcConnectionTarget

    unit, _ = specimen(8)
    physical = unit.pins[0]
    forged = IcConnectionTarget(
        physical.pin_id, PinRef("NOT_DD1", physical.number),
        physical.anchor, True, "FORGED_NET",
    )
    with pytest.raises(ValueError, match="IC_EDITOR_PINREF_COMPONENT_MISMATCH"):
        render_resolved_ic(
            unit, STYLE, FixedInk(), editor_targets=(forged,),
            editor_overlay=True,
        )


def test_editor_split_unit_reference_keeps_real_source_pinref():
    from gost_schematic.model.circuit import PinRef
    from gost_schematic.rendering.ic_hotspots import IcConnectionTarget

    unit, _ = specimen(8)
    view = replace(unit, reference="DD1.1")
    actual = unit.pins[0]
    valid = IcConnectionTarget(
        actual.pin_id, PinRef("DD1", actual.number),
        actual.anchor, True, "SRC_SIGNAL",
    )
    rendered = render_resolved_ic(
        view, STYLE, FixedInk(), editor_targets=(valid,),
        editor_overlay=True,
    )
    assert 'data-pin-ref="DD1.1"' in rendered.svg
    assert rendered.connection_targets == (valid,)
