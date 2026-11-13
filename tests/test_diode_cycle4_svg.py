"""Renderer-level visual regression and repeatable diode comparison fixtures."""

import json
from xml.etree import ElementTree as ET

from examples.review_diodes_cycle4 import generate

SVG = "{http://www.w3.org/2000/svg}"


def test_diode_clean_and_diagnostic_svgs_draw_real_distinct_lines(tmp_path):
    manifest = generate(tmp_path)
    assert manifest["issue"] == 32
    assert manifest["approval"] == "DRAFT"
    assert manifest["normative_certified"] is False
    assert manifest["physical_pin_numbering"] == "abstract_only_not_manufacturer_datasheet"
    assert manifest["font_metrics"] == "illustrative_not_measured_gost_type_a"
    assert len(manifest["files"]) == 6
    assert manifest["symbols"]["diode.general"]["pin_roles"] == {
        "1": "A", "2": "K",
    }
    for name, number_of_lines in (("diode.general", 6), ("diode.zener", 8)):
        report = manifest["symbols"][name]
        assert report["graphic_strokes"] == number_of_lines
        assert report["pin_polarity"] == {"1": "none", "2": "none"}
        assert report["conductor_groups"] == [["1"], ["2"]]
        for view in ("clean", "diagnostic"):
            path = tmp_path / f"{name}-{view}.svg"
            tree = ET.fromstring(path.read_text(encoding="utf-8"))
            assert tree.tag == SVG + "svg"
            assert tree.get("data-ugo") == name
            assert tree.get("data-approval-status") == "DRAFT"
            assert tree.get("data-view") == view
            assert len(tree.findall(f".//{SVG}line")) == number_of_lines
            assert not tree.findall(f".//{SVG}image")
            circles = tree.findall(f".//{SVG}circle")
            assert len(circles) == (2 if view == "diagnostic" else 0)
    assert (tmp_path / "diode.general-clean.svg").read_bytes() != (
        tmp_path / "diode.zener-clean.svg"
    ).read_bytes()


def test_paired_diode_sheet_keeps_both_identifiers_without_fabricated_nominals(
    tmp_path,
):
    generate(tmp_path)
    for view in ("clean", "diagnostic"):
        text = (tmp_path / f"diode-comparison-{view}.svg").read_text(
            encoding="utf-8",
        )
        root = ET.fromstring(text)
        assert root.get("data-approval-status") == "DRAFT"
        assert root.get("data-view") == view
        symbol_groups = root.findall(f".//{SVG}g[@data-layer='symbols']")
        assert {group.get("data-reference") for group in symbol_groups} == {
            "VD1", "VD2",
        }
        assert {label.text for label in root.findall(f".//{SVG}text")} == {
            "VD1", "VD2",
        }
        assert not root.findall(f".//{SVG}image")
        overlays = root.findall(f".//{SVG}g[@data-layer='geometry-review']")
        assert bool(overlays) == (view == "diagnostic")


def test_diode_svg_and_provenance_manifest_are_byte_reproducible(tmp_path):
    one = generate(tmp_path)
    before = {
        file: (tmp_path / file).read_bytes() for file in one["files"]
    }
    manifest_bytes = (tmp_path / "manifest.json").read_bytes()
    two = generate(tmp_path)
    assert one == two
    assert {
        file: (tmp_path / file).read_bytes() for file in two["files"]
    } == before
    assert (tmp_path / "manifest.json").read_bytes() == manifest_bytes
    assert json.loads(manifest_bytes)["normative_certified"] is False
