"""Cycle5 acceptance for DRAFT A4/A3 page composition (Issue #56)."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.units import format_mm, mm
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.formatted_sheet import (
    PageProfile,
    compose_formatted_sheet,
)

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("test-face.ttf", "Unit Test", 3500, 500)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


def specimen(*, diagnostic=False):
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    rendered = render_external_wire_sheet(
        circuit, graph, by_part, STYLE, FixedInk(), diagnostic=diagnostic,
    )
    return rendered, circuit, graph, by_part


def root(sheet):
    return ET.fromstring(sheet.svg)


@pytest.mark.parametrize(("profile", "dimensions", "frame", "title"), (
    (
        PageProfile("A4", "portrait"), (210, 297),
        (20, 5, 205, 292), (20, 237, 205, 292),
    ),
    (
        PageProfile("A3", "landscape"), (420, 297),
        (20, 5, 415, 292), (230, 237, 415, 292),
    ),
    (
        PageProfile("A3", "portrait"), (297, 420),
        (20, 5, 292, 415), (107, 360, 292, 415),
    ),
))
def test_paper_dimensions_margins_form_one_and_no_overlap(
    profile, dimensions, frame, title,
):
    rendered, *_ = specimen()
    result = compose_formatted_sheet(rendered, profile)
    svg = root(result)
    assert svg.attrib["width"] == f"{dimensions[0]}mm"
    assert svg.attrib["height"] == f"{dimensions[1]}mm"
    assert svg.attrib["viewBox"] == f"0 0 {dimensions[0]} {dimensions[1]}"
    assert svg.attrib["data-document-mode"] == "paper_first_sheet"
    assert svg.attrib["data-approval-status"] == "DRAFT"
    frame_rect = svg.find(f".//{SVG}rect[@data-kind='inner-frame']")
    assert frame_rect is not None
    assert tuple(mm(frame_rect.get(key)) for key in ("x", "y")) == tuple(
        1000 * n for n in frame[:2]
    )
    assert (
        mm(frame_rect.get("width")), mm(frame_rect.get("height")),
    ) == ((frame[2] - frame[0]) * 1000, (frame[3] - frame[1]) * 1000)
    title_group = svg.find(f".//{SVG}g[@data-layer='title-block']")
    assert title_group is not None
    outline = title_group.find(f".//{SVG}rect[@data-kind='form-one-outline']")
    assert outline is not None
    assert tuple(mm(outline.get(key)) for key in ("x", "y")) == tuple(
        1000 * n for n in title[:2]
    )
    assert (
        mm(outline.get("width")), mm(outline.get("height")),
    ) == (185000, 55000)
    assert svg.findall(f".//{SVG}g[@data-layer='title-block-grid']/{SVG}line")
    assert {el.get("data-grid-section") for el in svg.findall(
        f".//{SVG}g[@data-layer='title-block-grid']/{SVG}line"
    )} == {"revision-columns", "revision-rows", "title-rows", "title-columns"}
    # Default form is a real empty grid, never fabricated named/signature data.
    assert not svg.findall(f".//{SVG}g[@data-layer='title-block-fields']/{SVG}text")
    assert (result.placed_viewport_um.min_x >= profile.content_zone_um.min_x)
    assert (result.placed_viewport_um.max_x <= profile.content_zone_um.max_x)
    assert (result.placed_viewport_um.max_y <= profile.content_zone_um.max_y)
    assert result.placed_viewport_um.max_y < profile.title_um.min_y
    assert not svg.findall(f".//{SVG}clipPath")
    assert not svg.findall(f".//{SVG}image")


def test_title_field_geometry_and_content_are_independent():
    source, *_ = specimen()
    plain = root(compose_formatted_sheet(source, PageProfile()))
    filled = root(compose_formatted_sheet(
        source, PageProfile(),
        title_values={"designation": "Э3", "name": "Схема"},
        title_text_style=STYLE, title_measurer=FixedInk(),
    ))
    assert ET.tostring(plain.find(
        f".//{SVG}g[@data-layer='title-block-grid']"
    )) == ET.tostring(filled.find(
        f".//{SVG}g[@data-layer='title-block-grid']"
    ))
    fields = filled.findall(f".//{SVG}g[@data-layer='title-block-fields']/{SVG}text")
    assert {item.get("data-graph") for item in fields} == {"designation", "name"}
    for item in fields:
        ink = tuple(map(int, item.get("data-ink-bounds-um").split(",")))
        cell = tuple(map(int, item.get("data-cell-bounds-um").split(",")))
        assert cell[0] + 400 <= ink[0] <= ink[2] <= cell[2] - 400
        assert cell[1] + 400 <= ink[1] <= ink[3] <= cell[3] - 400
        assert item.get("data-cap-height-mm") == "2.5"
    assert not plain.findall(f".//{SVG}text[@data-graph]")


def test_form_one_measured_headings_use_full_seventeen_mm_role_column():
    source, *_ = specimen()
    filled = root(compose_formatted_sheet(
        source, PageProfile(),
        title_text_style=STYLE, title_measurer=FixedInk(),
        title_captions=True,
    ))
    named = {el.text: el for el in filled.findall(
        f".//{SVG}g[@data-layer='title-block-fields']/{SVG}text"
    )}
    assert {"Разраб.", "Пров.", "Т. контр.", "Н. контр.", "Утв."} <= named.keys()
    for value in ("Разраб.", "Т. контр.", "Н. контр."):
        node = named[value]
        cell = tuple(map(int, node.get("data-cell-bounds-um").split(",")))
        assert cell[2] - cell[0] == 17000  # not a 7 mm "Изм." cell
        assert node.get("data-cap-height-mm") == "2.5"
        assert node.get("font-size") == "3.5"  # test style; not a CSS cap-height claim


@pytest.mark.parametrize("title_values", (
    {"designation": "X" * 300},
    {"approved": "Слишком длинная подпись без автоподгонки"},
))
def test_form_one_rejects_long_text_without_font_shrink(title_values):
    source, *_ = specimen()
    with pytest.raises(ValueError, match="TITLE_FIELD_OVERFLOW"):
        compose_formatted_sheet(
            source, PageProfile(), title_values=title_values,
            title_text_style=STYLE, title_measurer=FixedInk(),
        )


def test_title_fields_empty_missing_style_and_unknown_keys_fail_closed():
    source, *_ = specimen()
    blank = root(compose_formatted_sheet(
        source, PageProfile(), title_values={"designation": ""},
        title_text_style=STYLE, title_measurer=FixedInk(),
    ))
    assert not blank.findall(f".//{SVG}g[@data-layer='title-block-fields']")
    with pytest.raises(ValueError, match="require calibrated"):
        compose_formatted_sheet(source, PageProfile(), title_values={"name": "X"})
    with pytest.raises(ValueError, match="Unknown form-1"):
        compose_formatted_sheet(
            source, PageProfile(), title_values={"unapproved_field": "X"},
            title_text_style=STYLE, title_measurer=FixedInk(),
        )
    with pytest.raises(ValueError, match="single-line"):
        compose_formatted_sheet(
            source, PageProfile(), title_values={"name": "A\\nB"},
            title_text_style=STYLE, title_measurer=FixedInk(),
        )
    with pytest.raises(ValueError, match="Title values require"):
        compose_formatted_sheet(
            source, PageProfile(mode="electronic_layout"),
            title_values={"designation": "X"},
            title_text_style=STYLE, title_measurer=FixedInk(),
        )


def test_preserves_exact_authored_wires_nets_physical_pins_and_source_inputs():
    source, circuit, graph, by_part = specimen()
    immutable = (source.svg, circuit, graph, by_part.copy())
    output = compose_formatted_sheet(source, PageProfile())
    svg = root(output)
    source_xml = ET.fromstring(source.svg)
    wires = svg.findall(f".//{SVG}line[@data-layer='wires']")
    original_lines = source_xml.findall(f".//{SVG}line[@data-layer='wires']")
    assert [line.attrib for line in wires] == [line.attrib for line in original_lines]
    assert len(wires) == len(graph.segments) == 18
    assert [
        (w.get("data-net"), w.get("data-wire-index")) for w in wires
    ] == [(edge.net_name, str(i)) for i, edge in enumerate(graph.segments)]
    dots = svg.findall(f".//{SVG}circle[@data-kind='authored-junction']")
    assert len(dots) == len(graph.junctions) == 3
    assert [
        Point(mm(node.get("cx")), mm(node.get("cy"))) for node in dots
    ] == list(graph.junctions)
    # Physically measured pins are retained inside each unchanged UGO group:
    groups = svg.findall(f".//{SVG}g[@data-layer='symbols']")
    assert [g.get("data-reference") for g in groups] == [
        item.reference for item in circuit.components
    ] == ["R1", "R2", "C1", "C2", "L1", "C3"]
    original_groups = source_xml.findall(f".//{SVG}g[@data-layer='symbols']")
    assert [
        ET.tostring(node, encoding="unicode") for node in groups
    ] == [ET.tostring(node, encoding="unicode") for node in original_groups]
    for item in circuit.components:
        actual_pins = item.pin_positions(by_part[item.part_id])
        for point in actual_pins.values():
            translated = Point(
                point.x + output.offset_um[0],
                point.y + output.offset_um[1],
            )
            assert output.placed_viewport_um.includes(translated)
    assert (source.svg, circuit, graph, by_part) == immutable


def test_explicit_t_dot_and_unconnected_crossing_survive_page_wrapper():
    source, _, graph, _ = specimen()
    result = compose_formatted_sheet(source, PageProfile())
    dots = root(result).findall(f".//{SVG}circle[@data-kind='authored-junction']")
    written = {
        (mm(dot.get("cx")), mm(dot.get("cy"))) for dot in dots
    }
    assert written == {(p.x, p.y) for p in graph.junctions}
    assert (40000, 40000) in written
    assert (40000, 60000) not in written


def test_clean_and_diagnostic_pages_keep_exact_same_placement():
    clean, *_ = specimen()
    debug, *_ = specimen(diagnostic=True)
    standard = PageProfile("A3", "landscape")
    original = compose_formatted_sheet(clean, standard)
    reviewed = compose_formatted_sheet(
        debug, standard, diagnostic=True, offset_um=original.offset_um,
    )
    assert reviewed.offset_um == original.offset_um
    clean_root, debug_root = root(original), root(reviewed)
    a = clean_root.find(f".//{SVG}g[@data-layer='schematic-content']")
    b = debug_root.find(f".//{SVG}g[@data-layer='schematic-content']")
    assert a.get("transform") == b.get("transform")
    assert not clean_root.findall(f".//{SVG}g[@data-layer='page-diagnostics']")
    assert debug_root.findall(f".//{SVG}g[@data-layer='page-diagnostics']")
    assert debug_root.findall(f".//{SVG}g[@data-layer='geometry-review']")
    for kind in ("safe-content-zone", "actual-source-viewport", "reserved-form-one"):
        assert debug_root.find(f".//{SVG}rect[@data-kind='{kind}']") is not None
    assert original.svg == compose_formatted_sheet(clean, standard).svg
    assert reviewed.svg == compose_formatted_sheet(
        debug, standard, diagnostic=True, offset_um=original.offset_um,
    ).svg


@pytest.mark.parametrize(("profile", "expected_frame", "expected_title"), (
    (PageProfile(mode="electronic_layout"), False, False),
    (PageProfile(mode="electronic_layout", electronic_title_block=True), False, True),
))
def test_electronic_exceptions_do_not_force_paper_frame(
    profile, expected_frame, expected_title,
):
    source, *_ = specimen()
    svg = root(compose_formatted_sheet(source, profile))
    assert (svg.find(f".//{SVG}g[@data-layer='frame']") is not None) == expected_frame
    assert (
        svg.find(f".//{SVG}g[@data-layer='title-block']") is not None
    ) == expected_title
    assert svg.get("data-document-mode") == "electronic_layout"


@pytest.mark.parametrize(("fields", "message"), (
    ({"format": "A2"}, "Unsupported paper"),
    ({"format": "A4", "orientation": "landscape"}, "A4"),
    ({"format": "A3", "orientation": "diagonal"}, "Orientation"),
    ({"mode": "bitmap"}, "document mode"),
    ({"safe_gap_um": -1}, "nonnegative"),
    ({"safe_gap_um": 0.3}, "nonnegative"),
    ({"electronic_title_block": 1}, "boolean"),
    ({"electronic_title_block": True}, "electronic exception"),
))
def test_invalid_profiles_rejected(fields, message):
    with pytest.raises((TypeError, ValueError), match=message):
        PageProfile(**fields)


def test_oversize_and_forced_title_overlap_rejected_instead_of_clipping():
    source, *_ = specimen()
    with pytest.raises(ValueError, match="SCHEMATIC_PAGE_OVERFLOW"):
        compose_formatted_sheet(source, PageProfile(safe_gap_um=100000))
    with pytest.raises(ValueError, match="SCHEMATIC_PAGE_OVERFLOW"):
        compose_formatted_sheet(
            source, PageProfile(), offset_um=(0, 180000),
        )
    with pytest.raises(TypeError, match="integer"):
        compose_formatted_sheet(source, PageProfile(), offset_um=(0.1, 0))


def test_source_viewbox_cannot_hide_lines_or_silently_resize_document():
    source, *_ = specimen()
    element = ET.fromstring(source.svg)
    element.set("viewBox", "0 0 20 20")
    element.set("width", "20mm")
    element.set("height", "20mm")
    with pytest.raises(ValueError, match="viewport excludes"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )
    element = ET.fromstring(source.svg)
    element.set("width", "999mm")
    with pytest.raises(ValueError, match="disagrees"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


def test_stroke_at_viewport_edge_is_rejected_even_if_line_axis_is_inside():
    source, *_ = specimen()
    element = ET.fromstring(source.svg)
    x, _, width, _ = (mm(value) for value in element.get("viewBox").split())
    line = element.find(f".//{SVG}line[@data-layer='wires']")
    assert line is not None
    line.set("x2", format_mm(x + width))
    # The centreline touches the input viewBox edge, but 0.3-mm ink exceeds it.
    with pytest.raises(ValueError, match="viewport excludes"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


def test_missing_stroke_width_cannot_be_misclassified_as_clipping_safe():
    source, *_ = specimen()
    element = ET.fromstring(source.svg)
    line = element.find(f".//{SVG}line[@data-layer='wires']")
    assert line is not None
    line.attrib.pop("stroke-width")
    with pytest.raises(ValueError, match="stroke width not specified"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


@pytest.mark.parametrize("kind", ("clipPath", "foreignObject", "script"))
def test_injected_clip_or_unsupported_geometry_is_rejected(kind):
    source, *_ = specimen()
    element = ET.fromstring(source.svg)
    ET.SubElement(element, SVG + kind, {"id": "not-allowed"})
    with pytest.raises(ValueError, match="Unsupported/clipping"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


def test_source_transform_is_rejected_because_geometry_cannot_be_verified():
    source, *_ = specimen()
    element = ET.fromstring(source.svg)
    group = element.find(f".//{SVG}g[@data-layer='symbols']")
    group.set("transform", "scale(9)")
    with pytest.raises(ValueError, match="Unsupported/clipping"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


def test_rejects_corrupted_svg_and_non_draft_source():
    source, *_ = specimen()
    with pytest.raises(ValueError, match="valid SVG"):
        compose_formatted_sheet(replace(source, svg="<svg"), PageProfile())
    element = ET.fromstring(source.svg)
    element.attrib.pop("data-approval-status")
    with pytest.raises(ValueError, match="DRAFT"):
        compose_formatted_sheet(
            replace(source, svg=ET.tostring(element, encoding="unicode")),
            PageProfile(),
        )


def test_grid_line_source_dimensions_are_exact_integer_um():
    source, *_ = specimen()
    result = compose_formatted_sheet(source, PageProfile())
    svg = root(result)
    lines = svg.findall(f".//{SVG}g[@data-layer='title-block-grid']/{SVG}line")
    assert len(lines) >= 25
    assert all(
        mm(line.get(key)) % 1000 == 0
        for line in lines for key in ("x1", "y1", "x2", "y2")
    )
    assert {format_mm(n) for n in result.offset_um}


def test_unplaceable_source_label_layout_rejected():
    class MassiveInk:
        def measure(self, text, style):
            return MeasuredText(Box(-9000000, -9000000, 9000000, 9000000), 18000000)

    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    invalid = render_external_wire_sheet(
        circuit, graph, by_part, STYLE, MassiveInk(), strict_layout=False,
    )
    assert not invalid.layout.valid
    with pytest.raises(ValueError, match="input annotation layout"):
        compose_formatted_sheet(invalid, PageProfile())
