"""TI TL494CN: true 16-source-pin E3 portrait, 6-char aliases + PAINT #93.

Replaces the reference-branch standalone specimen with ELECTRICAL #97's
authoritative device/unit/spec/PinRef: FEEDBACK pin 3 is INPUT, not OUTPUT.
Two typography poses NEVER change the physical package/anchors/Net.
GOST source approval, actual circuitry, and vendor package outline are
not claimed; rendered outputs are editorial DRAFT 1:1-mm SVG previews.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.electrical.ic import (
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_editor_targets import (
    make_ic_editor_manifest,
    make_paint_editor_targets,
)
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
    revise_ic_text_orientation,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_paint_bridge import (
    bind_ic_paint_text_only,
    propose_ic_paint_binding,
)
from gost_schematic.electrical.ic_pin_alias import verify_alias_display
from gost_schematic.electrical.tl494cn import (
    TI_DATA_SHEET,
    TI_E3_LEFT,
    TI_E3_RIGHT,
    TI_PHYSICAL_PINS,
    TI_REVISION,
    TI_SHORT_LABELS,
    IcFunctionReading,
    tl494cn_record,
    tl494cn_unwired_circuit,
    verify_tl494cn_ti_pinout,
)
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.pins import ElectricalType
from gost_schematic.standards.type_a_font import inspect_type_a_font

# Direct compatibility for the historical reference script's PINS table.
# Derived from independently tested TI source, NEVER manually forked.
PINS = {
    number: (name, ElectricalType(electrical.value))
    for number, name, _description, electrical in TI_PHYSICAL_PINS
}


def build(font_file: Path):
    """Initial 16-pin source geometry becomes one explicit checked revision."""
    record, aliases = tl494cn_record(reading=IcFunctionReading.BOTTOM_TO_TOP)
    verify_tl494cn_ti_pinout(record.device)
    assert PINS["3"] == ("FEEDBACK", ElectricalType.INPUT)
    assert PINS["13"] == ("OUTPUT CTRL", ElectricalType.INPUT)
    assert PINS["14"] == ("REF", ElectricalType.POWER_OUTPUT)
    inspection = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGost Type A TT",
        require_family_match=True,
    )
    style = inspection.style
    measurer = PillowTextMeasurer()
    proposal = propose_ic_paint_binding(record, style, measurer)
    before = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    after = resolve_ic_pin_positions(
        proposal.record.device, proposal.record.specs, proposal.record.placements,
    )
    moved = tuple(ref for ref in before if before[ref] != after[ref])
    original_circuit = tl494cn_unwired_circuit(record)
    permit = IcGeometryConsent(ic_record_fingerprint(record), moved)
    validate_ic_graphic_revision(
        record, proposal.record, circuit=original_circuit,
        consent=permit,
    )
    verify_alias_display(aliases, proposal.record)
    changed = revise_ic_text_orientation(
        proposal.record, IcTextAngle.HORIZONTAL,
    )
    validate_ic_graphic_revision(
        proposal.record, changed, circuit=original_circuit,
    )
    flat = bind_ic_paint_text_only(proposal, changed)
    assert proposal.record.device == flat.record.device
    assert proposal.views[0].pins == flat.views[0].pins
    assert proposal.views[0].body == flat.views[0].body
    return proposal, flat, original_circuit, aliases, style, measurer, inspection


def _validate_svg(
    svg: str, *, orientation: IcFunctionReading, physical,
    markers: bool,
) -> None:
    root = ET.fromstring(svg)
    functions = [
        item for item in root.iter()
        if item.attrib.get("data-kind") == "function"
    ]
    if len(functions) != 1 or functions[0].text != "PWM":
        raise ValueError("TL494_FUNCTION_WORD_MISSING")
    matrix = functions[0].attrib.get("transform", "")
    if orientation is IcFunctionReading.BOTTOM_TO_TOP:
        if not matrix.startswith("matrix(0 -1 1 0 "):
            raise ValueError("TL494_PWM_WRONG_READING_DIRECTION")
    elif matrix:
        raise ValueError("TL494_HORIZONTAL_FUNCTION_WRONG_ROTATION")
    leads = [
        item for group in root.iter()
        if group.attrib.get("data-layer") == "ic-physical-pin-leads"
        for item in group if item.tag.endswith("line")
    ]
    if len(leads) != 16 or len({
        item.attrib["data-pin-number"] for item in leads
    }) != 16:
        raise ValueError("TL494_SVG_INCOMPLETE_PHYSICAL_LEADS")
    from gost_schematic.core.units import format_mm

    for item in leads:
        ref = item.attrib["data-pin-number"]
        pin = physical[ref]
        if (
            item.attrib.get("x2") != format_mm(pin.x)
            or item.attrib.get("y2") != format_mm(pin.y)
            or item.attrib.get("data-real-anchor") != "true"
        ):
            raise ValueError("TL494_LEAD_ENDPOINT_1UM_MISMATCH")
    layers = [
        node for node in root.iter()
        if node.attrib.get("data-layer") == "editor-connection-targets"
    ]
    if markers:
        if len(layers) != 1 or len(layers[0]) != 16 or (
            layers[0].attrib.get("data-physical-print") != "false"
        ):
            raise ValueError("TL494_DIAGNOSTIC_ENDPOINT_LAYER_INCOMPLETE")
    elif layers or any(marker in svg for marker in ("#148645", "#8b1e27")):
        raise ValueError("TL494_EDITOR_MARKERS_LEAKED_INTO_PRINT")


def generate(output: Path, font_file: Path) -> dict:
    vertical, horizontal, circuit, aliases, style, measurer, face = build(font_file)
    output.mkdir(parents=True, exist_ok=True)
    source_nets = circuit.nets
    source_pin_points = resolve_ic_pin_positions(
        vertical.record.device, vertical.record.specs,
        vertical.record.placements,
    )
    manifest = {
        "status": "DRAFT_TI_VERIFIED_PINOUT_NONAPPROVED_GOST_VIEW",
        "source": TI_DATA_SHEET + "#page=3",
        "revision": TI_REVISION,
        "device": vertical.record.device.identifier,
        "component_ref": "DA1",
        "font_sha256": style.font_sha256,
        "font_h_um": 3500,
        "physical_count": 16,
        "manufacturer_pin_names": {
            item.number: item.name for item in vertical.record.device.pins
        },
        "functions": {
            item.number: item.function for item in vertical.record.device.pins
        },
        "types": {
            item.number: item.electrical_type.value
            for item in vertical.record.device.pins
        },
        "short_labels": TI_SHORT_LABELS,
        "pin_group_left": TI_E3_LEFT,
        "pin_group_right": TI_E3_RIGHT,
        "source_photo_pin_order_reproduced": False,
        "photo_routing_untouched": True,
        "net_assignment_verified": False,
        "body_local_um": [
            vertical.views[0].body.min_x, vertical.views[0].body.min_y,
            vertical.views[0].body.max_x, vertical.views[0].body.max_y,
        ],
        "world_pinref_points_um": {
            f"{ref.reference}.{ref.number}": [point.x, point.y]
            for ref, point in source_pin_points.items()
        },
        "labels": [
            {
                "physical_number": a.physical_number,
                "manufacturer_pin_name": a.manufacturer_pin_name,
                "schematic_short_label": a.schematic_short_label,
                "electrical_type": a.electrical_type.value,
                "real_pin_ref": [
                    a.real_pin_ref.reference, a.real_pin_ref.number,
                ],
                "display_orientation": a.display_orientation.value,
                "source_document_reference": a.source_document_reference,
            } for a in aliases.labels
        ],
        "variants": {},
    }
    for name, binding, direction in (
        ("bottom_to_top_90", vertical, IcFunctionReading.BOTTOM_TO_TOP),
        ("horizontal_0", horizontal, IcFunctionReading.HORIZONTAL),
    ):
        binding.verify_endpoints()
        contact_inventory = make_ic_editor_manifest(binding, circuit)
        target_sets = make_paint_editor_targets(binding, contact_inventory, circuit)
        assert len(target_sets) == len(binding.views) == 1
        view = binding.views[0]
        expected = {c.physical_number: c.anchor for c in contact_inventory.contacts}
        assert len(expected) == 16
        from gost_schematic.rendering.ic_rectangular import render_resolved_ic

        for diagnostic in (False, True):
            picture = render_resolved_ic(
                view, style, measurer,
                editor_targets=target_sets[0] if diagnostic else (),
                editor_overlay=diagnostic,
                review_overlay=diagnostic,
                glyph_detail=diagnostic,
            )
            assert picture.pin_anchors == tuple(
                (pin.pin_id, pin.anchor) for pin in view.pins
            )
            _validate_svg(
                picture.svg, orientation=direction,
                physical=expected, markers=diagnostic,
            )
            title = f"TL494CN_PWM_{name}_{'diagnostic' if diagnostic else 'clean'}"
            file = output / (title + ".svg")
            file.write_text(picture.svg, encoding="utf-8")
            manifest["variants"][title] = {
                "svg": file.name,
                "function_reading": direction.value,
                "is_editor_only": diagnostic,
                "pin_count": len(picture.pin_anchors),
            }
    if circuit.nets is not source_nets:
        raise ValueError("TL494_TEXT_SWITCH_MUTATED_CIRCUIT")
    (output / "TL494CN_ic_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "pin_count": 16,
        "sources": TI_REVISION,
        "variants": len(manifest["variants"]),
        "font_family": face.reported_face[0],
        "display": ["horizontal", "bottom_to_top"],
        "physical_pinref_count": len(source_pin_points),
    }, ensure_ascii=False, sort_keys=True))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    generate(args.output, args.font_file)


if __name__ == "__main__":
    main()
