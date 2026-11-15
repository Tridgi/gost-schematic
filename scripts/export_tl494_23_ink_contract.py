"""Export real NET-consumable 23-instance ink and PinRef obstacles for TL494.

Source of truth: RECON's source_signed_ink_footprint (real IC+PAINT),
YGO's source_footprint (all 13 source-used glyphs including VT1 dot),
and actual NET sheet-layout graphic obstacles. No fabricated DA1 shape.
Not a routed/print-approved artifact. All distances are integer micrometres.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.route_candidate_driver import (
    _build_obstacles,
    load_original_owner_fixture,
    position_only_move,
    restore_original_named_nets,
    source_signed_ink_footprint,
)

from gost_schematic.catalog.source_footprints import (
    footprint_record,
    source_footprint,
    source_reference_symbol,
)
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.sheet_layout import component_graphic_obstacles
from gost_schematic.model.circuit import PinRef

FROZEN_ORIGINAL_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
EXPECTED_FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def box_record(box) -> list[int]:
    return [box.min_x, box.min_y, box.max_x, box.max_y]


def point_record(point) -> list[int]:
    return [point.x, point.y]


def owner_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True,
    ).strip()


def build_snapshot(assembly, font: Path) -> dict:
    frozen, _binding = load_original_owner_fixture()
    canonical = restore_original_named_nets(assembly, frozen)
    symbols, measured_full = source_signed_ink_footprint(assembly, font)
    # Use actual owner PAINT/Type A measured text and IC pin-label ink,
    # never an invented text buffer or guessed font. This is the geometry
    # that the genuine NET candidate _build_obstacles already consumes.
    verified_ti = bind_verified_compact_ti(assembly, canonical)
    _owner_symbols, guards, _sheet, _footprint, _style = _build_obstacles(
        assembly, canonical, font, verified_ti=verified_ti,
    )
    if len(guards) != 73:
        raise AssertionError("UGO_DELIVERY_ACTUAL_TYPE_A_73_GUARDS_MISSING")
    if len(canonical.components) != 23 or len(canonical.nets) != 15:
        raise AssertionError("UGO_DELIVERY_ORIGINAL_23_15_REQUIRED")

    original_refs = {
        pin: net.name
        for net in canonical.nets for pin in net.members
    }
    if len(original_refs) != 62 or len({
        pin for net in canonical.nets for pin in net.members
    }) != 62:
        raise AssertionError("UGO_DELIVERY_ORIGINAL_62_REQUIRED")
    source = {
        binding.reference: binding
        for binding in assembly.source_UGO_bindings
    }
    if len(source) != 13:
        raise AssertionError("UGO_DELIVERY_SOURCE_USED_13_REQUIRED")

    records = {}
    for component in canonical.components:
        ref = component.reference
        if component.part_id not in symbols or component.part_id not in assembly.parts:
            raise AssertionError("UGO_DELIVERY_REAL_PART_OR_INK_MISSING:" + ref)
        symbol = symbols[component.part_id]
        part = assembly.parts[component.part_id]
        # VT1's source-photo dot is real decorative ink, NOT a fourth pin.
        # NET must see the identical rendered source shape as gallery/PAINT.
        rendered = source_reference_symbol(symbol, ref) if ref in source else symbol
        ink = component_graphic_obstacles(rendered, component)
        if len(ink) != len(rendered.graphics):
            raise AssertionError("UGO_DELIVERY_RENDERED_INK_MISSING:" + ref)
        corridors = pin_corridors_for_component(symbol, component)
        positions = component.pin_positions(symbol)
        numbers = tuple(p.number for p in part.pins)
        if (len(numbers) != len(set(numbers))
            or {p.number for p in symbol.pins} != set(numbers)
            or len(corridors) != len(numbers)
            or set(positions) != set(numbers)):
            raise AssertionError("UGO_DELIVERY_REAL_PIN_ID_DRIFT:" + ref)
        pin_obstacles = []
        for pin in part.pins:
            pref = PinRef(ref, pin.number)
            linked = next((c for c in corridors if c.pin == pref), None)
            if linked is None or linked.contact != positions[pin.number]:
                raise AssertionError("UGO_DELIVERY_REAL_PIN_CORRIDOR_DRIFT:" + str(pref))
            net_name = original_refs.get(pref)
            if net_name is None:
                raise AssertionError("UGO_DELIVERY_UNSOURCED_OR_NC_PIN:" + str(pref))
            pin_obstacles.append({
                "pin_ref": f"{ref}.{pin.number}",
                "number": pin.number,
                "manufacturer_role": pin.name,
                "canonical_source_net": net_name,
                "contact_um": point_record(positions[pin.number]),
                "escape_side": linked.side.value,
                "escape_box_um": box_record(linked.box),
                "escape_rule": "PIN_REF_ONLY_NO_FOREIGN_NET_CLEARANCE",
            })
        record = {
            "reference": ref,
            "part_id": component.part_id,
            "actual_symbol_id": symbol.identifier,
            "symbol_revision": symbol.revision,
            "origin_um": point_record(component.origin),
            "rotation_deg": component.transform.rotation,
            "mirror_x": component.transform.mirror_x,
            "stroke_width_um": symbol.line_width_um,
            "actual_glyph_body_box_um": box_record(
                component.transform.box(symbol.body_keepout).translated(
                    component.origin,
                ),
            ),
            "actual_glyph_stroke_box_um": box_record(
                component.transform.box(rendered.stroked_bounds).translated(
                    component.origin,
                ),
            ),
            "individual_stroked_primitives_um": [
                {
                    "id": item.identifier,
                    "kind": item.kind,
                    "conservative_box_um": box_record(item.box),
                } for item in ink
            ],
            "real_physical_contacts": pin_obstacles,
            "ink_scope": (
                "OWNER_PAINT_SIGNED_DA1_ROUTER_GRAPHIC_NOT_PRINT_APPROVAL"
                if ref == "DA1" else
                "SOURCE_LOCKED_YGO_DRAFT"
                if ref in source else
                "ORIGINAL_CATALOG_SOURCE_SYMBOL_DRAFT"
            ),
        }
        if ref in source:
            locked = source_footprint(source[ref])
            original = footprint_record(locked)
            if (locked.rendered_ink_bounds !=
                    component.transform.box(
                        rendered.stroked_bounds,
                    ).translated(component.origin)):
                raise AssertionError("UGO_DELIVERY_DRAFT_SYMBOL_BOUNDS_DRIFT:" + ref)
            if len(locked.lead_obstacles) != len(numbers):
                raise AssertionError("UGO_DELIVERY_SOURCE_LEAD_LOSS:" + ref)
            record["locked_ygo_source_footprint"] = original
        records[ref] = record

    pin_refs = [
        item["pin_ref"]
        for part in records.values()
        for item in part["real_physical_contacts"]
    ]
    if len(pin_refs) != 62 or len(set(pin_refs)) != 62:
        raise AssertionError("UGO_DELIVERY_TOTAL_62_CONTACTS_MISSING")
    actual_da1 = records["DA1"]
    if ({p["number"] for p in actual_da1["real_physical_contacts"]}
        != {str(i) for i in range(1, 17)}):
        raise AssertionError("UGO_DELIVERY_DA1_16_PHYSICAL_MISSING")
    if not any("PAINT" in text for text in symbols[
        "reference.tl494cn"
    ].standard_refs):
        raise AssertionError("UGO_DELIVERY_REAL_PAINT_DA1_SOURCE_MISSING")
    if set(records) != {c.reference for c in canonical.components}:
        raise AssertionError("UGO_DELIVERY_23_REAL_REFERENCE_MISSING")
    netlist = {
        n.name: [f"{p.reference}.{p.number}" for p in n.members]
        for n in canonical.nets
    }
    if set(netlist) != set(frozen["nets"]) or any(
        tuple(netlist[key]) != tuple(frozen["nets"][key])
        for key in netlist
    ):
        raise AssertionError("UGO_DELIVERY_CANONICAL_SOURCE_NET_CHANGED")
    text_guards = [
        {
            "owner": guard.owner,
            "kind": type(guard).__name__,
            "collision_box_um": box_record(guard.collision_bounds),
            "actual_ink_box_um": (
                box_record(guard.ink_bounds)
                if getattr(guard, "ink_bounds", None) is not None else None
            ),
            "printed_text": getattr(guard, "text", None),
        }
        for guard in guards
    ]
    paper_bounds = (420000, 297000)
    inset = 10000  # project editorial inset, NOT a ГОСТ-wide norm
    within = all(
        inset <= row["collision_box_um"][0]
        <= row["collision_box_um"][2] <= paper_bounds[0] - inset
        and inset <= row["collision_box_um"][1]
        <= row["collision_box_um"][3] <= paper_bounds[1] - inset
        for row in text_guards
    )
    return {
        "source_original_sha": FROZEN_ORIGINAL_SHA,
        "status": "DRAFT_CONSERVATIVE_OBSTACLES_NOT_FULL_PRINT_DRC",
        "real_part_count": len(records),
        "real_net_count": len(netlist),
        "real_pin_ref_memberships": len(pin_refs),
        "DA1_physical_contact_count": len(actual_da1["real_physical_contacts"]),
        "source_glyph_instances": len(source),
        "source_glyphs_verified": sorted(source),
        "full_23_component_stroke_bbox_um": measured_full["bbox_um"],
        "all_component_stroke_boxes_within_A3_margins": measured_full[
            "A3_bbox_within_margins"
        ],
        "terminal_stroke_width_um": 300,
        "actual_PAINT_TypeA_label_guard_count": len(text_guards),
        "actual_PAINT_TypeA_text_guards": text_guards,
        "project_10mm_text_collision_frame_fit": within,
        "minimum_text_collision_y_um": min(
            row["collision_box_um"][1] for row in text_guards
        ),
        "original_named_nets": netlist,
        "parts": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--owner-recon-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if owner_sha() != args.owner_recon_sha:
        raise ValueError("UGO_DELIVERY_RECON_HEAD_MISMATCH")
    if not args.font.is_file() or sha_bytes(
        args.font.read_bytes()
    ) != EXPECTED_FONT_SHA:
        raise ValueError("UGO_DELIVERY_REAL_PINNED_OPENGOST_FONT_REQUIRED")

    base = compact_source_assembly()
    # Both controlled moves have 2.5 mm exact step. "C1:0:2.5"
    # is the actual owner Type A label margin fix; R2 y+2.5 is
    # the measured 8→9 Net congestion candidate, not route approval.
    moved = position_only_move(
        base, (("R2", 0, Decimal("2.5")), ("C1", 0, Decimal("2.5"))),
    )
    if moved.circuit.nets is not base.circuit.nets:
        raise AssertionError("UGO_DELIVERY_POSITION_REWROTE_NETS")
    before = build_snapshot(base, args.font)
    after = build_snapshot(moved, args.font)
    diffs = {
        ref: {
            "old_origin_um": before["parts"][ref]["origin_um"],
            "new_origin_um": after["parts"][ref]["origin_um"],
            "old_stroke_box_um": before["parts"][ref][
                "actual_glyph_stroke_box_um"
            ],
            "new_stroke_box_um": after["parts"][ref][
                "actual_glyph_stroke_box_um"
            ],
        }
        for ref in before["parts"]
        if before["parts"][ref]["origin_um"] != after["parts"][ref]["origin_um"]
    }
    if (
        set(diffs) != {"R2", "C1"}
        or before["project_10mm_text_collision_frame_fit"] is not False
        or after["project_10mm_text_collision_frame_fit"] is not True
        or before["minimum_text_collision_y_um"] != 9100
        or after["minimum_text_collision_y_um"] != 11600
    ):
        raise AssertionError("UGO_DELIVERY_C1_TYPE_A_FRAME_NOT_REPAIRED")
    if any(
        after["parts"][ref]["real_physical_contacts"][i]["canonical_source_net"]
        != before["parts"][ref]["real_physical_contacts"][i][
            "canonical_source_net"
        ]
        for ref in before["parts"]
        for i in range(len(before["parts"][ref]["real_physical_contacts"]))
    ):
        raise AssertionError("UGO_DELIVERY_UNAUTHORIZED_TOPOLOGY_MOVE")
    payload = {
        "schema": "YGO_TL494_TRUE_23_INSTALLATIONS_NET_PHYSICAL_OBSTACLES_V1",
        "source_reference_sha": FROZEN_ORIGINAL_SHA,
        "recon_exact_sha": args.owner_recon_sha,
        "font_type_a_sha256": EXPECTED_FONT_SHA,
        "NET_semantics": "CONSERVATIVE_STROKED_OBSTACLE_AND_PIN_SPECIFIC_ESCAPE",
        "route_15_net_pass": False,
        "DRC_full_print_pass": False,
        "normative_status": "36_DRAFT_0_APPROVED",
        "control": before,
        "moved_R2_Y_2p5_C1_Y_2p5": after,
        "diff": diffs,
    }
    encoded = (
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2)
        + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps({
        "artifact": str(args.output),
        "artifact_sha256": sha_bytes(encoded),
        "control_parts": before["real_part_count"],
        "moved_parts": after["real_part_count"],
        "true_source_nets": after["real_net_count"],
        "physical_memberships": after["real_pin_ref_memberships"],
        "DA1_contacts": after["DA1_physical_contact_count"],
        "movements": sorted(diffs),
        "A3_all_glyphs_fit": after["all_component_stroke_boxes_within_A3_margins"],
        "TypeA_73_label_ink_guards": after["actual_PAINT_TypeA_label_guard_count"],
        "C1_label_frame_before": before["project_10mm_text_collision_frame_fit"],
        "C1_label_frame_after": after["project_10mm_text_collision_frame_fit"],
        "top_text_guard_y_before_um": before["minimum_text_collision_y_um"],
        "top_text_guard_y_after_um": after["minimum_text_collision_y_um"],
        "print_release": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
