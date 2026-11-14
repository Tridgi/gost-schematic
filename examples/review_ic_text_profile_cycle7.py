"""DRAFT model-driven IC portrait PWM and genuine TOP/BOTTOM pose gallery.

Paired 0/90 source records share one physical Circuit.Net and identical world
PinRefs. A BLOCKED orientation writes an explicit diagnostic entry instead of
silently rotating a whole UGO or manufacturing fake geometry.
Requires pinned PAINT #93 and SHA-checked OpenGost Type A in CI.
"""
import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.ic import (
    IcBodyAxis,
    IcKind,
    IcPortLayout,
    IcTextAngle,
    resolve_ic_pin_positions,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_graphic_revision import (
    revise_ic_text_orientation,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_paint_bridge import (
    bind_ic_paint_text_only,
    propose_ic_paint_binding,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_to_json
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font


def _circuit(record: IcLibraryRecord) -> Circuit:
    number = record.device.package.pin_count
    reference = record.placements[0].component_ref
    return Circuit(
        (ComponentInstance(reference, record.device.identifier),),
        (
            Net("PWM", (PinRef(reference, "1"),)),
            Net("VDD", (PinRef(reference, str(number - 1)),)),
            Net("OC", (PinRef(reference, str(number - 2)),)),
        ),
    )


def _portrait(record: IcLibraryRecord) -> IcLibraryRecord:
    return IcLibraryRecord(
        record.device,
        tuple(replace(
            s, main_field="PWM", body=Box(0, 0, 60000, 300000),
            profile=replace(s.profile, body_axis=IcBodyAxis.PORTRAIT),
            revision=s.revision + 1,
        ) for s in record.specs),
        record.placements,
    )


def _top_bottom(record: IcLibraryRecord) -> IcLibraryRecord:
    specs = []
    for spec in record.specs:
        width = (len(spec.rows) + 5) * 5000
        body = Box(0, 0, width, 65000)
        rows = []
        for index, row in enumerate(spec.rows, 1):
            kind = record.device.pin_map[row.number].electrical_type.value
            side = Side.TOP if kind in ("input", "power_input") else Side.BOTTOM
            rows.append(replace(
                row, side=side,
                anchor=Point(
                    index * 5000,
                    body.min_y - 10000 if side is Side.TOP else body.max_y + 10000,
                ),
            ))
        specs.append(replace(
            spec, main_field="PWM", body=body, rows=tuple(rows),
            profile=replace(spec.profile, port_layout=IcPortLayout.TOP_BOTTOM),
            revision=spec.revision + 1,
        ))
    return IcLibraryRecord(record.device, tuple(specs), record.placements)


def generate(output_dir: Path, font_file: Path) -> dict:
    from gost_schematic.rendering.ic_rectangular import render_resolved_ic

    verification = inspect_type_a_font(font_file, h_um=3500)
    style = verification.style
    measurer = PillowTextMeasurer()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "approval": "DRAFT_NOT_ESKD_APPROVED",
        "font_sha256": style.font_sha256,
        "paint_sha": "db53e0ab89bb23f555badc2def41ea9895a5d64c",
        "cases": {},
    }
    for kind, count in (
        (IcKind.ANALOG, 8), (IcKind.DIGITAL, 14),
        (IcKind.DIGITAL, 40), (IcKind.DIGITAL, 64),
    ):
        name = f"{kind.reference_prefix}{count}"
        result["cases"][name] = {}
        for layout, record in (
            ("portrait_left_right", _portrait(synthetic_ic(count, kind))),
            ("genuine_top_bottom", _top_bottom(synthetic_ic(count, kind))),
        ):
            # PAINT is allowed to PROPOSE a new explicit graphic revision.
            # No existing Circuit, wire graph or physical terminal is edited.
            measured = propose_ic_paint_binding(record, style, measurer)
            original = measured.record
            circuit = _circuit(original)
            validate_ic_circuit(original.device, circuit, kind.reference_prefix + "1")
            switched = revise_ic_text_orientation(
                original, IcTextAngle.VERTICAL,
            )
            delta = validate_ic_graphic_revision(
                original, switched, circuit=circuit,
            )
            assert not delta.moved
            assert ic_to_json(original) != ic_to_json(switched)
            original_points = resolve_ic_pin_positions(
                original.device, original.specs, original.placements,
            )
            switch_points = resolve_ic_pin_positions(
                switched.device, switched.specs, switched.placements,
            )
            assert original_points == switch_points
            group = {
                "physical_pin_count": count,
                "logical_unit_count": len(original.device.units),
                "physical_component_count": len(circuit.components),
                "circuit_net_signatures": [
                    [n.name, [[p.reference, p.number] for p in n.members]]
                    for n in circuit.nets
                ],
                "world_pin_points_um": {
                    f"{p.reference}.{p.number}": [point.x, point.y]
                    for p, point in sorted(
                        original_points.items(),
                        key=lambda item: int(item[0].number),
                    )
                },
                "angles": {},
            }
            for angle, model in ((0, original), (90, switched)):
                fname = f"{name}-{layout}-function{angle}.json"
                source_text = ic_to_json(model)
                (output_dir / fname).write_text(source_text, encoding="utf-8")
                text_data = {
                    "source_model": fname,
                    "model_sha256": hashlib.sha256(
                        source_text.encode("utf-8"),
                    ).hexdigest(),
                    "same_real_pinrefs": True,
                    "same_circuit_nets": True,
                    "per_unit_render": [],
                }
                try:
                    layout_binding = (
                        measured if angle == 0 else
                        bind_ic_paint_text_only(measured, model)
                    )
                    # Bind the rotated whole word to the *original* body and
                    # physical lead positions; no dimension reproposal.
                    same_points = resolve_ic_pin_positions(
                        layout_binding.record.device,
                        layout_binding.record.specs,
                        layout_binding.record.placements,
                    )
                    if same_points != original_points:
                        raise ValueError("IC_TEXT_RENDER_MOVED_PHYSICAL_PINREF")
                    for index, unit in enumerate(layout_binding.views, 1):
                        rendered = render_resolved_ic(
                            unit, style, measurer, glyph_detail=True,
                        )
                        assert {n: point for n, point in rendered.pin_anchors} == {
                            pin.pin_id: pin.anchor for pin in unit.pins
                        }
                        root = ET.fromstring(rendered.svg)
                        lines = root.findall(
                            ".//{http://www.w3.org/2000/svg}"
                            "g[@data-layer='ic-physical-pin-leads']/"
                            "{http://www.w3.org/2000/svg}line"
                        )
                        assert len(lines) == len(unit.pins)
                        seen = set()
                        physical_ref = original.placements[0].component_ref
                        for line in lines:
                            number = line.get("data-pin-number")
                            assert number is not None and number not in seen
                            seen.add(number)
                            expected = original_points[PinRef(physical_ref, number)]
                            assert line.get("x2") == format_mm(expected.x)
                            assert line.get("y2") == format_mm(expected.y)
                        assert seen == {p.number for p in unit.pins}
                        filename = (
                            f"{name}-{layout}-function{angle}-unit{index}.svg"
                        )
                        (output_dir / filename).write_text(
                            rendered.svg, encoding="utf-8",
                        )
                        text_data["per_unit_render"].append({
                            "status": "DRAFT_SVG",
                            "filename": filename,
                            "physical_pin_count": len(rendered.pin_anchors),
                        })
                except ValueError as exc:
                    text_data["per_unit_render"].append({
                        "status": "BLOCKED",
                        "reason": str(exc),
                    })
                group["angles"][str(angle)] = text_data
            result["cases"][name][layout] = group
    (output_dir / "ic-pwm-text-orientations-manifest.json").write_text(
        json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cases = generate(args.output_dir, args.font_file)
    print(json.dumps({
        "approval": cases["approval"],
        "cases": list(cases["cases"]),
        "render_matrix": {
            name: {
                layout: {
                    angle: value["per_unit_render"]
                    for angle, value in layout_value["angles"].items()
                }
                for layout, layout_value in profiles.items()
            }
            for name, profiles in cases["cases"].items()
        },
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
