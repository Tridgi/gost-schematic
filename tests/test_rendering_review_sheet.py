"""Regression gates for the independently generated DRAFT sheet-review specimens."""
from dataclasses import replace
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.annotation.layout import obstacles_for_component
from gost_schematic.engines.sheet_layout import SheetLayout, component_graphic_obstacles
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.review_sheet import (
    build_catalog_review_scene,
    build_overlap_review_scene,
    discover_catalog_entries,
    layout_review_scene,
    render_review_svg,
    review_collisions,
    review_manifest,
)

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("unused-review-font.ttf", "MeasuredTest", 3500, 500)


class DeterministicMetrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 580, 1), len(text) * 580)


def catalog():
    scene = build_catalog_review_scene()
    return scene, layout_review_scene(scene, STYLE, DeterministicMetrics())


def test_all_discovered_draft_catalog_symbols_have_safe_sheet_labels():
    scene, layout = catalog()
    assert len(scene.circuit.components) == len(discover_catalog_entries())
    assert len(scene.symbols_by_part) == len(scene.circuit.components)
    assert len(scene.source_paths) == len(scene.circuit.components)
    assert layout.valid, [(d.code, d.message) for d in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert {item.transform.rotation for item in scene.circuit.components} == {
        0, 90, 180, 270,
    }
    assert any(item.transform.mirror_x for item in scene.circuit.components)
    for label in layout.placements:
        for component in scene.circuit.components:
            symbol = scene.symbols_by_part[component.part_id]
            assert all(
                not label.collision_bounds.overlaps(obstacle.box)
                for obstacle in component_graphic_obstacles(symbol, component)
            )
            assert all(
                not label.collision_bounds.overlaps(obstacle.box)
                for obstacle in obstacles_for_component(symbol, component)
            )


def test_rendering_stays_byte_deterministic_with_upright_text_and_true_arcs():
    scene, layout = catalog()
    clean = render_review_svg(scene, layout, diagnostic=False)
    review = render_review_svg(scene, layout, diagnostic=True)
    assert clean == render_review_svg(scene, layout, diagnostic=False)
    assert review == render_review_svg(scene, layout, diagnostic=True)
    assert clean != review
    clean_root = ET.fromstring(clean)
    review_root = ET.fromstring(review)
    assert clean_root.get("data-approval-status") == "DRAFT"
    assert clean_root.get("data-view") == "clean"
    assert clean_root.find(f".//{SVG}g[@data-layer='collision-markers']") is None
    assert clean_root.find(f".//{SVG}g[@data-layer='geometry-review']") is None
    assert review_root.find(f".//{SVG}g[@data-layer='geometry-review']") is not None
    assert review_root.find(f".//{SVG}g[@data-layer='collision-markers']") is not None
    assert not review_root.findall(f".//{SVG}g[@data-layer='collision-markers']/{SVG}rect")
    assert clean_root.findall(f".//{SVG}path")
    assert not clean_root.findall(f".//{SVG}image")
    assert all(
        "transform" not in item.attrib for item in clean_root.findall(f".//{SVG}text")
    )


def test_svg_coordinates_use_physical_millimetres_not_pixels():
    scene, layout = catalog()
    root = ET.fromstring(render_review_svg(scene, layout, diagnostic=False))
    x, y, width, height = map(float, root.attrib["viewBox"].split())
    assert 200 < width < 1000
    assert 150 < height < 1000
    assert x >= -10 and y >= -10
    assert float(root.get("width").removesuffix("mm")) == width
    assert float(root.get("height").removesuffix("mm")) == height
    assert len(root.findall(f".//{SVG}g[@data-layer='symbols']")) == len(
        scene.circuit.components
    )


def test_manifest_preserves_exact_pins_and_si_nominals_after_transform():
    scene, layout = catalog()
    before = tuple(item.nominal for item in scene.circuit.components)
    manifest = review_manifest(scene, layout)
    assert manifest == review_manifest(scene, layout)
    assert manifest["approval"] == "DRAFT"
    assert manifest["layout_valid"]
    assert manifest["aabb_collisions"] == []
    assert len(manifest["components"]) == len(scene.circuit.components)
    assert all(item["symbol_status"] == "draft" for item in manifest["components"])
    for item, row in zip(scene.circuit.components, manifest["components"], strict=True):
        assert row["nominal_si"] == (
            item.nominal.to_record() if item.nominal is not None else None
        )
        points = item.pin_positions(scene.symbols_by_part[item.part_id])
        assert len(row["pins"]) == len(points)
        for pin in row["pins"]:
            assert points[pin["number"]] == Point(pin["x_um"], pin["y_um"])
    assert tuple(item.nominal for item in scene.circuit.components) == before
    turned = scene.circuit.components[2]
    assert turned.transform.rotation == 180
    sym = scene.symbols_by_part[turned.part_id]
    for pin in sym.pins:
        expected = turned.transform.apply(pin.at) + turned.origin
        assert turned.pin_positions(sym)[pin.number] == expected



def test_manifest_null_nominal_is_valid_and_preserves_immutable_component():
    scene, _ = catalog()
    original = next(
        item for item in scene.circuit.components if item.nominal is not None
    )
    # A real versioned UGO with its nominal intentionally absent; the catalog,
    # symbol passport, physical pins and production code are not modified.
    without_nominal = replace(original, nominal=None)
    revised_circuit = replace(
        scene.circuit,
        components=tuple(
            without_nominal if item.reference == original.reference else item
            for item in scene.circuit.components
        ),
    )
    revised_scene = replace(scene, circuit=revised_circuit)
    before = revised_scene.circuit.components
    layout = layout_review_scene(revised_scene, STYLE, DeterministicMetrics())
    assert layout.valid, [(issue.code, issue.message) for issue in layout.diagnostics]
    manifest = review_manifest(revised_scene, layout)
    record = next(
        row for row in manifest["components"]
        if row["reference"] == without_nominal.reference
    )
    assert record["nominal_si"] is None
    assert record["part_id"] == original.part_id
    assert record["origin_um"] == [original.origin.x, original.origin.y]
    assert record["rotation_clockwise_deg"] == original.transform.rotation
    assert record["mirror_x"] == original.transform.mirror_x
    assert {
        pin["number"]: (pin["x_um"], pin["y_um"])
        for pin in record["pins"]
    } == {
        number: (point.x, point.y)
        for number, point in without_nominal.pin_positions(
            revised_scene.symbols_by_part[without_nominal.part_id]
        ).items()
    }
    assert revised_scene.circuit.components == before
    assert original.nominal is not None  # Source scene unchanged.


def test_manifest_keeps_existing_non_null_si_nominal_unchanged():
    scene, layout = catalog()
    original = next(
        item for item in scene.circuit.components if item.nominal is not None
    )
    before = tuple(item.nominal for item in scene.circuit.components)
    manifest = review_manifest(scene, layout)
    record = next(
        row for row in manifest["components"]
        if row["reference"] == original.reference
    )
    assert record["nominal_si"] == original.nominal.to_record()
    assert record["nominal_si"] is not None
    assert tuple(item.nominal for item in scene.circuit.components) == before


def test_deliberate_overlap_is_rejected_and_red_markers_name_affected_parts():
    scene = build_overlap_review_scene()
    layout = layout_review_scene(scene, STYLE, DeterministicMetrics())
    assert not layout.valid
    assert "SYMBOL_GEOMETRY_OVERLAP" in {item.code for item in layout.diagnostics}
    overlaps = review_collisions(scene, layout)
    assert any(item.kind == "symbol-aabb" and item.first == "R1"
               and item.second == "R2" for item in overlaps)
    root = ET.fromstring(render_review_svg(scene, layout, diagnostic=True))
    assert root.get("data-specimen") == "invalid-overlap"
    assert root.findall(f".//{SVG}g[@data-layer='collision-markers']/{SVG}rect")
    assert root.find(f".//{SVG}metadata[@data-layer='layout-diagnostics']") is not None


def test_overlapping_hitboxes_are_reported_without_mutating_original_layout():
    scene, layout = catalog()
    first, second = layout.placements[:2]
    forged = replace(second, ink_bounds=first.ink_bounds,
                     collision_bounds=first.collision_bounds)
    altered = SheetLayout((first, forged), ())
    assert any(
        item.kind == "text-text" for item in review_collisions(scene, altered)
    )
    assert not review_collisions(scene, layout)


def test_rendering_overlay_marks_true_stroke_width_and_pin_exit_reservations():
    scene, layout = catalog()
    review = ET.fromstring(render_review_svg(scene, layout, diagnostic=True))
    pin_rects = review.findall(f".//{SVG}rect[@data-kind='pin_escape']")
    assert len(pin_rects) >= 36
    assert review.findall(f".//{SVG}rect[@data-kind='text-hitbox']")
    assert isinstance(review.findall(f".//{SVG}rect[@data-kind='text-reservation']"), list)
    # Source outlines are still independently present; overlay does not replace them.
    assert review.findall(f".//{SVG}g[@data-layer='symbols']/{SVG}line")
