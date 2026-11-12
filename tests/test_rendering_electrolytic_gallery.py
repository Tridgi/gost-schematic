"""Real 19-UGO visual contracts; not a normative ГОСТ approval of the new capacitor."""
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.verify_rendering_review import (
    _validate_png,
    validate_focus_svg,
    validate_sheet_svg,
)
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.engines.annotation.metrics import font_sha256
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.pins import TerminalPolarity
from gost_schematic.rendering.review_sheet import (
    build_catalog_review_scene,
    discover_catalog_entries,
    layout_review_scene,
    render_review_svg,
    review_collisions,
    review_manifest,
)
from gost_schematic.rendering.svg import render_symbol_svg
from scripts.audit_symbol_catalog import audit_catalog

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("test-only.ttf", "MeasuredFake", 3500, 500, font_sha256="a" * 64)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 580, 1), len(text) * 580)


def _scene_and_manifest():
    scene = build_catalog_review_scene()
    layout = layout_review_scene(scene, STYLE, FixedInk())
    manifest = review_manifest(scene, layout)
    manifest["font"] = {"family": STYLE.font_family, "sha256": STYLE.font_sha256}
    return scene, layout, manifest


def _part_and_symbol(name):
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    return (
        load_part(root / "parts/capacitors" / f"{name}.json"),
        load_symbol(root / "symbols/capacitors" / f"{name}.json"),
    )


def _add_focus_provenance(symbol, source, *, diagnostic):
    root = ET.fromstring(render_symbol_svg(symbol, review_overlay=diagnostic))
    root.set("data-approval-status", "DRAFT")
    root.set("data-symbol-id", symbol.identifier)
    root.set("data-symbol-revision", str(symbol.revision))
    root.set("data-catalog-source", source)
    root.set("data-view", "diagnostic" if diagnostic else "clean")
    return ET.tostring(root, encoding="unicode")


def test_real_19_catalog_entries_and_unique_C_references():
    audit = audit_catalog()
    scene, layout, manifest = _scene_and_manifest()
    entries = discover_catalog_entries()
    assert audit["total_symbols"] == 19  # Baseline 2026-11-12 visual acceptance gate
    assert audit["draft_count"] == 19
    assert audit["hard_errors"] == 0
    assert len(scene.circuit.components) == len(entries) == 19
    assert layout.valid, [(item.code, item.message) for item in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert not manifest["aabb_collisions"]
    assert manifest["catalog_size"] == 19
    assert all(component["symbol_status"] == "draft" for component in manifest["components"])
    assert len({component.reference for component in scene.circuit.components}) == 19
    assert scene.circuit.nets == ()
    ids = {item.symbol.identifier for item in entries}
    assert {"capacitor.electrolytic", "capacitor.polarized"} <= ids
    refs = {
        row["symbol_id"]: row["reference"] for row in manifest["components"]
    }
    assert refs["capacitor.electrolytic"] != refs["capacitor.polarized"]
    assert refs["capacitor.electrolytic"].startswith("C")
    assert refs["capacitor.polarized"].startswith("C")
    assert [entry.symbol.identifier for entry in entries] == sorted(ids)


def test_real_electrolytic_source_vectors_are_distinct_from_general_polarized():
    electro_part, electro = _part_and_symbol("electrolytic")
    general_part, general = _part_and_symbol("polarized")
    assert electro.identifier == "capacitor.electrolytic"
    assert general.identifier == "capacitor.polarized"
    assert electro.graphics != general.graphics
    assert len(electro.graphics) == 12  # Current authored draft: outlined electrode pair
    assert len(general.graphics) == 6  # General capacitor: two ordinary plate strokes
    assert electro.graphics[0] == Line(Point(-9000, 0), Point(-2250, 0))
    assert electro.graphics[1] == Line(Point(2250, 0), Point(9000, 0))
    assert [pin.number for pin in electro_part.pins] == ["1", "2"]
    assert [pin.polarity for pin in electro_part.pins] == [
        TerminalPolarity.POSITIVE, TerminalPolarity.NEGATIVE,
    ]
    assert electro_part.symbol_id == electro.identifier
    assert general_part.symbol_id == general.identifier
    assert [pin.label for pin in electro.pins] == ["+", ""]
    assert electro.status.value == general.status.value == "draft"
    # Explicitly recognize DRAFT/editorial rather than asserting ГОСТ compliance.
    assert "EDITORIAL_ASSUMPTION" in " ".join(electro.standard_refs)


def test_all_19_drawn_vector_groups_equal_actual_transformed_catalog_primitives():
    scene, layout, manifest = _scene_and_manifest()
    clean = render_review_svg(scene, layout, diagnostic=False)
    diagnostic = render_review_svg(scene, layout, diagnostic=True)
    validate_sheet_svg(clean, scene, manifest, diagnostic=False)
    validate_sheet_svg(diagnostic, scene, manifest, diagnostic=True)
    root = ET.fromstring(clean)
    original_counts = {
        component.reference: len(scene.symbols_by_part[component.part_id].graphics)
        for component in scene.circuit.components
    }
    assert {
        element.get("data-reference"): len(element)
        for element in root.findall(f".//{SVG}g[@data-layer='symbols']")
    } == original_counts
    assert not root.findall(f".//{SVG}image")
    assert render_review_svg(scene, layout, diagnostic=False) == clean


def test_electrolytic_focus_is_true_original_vector_and_keeps_real_pin_markers():
    by_id = {entry.symbol.identifier: entry for entry in discover_catalog_entries()}
    for name in ("capacitor.electrolytic", "capacitor.polarized"):
        entry = by_id[name]
        for diagnostic in (False, True):
            svg = _add_focus_provenance(
                entry.symbol, entry.source, diagnostic=diagnostic,
            )
            validate_focus_svg(svg, entry, diagnostic=diagnostic)
            image = ET.fromstring(svg)
            assert image.get("data-approval-status") == "DRAFT"
            assert not image.findall(f".//{SVG}image")
            if diagnostic:
                marks = image.findall(f"./{SVG}circle")
                assert len(marks) == len(entry.symbol.pins)


def test_gallery_rejects_raster_substitution_missing_stroke_or_wrong_font():
    scene, layout, manifest = _scene_and_manifest()
    source = render_review_svg(scene, layout, diagnostic=False)
    root = ET.fromstring(source)
    first_group = root.findall(f".//{SVG}g[@data-layer='symbols']")[0]
    first_group.remove(first_group[-1])
    with pytest.raises(ValueError, match="primitives changed"):
        validate_sheet_svg(
            ET.tostring(root, encoding="unicode"), scene, manifest, diagnostic=False,
        )
    root = ET.fromstring(source)
    first_text = root.findall(f".//{SVG}text[@data-layer='annotations']")[0]
    first_text.set("font-family", "Another Font")
    with pytest.raises(ValueError, match="font family"):
        validate_sheet_svg(
            ET.tostring(root, encoding="unicode"), scene, manifest, diagnostic=False,
        )
    root = ET.fromstring(source)
    ET.SubElement(root, SVG + "image", {"href": "fake.png"})
    with pytest.raises(ValueError, match="Raster-replaced"):
        validate_sheet_svg(
            ET.tostring(root, encoding="unicode"), scene, manifest, diagnostic=False,
        )


def test_font_resolver_provenance_and_png_corruption_check(tmp_path):
    # The real OpenGost SHA is checked in Actions. These are negative guards.
    font = tmp_path / "font.ttf"
    font.write_bytes(b"measure-only-no-redistribution")
    initial = font_sha256(str(font))
    assert len(initial) == 64
    font.write_bytes(b"changed-file-same-name")
    assert font_sha256(str(font)) != initial
    png = tmp_path / "preview.png"
    png.write_bytes(b"not a PNG")
    with pytest.raises(ValueError, match="Not a PNG"):
        _validate_png(png)


def test_workflow_triggers_catalog_changes_and_only_integration_push():
    workflow = Path(".github/workflows/rendering-review.yml").read_text(
        encoding="utf-8"
    )
    pr = workflow.split("  pull_request:\n", 1)[1].split("  push:\n", 1)[0]
    push = workflow.split("  push:\n", 1)[1].split("  workflow_dispatch:\n", 1)[0]
    needed = (
        "src/gost_schematic/catalog/symbols/**/*.json",
        "src/gost_schematic/catalog/parts/**/*.json",
        "src/gost_schematic/catalog/inductors/*.json",
        "src/gost_schematic/catalog/inductors.py",
        "src/gost_schematic/rendering/**",
    )
    for pattern in needed:
        assert f'"{pattern}"' in pr
        assert f'"{pattern}"' in push
    assert "      - integration/stage0-12" in pr
    assert "      - integration/stage0-12" in push
    assert "parallel/rendering-cycle3" not in push
    assert "cancel-in-progress: true" in workflow
