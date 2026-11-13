"""Issue #68: measured legacy keepout versus visible-winding refdes comparison.

Read-only data: same 6-component PR62 circuit, physical pins, and 16 wires.
The original specimen_svg() and electrical golden files remain unchanged.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_end_to_end_circuit import authored_specimen, definitions, renderer_wires
from gost_schematic.core.geometry import Point
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.annotation.visual_refdes import (
    distance_ink_to_main_ugo_um,
    legacy_keepout_label_ink,
    main_ugo_graphic_bounds,
    place_refdes_near_visible_graphics,
)
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.annotations import AnnotationPlacement, AnnotationRole
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.external_wire_checks import validate_external_wires

SVG = "{http://www.w3.org/2000/svg}"


def legacy_placements(circuit, by_part, style, measurer):
    """Reconstruct the old keepout-y-2.5mm baseline using identical font ink."""
    objects = []
    for component in circuit.components:
        symbol = by_part[component.part_id]
        metrics = measurer.measure(component.reference, style)
        ink = legacy_keepout_label_ink(symbol, component, metrics)
        baseline = Point(ink.min_x - metrics.ink_box.min_x,
                         ink.max_y - metrics.ink_box.max_y)
        objects.append(AnnotationPlacement(
            component.reference, "refdes", AnnotationRole.REFDES,
            component.reference, style, baseline, ink,
            ink.expanded(style.clearance_um), None, 0,
        ))
    return tuple(objects)


def _svg(circuit, by_part, wires, placements, graph, *, review, name):
    root = ET.fromstring(render_sheet_svg(
        circuit, by_part, SheetLayout(placements, ()),
        wires=wires, review_overlay=review,
    ))
    root.set("data-policy", name)
    root.set("data-issue", "68")
    root.set("data-approval", "DRAFT")
    root.set("data-original-electrical-geometry", "untouched")
    group = ET.SubElement(root, SVG + "g", {
        "data-layer": "explicit-junctions", "stroke": "none", "fill": "#000000",
    })
    for pin in graph.junctions:
        ET.SubElement(group, SVG + "circle", {
            "data-kind": "authored-junction",
            "cx": format_mm(pin.x), "cy": format_mm(pin.y), "r": "0.55",
        })
    return ET.tostring(root, encoding="unicode") + "\n"


def _l1_closeup(svg: str, kind: str, diagnostic: bool) -> str:
    """Explicit 40x23mm crop around accepted L1; never a sheet/route edit."""
    root = ET.fromstring(svg)
    root.set("width", "40mm")
    root.set("height", "23mm")
    root.set("viewBox", "85 24 40 23")
    root.set("data-closeup", "L1")
    root.set("data-crop-only", "true")
    root.set("data-variant", kind)
    ET.SubElement(root, SVG + "title").text = (
        f"L1 {kind} ({'diagnostic' if diagnostic else 'clean'}), "
        "unapproved refdes comparison"
    )
    return ET.tostring(root, encoding="unicode") + "\n"


def _c3_and_l1(circuit, by_part, before, after):
    summary = {}
    for component in circuit.components:
        symbol = by_part[component.part_id]
        main = main_ugo_graphic_bounds(symbol, component)
        previous = next(x for x in before if x.owner == component.reference)
        proposed = next(x for x in after if x.owner == component.reference)
        summary[component.reference] = {
            "symbol_id": symbol.identifier,
            "revision": symbol.revision,
            "main_visual_bbox_mm": [
                format_mm(k) for k in
                (main.min_x, main.min_y, main.max_x, main.max_y)
            ],
            "legacy_ink_bbox_mm": [
                format_mm(k) for k in (
                    previous.ink_bounds.min_x, previous.ink_bounds.min_y,
                    previous.ink_bounds.max_x, previous.ink_bounds.max_y,
                )
            ],
            "proposed_ink_bbox_mm": [
                format_mm(k) for k in (
                    proposed.ink_bounds.min_x, proposed.ink_bounds.min_y,
                    proposed.ink_bounds.max_x, proposed.ink_bounds.max_y,
                )
            ],
            "legacy_ink_to_visual_mm": round(
                distance_ink_to_main_ugo_um(previous.ink_bounds, main) / 1000, 3,
            ),
            "proposed_ink_to_visual_mm": round(
                distance_ink_to_main_ugo_um(proposed.ink_bounds, main) / 1000, 3,
            ),
            "selected_candidate_rank": proposed.candidate_index,
        }
    return summary


def generate(output_dir: Path, font_file: Path) -> dict:
    circuit, graph = authored_specimen()
    copy_of_semantics = (circuit, graph)
    parts, symbols = definitions()
    assert not validate_external_wires(circuit, graph, parts, symbols)
    if len(graph.segments) != 16 or len(graph.junctions) != 3:
        raise ValueError("Issue68 review requires accepted PR62 live graph")
    by_part = {p: symbols[part.symbol_id] for p, part in parts.items()}
    style = inspect_type_a_font(
        font_file, family="OpenGost Type A", h_um=3500,
    ).style
    measurer = PillowTextMeasurer()
    wires = renderer_wires(graph)
    before = legacy_placements(circuit, by_part, style, measurer)
    after = place_refdes_near_visible_graphics(
        circuit, by_part, style, measurer, wires=wires,
    )
    report = {
        "schema_version": 1,
        "issue": 68,
        "status": "DRAFT_SEPARATE_REF_DESIGNATOR_PLACEMENT",
        "original_fixture_not_changed": True,
        "font_family": style.font_family,
        "font_sha256": style.font_sha256,
        "font_cap_height_mm": 3.5,
        "font_em_mm": format_mm(style.em_height_um),
        "source": "current examples/review_end_to_end_circuit.py authored_specimen",
        "original_label_policy": "body_keepout.min_y - 2.5mm baseline",
        "candidate_label_policy": "nearest free measured ink to visible winding/UGO",
        "wires": len(graph.segments),
        "junctions": [[p.x, p.y] for p in graph.junctions],
        "components": _c3_and_l1(circuit, by_part, before, after),
        "note": "Original SVG authored specimen and catalog UGO are immutable.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for key, placed in (("before", before), ("after", after)):
        for diagnostic in (False, True):
            name = f"refdes-{key}-{'diagnostic' if diagnostic else 'clean'}.svg"
            svg = _svg(circuit, by_part, wires, placed, graph,
                       review=diagnostic, name=key)
            (output_dir / name).write_text(svg, encoding="utf-8")
            closeup = f"refdes-{key}-l1-{'diagnostic' if diagnostic else 'clean'}.svg"
            (output_dir / closeup).write_text(
                _l1_closeup(svg, key, diagnostic), encoding="utf-8",
            )
    (output_dir / "refdes-distance-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if (circuit, graph) != copy_of_semantics:
        raise ValueError("Issue68 drawing mutated physical source graph")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("output/refdes-cycle6"))
    args = parser.parse_args(argv)
    report = generate(args.output_dir, args.font_file)
    l1 = report["components"]["L1"]
    print(f"Issue68 DRAFT: L1 physical ink gap {l1['legacy_ink_to_visual_mm']} mm"
          f" -> {l1['proposed_ink_to_visual_mm']} mm; "
          "16 source wires unchanged; no merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
