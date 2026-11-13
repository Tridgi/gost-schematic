"""Render A4/A3 1:1 DRAFT page specimens with the known six-part circuit.

Usage:
  python -m examples.review_formatted_sheet \
    --font-file /path/to/OpenGostTypeA.ttf \
    --output-dir output/formatted-sheet-review

Images/fonts are NOT embedded. The title-block requisites are not approved.
"""
import argparse
import json
from pathlib import Path

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.formatted_sheet import PageProfile, compose_formatted_sheet
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.external_wire_checks import validate_external_wires


def generate(
    output_dir: Path,
    font_file: Path,
    *,
    font_family: str = "OpenGost Type A",
) -> dict[str, object]:
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    issues = validate_external_wires(circuit, graph, parts, symbols)
    if issues:
        raise ValueError("Refusing invalid authored wiring: " + ", ".join(
            f"{issue.code}:{issue.subject}" for issue in issues
        ))
    style = inspect_type_a_font(font_file, family=font_family, h_um=3500).style
    by_part = {
        part_id: symbols[part.symbol_id] for part_id, part in parts.items()
    }
    original_clean = render_external_wire_sheet(
        circuit, graph, by_part, style, PillowTextMeasurer(),
    )
    original_diag = render_external_wire_sheet(
        circuit, graph, by_part, style, PillowTextMeasurer(), diagnostic=True,
    )

    profiles = (
        ("a4-portrait", PageProfile("A4", "portrait")),
        ("a3-landscape", PageProfile("A3", "landscape")),
        ("a3-portrait", PageProfile("A3", "portrait")),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    sheets: list[dict[str, object]] = []
    for name, profile in profiles:
        clean = compose_formatted_sheet(original_clean, profile)
        diagnostic = compose_formatted_sheet(
            original_diag, profile, diagnostic=True, offset_um=clean.offset_um,
        )
        output_names = (
            f"{name}-clean.svg",
            f"{name}-diagnostic.svg",
        )
        (output_dir / output_names[0]).write_text(clean.svg, encoding="utf-8")
        (output_dir / output_names[1]).write_text(
            diagnostic.svg, encoding="utf-8",
        )
        sheets.append({
            "format": profile.format,
            "orientation": profile.orientation,
            "mode": profile.mode,
            "dimensions_um": list(profile.dimensions_um),
            "frame_um": [
                profile.frame_um.min_x, profile.frame_um.min_y,
                profile.frame_um.max_x, profile.frame_um.max_y,
            ],
            "form_1_um": [
                profile.title_um.min_x, profile.title_um.min_y,
                profile.title_um.max_x, profile.title_um.max_y,
            ],
            "content_viewport_um": [
                clean.placed_viewport_um.min_x,
                clean.placed_viewport_um.min_y,
                clean.placed_viewport_um.max_x,
                clean.placed_viewport_um.max_y,
            ],
            "offset_um": list(clean.offset_um),
            "files": list(output_names),
        })
    report: dict[str, object] = {
        "schema_version": 1,
        "status": "DRAFT_VISUAL_REVIEW_ONLY",
        "not_gost_approved": True,
        "standard_reference": "GOST R 2.104-2023 annex B.1; Issue #35",
        "font": {
            "family": style.font_family,
            "sha256": style.font_sha256,
            "source": "externally installed; NOT embedded; glyph substitution possible",
        },
        "components": [component.reference for component in circuit.components],
        "component_part_ids": [component.part_id for component in circuit.components],
        "net_names": [net.name for net in circuit.nets],
        "wires": len(graph.segments),
        "junctions": [[point.x, point.y] for point in graph.junctions],
        "sheets": sheets,
        "restrictions": (
            "Illustrative first-sheet grid has not received manual B.1 1:1 "
            "comparison or verified requisites. Actual wire topology and "
            "pin data are unchanged. This is not a production-approved КД."
        ),
    }
    (output_dir / "formatted-sheet-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="OpenGost Type A")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/formatted-sheet-review"),
    )
    args = parser.parse_args(argv)
    report = generate(
        args.output_dir, args.font_file, font_family=args.font_family,
    )
    print(
        f"DRAFT formatted sheets: {len(report['sheets'])} profiles, "
        f"{len(report['components'])} real symbols, {report['wires']} wires, "
        f"{len(report['junctions'])} authored junctions; not ГОСТ-approved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
