"""Generate reproducible SVG catalog and deliberately-invalid overlap specimens.

Usage:
  python examples/review_full_sheet.py --font-file /path/to/font.ttf \
    --font-family 'OpenGost Type A' --type-a --output-dir output/rendering-review

Font binaries are never embedded or committed. SVG viewers MUST use that face.
"""
import argparse
import json
from pathlib import Path
from runpy import run_path

from gost_schematic.engines.annotation.metrics import PillowTextMeasurer, font_sha256
from gost_schematic.model.annotations import TextStyle
from gost_schematic.rendering.review_sheet import (
    build_catalog_review_scene,
    build_overlap_review_scene,
    layout_review_scene,
    render_review_svg,
    review_collisions,
    review_manifest,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font


def generate(output_dir: Path, font_file: Path, family: str, *, type_a: bool) -> dict:
    if type_a:
        style = inspect_type_a_font(font_file, family=family, h_um=3500).style
    else:
        style = TextStyle(
            str(font_file), family, em_height_um=3500, clearance_um=500,
            font_sha256=font_sha256(str(font_file)),
        )
    measurer = PillowTextMeasurer()
    scene = build_catalog_review_scene()
    # The example also runs as "python examples/review_full_sheet.py": repo-root
    # scripts/ is not importable as a package in that invocation.
    audit_namespace = run_path(
        str(Path(__file__).resolve().parents[1] / "scripts" / "audit_symbol_catalog.py")
    )
    audit = audit_namespace["audit_catalog"]()
    reported = sorted(
        (row["id"], row["revision"], row["source"]) for row in audit["entries"]
    )
    discovered = sorted(
        (scene.symbols_by_part[component.part_id].identifier,
         scene.symbols_by_part[component.part_id].revision, source)
        for component, source in zip(
            scene.circuit.components, scene.source_paths, strict=True,
        )
    )
    if (
        audit["hard_errors"] != 0
        or audit["draft_count"] != audit["total_symbols"]
        or audit["without_physical_part"]
        or len(scene.circuit.components) != audit["total_symbols"]
        or discovered != reported
    ):
        raise RuntimeError(
            "SVG gallery does not match the approved-scope structural catalog audit: "
            f"gallery={len(scene.circuit.components)}, "
            f"audit={audit['total_symbols']}, "
            f"draft={audit['draft_count']}, errors={audit['hard_errors']}, "
            f"missing={audit['without_physical_part']}"
        )
    layout = layout_review_scene(scene, style, measurer)
    if not layout.valid or review_collisions(scene, layout):
        details = [f"{issue.code}: {issue.message}" for issue in layout.diagnostics]
        details.extend(
            f"{c.kind}: {c.first} / {c.second}" for c in review_collisions(scene, layout)
        )
        raise RuntimeError("Unexpected collision in DRAFT catalog specimen: " + "; ".join(
            details
        ))

    bad = build_overlap_review_scene()
    bad_layout = layout_review_scene(bad, style, measurer)
    if bad_layout.valid or not any(
        c.kind == "symbol-aabb" for c in review_collisions(bad, bad_layout)
    ):
        raise RuntimeError("Broken negative control: overlap was not detected")

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, target, placement, diagnostic in (
        ("catalog-clean.svg", scene, layout, False),
        ("catalog-diagnostic.svg", scene, layout, True),
        ("overlap-diagnostic.svg", bad, bad_layout, True),
    ):
        (output_dir / filename).write_text(
            render_review_svg(target, placement, diagnostic=diagnostic),
            encoding="utf-8",
        )
    manifest = review_manifest(scene, layout)
    manifest["catalog_audit"] = {
        "total_symbols": audit["total_symbols"],
        "draft_count": audit["draft_count"],
        "hard_errors": audit["hard_errors"],
        "source_match": True,
    }
    manifest["font"] = {
        "family": family,
        "sha256": style.font_sha256,
        "source": "external licensed font; not embedded",
        "type_a_height_calibrated": type_a,
    }
    manifest["negative_control"] = {
        "layout_valid": bad_layout.valid,
        "detected_aabb_collisions": len(review_collisions(bad, bad_layout)),
        "diagnostic_codes": [item.code for item in bad_layout.diagnostics],
    }
    manifest["artifacts"] = [
        "catalog-clean.svg", "catalog-diagnostic.svg", "overlap-diagnostic.svg"
    ]
    (output_dir / "review-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="DejaVu Sans")
    parser.add_argument("--type-a", action="store_true",
                        help="Calibrate actual uppercase height to 3.5 mm")
    parser.add_argument("--output-dir", type=Path, default=Path("output/rendering-review"))
    args = parser.parse_args(argv)
    result = generate(
        args.output_dir, args.font_file, args.font_family, type_a=args.type_a,
    )
    print(f"DRAFT specimens: {len(result['components'])} symbols, "
          f"{len(result['labels'])} labels, {len(result['aabb_collisions'])} "
          f"valid-scene AABB collisions")
    print(f"Invalid control: {result['negative_control']['detected_aabb_collisions']} "
          f"marker(s); output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
