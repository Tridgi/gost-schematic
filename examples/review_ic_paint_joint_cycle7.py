"""Joint DRAFT real-model + real-PAINT Cycle7 SVG review, not a real IC.

Requires the independent unmerged PAINT #93 module on PYTHONPATH. The
dedicated CI pins both exact source revisions and real OpenGost Type A.
Creates source-verified PinRef endpoint records, separate split-unit SVGs
and a machine-readable QA manifest. NO manufacturer pinout is represented.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.ic import (
    IcKind,
    resolve_ic_pin_positions,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
from gost_schematic.electrical.ic_serde import ic_to_json
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def generate(output_dir: Path, font_file: Path) -> dict:
    from gost_schematic.rendering.ic_rectangular import render_resolved_ic

    inspection = inspect_type_a_font(font_file, h_um=3500)
    style = inspection.style
    measurer = PillowTextMeasurer()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "approval": "DRAFT",
        "pinout_source": "SYNTHETIC_TEST_ONLY_NOT_A_MANUFACTURER_PART",
        "elektrik_pr": 97,
        "paint_pr": 93,
        "paint_snapshot_sha": "f8f9dc4c1fd8266b807dea9d6f268d971bec8d7a",
        "eskd_pr": 95,
        "font_sha256": style.font_sha256,
        "cap_height_um": inspection.measured_cap_height_um,
        "cases": {},
    }
    for count, kind in (
        (8, IcKind.ANALOG), (14, IcKind.DIGITAL),
        (40, IcKind.DIGITAL), (64, IcKind.DIGITAL),
    ):
        source = synthetic_ic(count, kind)
        reference = kind.reference_prefix + "1"
        nets = (Net("SIGNAL", (PinRef(reference, "1"),)),)
        if count > 4:
            nets += (Net("VDD", (PinRef(reference, str(count - 1)),)),)
        circuit = Circuit(
            (ComponentInstance(reference, source.device.identifier),), nets,
        )
        validate_ic_circuit(source.device, circuit, reference)
        binding = propose_ic_paint_binding(source, style, measurer)
        positions = resolve_ic_pin_positions(
            source.device, binding.record.specs, binding.record.placements,
        )
        binding.verify_endpoints()
        key = f"TEST_IC_{kind.value.upper()}_{count}"
        (output_dir / f"{key}.json").write_text(
            ic_to_json(binding.record), encoding="utf-8",
        )
        case = {
            "component_instance_count": len(circuit.components),
            "physical_pin_count": count,
            "logical_unit_count": len(source.device.units),
            "nets": {
                net.name: [
                    {"reference": pin.reference, "number": pin.number}
                    for pin in net.members
                ] for net in circuit.nets
            },
            "pinrefs": {
                f"{pin.reference}:{pin.number}": [point.x, point.y]
                for pin, point in sorted(
                    positions.items(), key=lambda item: int(item[0].number),
                )
            },
            "units": [],
        }
        for unit_index, (view, placement) in enumerate(
            zip(binding.views, binding.record.placements, strict=True), start=1,
        ):
            rendered = render_resolved_ic(
                view, style, measurer, review_overlay=False, glyph_detail=True,
            )
            root = ET.fromstring(rendered.svg)
            lines = root.findall(
                f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
            )
            assert len(lines) == len(view.pins)
            for line in lines:
                ref = PinRef(placement.component_ref, line.get("data-pin-number"))
                expected = positions[ref]
                assert line.get("x2") == format_mm(expected.x)
                assert line.get("y2") == format_mm(expected.y)
            filename = f"{key}-unit{unit_index}.svg"
            (output_dir / filename).write_text(rendered.svg, encoding="utf-8")
            diagnostic = render_resolved_ic(
                view, style, measurer, review_overlay=True, glyph_detail=True,
            )
            assert diagnostic.pin_anchors == rendered.pin_anchors
            diagnostic_name = f"{key}-unit{unit_index}-review.svg"
            (output_dir / diagnostic_name).write_text(
                diagnostic.svg, encoding="utf-8",
            )
            case["units"].append({
                "unit_id": placement.unit_id,
                "refdes": view.reference,
                "filename": filename,
                "svg_sha256": hashlib.sha256(
                    rendered.svg.encode("utf-8"),
                ).hexdigest(),
                "diagnostic_filename": diagnostic_name,
                "diagnostic_svg_sha256": hashlib.sha256(
                    diagnostic.svg.encode("utf-8"),
                ).hexdigest(),
                "physical_numbers": [p.number for p in view.pins],
                "outer_frame_um": [
                    view.body.min_x, view.body.min_y,
                    view.body.max_x, view.body.max_y,
                ],
                "measured_glyph_boxes": len(rendered.glyph_ink),
            })
        manifest["cases"][key] = case
    (output_dir / "joint-ic-qa-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output_dir, args.font_file)
    print(json.dumps({
        "approval": result["approval"],
        "cases": list(result["cases"]),
        "font_sha256": result["font_sha256"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
