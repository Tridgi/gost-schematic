"""Generate a 15-family GOST 2.723-68 review sheet, manifest and collision SVG.

All components are draft. The nominal values belong to the example, not to
the authoritative part catalog. Fonts are externally installed with permission.
"""

import argparse
import json
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.core.geometry import Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.standards.type_a_font import inspect_type_a_font

VARIANTS = (
    "inductor.air_core", "inductor.ferromagnetic", "inductor.gapped_core",
    "inductor.ferrite", "inductor.magnetodielectric",
    "inductor.trim_magnetodielectric", "inductor.trim_copper",
    "inductor.tapped", "inductor.double_tapped", "inductor.sliding_contact",
    "inductor.double_sliding", "inductor.variable",
    "choke.air_core", "choke.ferromagnetic", "choke.ferrite",
)


def build_review(output: Path, font_file: Path, family: str) -> dict[str, object]:
    font = inspect_type_a_font(font_file, family=family, h_um=3500)
    spec_root = files("gost_schematic").joinpath("catalog/inductors")
    variants = [
        load_inductor(Path(str(spec_root.joinpath(f"{name}.json"))))
        for name in VARIANTS
    ]
    components = []
    symbols = {}
    items = []
    for index, item in enumerate(variants):
        reference = f"L{index + 1}"
        part = item.part
        symbols[part.identifier] = item.symbol
        pos = Point((index % 3) * 54000, (index // 3) * 38000)
        nominal = Quantity.from_unit(str(33 + index), Unit.MICROHENRY)
        components.append(ComponentInstance(
            reference, part.identifier, pos, nominal=nominal,
        ))
        items.append({
            "reference": reference, "part_id": part.identifier,
            "core": item.spec.core.value,
            "adjustment": item.spec.adjustment.value,
            "pins": [
                {"number": pin.number, "name": pin.name}
                for pin in part.pins
            ],
            "source_standard": "ГОСТ 2.723-68",
            "normative_relation": item.spec.normative_relation.value,
            "normative_basis": item.spec.normative_basis,
            "approval": "draft",
        })
    circuit = Circuit(tuple(components), ())
    placement = layout_sheet(circuit, symbols, font.style, PillowTextMeasurer())
    if not placement.valid:
        issues = [f"{d.code}: {d.message}" for d in placement.diagnostics
                  if d.severity.value == "error"]
        raise RuntimeError("Cannot render collision-free sheet: " + "; ".join(issues))
    output.mkdir(parents=True, exist_ok=True)
    individual = output / "variants"
    individual.mkdir(parents=True, exist_ok=True)
    for item in variants:
        # One separate, reviewable UGO per profile; no nominal in raw symbol SVG.
        for debug in (False, True):
            suffix = "-review" if debug else "-clean"
            (individual / f"{item.spec.identifier}{suffix}.svg").write_text(
                render_symbol_svg(item.symbol, review_overlay=debug),
                encoding="utf-8",
            )
    for debug in (False, True):
        name = "inductor-family-review.svg" if debug else "inductor-family-clean.svg"
        (output / name).write_text(
            render_sheet_svg(circuit, symbols, placement, review_overlay=debug),
            encoding="utf-8",
        )
    manifest = {
        "schema_version": 1, "status": "draft",
        "font_face": list(font.reported_face),
        "font_sha256": font.style.font_sha256,
        "font_cap_height_mm": "3.5",
        "items": items,
        "diagnostics": [
            {"code": d.code, "severity": d.severity.value, "subject": d.subject}
            for d in placement.diagnostics
        ],
        "warning": (
            "Source standard is active. This review is NOT a certified GOST "
            "symbol library and does not include transformers or three-phase reactors."
        ),
    }
    (output / "inductor-family-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/inductors"))
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="OpenGost Type A")
    args = parser.parse_args(argv)
    result = build_review(args.output_dir, args.font_file, args.font_family)
    print(f"Created {len(result['items'])} variant specimens in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
