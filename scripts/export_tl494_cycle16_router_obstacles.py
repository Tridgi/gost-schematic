"""Cycle16 source-locked multi-placement 23-part obstacle handoff to NET/RECON.

This is geometry, NOT an auto-routed electrical graph or full-sheet DRC.
All data are computed from real RECON, IC, YGO and PAINT owner sources.
No placeholder DA1 symbol or invented b electrical pin is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

FROZEN_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FONT_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
DIRECTIONS = {
    "left": [-1, 0],
    "right": [1, 0],
    "top": [0, -1],
    "bottom": [0, 1],
}


def require(ok: bool, code: str) -> None:
    if not ok:
        raise AssertionError(code)


def require_box(raw: object, tag: str) -> list[int]:
    require(
        isinstance(raw, list) and len(raw) == 4 and
        all(type(v) is int for v in raw),
        "UGO_C16_UNKNOWN_OBSTACLE_BOX:" + tag,
    )
    require(raw[0] <= raw[2] and raw[1] <= raw[3],
            "UGO_C16_INVALID_OBSTACLE_BOX:" + tag)
    return raw


def orthogonal_segment_hits_stroked_box(
    start_um: tuple[int, int],
    end_um: tuple[int, int],
    stroked_box_um: list[int],
) -> bool:
    """Exact segment vs real ink AABB; remote coordinate alone never blocks.

    This is a geometric broad-phase predicate, NOT permission for a wire
    crossing, a routed connection, or a substitute for global DRC.
    Callers must still run NET's real clearance/pin/foreign-net veto.
    """
    require(len(start_um) == len(end_um) == 2 and
            all(type(n) is int for n in (*start_um, *end_um)),
            "UGO_C16_NON_INTEGER_SEGMENT")
    x0, y0, x1, y1 = require_box(stroked_box_um, "segment_query")
    sx, sy = start_um
    ex, ey = end_um
    if sy == ey:
        return y0 <= sy <= y1 and max(sx, ex) >= x0 and min(sx, ex) <= x1
    if sx == ex:
        return x0 <= sx <= x1 and max(sy, ey) >= y0 and min(sy, ey) <= y1
    raise AssertionError("UGO_C16_DIAGONAL_SEGMENT_NOT_ORTHOGONAL")


def router_obstacle_contract(snapshot: dict) -> dict:
    """Project actual strokes/text and exact PinRef-only escape portals.

    A faraway obstacle is only an obstacle at its own physical AABB.
    Its X/Y coordinates are NEVER unconditional search barriers.
    NET should build visibility edges from actual segment intersections,
    never connect electrical nodes merely because a search portal is crossed.
    """
    require(snapshot["real_part_count"] == 23 and
            snapshot["real_net_count"] == 15 and
            snapshot["real_pin_ref_memberships"] == 62 and
            snapshot["DA1_physical_contact_count"] == 16 and
            snapshot["source_glyph_instances"] == 13,
            "UGO_C16_REAL_23_15_62_16_13_REQUIRED")
    source_nets = snapshot["original_named_nets"]
    source_members = {
        pin_ref: name for name, pins in source_nets.items()
        for pin_ref in pins
    }
    require(len(source_nets) == 15 and
            sum(len(pins) for pins in source_nets.values()) == 62 and
            len(source_members) == 62,
            "UGO_C16_ORIGINAL_SOURCE_NET_PINREF_DRIFT")
    strokes = []
    portals = []
    for ref, part in sorted(snapshot["parts"].items()):
        require(part["reference"] == ref, "UGO_C16_PART_REF_DRIFT:" + ref)
        require(part["individual_stroked_primitives_um"],
                "UGO_C16_EMPTY_REAL_STROKES:" + ref)
        for index, stroke in enumerate(part["individual_stroked_primitives_um"]):
            ident = f"{ref}.ink.{index}"
            strokes.append({
                "id": ident,
                "owner_reference": ref,
                "actual_symbol_id": part["actual_symbol_id"],
                "primitive_id": stroke["id"],
                "primitive_kind": stroke["kind"],
                "stroked_box_um": require_box(
                    stroke["conservative_box_um"], ident,
                ),
                "source": "REAL_D4_GRAPHIC_STROKE_NOT_COMPONENT_PROXY",
                "electrical_connection": False,
            })
        for pin in part["real_physical_contacts"]:
            tag = pin["pin_ref"]
            require(tag.startswith(ref + "."), "UGO_C16_PIN_REF_OWNER:" + tag)
            require(pin["canonical_source_net"] == source_members.get(tag),
                    "UGO_C16_PIN_REF_NET_MEMBERSHIP_CHANGED:" + tag)
            side = pin["escape_side"]
            require(side in DIRECTIONS, "UGO_C16_UNKNOWN_ESCAPE_SIDE:" + tag)
            require(
                pin["escape_rule"] == "PIN_REF_ONLY_NO_FOREIGN_NET_CLEARANCE",
                "UGO_C16_FOREIGN_NET_ESCAPE_BYPASS:" + tag,
            )
            anchor = pin["contact_um"]
            require(len(anchor) == 2 and all(type(n) is int for n in anchor),
                    "UGO_C16_REAL_PIN_COORD_UNKNOWN:" + tag)
            portals.append({
                "pin_ref": tag,
                "owner_reference": ref,
                "canonical_source_net": pin["canonical_source_net"],
                "manufacturer_role": pin["manufacturer_role"],
                "contact_um": anchor,
                "escape_side": side,
                "escape_unit_vector": DIRECTIONS[side],
                "own_pin_only_escape_box_um": require_box(
                    pin["escape_box_um"], tag,
                ),
                "foreign_net_crossing_allowed": False,
                "electrical_connection_only_at_exact_pinref": True,
            })
    text = []
    for index, guard in enumerate(snapshot["actual_PAINT_TypeA_text_guards"]):
        tag = f"TypeA.{index}"
        rect = require_box(guard["collision_box_um"], tag)
        require(rect[0] < rect[2] and rect[1] < rect[3],
                "UGO_C16_UNKNOWN_REAL_TYPE_A_EXTENTS:" + tag)
        text.append({
            "id": tag,
            "source_owner": guard["owner"],
            "measured_guard_kind": guard["kind"],
            "collision_box_um": rect,
            "measured_type_a_platform_specific": True,
            "foreign_wire_clearance_allowed": False,
        })
    require(len(strokes) >= 23 and len(portals) == 62 and len(text) == 73,
            "UGO_C16_INCOMPLETE_REAL_ROUTER_OBSTACLES")
    require(len({p["pin_ref"] for p in portals}) == 62,
            "UGO_C16_DUPLICATED_PHYSICAL_PORT")
    require(
        {p["pin_ref"] for p in portals if p["owner_reference"] == "DA1"} ==
        {f"DA1.{i}" for i in range(1, 17)},
        "UGO_C16_REAL_16_TL494_TERMINALS_REQUIRED",
    )
    return {
        "obstacle_model": "REAL_STROKES_NO_REMOTE_COORDINATE_VETO",
        "visual_ink_stroke_obstacles": strokes,
        "measured_type_a_text_obstacles": text,
        "physical_pinref_portals": portals,
        "primitive_ink_obstacle_count": len(strokes),
        "type_a_measured_text_count": len(text),
        "pin_portal_count": len(portals),
        "outbound_escape_is_own_pinref_only": True,
        "crossed_visibility_portal_creates_electrical_node": False,
        "route_pass": False,
        "full_drc_pass": False,
    }


def true_b_graphical_continuations(assembly, font: Path, snapshot: dict) -> list[dict]:
    """Rebind frozen SOURCE two b marker vectors; never create a new Net."""
    from importlib import import_module

    from examples.tl494_v5.cycle11_b_continuation import rebind_true_source_b
    from examples.tl494_v5.route_candidate_driver import (
        load_original_owner_fixture,
        restore_original_named_nets,
        source_signed_ink_footprint,
    )

    frozen, _binding = load_original_owner_fixture()
    circuit = restore_original_named_nets(assembly, frozen)
    symbols, _full = source_signed_ink_footprint(assembly, font)
    source_project = import_module(
        "examples.tl494_named_photo_sheet",
    ).compose_circuit(font)[-1]
    rebound = rebind_true_source_b(source_project, circuit, symbols)
    require(
        len(rebound.stubs) == len(rebound.endpoints) == 2 and
        {s.endpoint_id for s in rebound.stubs} == {"b-X2", "b-R5"},
        "UGO_C16_SOURCE_TWO_B_GRAPHICAL_CONTINUATIONS_REQUIRED",
    )
    result = []
    for stub in sorted(rebound.stubs, key=lambda s: s.endpoint_id):
        pin_ref = f"{stub.pin.reference}.{stub.pin.number}"
        contact = next(
            p["contact_um"]
            for p in snapshot["parts"][stub.pin.reference][
                "real_physical_contacts"
            ]
            if p["pin_ref"] == pin_ref
        )
        start, end = [stub.start.x, stub.start.y], [stub.end.x, stub.end.y]
        require(start == contact, "UGO_C16_B_NOT_ON_REAL_PIN:" + pin_ref)
        require((start[0] == end[0]) != (start[1] == end[1]),
                "UGO_C16_B_NOT_ORTHOGONAL_SOURCE_STUB:" + pin_ref)
        result.append({
            "marker_id": stub.endpoint_id,
            "physical_source_pinref": pin_ref,
            "source_net": "b_NEGATIVE_OUTPUT",
            "from_contact_um": start,
            "to_graphic_marker_um": end,
            "electrical_conductor": False,
            "adds_new_pin_ref": False,
            "provenance": "REAL_SOURCE_TYPED_REBOUND_NOT_RENDERED_SVG",
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--owner-recon-sha", required=True)
    parser.add_argument("--owner-ic-sha", required=True)
    parser.add_argument("--owner-paint-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    real_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True,
    ).strip()
    require(real_head == args.owner_recon_sha,
            "UGO_C16_RECON_HEAD_NOT_EXACT")
    for label, owner_sha in (
        ("IC", args.owner_ic_sha), ("PAINT", args.owner_paint_sha),
    ):
        require(len(owner_sha) == 40 and
                all(c in "0123456789abcdef" for c in owner_sha),
                "UGO_C16_MISSING_EXACT_" + label + "_SHA")
    require(args.font.is_file() and
            hashlib.sha256(args.font.read_bytes()).hexdigest() == FONT_SHA256,
            "UGO_C16_SIGNED_TYPE_A_FONT_REQUIRED")

    # Deferred imports: the pure obstacle model and negative unit tests run
    # on the YGO branch; real RECON+IC+PAINT are required ONLY for production.
    from examples.tl494_v5.compact_layout import compact_source_assembly
    from examples.tl494_v5.route_candidate_driver import position_only_move
    from scripts.export_tl494_23_ink_contract import build_snapshot

    base = compact_source_assembly()
    candidates = {
        "x17_control": base,
        "x17_C1_down_2p5mm": position_only_move(
            base, (("C1", 0, Decimal("2.5")),),
        ),
        "x17_R2_down_2p5mm": position_only_move(
            base, (("R2", 0, Decimal("2.5")),),
        ),
        "x17_C1_R2_down_2p5mm": position_only_move(
            base, (
                ("C1", 0, Decimal("2.5")),
                ("R2", 0, Decimal("2.5")),
            ),
        ),
    }
    snapshots = {}
    original_nets = None
    original_port_identity = None
    for name, assembly in candidates.items():
        snapshot = build_snapshot(assembly, args.font)
        graph = router_obstacle_contract(snapshot)
        ports = {
            p["pin_ref"]: (
                p["canonical_source_net"], p["manufacturer_role"],
            ) for p in graph["physical_pinref_portals"]
        }
        if original_nets is None:
            original_nets = snapshot["original_named_nets"]
            original_port_identity = ports
        require(snapshot["original_named_nets"] == original_nets and
                ports == original_port_identity,
                "UGO_C16_SOURCE_TOPOLOGY_CHANGED_BY_PLACEMENT:" + name)
        graphical_b = true_b_graphical_continuations(
            assembly, args.font, snapshot,
        )
        snapshots[name] = {
            "placement_geometry": snapshot,
            "router_consumable_obstacles": graph,
            "source_b_non_electrical_continuations": graphical_b,
        }
    base_data = snapshots["x17_control"]["placement_geometry"]
    for name, reference in (
        ("x17_C1_down_2p5mm", "C1"),
        ("x17_R2_down_2p5mm", "R2"),
    ):
        changed = {
            ref for ref in base_data["parts"] if (
                snapshots[name]["placement_geometry"]["parts"][ref][
                    "origin_um"
                ] != base_data["parts"][ref]["origin_um"]
            )
        }
        require(changed == {reference},
                "UGO_C16_SINGLE_COMPONENT_MOVE_NOT_ISOLATED:" + name)
    require(
        not snapshots["x17_control"]["placement_geometry"][
            "project_10mm_text_collision_frame_fit"
        ] and snapshots["x17_C1_down_2p5mm"]["placement_geometry"][
            "project_10mm_text_collision_frame_fit"
        ] and not snapshots["x17_R2_down_2p5mm"][
            "placement_geometry"
        ]["project_10mm_text_collision_frame_fit"],
        "UGO_C16_C1_ONLY_TRUE_TYPE_A_FIX_NOT_PROVED",
    )
    payload = {
        "schema": "YGO_TL494_C16_FOUR_TRUE_23_INSTANCE_PORTAL_CONTRACT_V1",
        "source_original_sha": FROZEN_SHA,
        "recon_exact_sha": real_head,
        "signed_physical_ic_owner_sha": args.owner_ic_sha,
        "real_render_paint_owner_sha": args.owner_paint_sha,
        "pinned_opengost_type_a_sha256": FONT_SHA256,
        "source_net_count": 15,
        "source_memberships": 62,
        "true_DA1_contact_count": 16,
        "status": "DRAFT_NOT_ROUTED_NOT_GLOBAL_PRINT_DRC",
        "reconstructed_b_graphical_stubs_per_layout": 2,
        "layouts": snapshots,
    }
    data = (json.dumps(
        payload, sort_keys=True, ensure_ascii=False, indent=2,
    ) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({
        "result": "PASS_FOUR_TRUE_PHYSICAL_GEOMETRY_SNAPSHOTS",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "recon_sha": real_head,
        "layouts": sorted(snapshots),
        "source_nets": 15,
        "source_pinrefs": 62,
        "all_16_DA1": True,
        "all_layouts_two_b_stubs_non_electrical": True,
        "complete_route": False,
        "print_drc": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
