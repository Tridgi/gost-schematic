"""Expansion tests use temp copies; no new catalog UGO is committed or approved."""
import json
import shutil
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Box, Point
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.review_sheet import (
    CatalogReviewError,
    build_catalog_review_scene,
    discover_catalog_entries,
    layout_review_scene,
    render_review_svg,
    review_collisions,
    review_manifest,
)
from scripts.audit_symbol_catalog import audit_catalog

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("not-needed-for-fake-measurement.ttf", "TestFace", 3500, 500)


class StableMetrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 580, 1), len(text) * 580)


def _catalog_copy(tmp_path: Path) -> Path:
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    destination = tmp_path / "catalog"
    shutil.copytree(root, destination)
    return destination


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _store(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _add_capacitor(root: Path, identifier: str) -> None:
    filename = identifier.split(".", 1)[1]
    original_symbol = root / "symbols/capacitors/polarized.json"
    original_part = root / "parts/capacitors/polarized.json"
    ugo = _load(original_symbol)
    part = _load(original_part)
    ugo["id"] = identifier
    part["id"] = identifier
    part["symbol_id"] = identifier
    _store(root / "symbols" / "capacitors" / f"{filename}.json", ugo)
    _store(root / "parts" / "capacitors" / f"{filename}.json", part)


def _additional_id(root: Path) -> str:
    # The same test keeps extending the catalog after electrolytic is merged.
    if not (root / "symbols/capacitors/electrolytic.json").exists():
        return "capacitor.electrolytic"
    return "capacitor.review_fixture"


def test_installed_catalog_discovery_agrees_with_audit_not_a_literal_count():
    report = audit_catalog()
    scene = build_catalog_review_scene()
    found = discover_catalog_entries()
    assert report["hard_errors"] == 0
    assert report["draft_count"] == report["total_symbols"]
    assert not report["without_physical_part"]
    assert report["total_symbols"] == len(found) == len(scene.circuit.components)
    assert sorted((row["id"], row["revision"], row["source"]) for row in report["entries"]) == [
        (item.symbol.identifier, item.symbol.revision, item.source) for item in found
    ]
    assert scene.source_paths == tuple(item.source for item in found)


def test_temporary_nineteenth_electrolytic_is_discovered_without_code_changes(tmp_path):
    root = _catalog_copy(tmp_path)
    old = discover_catalog_entries(root)
    sample_id = _additional_id(root)
    _add_capacitor(root, sample_id)
    fresh = discover_catalog_entries(root)
    scene = build_catalog_review_scene(root)
    layout = layout_review_scene(scene, STYLE, StableMetrics())
    manifest = review_manifest(scene, layout)

    assert len(fresh) == len(old) + 1  # 18 -> 19 in current source, also future-proof
    assert len(scene.circuit.components) == len(fresh)
    assert [entry.symbol.identifier for entry in fresh] == sorted(
        entry.symbol.identifier for entry in fresh
    )
    assert sample_id in {entry.symbol.identifier for entry in fresh}
    assert [item.reference for item in scene.circuit.components].count("C3") == 1
    assert len({item.reference for item in scene.circuit.components}) == len(fresh)
    assert layout.valid, [(d.code, d.message) for d in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert manifest["catalog_size"] == len(fresh)
    assert manifest["approval"] == "DRAFT"
    assert manifest["aabb_collisions"] == []
    assert all(row["symbol_status"] == "draft" for row in manifest["components"])
    assert any(row["symbol_id"] == sample_id for row in manifest["components"])
    assert all(row["catalog_source"] for row in manifest["components"])

    clean = ET.fromstring(render_review_svg(scene, layout, diagnostic=False))
    diagnostic = ET.fromstring(render_review_svg(scene, layout, diagnostic=True))
    assert len(clean.findall(f".//{SVG}g[@data-layer='symbols']")) == len(fresh)
    assert diagnostic.find(f".//{SVG}g[@data-layer='geometry-review']") is not None
    assert clean.find(f".//{SVG}g[@data-layer='geometry-review']") is None
    assert not clean.findall(f".//{SVG}image")
    assert all(
        "transform" not in text.attrib for text in clean.findall(f".//{SVG}text")
    )
    assert render_review_svg(scene, layout, diagnostic=False) == render_review_svg(
        scene, layout, diagnostic=False,
    )


def test_expansion_does_not_change_any_preexisting_primitives_or_physical_identity(tmp_path):
    root = _catalog_copy(tmp_path)
    originals = discover_catalog_entries(root)
    original_by_id = {item.symbol.identifier: item for item in originals}
    _add_capacitor(root, _additional_id(root))
    refreshed = discover_catalog_entries(root)
    scene = build_catalog_review_scene(root)
    for entry in refreshed:
        if entry.symbol.identifier in original_by_id:
            original = original_by_id[entry.symbol.identifier]
            assert entry.symbol.graphics == original.symbol.graphics
            assert entry.symbol.pins == original.symbol.pins
            assert entry.symbol.body_keepout == original.symbol.body_keepout
            assert entry.symbol.line_width_um == original.symbol.line_width_um
            assert entry.part == original.part
    assert scene.circuit.nets == ()
    assert {component.part_id for component in scene.circuit.components} == {
        entry.part.identifier for entry in refreshed
    }
    for component in scene.circuit.components:
        expected = next(
            item for item in refreshed if item.part.identifier == component.part_id
        )
        assert component.pin_positions(expected.symbol) == {
            pin.number: component.transform.apply(pin.at) + component.origin
            for pin in expected.symbol.pins
        }
        assert component.nominal is None or component.nominal.kind == expected.part.nominal_kind


def test_dynamic_cell_dimensions_protect_wide_new_ugo(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    new_path = root / "symbols/capacitors" / (new_id.split(".", 1)[1] + ".json")
    data = _load(new_path)
    # A wider body and longer leads are a TEST ONLY synthetic geometry,
    # deliberately not a candidate for GOST approval.
    data["geometry"]["lines"][0][0] = [-180, 0]
    data["geometry"]["lines"][1][1] = [180, 0]
    data["pins"][0]["at_mm"] = [-180, 0]
    data["pins"][1]["at_mm"] = [180, 0]
    _store(new_path, data)
    scene = build_catalog_review_scene(root)
    layout = layout_review_scene(scene, STYLE, StableMetrics())
    assert layout.valid, [(d.code, d.message) for d in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert max(c.origin.x for c in scene.circuit.components) > 180000
    assert not any(d.code == "PIN_EXIT_OBSTRUCTED" for d in layout.diagnostics)


def test_missing_physical_passport_is_explicit_failure_not_silent_skip(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    (root / "parts/capacitors" / (new_id.split(".", 1)[1] + ".json")).unlink()
    with pytest.raises(CatalogReviewError, match="missing or invalid UGO/part"):
        build_catalog_review_scene(root)


def test_mismatched_symbol_id_or_pin_map_fails_closed(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    path = root / "parts/capacitors" / (new_id.split(".", 1)[1] + ".json")
    record = _load(path)
    record["symbol_id"] = "capacitor.polarized"
    _store(path, record)
    with pytest.raises(CatalogReviewError, match="points to"):
        discover_catalog_entries(root)
    record["symbol_id"] = new_id
    record["pins"][1]["number"] = "99"
    _store(path, record)
    with pytest.raises(CatalogReviewError, match="terminal numbers disagree"):
        discover_catalog_entries(root)


def test_duplicate_part_ids_or_non_draft_entries_are_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    part_path = root / "parts/capacitors" / (new_id.split(".", 1)[1] + ".json")
    symbol_path = root / "symbols/capacitors" / (new_id.split(".", 1)[1] + ".json")
    record = _load(part_path)
    record["id"] = "capacitor.fixed"
    _store(part_path, record)
    with pytest.raises(CatalogReviewError, match="duplicate physical part ID"):
        discover_catalog_entries(root)
    record["id"] = new_id
    _store(part_path, record)
    symbol = _load(symbol_path)
    symbol["status"] = "approved"
    _store(symbol_path, symbol)
    with pytest.raises(CatalogReviewError, match="expected DRAFT"):
        discover_catalog_entries(root)


def test_unknown_nominal_kind_remains_unknown_without_fabricating_value(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    part_path = root / "parts/capacitors" / (new_id.split(".", 1)[1] + ".json")
    record = _load(part_path)
    record["nominal_kind"] = None
    _store(part_path, record)
    scene = build_catalog_review_scene(root)
    instance = next(item for item in scene.circuit.components if item.part_id == new_id)
    assert instance.nominal is None
    layout = layout_review_scene(scene, STYLE, StableMetrics())
    assert layout.valid
    row = next(item for item in review_manifest(scene, layout)["components"]
               if item["part_id"] == new_id)
    assert row["nominal_si"] is None


def test_disallowed_columns_and_unplaceable_annotation_remain_explicit():
    for value in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="columns"):
            build_catalog_review_scene(columns=value)
    scene = build_catalog_review_scene()

    class OversizedMetrics:
        def measure(self, text, style):
            return MeasuredText(Box(0, -2000, 10_000_000, 1), 10_000_000)

    result = layout_review_scene(scene, STYLE, OversizedMetrics())
    assert not result.valid
    assert "ANNOTATION_UNPLACEABLE" in {issue.code for issue in result.diagnostics}


def test_shuffled_catalog_reading_cannot_change_stable_sort_or_refdes(tmp_path, monkeypatch):
    root = _catalog_copy(tmp_path)
    baseline = discover_catalog_entries(root)
    original_rglob = Path.rglob

    def reversed_rglob(self, pattern):
        return iter(reversed(tuple(original_rglob(self, pattern))))

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rglob", reversed_rglob)
        reordered = discover_catalog_entries(root)
    assert reordered == baseline
    assert build_catalog_review_scene(root) == build_catalog_review_scene(root)
    scene = build_catalog_review_scene(root)
    prefixes = [entry.part.reference_prefix for entry in baseline]
    refs = [item.reference for item in scene.circuit.components]
    assert len(refs) == len(set(refs))
    assert all(ref.startswith(prefix) for ref, prefix in zip(refs, prefixes, strict=True))


def test_metadata_without_nominal_does_not_affect_underlying_symbol(tmp_path):
    root = _catalog_copy(tmp_path)
    new_id = _additional_id(root)
    _add_capacitor(root, new_id)
    target = next(item for item in discover_catalog_entries(root)
                  if item.part.identifier == new_id)
    blank = replace(target.part, nominal_kind=None)
    assert blank.symbol_id == target.part.symbol_id
    assert blank.pins == target.part.pins
    assert target.symbol.status.value == "draft"
