"""DRAFT DA1-only genuine ELEKTRIK IC #97 + PAINT #93 vector smoke gate.

No whole-sheet SVG synthesis. A real 23/15 route is absent and not simulated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_v5.native_circuit import assemble_native_v5
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.ic import resolve_ic_pin_positions
from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.ic_rectangular import render_resolved_ic
from gost_schematic.standards.type_a_font import inspect_type_a_font

S = "{http://www.w3.org/2000/svg}"


def generate_da1_only(output: Path, font_file: Path) -> dict:
    assembly = assemble_native_v5()
    inspection = inspect_type_a_font(
        font_file, h_um=3500,
        family="OpenGost Type A TT", require_family_match=True,
    )
    style = inspection.style
    measurer = PillowTextMeasurer()
    bridge = propose_ic_paint_binding(
        assembly.owner_ic_record, style, measurer
    )
    bridge.verify_endpoints()
    if len(bridge.views) != 1:
        raise AssertionError("DA1_ONLY_SINGLE_UNIT_EXPECTED")
    positions = resolve_ic_pin_positions(
        bridge.record.device, bridge.record.specs, bridge.record.placements
    )
    if len(positions) != 16:
        raise AssertionError("DA1_16_REAL_WORLD_ANCHORS_EXPECTED")
    output.mkdir(parents=True, exist_ok=True)
    view = bridge.views[0]
    clean = render_resolved_ic(
        view, style, measurer, review_overlay=False, glyph_detail=True
    )
    diagnostic = render_resolved_ic(
        view, style, measurer, review_overlay=True, glyph_detail=True
    )
    if clean.pin_anchors != diagnostic.pin_anchors:
        raise AssertionError("DA1_DIAGNOSTICS_CHANGED_ANCHORS")
    root = ET.fromstring(clean.svg)
    if root.get("data-function-reading-local") != "bottom_to_top":
        raise AssertionError("DA1_PWM_WRONG_READING_DIRECTION")
    lines = root.findall(
        f".//{S}g[@data-layer='ic-physical-pin-leads']/{S}line"
    )
    if len(lines) != 16:
        raise AssertionError("DA1_16_PHYSICAL_SVG_LEADS_REQUIRED")
    for line in lines:
        pin = PinRef("DA1", line.attrib["data-pin-number"])
        endpoint = positions[pin]
        if line.get("x2") != format_mm(endpoint.x):
            raise AssertionError(f"DA1_{pin.number}_PIN_X_CHANGED")
        if line.get("y2") != format_mm(endpoint.y):
            raise AssertionError(f"DA1_{pin.number}_PIN_Y_CHANGED")
    if "green" in clean.svg.lower() or "#00ff00" in clean.svg.lower():
        raise AssertionError("DA1_EDITOR_GREEN_IN_CLEAN")
    (output / "DA1-owner-clean.svg").write_text(
        clean.svg, encoding="utf-8"
    )
    (output / "DA1-owner-diagnostic.svg").write_text(
        diagnostic.svg, encoding="utf-8"
    )
    manifest = {
        "scope": "DA1_ONLY_NOT_FULL_23_COMPONENT_SCHEMATIC",
        "status": "DRAFT_NO_PRINT_RELEASE",
        "source_circuit_parts": len(assembly.circuit.components),
        "source_circuit_nets": len(assembly.circuit.nets),
        "physical_pin_count": len(positions),
        "PWM_reading": root.attrib["data-function-reading-local"],
        "font": style.font_family,
        "font_sha256": style.font_sha256,
        "clean_sha256": hashlib.sha256(clean.svg.encode()).hexdigest(),
        "diagnostic_sha256": hashlib.sha256(
            diagnostic.svg.encode()
        ).hexdigest(),
        "physical_pin_points_um": {
            f"{pin.reference}.{pin.number}": [point.x, point.y]
            for pin, point in sorted(
                positions.items(), key=lambda v: int(v[0].number)
            )
        },
        "sheet_DRC": "BLOCKED; old source remains 9 ERROR / 32 WARNING",
    }
    (output / "DA1-owner-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(
        generate_da1_only(args.output_dir, args.font_file),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
