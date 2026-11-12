"""Fail-closed structural visual gate for the exported DRAFT SVG/PNG specimens.

This checks catalog-to-SVG primitive fidelity, identities, contacts, viewer-font
provenance and artifact presence. It does NOT certify ГОСТ conformity or
prove pixel-perfect rasterization in third-party SVG viewers.
"""
import argparse
import json
import struct
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.engines.annotation.metrics import font_sha256
from gost_schematic.rendering.primitives import draw_primitive
from gost_schematic.rendering.review_sheet import (
    build_catalog_review_scene,
    discover_catalog_entries,
)

SVG = "{http://www.w3.org/2000/svg}"
FOCUS = ("capacitor.electrolytic", "capacitor.polarized")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _read_svg(path: Path) -> ET.Element:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"Cannot read valid vector SVG: {path}") from error
    _require(root.tag == SVG + "svg", f"Invalid SVG root: {path}")
    _require(not root.findall(f".//{SVG}image"), f"Raster image found: {path}")
    _require(not root.findall(f".//{SVG}foreignObject"),
             f"Non-vector object found: {path}")
    _require(root.get("data-approval-status") == "DRAFT",
             f"Missing DRAFT marker: {path}")
    return root


def _primitive_signature(element: ET.Element) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (element.tag.rsplit("}", maxsplit=1)[-1], tuple(sorted(element.attrib.items())))


def _expected_primitives(symbol, component=None):
    group = ET.Element("g")
    for primitive in symbol.graphics:
        if component is not None:
            primitive = component.transform.primitive(primitive, component.origin)
        draw_primitive(group, primitive)
    return tuple(_primitive_signature(item) for item in group)


def _assert_primitives(actual: ET.Element, expected: tuple, identifier: str) -> None:
    found = tuple(_primitive_signature(item) for item in actual)
    _require(found == expected, f"Original vector primitives changed or missing: {identifier}")


def validate_sheet_svg(
    xml: str,
    scene,
    manifest: dict,
    *,
    diagnostic: bool,
) -> None:
    """Compare *drawn SVG primitives*, not just the manifest's symbol names."""
    root = ET.fromstring(xml)
    _require(root.tag == SVG + "svg", "Not an SVG")
    _require(root.get("data-approval-status") == "DRAFT", "Missing sheet DRAFT marker")
    _require(root.get("data-specimen") == "catalog", "Wrong sheet specimen")
    _require(root.get("data-view") == ("diagnostic" if diagnostic else "clean"),
             "Wrong sheet view")
    _require(not root.findall(f".//{SVG}image"), "Raster-replaced UGO detected")
    groups = root.findall(f".//{SVG}g[@data-layer='symbols']")
    _require(len(groups) == len(scene.circuit.components), "Missing or duplicated UGO")
    for group, component in zip(groups, scene.circuit.components, strict=True):
        _require(group.get("data-reference") == component.reference,
                 f"Wrong refdes or order: {component.reference}")
        original = scene.symbols_by_part[component.part_id]
        _assert_primitives(
            group, _expected_primitives(original, component), original.identifier,
        )

    font = manifest["font"]
    labels = manifest["labels"]
    annotations = root.findall(f".//{SVG}text[@data-layer='annotations']")
    _require(len(annotations) == len(labels), "Wrong number of SVG text labels")
    for painted, measured in zip(annotations, labels, strict=True):
        _require(painted.get("data-owner") == measured["owner"],
                 "Wrong annotation owner")
        _require(painted.get("data-key") == measured["key"],
                 "Wrong annotation role")
        _require(painted.text == measured["text"], "Text changed after measuring")
        _require(painted.get("font-family") == font["family"],
                 "SVG font family differs from measured font")
        _require(painted.get("data-font-sha256") == font["sha256"],
                 "SVG text lacks source font fingerprint")
        _require("transform" not in painted.attrib, "Annotation must remain upright")

    markers = root.findall(
        f".//{SVG}g[@data-layer='collision-markers']/{SVG}rect"
    )
    _require(not markers, "Unexpected collision markers in valid gallery")
    overlays = root.findall(f".//{SVG}g[@data-layer='geometry-review']")
    _require(bool(overlays) == diagnostic, "Missing/unexpected geometry overlay")
    if not diagnostic:
        _require(root.find(f".//{SVG}g[@data-layer='collision-markers']") is None,
                 "Clean SVG contains review-only collision layer")


def validate_focus_svg(xml: str, entry, *, diagnostic: bool) -> None:
    root = ET.fromstring(xml)
    identifier = entry.symbol.identifier
    _require(root.tag == SVG + "svg", f"{identifier}: not SVG")
    _require(root.get("data-symbol-id") == identifier, "Focus ID mismatch")
    _require(root.get("data-symbol-revision") == str(entry.symbol.revision),
             "Focus revision mismatch")
    _require(root.get("data-catalog-source") == entry.source, "Focus source mismatch")
    _require(root.get("data-approval-status") == "DRAFT", "Focus not marked DRAFT")
    _require(root.get("data-view") == ("diagnostic" if diagnostic else "clean"),
             "Focus view mismatch")
    _require(not root.findall(f".//{SVG}image"), "Focus uses an image replacement")
    groups = root.findall(f"./{SVG}g")
    _require(len(groups) == 1, f"{identifier}: expected one original vector group")
    _assert_primitives(groups[0], _expected_primitives(entry.symbol), identifier)
    if diagnostic:
        _require(bool(root.findall(f"./{SVG}rect")), "Missing focus keepout")
        _require(len(root.findall(f"./{SVG}circle")) == len(entry.symbol.pins),
                 "Missing pin markers in diagnostic focus")
    else:
        _require(not root.findall(f"./{SVG}rect"),
                 "Clean focus contains diagnostic keepouts")


def _validate_png(path: Path) -> None:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ValueError(f"Missing PNG preview: {path}") from error
    _require(content[:8] == b"\x89PNG\r\n\x1a\n", f"Not a PNG preview: {path}")
    _require(len(content) >= 33 and content[12:16] == b"IHDR",
             f"PNG has no IHDR: {path}")
    width, height = struct.unpack(">II", content[16:24])
    _require(0 < width <= 10000 and 0 < height <= 10000,
             f"Invalid PNG dimensions: {path}")


def validate_artifacts(
    output_dir: Path,
    *,
    font_file: Path,
    min_symbols: int = 19,
) -> dict[str, object]:
    """Inspect live exported artifacts against the actual installed catalog."""
    if type(min_symbols) is not int or min_symbols < 1:
        raise ValueError("min_symbols must be a positive integer")
    data = json.loads((output_dir / "review-manifest.json").read_text(encoding="utf-8"))
    scene = build_catalog_review_scene()
    entries = discover_catalog_entries()
    count = len(scene.circuit.components)
    _require(count >= min_symbols, f"Only {count} UGO; expected at least {min_symbols}")
    _require(data["catalog_size"] == count, "Manifest catalog count mismatch")
    _require(len(data["components"]) == count, "Manifest dropped catalog entries")
    _require(data["catalog_audit"]["total_symbols"] == count,
             "Structural audit inventory mismatch")
    _require(data["catalog_audit"]["draft_count"] == count,
             "Non-DRAFT symbol found")
    _require(data["catalog_audit"]["hard_errors"] == 0,
             "Catalog has structural errors")
    _require(data["catalog_audit"]["source_match"] is True,
             "Manifest did not match catalog audit")
    _require(data["approval"] == "DRAFT" and data["not_gost_certified"] is True,
             "Cannot treat review gallery as GOST approval")
    _require(data["layout_valid"] is True and not data["aabb_collisions"],
             "Gallery has unchecked collisions or invalid layout")
    _require(scene.circuit.nets == (), "Preview must not fabricate nets")
    refs = [item.reference for item in scene.circuit.components]
    _require(len(refs) == len(set(refs)), "Duplicate positional designators")
    _require(all(item.symbol.status.value == "draft" for item in entries),
             "Discovered an approved or invalid symbol")
    _require(len(scene.source_paths) == count, "Missing source file mapping")
    for index, (component, reported) in enumerate(
        zip(scene.circuit.components, data["components"], strict=True)
    ):
        original = scene.symbols_by_part[component.part_id]
        _require(reported["part_id"] == component.part_id
                 and reported["symbol_id"] == original.identifier
                 and reported["reference"] == component.reference,
                 f"Wrong catalog identity at position {index}")
        _require(reported["catalog_source"] == scene.source_paths[index]
                 and reported["symbol_revision"] == original.revision,
                 f"Source/revision mismatch: {component.reference}")
        _require(reported["symbol_status"] == "draft", "UGO status is not DRAFT")
        pins = component.pin_positions(original)
        _require(
            {pin["number"]: (pin["x_um"], pin["y_um"]) for pin in reported["pins"]}
            == {number: (point.x, point.y) for number, point in pins.items()},
            f"Changed physical pin positions: {component.reference}",
        )
        _require(
            reported["nominal_si"] == (
                component.nominal.to_record() if component.nominal else None
            ),
            f"Preview nominal was mutated: {component.reference}",
        )

    font = data["font"]
    _require(font["source"] == "external licensed font; not embedded",
             "Font provenance changed")
    _require(font["type_a_height_calibrated"] is True,
             "Expected calibrated Type A font")
    _require(font["sha256"] == font_sha256(str(font_file)),
             "Font file changed since measuring SVG text")

    clean = (output_dir / "catalog-clean.svg").read_text(encoding="utf-8")
    review = (output_dir / "catalog-diagnostic.svg").read_text(encoding="utf-8")
    validate_sheet_svg(clean, scene, data, diagnostic=False)
    validate_sheet_svg(review, scene, data, diagnostic=True)

    bad = _read_svg(output_dir / "overlap-diagnostic.svg")
    _require(bad.get("data-specimen") == "invalid-overlap",
             "Missing invalid control scene")
    _require(bool(bad.findall(
        f".//{SVG}g[@data-layer='collision-markers']/{SVG}rect"
    )), "Negative collision control did not render markers")

    by_id = {item.symbol.identifier: item for item in entries}
    _require(all(item in by_id for item in FOCUS),
             "Missing electrolytic or general polarized capacitor")
    _require(by_id[FOCUS[0]].symbol.graphics != by_id[FOCUS[1]].symbol.graphics,
             "Electrolytic silently replaced by generic polarized graphics")
    focus_rows = {item["symbol_id"]: item for item in data["focus_symbols"]}
    _require(set(focus_rows) == set(FOCUS), "Missing/duplicate focused capacitor")
    for identifier in FOCUS:
        entry = by_id[identifier]
        record = focus_rows[identifier]
        _require(record["revision"] == entry.symbol.revision
                 and record["catalog_source"] == entry.source,
                 "Focus manifest revision/source mismatch")
        _require(record["graphics_primitives"] == len(entry.symbol.graphics),
                 "Focus manifest primitive count mismatch")
        _require(record["pin_numbers"] == [pin.number for pin in entry.part.pins],
                 "Focus manifest physical pin mismatch")
        _require(record["reference"] in refs, "Focus refdes does not exist on sheet")
        variant = identifier.split(".", maxsplit=1)[1]
        for view in ("clean", "diagnostic"):
            filename = f"capacitor-{variant}-{view}.svg"
            validate_focus_svg(
                (output_dir / filename).read_text(encoding="utf-8"),
                entry,
                diagnostic=view == "diagnostic",
            )

    expected_svg = {
        "catalog-clean.svg", "catalog-diagnostic.svg", "overlap-diagnostic.svg",
        *(f"capacitor-{variant}-{view}.svg"
          for variant in ("electrolytic", "polarized")
          for view in ("clean", "diagnostic")),
    }
    _require(set(data["artifacts"]) == expected_svg,
             "Manifest lacks one or more SVG files")
    for name in sorted(expected_svg):
        _validate_png(output_dir / name.replace(".svg", ".png"))

    report = {
        "schema_version": 1,
        "status": "DRAFT_VISUAL_REVIEW_ONLY",
        "gost_certified": False,
        "catalog_symbols": count,
        "unique_references": count,
        "geometry_source": "versioned UGO catalog, no raster substitutions",
        "unexpected_aabb_collisions": 0,
        "font_family": font["family"],
        "font_sha256": font["sha256"],
        "focus": {identifier: focus_rows[identifier]["reference"] for identifier in FOCUS},
        "svg_files": len(expected_svg),
        "png_files": len(expected_svg),
        "limitations": (
            "Conservative AABB intersections; font is not embedded in SVG; "
            "external SVG viewers may substitute glyphs; manual normative "
            "comparison and acceptance still required."
        ),
    }
    (output_dir / "visual-gate.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--min-symbols", type=int, default=19)
    args = parser.parse_args(argv)
    result = validate_artifacts(
        args.output_dir, font_file=args.font_file, min_symbols=args.min_symbols,
    )
    print(
        f"Visual gate: {result['catalog_symbols']} DRAFT UGO, "
        f"{result['svg_files']} SVG + {result['png_files']} PNG, "
        f"0 unexpected AABB intersections; electrolytic "
        f"{result['focus']['capacitor.electrolytic']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
