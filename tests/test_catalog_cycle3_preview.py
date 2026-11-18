"""Comparative Cu vs magnetodielectric SVG from the actual sheet renderer."""

import json
from xml.etree import ElementTree as ET

from examples.review_copper_core_cycle3 import generate

SVG = "{http://www.w3.org/2000/svg}"


def _elements(path):
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    return root, root.findall(f".//{SVG}line"), root.findall(f".//{SVG}text")


def test_comparison_svg_generator_keeps_cu_label_and_different_stroke_types(tmp_path):
    manifest = generate(tmp_path)
    assert manifest["approval"] == "DRAFT"
    assert manifest["gost_certified"] is False
    assert manifest["text_metrics"] == "illustrative_only_not_verified_gost_type_a"
    assert len(manifest["files"]) == 6
    assert manifest["materials"]["inductor.trim_copper"]["core_dash_pattern_um"] == []
    assert manifest["materials"]["inductor.trim_magnetodielectric"][
        "core_dash_pattern_um"
    ] == [2000, 1100]
    assert manifest["materials"]["inductor.trim_copper"]["constant_annotations"] == {
        "core_material": "Cu",
    }

    copper, cu_lines, cu_labels = _elements(tmp_path / "copper-clean.svg")
    magneto, md_lines, md_labels = _elements(tmp_path / "magnetodielectric-clean.svg")
    assert copper.attrib["data-review-stage"] == "DRAFT"
    assert magneto.attrib["data-review-stage"] == "DRAFT"
    assert any(text.text == "Cu" for text in cu_labels)
    assert not any(text.text == "Cu" for text in md_labels)
    cu_core = [line for line in cu_lines if "stroke-width" in line.attrib]
    md_core = [line for line in md_lines if "stroke-width" in line.attrib]
    assert len(cu_core) == len(md_core) == 1
    assert "stroke-dasharray" not in cu_core[0].attrib
    assert md_core[0].attrib["stroke-dasharray"] == "2,1.1"

    comparison, shared_lines, shared_labels = _elements(
        tmp_path / "side-by-side-clean.svg"
    )
    assert comparison.attrib["data-svg-purpose"] == "clean"
    assert len([text for text in shared_labels if text.text == "Cu"]) == 1
    assert len([line for line in shared_lines if "stroke-width" in line.attrib]) == 2


def test_clean_and_diagnostic_svg_are_deterministic_without_false_gost_approval(
    tmp_path,
):
    manifest = generate(tmp_path)
    first = {
        path: (tmp_path / path).read_bytes() for path in manifest["files"]
    }
    first_manifest = (tmp_path / "manifest.json").read_bytes()
    assert generate(tmp_path) == manifest
    assert {
        path: (tmp_path / path).read_bytes() for path in manifest["files"]
    } == first
    assert (tmp_path / "manifest.json").read_bytes() == first_manifest
    assert json.loads(first_manifest)["gost_certified"] is False

    for stem in ("copper", "magnetodielectric", "side-by-side"):
        clean, _, _ = _elements(tmp_path / f"{stem}-clean.svg")
        diagnostic, _, _ = _elements(tmp_path / f"{stem}-diagnostic.svg")
        assert clean.attrib["data-svg-purpose"] == "clean"
        assert diagnostic.attrib["data-svg-purpose"] == "diagnostic"
        assert not clean.findall(f".//{SVG}g[@data-layer='geometry-review']")
        assert diagnostic.findall(f".//{SVG}g[@data-layer='geometry-review']")
