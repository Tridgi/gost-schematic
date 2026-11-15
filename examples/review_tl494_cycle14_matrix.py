"""Same-budget TL494 owner A3 source-physical placement/routing matrix.

Requires the source-locked RECON/IC/YGO/PAINT modules exactly as the
existing tl494-compact-a3-router-integration workflow. No edits to original
E695 source; the matrix remains DRAFT until canonical source ID rebinding,
15/15, complete printed DRC and independent QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from examples.tl494_v5 import compact_layout
from examples.tl494_v5.route_candidate_driver import (
    NET_RENAMES,
    REAL_SOURCE_NAMES,
    position_only_move,
)

from examples import review_tl494_compact_cycle9 as owner

_SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
# Only displacement of real positioned components, never electrical edits.
# old-x16 is a deliberately INVALID previous-print baseline: its left ink
# margin was 9.850mm instead of the required editorial 10.000mm.
MOVE_VARIANTS = {
    "old-x16": (),
    "fixed-x17": (),
    "r2-down-2p5": (("R2", 0, Decimal("2.5")),),
    "c1-down-2p5": (("C1", 0, Decimal("2.5")),),
    "r2-c1-down-2p5": (
        ("R2", 0, Decimal("2.5")),
        ("C1", 0, Decimal("2.5")),
    ),
    "da1-right-2p5": (("DA1", Decimal("2.5"), 0),),
    "r1-up-2p5": (("R1", 0, Decimal("-2.5")),),
    "vt1-right-2p5": (("VT1", Decimal("2.5"), 0),),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _typed_assembly(key: str):
    if key not in MOVE_VARIANTS:
        raise ValueError("C14_UNDECLARED_SOURCE_MOVE")
    original_x1 = compact_layout.COMPACT_A3_MM["X1"]
    try:
        if key == "old-x16":
            compact_layout.COMPACT_A3_MM["X1"] = (16, 35)
        model = compact_layout.compact_source_assembly()
    finally:
        compact_layout.COMPACT_A3_MM["X1"] = original_x1
    if MOVE_VARIANTS[key]:
        model = position_only_move(model, MOVE_VARIANTS[key])
    model.verify()
    return model


def _physical_source_identity(model, frozen: dict) -> dict[str, tuple[str, ...]]:
    """Byte-locked authored alias PinRefs must represent the same 15 real Nets.

    Do not call the older aliases "original user raw names". RECON's signed
    canonical restoration is still mandatory for final released print.
    """
    actual = {
        net.name: tuple(f"{p.reference}.{p.number}" for p in net.members)
        for net in model.circuit.nets
    }
    expected = {
        name: tuple(members) for name, members in frozen["net_members"].items()
    }
    if actual != expected:
        raise ValueError("C14_SOURCE_PHYSICAL_PINREF_MEMBERSHIP_CHANGED")
    source_to_alias = {
        original: NET_RENAMES.get(original, original)
        for original in REAL_SOURCE_NAMES
    }
    if set(source_to_alias.values()) != set(actual):
        raise ValueError("C14_SOURCE_ORIGINAL_NAME_ALIAS_NOT_BIJECTIVE")
    members = sum(map(len, actual.values()))
    if (
        len(model.circuit.components) != 23
        or len(actual) != 15 or members != 62
        or len({
            p.number for net in model.circuit.nets for p in net.members
            if p.reference == "DA1"
        }) != 16
    ):
        raise ValueError("C14_SOURCE_PHYSICAL_23_15_62_16_CHANGED")
    return actual


def run_matrix(
    destination: Path,
    font_file: Path,
    *,
    owner_sha: str,
    reference_sha: str,
    variants: tuple[str, ...],
    max_nodes: int,
    physical_ripup_attempts: int,
    physical_group_attempts: int = 0,
    priority_offset: int = 0,
) -> dict:
    if (
        not variants or len(set(variants)) != len(variants)
        or any(key not in MOVE_VARIANTS for key in variants)
    ):
        raise ValueError("C14_DUPLICATE_OR_UNDECLARED_VARIANTS")
    if type(max_nodes) is not int or not 100 <= max_nodes <= 25000:
        raise ValueError("C14_INVALID_BOUNDED_SEARCH_BUDGET")
    if type(priority_offset) is not int or not 0 <= priority_offset <= 5:
        raise ValueError("C14_INVALID_FIXED_PRIORITY")
    if type(physical_ripup_attempts) is not int or not (
        0 <= physical_ripup_attempts <= 4
    ):
        raise ValueError("C14_INVALID_RIPUP_BUDGET")
    if type(physical_group_attempts) is not int or not (0 <= physical_group_attempts <= 3):
        raise ValueError("C15_INVALID_CONFLICT_GROUP_ATTEMPTS")
    if len(owner_sha) != 40 or len(reference_sha) != 40:
        raise ValueError("C14_INVALID_OWNER_IDENTITY")

    frozen_path = Path(__file__).resolve().parents[1] / (
        "tests/fixtures/tl494-routing-source-e695c415.json"
    )
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if frozen["source_head_sha"] != _SOURCE_SHA:
        raise ValueError("C14_ORIGINAL_SOURCE_SHA_DRIFT")
    original_component_refs = set(frozen["part_refs"])
    base = _typed_assembly("fixed-x17")
    original_nets = _physical_source_identity(base, frozen)
    first_instances = {part.reference: part for part in base.circuit.components}
    results = []

    for key in variants:
        model = _typed_assembly(key)
        assert _physical_source_identity(model, frozen) == original_nets
        instances = {part.reference: part for part in model.circuit.components}
        if set(instances) != original_component_refs:
            raise ValueError("C14_BOM_PARTS_CHANGED")
        # Every variant may alter origin ONLY; same D4, nominal, Part ID,
        # physical PinRefs and all original component reference identities.
        if any(
            (part.part_id, part.nominal, part.transform) != (
                first_instances[ref].part_id, first_instances[ref].nominal,
                first_instances[ref].transform,
            )
            for ref, part in instances.items()
        ):
            raise ValueError("C14_SOURCE_PART_OR_D4_EDIT")
        owner.compact_source_assembly = lambda model=model: model
        folder = destination / key
        proof = owner.produce(
            folder, font_file,
            owner_sha=owner_sha,
            reference_sha=reference_sha,
            node_cap=max_nodes,
            priority_trials=1,
            priority_offset=priority_offset,
            physical_veto_restarts=0,
            physical_ripup_attempts=physical_ripup_attempts,
            physical_group_attempts=physical_group_attempts,
            page_format="A3",
        )
        report_path = folder / "TL494-compact-A3-route-drc.json"
        roots = [{
            "net": tree["net"],
            "connected_physical_PinRefs": tree["connected_pin_refs"],
            "source_physical_PinRefs": tree["pin_refs"],
            "complete": tree["complete"],
            "diagnostics": tree["diagnostics"],
        } for tree in proof["routing"]["net_trees"]]
        if {item["net"] for item in roots} != set(original_nets):
            raise ValueError("C14_ROUTER_OMITTED_SOURCE_NET")
        results.append({
            "key": key,
            "position_only_moves_mm": [
                [name, str(dx), str(dy)]
                for name, dx, dy in MOVE_VARIANTS[key]
            ],
            "component_stroke_bbox_um": proof["occupied_mm"]["bbox_um"],
            "a3_10mm_margin_pass": proof["occupied_mm"]["A3_bbox_within_margins"],
            "routed_net_count": proof["routed_nets"],
            "connected_physical_contacts": sum(
                len(tree["connected_physical_PinRefs"])
                for tree in roots if tree["complete"]
            ),
            "accepted_segments": proof["routed_segments"],
            "wire_length_um": proof["routed_length_um"],
            "partial_graph_drc_error_count": proof["new_after_drc"]["error_count"],
            "print_pass": proof["print_pass"],
            "net_trees": roots,
            "source_drc_json_sha256": _sha(report_path),
            "source_drc_json": report_path.as_posix(),
            "status": proof["status"],
            "per_try_ripup": proof["routing"]["ripup_trials"],
        })
    summary = {
        "schema": "TL494_CYCLE14_EQUAL_BUDGET_POSITION_ROUTING_MATRIX_V1",
        "review": "DRAFT_PARTIAL_DIAGNOSTIC_NOT_NATIVE_PRINT_CERTIFICATION",
        "immutable_original_source_sha": _SOURCE_SHA,
        "immutable_original_fixture_sha256": _sha(frozen_path),
        "old_alias_names_only_in_router": list(original_nets),
        "actual_canonical_source_names": list(REAL_SOURCE_NAMES),
        "source_raw_name_binding_to_routed_graph_approved": False,
        "owner_router_code_sha256": _sha(
            Path(__file__).resolve().parents[1]
            / "src/gost_schematic/engines/multiterminal_router.py"
        ),
        "owner_sha_metadata": owner_sha,
        "reference_sha_metadata": reference_sha,
        "actual_23_15_62_16_source_preserved": True,
        "max_nodes_per_search": max_nodes,
        "fixed_order_offset": priority_offset,
        "priority_trials": 1,
        "physical_veto_restarts": 0,
        "physical_ripup_attempts": physical_ripup_attempts,
        "physical_group_attempts": physical_group_attempts,
        "matrix": results,
        "legal_print_15_15_verified": False,
        "global_post_render_3_2_1mm_signed": False,
    }
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "TL494-cycle14-equal-budget-matrix.json"
    output.write_text(
        json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "matrix": str(output),
        "routed_per_variant": {
            item["key"]: item["routed_net_count"] for item in results
        },
        "all_15_net_print": False,
    }, sort_keys=True, ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--owner-sha", required=True)
    parser.add_argument("--reference-sha", required=True)
    parser.add_argument("--node-cap", type=int, default=4000)
    parser.add_argument("--priority-offset", type=int, default=0)
    parser.add_argument("--physical-ripup-attempts", type=int, default=0)
    parser.add_argument("--physical-group-attempts", type=int, default=0)
    parser.add_argument(
        "--variant", action="append", choices=tuple(MOVE_VARIANTS),
    )
    args = parser.parse_args()
    run_matrix(
        args.output, args.font_file,
        owner_sha=args.owner_sha,
        reference_sha=args.reference_sha,
        variants=tuple(args.variant or MOVE_VARIANTS),
        max_nodes=args.node_cap,
        priority_offset=args.priority_offset,
        physical_ripup_attempts=args.physical_ripup_attempts,
        physical_group_attempts=args.physical_group_attempts,
    )


if __name__ == "__main__":
    main()
