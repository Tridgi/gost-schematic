"""Cycle11 standalone source-signed 23/15/62 + compact A3 b binding evidence.

This is a reproducible *nonprint* integration artifact for MAIN3/QA.
It cannot draw/approve a complete schematic or synthesize missing wires.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_b_continuation import rebind_true_source_b
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.route_candidate_driver import (
    OWNER_SHAS,
    ORIGINAL_BAD_DRC,
    SOURCE_SHA,
    load_original_owner_fixture,
    restore_original_named_nets,
)
from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font


def generate_cycle11_evidence(
    font_file: Path, output: Path,
) -> dict:
    """Emit identity, true two b marker coordinates and signed DA1 targets."""
    from examples.tl494_named_photo_sheet import compose_circuit

    assembly = compact_source_assembly()
    frozen, _ = load_original_owner_fixture()
    original = restore_original_named_nets(assembly, frozen)
    signed = bind_verified_compact_ti(assembly, original)
    style = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    ).style
    measurer = PillowTextMeasurer()
    paint = propose_ic_paint_binding(
        assembly.owner_ic_record, style, measurer,
    )
    revised, signed_overlay = signed.seal_paint(paint)
    signed_overlay.verify_against(revised, paint)
    clean = signed_overlay.render(
        revised, paint, style, measurer, diagnostics=False,
    )
    diagnostic = signed_overlay.render(
        revised, paint, style, measurer, diagnostics=True,
    )
    if len(clean) != 1 or len(diagnostic) != 1:
        raise ValueError("TL494_C11_EVIDENCE_PHYSICAL_UNIT_NOT_ONE")
    if (
        len(clean[0].pin_anchors) != 16
        or len(diagnostic[0].pin_anchors) != 16
        or clean[0].pin_anchors != diagnostic[0].pin_anchors
        or clean[0].connection_targets != diagnostic[0].connection_targets
    ):
        raise ValueError("TL494_C11_EVIDENCE_CLEAN_DEBUG_REAL_PIN_DRIFT")
    typed_continuation = compose_circuit(font_file)[-1]
    b = rebind_true_source_b(
        typed_continuation, signed.signed.circuit, assembly.symbols,
    )
    source_net_names = {net.name for net in original.nets}
    if len(source_net_names) != 15 or "b_NEGATIVE_OUTPUT" not in source_net_names:
        raise ValueError("TL494_C11_EVIDENCE_NOT_REAL_15_SOURCE_NETS")
    pin_evidence = []
    for i in range(1, 17):
        p = PinRef("DA1", str(i))
        item = revised.contact(p)
        pin_evidence.append({
            "number": str(i),
            "manufacturer_name": item.manufacturer_pin_name,
            "display_label": item.schematic_short_label,
            "electrical_type": item.electrical_type.value,
            "owner_Net": item.net_id,
            "physical_um": [item.world_anchor.x, item.world_anchor.y],
        })
    result = {
        "schema": "C11_SOURCE_LOCKED_SIGNED_DA1_B_CONTINUATION_V1",
        "status": "PASS_SOURCE_BINDING_ONLY_NOT_15_NET_PRINT",
        "immutable_original_commit": SOURCE_SHA,
        "owner_exact_HEADs": OWNER_SHAS,
        "frozen_source_components": 23,
        "frozen_source_Net_count": 15,
        "frozen_source_physical_memberships": 62,
        "true_original_nets": {
            n.name: [
                f"{p.reference}.{p.number}" for p in n.members
            ] for n in original.nets
        },
        "original_bad_DRC_negative": ORIGINAL_BAD_DRC,
        "before_legacy_DA1_part_id": signed.source_part_id,
        "after_signed_DA1_part_id": signed.signed_part_id,
        "signed_source_Circuit_Nets_identical": (
            signed.signed.circuit.nets is original.nets
        ),
        "GOST_A_font_SHA256": style.font_sha256,
        "manufacturer_DA1_physical_pin_count": len(pin_evidence),
        "signed_DA1_pin_contacts": pin_evidence,
        "source_b_nonphysical_Net": b.nets[0].net_name,
        "source_b_physical_members": [
            f"{p.reference}.{p.number}" for p in b.nets[0].members
        ],
        "source_b_marker_um": {
            m.id: [m.anchor.x, m.anchor.y] for m in b.endpoints
        },
        "source_b_stubs_um": {
            f"{s.pin.reference}.{s.pin.number}": {
                "start": [s.start.x, s.start.y],
                "end": [s.end.x, s.end.y],
            } for s in b.stubs
        },
        "b_marker_continuations_are_NOT_new_physical_Nets": True,
        "full_15_Net_route_proven": False,
        "full_A3_print_and_photo_1_to_1": "BLOCKED",
        "GOST_normative_source_UGO_status": "DRAFT_UNAPPROVED",
        "full_clean_SVG_or_300DPI_PNG_released": False,
    }
    if not result["signed_source_Circuit_Nets_identical"]:
        raise ValueError("TL494_C11_EVIDENCE_SIGNED_NET_TUPLE_MUTATED")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    args = parser.parse_args()
    report = generate_cycle11_evidence(args.font_file, args.output_file)
    print(json.dumps({
        "status": report["status"],
        "real_Pins": report["manufacturer_DA1_physical_pin_count"],
        "real_b_markers": list(report["source_b_marker_um"]),
        "full_print": report["full_A3_print_and_photo_1_to_1"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
