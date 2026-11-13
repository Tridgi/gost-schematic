"""Live-catalog visual contracts; allow new UGO while guarding baseline identities."""
import json
import shutil
from difflib import unified_diff
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import scripts.audit_symbol_catalog as audit_module
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

# Frozen minimum accepted inventory, not a maximum or dynamic gallery roster.
# Future YGO additions must NOT require updating this set or any exact count.
MINIMUM_BASELINE = 19
REQUIRED_BASELINE_IDS = frozenset((
    "capacitor.electrolytic",
    "capacitor.fixed",
    "capacitor.polarized",
    "choke.air_core",
    "choke.ferrite",
    "choke.ferromagnetic",
    "inductor.air_core",
    "inductor.double_sliding",
    "inductor.double_tapped",
    "inductor.ferrite",
    "inductor.ferromagnetic",
    "inductor.gapped_core",
    "inductor.magnetodielectric",
    "inductor.sliding_contact",
    "inductor.tapped",
    "inductor.trim_copper",
    "inductor.trim_magnetodielectric",
    "inductor.variable",
    "resistor.fixed",
))


def assert_baseline_ids_present(ids: set[str]) -> None:
    """Accepted 19 IDs are a required SUBSET; additional catalog IDs are fine."""
    missing = REQUIRED_BASELINE_IDS - ids
    if missing:
        comparison = "\n".join(unified_diff(
            sorted(REQUIRED_BASELINE_IDS), sorted(ids),
            fromfile="accepted-baseline-ugo", tofile="live-catalog-ugo",
            lineterm="",
        ))
        raise AssertionError(
            f"Missing previously accepted UGO IDs: {sorted(missing)}\n{comparison}"
        )

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("test-only.ttf", "MeasuredFake", 3500, 500, font_sha256="a" * 64)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 580, 1), len(text) * 580)


def _scene_and_manifest(catalog_root=None):
    scene = build_catalog_review_scene(catalog_root)
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


def test_live_catalog_audit_parity_and_unique_C_references():
    audit = audit_catalog()
    scene, layout, manifest = _scene_and_manifest()
    entries = discover_catalog_entries()
    ids = {entry.symbol.identifier for entry in entries}
    audited = {record["id"] for record in audit["entries"]}
    assert_baseline_ids_present(ids)
    assert ids == audited, (
        f"Audit vs SVG discovery mismatch: audit-only={sorted(audited - ids)}; "
        f"renderer-only={sorted(ids - audited)}"
    )
    count = audit["total_symbols"]
    assert count >= MINIMUM_BASELINE
    assert len(audited) == count  # Repeated ID is never silently accepted.
    assert audit["draft_count"] == count
    assert audit["hard_errors"] == 0
    assert len(scene.circuit.components) == len(entries) == count
    assert layout.valid, [(item.code, item.message) for item in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert not manifest["aabb_collisions"]
    assert manifest["catalog_size"] == count
    assert all(component["symbol_status"] == "draft" for component in manifest["components"])
    assert len({component.reference for component in scene.circuit.components}) == count
    assert scene.circuit.nets == ()
    assert {"capacitor.electrolytic", "capacitor.polarized"} <= ids
    refs = {row["symbol_id"]: row["reference"] for row in manifest["components"]}
    assert refs["capacitor.electrolytic"] != refs["capacitor.polarized"]
    assert refs["capacitor.electrolytic"].startswith("C")
    assert refs["capacitor.polarized"].startswith("C")
    assert [entry.symbol.identifier for entry in entries] == sorted(ids)


def test_removed_baseline_id_is_reported_with_reviewable_diff():
    missing_id = "inductor.variable"
    expanded = (REQUIRED_BASELINE_IDS - {missing_id}) | {
        "capacitor.future_A", "capacitor.future_B",
    }
    with pytest.raises(AssertionError) as error:
        assert_baseline_ids_present(expanded)
    message = str(error.value)
    assert missing_id in message
    assert "--- accepted-baseline-ugo" in message
    assert "+++ live-catalog-ugo" in message
    assert f"-{missing_id}" in message


@pytest.mark.parametrize("growth", (1, 2))
def test_catalog_growth_20_21_preserves_full_svg_manifest_and_pin_map(
    tmp_path, monkeypatch, growth,
):
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    sandbox = tmp_path / "catalog"
    shutil.copytree(root, sandbox)
    start = discover_catalog_entries(sandbox)
    assert_baseline_ids_present({item.symbol.identifier for item in start})

    reference_symbol = json.loads(
        (sandbox / "symbols/capacitors/polarized.json").read_text(encoding="utf-8")
    )
    reference_part = json.loads(
        (sandbox / "parts/capacitors/polarized.json").read_text(encoding="utf-8")
    )
    for index in range(growth):
        identity = f"capacitor.cycle4_fixture_{index}"
        path = sandbox / "symbols/capacitors" / f"cycle4_fixture_{index}.json"
        physical = sandbox / "parts/capacitors" / f"cycle4_fixture_{index}.json"
        graphic_data = {**reference_symbol, "id": identity}
        physical_data = {**reference_part, "id": identity, "symbol_id": identity}
        path.write_text(json.dumps(graphic_data), encoding="utf-8")
        physical.write_text(json.dumps(physical_data), encoding="utf-8")

    entries = discover_catalog_entries(sandbox)
    scene, layout, manifest = _scene_and_manifest(sandbox)
    ids = {row.symbol.identifier for row in entries}
    assert_baseline_ids_present(ids)
    assert len(entries) == len(start) + growth
    assert len(entries) >= MINIMUM_BASELINE + growth
    assert len(scene.circuit.components) == len(entries)
    assert manifest["catalog_size"] == len(entries)
    assert len(manifest["components"]) == len(entries)
    assert len({item.reference for item in scene.circuit.components}) == len(entries)
    assert layout.valid, [(d.code, d.message) for d in layout.diagnostics]
    assert not review_collisions(scene, layout)
    assert manifest["aabb_collisions"] == []
    # The SAME structural audit must also accept 20/21 without changing any
    # literal, while the production on-disk catalog remains untouched.
    with monkeypatch.context() as patch:
        patch.setattr(audit_module, "files", lambda _package: sandbox.parent)
        simulated_audit = audit_catalog()
    assert simulated_audit["total_symbols"] == len(entries)
    assert simulated_audit["draft_count"] == len(entries)
    assert simulated_audit["hard_errors"] == 0
    assert simulated_audit["without_physical_part"] == []
    assert {item["id"] for item in simulated_audit["entries"]} == ids
    for item, row in zip(scene.circuit.components, manifest["components"], strict=True):
        original = scene.symbols_by_part[item.part_id]
        assert row["symbol_id"] == original.identifier
        assert row["reference"] == item.reference
        assert row["pins"] == [
            {"number": number, "x_um": point.x, "y_um": point.y}
            for number, point in item.pin_positions(original).items()
        ]
    for diagnostic in (False, True):
        visual = render_review_svg(scene, layout, diagnostic=diagnostic)
        validate_sheet_svg(visual, scene, manifest, diagnostic=diagnostic)
        assert visual == render_review_svg(scene, layout, diagnostic=diagnostic)


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


def test_all_current_drawn_vector_groups_equal_transformed_catalog_primitives():
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
