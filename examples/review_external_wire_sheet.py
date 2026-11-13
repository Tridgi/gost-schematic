"""Review real six-device authored wiring without post-editing SVG junction dots.

Run:
  python -m examples.review_external_wire_sheet \
    --font-file /path/to/OpenGostTypeA.ttf \
    --output-dir output/external-wire-review

The input Circuit and ExternalWireGraph are the unchanged example #29.
The result is DRAFT, with externally referenced (NOT embedded) Type A font.
"""
import argparse
import json
from pathlib import Path

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.obstacles import wire_intersects_box
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
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
        raise ValueError(
            "End-to-end authored external wires were modified or invalid: "
            + "; ".join(f"{item.code} {item.message}" for item in issues)
        )
    style = inspect_type_a_font(font_file, family=font_family, h_um=3500).style
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    clean = render_external_wire_sheet(
        circuit, graph, by_part, style, PillowTextMeasurer(),
    )
    diagnostic = render_external_wire_sheet(
        circuit, graph, by_part, style, PillowTextMeasurer(), diagnostic=True,
    )
    if not clean.layout.valid or not diagnostic.layout.valid:
        raise RuntimeError("Cannot export an invalid annotation layout")
    if any(
        wire_intersects_box(wire, label.collision_bounds)
        for wire in clean.wires for label in clean.layout.placements
    ):
        raise RuntimeError("Text hitbox overlaps an authored external wire")

    if len(clean.wires) != len(graph.segments):
        raise RuntimeError("Lost authored wire segments")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "authored-wire-clean.svg").write_text(
        clean.svg, encoding="utf-8",
    )
    (output_dir / "authored-wire-diagnostic.svg").write_text(
        diagnostic.svg, encoding="utf-8",
    )

    report: dict[str, object] = {
        "schema_version": 1,
        "status": "DRAFT_VISUAL_REVIEW_ONLY",
        "not_gost_approved": True,
        "font": {
            "family": style.font_family,
            "sha256": style.font_sha256,
            "source": "external, NOT embedded; viewer substitution is possible",
        },
        "component_references": [item.reference for item in circuit.components],
        "component_part_ids": [item.part_id for item in circuit.components],
        "wire_count": len(graph.segments),
        "wires": [
            {
                "index": index,
                "start_um": [segment.start.x, segment.start.y],
                "end_um": [segment.end.x, segment.end.y],
                "net_name": segment.net_name,
            }
            for index, segment in enumerate(graph.segments)
        ],
        "junction_count": len(graph.junctions),
        "explicit_junctions_um": [
            [point.x, point.y] for point in graph.junctions
        ],
        "labels": [
            {
                "owner": label.owner,
                "key": label.key,
                "text": label.text,
                "baseline_um": [label.baseline.x, label.baseline.y],
                "hitbox_um": [
                    label.collision_bounds.min_x, label.collision_bounds.min_y,
                    label.collision_bounds.max_x, label.collision_bounds.max_y,
                ],
            }
            for label in clean.layout.placements
        ],
        "layout_diagnostics": [
            {
                "severity": item.severity.value,
                "code": item.code,
                "subject": item.subject,
                "message": item.message,
            }
            for item in clean.layout.diagnostics
        ],
        "restrictions": (
            "The graphic is a geometry inspection fixture, not a simulator "
            "or a certified ГОСТ/ЕСКД document. Only authored graph.junctions "
            "are marked; unmarked T/X crossings never imply a connection. "
            "Viewer must have the same font file as the manifest SHA."
        ),
    }
    (output_dir / "authored-wire-manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="OpenGost Type A")
    parser.add_argument("--output-dir", type=Path, default=Path("output/external-wire-review"))
    args = parser.parse_args(argv)
    result = generate(args.output_dir, args.font_file, font_family=args.font_family)
    print(
        f"Authored-wire SVG: {result['wire_count']} segments, "
        f"{result['junction_count']} explicit junctions, "
        f"{len(result['labels'])} measured labels; DRAFT/not ГОСТ-approved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
