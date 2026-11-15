"""Deterministic bounded physical A3 placement experiments for TL494 Cycle 13.

Only the 23 genuine component origins may move, on a strict 2.5 mm grid.
The signed manufacturer IC, all 15 ORIGINAL named Nets and all 62 physical
PinRefs are checked afresh for every proposal. Results are diagnostics,
never a completed E3 print approval or a synthetic repair of failed Nets.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.route_candidate_driver import (
    ORIGINAL_BAD_DRC,
    OWNER_SHAS,
    REAL_SOURCE_NAMES,
    SOURCE_SHA,
    Candidate,
    load_original_owner_fixture,
    position_only_move,
    restore_original_named_nets,
    run_candidate,
)
from examples.tl494_v5.routed_graph_contract import rehydrate_verified_route_graph

# Actual reported paper/ink bottlenecks were DA1.3/6/13/15, VT1.1/R8.1
# and R1.1. These are editorial proposals, NOT electrical amendments.
# Restrict experiments to three bounded move sets and an unchanged baseline.
PLACEMENT_TRIALS = (
    ("x1_17_baseline", ()),
    ("da1_left_2p5", (("DA1", Decimal("-2.5"), 0),)),
    ("gate_vt1_r8_right_5", (("VT1", 5, 0), ("R8", 5, 0))),
    ("reference_r1_up_2p5", (("R1", 0, Decimal("-2.5")),)),
)


def summarize_trial(name: str, trial: dict) -> dict:
    """Preserve every original-name failure, including layout-blocked trials."""
    if trial["source_unchanged"] is not True:
        raise ValueError("C13_PLACEMENT_CHANGED_SOURCE")
    footprint = trial["a3"]
    count = trial["routed_net_count"]
    if type(count) is not int or not 0 <= count <= 15:
        raise ValueError("C13_PLACEMENT_INVALID_ROUTE_COUNT")
    attempted = trial["routes_attempted"]
    if attempted not in (0, 15):
        raise ValueError("C13_PLACEMENT_ROUTER_SILENTLY_SKIPPED_NET")
    if attempted == 0 and trial["status"] != (
        "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT"
    ):
        raise ValueError("C13_PLACEMENT_ROUTE_NOT_ATTEMPTED_UNDISCLOSED")
    if attempted == 15 and len(trial["named_net_status"]) != 15:
        raise ValueError("C13_PLACEMENT_NET_DIAGNOSTICS_MISSING")
    if trial["print_after_released"] is not False:
        raise ValueError("C13_PLACEMENT_UNVERIFIED_PRINT_RELEASE")
    return {
        "name": name,
        "status": trial["status"],
        "moves_mm": trial.get("moves_mm", []),
        "completed_nets": count,
        "routes_attempted": attempted,
        "a3_bbox_um": footprint["bbox_um"],
        "a3_bbox_within_margins": footprint["A3_bbox_within_margins"],
        "a3_capacity_fit": footprint["A3_capacity_fit"],
        "layout_valid": trial["layout_valid"],
        "manufacturer_binding": trial.get("manufacturer_binding"),
        "b_continuation_rebound": trial.get("b_continuation_rebound"),
        "named_net_status": trial.get("named_net_status", {}),
        "technical_route_eligible": trial["technical_route_eligible"],
        "print_after_released": False,
    }


def run_placement_matrix(
    font_file: Path,
    output_file: Path,
    *,
    node_cap: int = 1500,
) -> dict:
    """Try each real position-only draft separately, never pool partial wires."""
    frozen, owner = load_original_owner_fixture()
    base = compact_source_assembly()
    source = restore_original_named_nets(base, frozen)
    original_nets = {
        net.name: tuple(net.members) for net in source.nets
    }
    assert len(base.circuit.components) == 23
    assert len(original_nets) == 15
    assert sum(map(len, original_nets.values())) == 62
    assert {pin.number for net in source.nets for pin in net.members
            if pin.reference == "DA1"} == set(map(str, range(1, 17)))

    variants = []
    for key, changes in PLACEMENT_TRIALS:
        moved = position_only_move(base, changes)
        if moved.circuit.nets is not base.circuit.nets:
            raise ValueError("C13_PLACEMENT_MOVED_CANONICAL_NET_TUPLE")
        verified_source = restore_original_named_nets(moved, frozen)
        if {
            net.name: tuple(net.members) for net in verified_source.nets
        } != original_nets:
            raise ValueError("C13_PLACEMENT_MOVED_PHYSICAL_PINREFS")
        trial = run_candidate(
            font_file,
            Candidate(
                "congested-veto", REAL_SOURCE_NAMES, changes,
                router_mode="congested-veto",
            ),
            node_cap=node_cap, frozen=frozen, owner_binding=owner,
        )
        if trial["source_nets"] != {
            name: tuple(f"{p.reference}.{p.number}" for p in pins)
            for name, pins in original_nets.items()
        }:
            raise ValueError("C13_PLACEMENT_SOURCE_NAME_OR_PINREF_DRIFT")
        if trial["status"] != "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT":
            rehydrate_verified_route_graph(trial, frozen["nets"])
        variants.append(summarize_trial(key, trial))
    result = {
        "schema": "C13_SOURCE_LOCKED_PHYSICAL_A3_PLACEMENT_MATRIX_V1",
        "source_sha": SOURCE_SHA,
        "owner_exact_shas": OWNER_SHAS,
        "components": 23,
        "nets": 15,
        "pinref_memberships": 62,
        "manufacturer_DA1_pins": 16,
        "frozen_negative_DRC": ORIGINAL_BAD_DRC,
        "node_cap": node_cap,
        "trials": variants,
        "best_partial_completed_nets": max(
            t["completed_nets"] for t in variants
        ),
        "full_print_QA_ESKD": "BLOCKED_UNTIL_15_OF_15_AND_REAL_INK_DRC",
        "actual_full_sheet_svg_or_png_emitted": False,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--node-cap", type=int, default=1500)
    options = parser.parse_args()
    report = run_placement_matrix(
        options.font_file, options.output_file, node_cap=options.node_cap,
    )
    print(json.dumps({
        "owner_shas": report["owner_exact_shas"],
        "trials": [
            (trial["name"], trial["completed_nets"], trial["a3_capacity_fit"])
            for trial in report["trials"]
        ],
        "release": report["full_print_QA_ESKD"],
    }, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
