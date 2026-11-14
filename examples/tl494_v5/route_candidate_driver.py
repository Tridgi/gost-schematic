"""Owner-pinned TL494 v5 multi-candidate, ALL-15-Net route diagnostics.

This is a fail-closed model/route driver, NOT a sheet print generator.
It compares with the original bytes-locked #97 source fixture before any
routing, then restores the ORIGINAL 15 Net names (including a_/b_/TRANSFER)
while retaining the 23 positioned source ComponentInstances and 62 PinRefs.
No raster/SVG, phantom Net, inferred junction, wire deletion or QA approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, replace
from importlib import import_module
from pathlib import Path

from examples.tl494_v5.compact_layout import (
    A3_LANDSCAPE_UM,
    COMPACT_A3_MM,
    actual_component_occupied_mm,
    compact_source_assembly,
)
from examples.tl494_v5.native_circuit import (
    NET_RENAMES,
    NativeV5Assembly,
    assemble_native_v5,
)
from examples.tl494_v5.route_preflight import (
    MeasuredInkGuard,
    _owner_ic_obstacle,
)
from examples.tl494_v5.routed_graph_contract import rehydrate_verified_route_graph
from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.circuit import Circuit, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
OWNER_SHAS = {
    "ELEKTRIK_IC_PR97": "19d14c4b660c9ad490a65cd1eab644f1637bc334",
    "PAINT_PR93": "32f2efb2cdcb561cb2567a54448381de3cb87832",
    "YGO2_PR113": "eb16121e07efec71de77dfc7b8123bc09f66ddd6",
    "ELEKTRIK_NET_PR114": "5033659747f01fdc03adc084b846f47b05001963",
}
EXPECTED_FIXTURE_GIT_SHA1 = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
ORIGINAL_BAD_DRC = {
    "error_count": 9, "warning_count": 32,
    "segments": 91, "junctions": 37,
}
REAL_SOURCE_NAMES = (
    "a_INPUT_PLUS", "SWITCH", "TRANSFER", "OUT_BEFORE_FUSE",
    "b_NEGATIVE_OUTPUT", "GATE_DRIVE", "CONTROL_REFERENCE", "SOFT_START",
    "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK", "ADJUSTED_DIVIDER",
    "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
)


@dataclass(frozen=True, slots=True)
class Candidate:
    """Only route order or genuine ComponentInstance origins may differ."""
    key: str
    priority: tuple[str, ...]
    move_mm: tuple[tuple[str, int, int], ...] = ()


def _pins(nets) -> dict[str, tuple[str, ...]]:
    return {
        net.name: tuple(f"{p.reference}.{p.number}" for p in net.members)
        for net in nets
    }


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def restore_original_named_nets(
    positioned: NativeV5Assembly, source_fixture: dict,
) -> Circuit:
    """Refuse any alias, PinRef or Decimal BOM difference; restore raw names.

    The historical v5 alias map is explicit/reversible, not permission to
    silently rename the actual photographed Net IDs on the resulting drawing.
    """
    positioned.verify()
    source_parts = {
        row["ref"]: row for row in source_fixture["components"]
    }
    if set(source_parts) != {
        instance.reference for instance in positioned.circuit.components
    } or len(source_parts) != 23:
        raise ValueError("V5_CANDIDATE_SOURCE_BOM_REFS_DRIFT")
    for item in positioned.circuit.components:
        row = source_parts[item.reference]
        if row["part_id"] != item.part_id:
            raise ValueError("V5_CANDIDATE_ORIGINAL_PART_ID_CHANGED:" + item.reference)
        nominal = item.nominal
        if row["nominal_si"] is None:
            if nominal is not None:
                raise ValueError("V5_CANDIDATE_PHANTOM_NOMINAL:" + item.reference)
        else:
            from decimal import Decimal

            if nominal is None or nominal.si_value != Decimal(row["nominal_si"]):
                raise ValueError("V5_CANDIDATE_REAL_NOMINAL_CHANGED:" + item.reference)
    raw = source_fixture["nets"]
    if set(raw) != set(REAL_SOURCE_NAMES) or len(raw) != 15:
        raise ValueError("V5_CANDIDATE_SOURCE_ORIGINAL_NET_NAMES_DRIFT")
    if set(NET_RENAMES) != {
        "a_INPUT_PLUS", "TRANSFER", "b_NEGATIVE_OUTPUT"
    } or len(set(NET_RENAMES.values())) != len(NET_RENAMES):
        raise ValueError("V5_CANDIDATE_ALIAS_REGISTRY_CHANGED")
    aliases = _pins(positioned.circuit.nets)
    restored = []
    for original_name, members in raw.items():
        canonical_alias = NET_RENAMES.get(original_name, original_name)
        if aliases.get(canonical_alias) != tuple(members):
            raise ValueError(
                f"V5_CANDIDATE_PHYSICAL_PINREF_NET_DRIFT:{original_name}"
            )
        restored.append(Net(
            original_name,
            tuple(PinRef(*member.rsplit(".", 1)) for member in members),
        ))
    out = Circuit(positioned.circuit.components, tuple(restored))
    all_members = tuple(
        member for net in out.nets for member in net.members
    )
    if len(all_members) != 62 or len(set(all_members)) != 62:
        raise ValueError("V5_CANDIDATE_SOURCE_62_PHYSICAL_CONTACTS_DRIFT")
    if {
        p.number for p in all_members if p.reference == "DA1"
    } != {str(n) for n in range(1, 17)}:
        raise ValueError("V5_CANDIDATE_TI_PHYSICAL_16_DRIFT")
    if "PE" in raw or "CHASSIS" in raw:
        raise ValueError("V5_CANDIDATE_FORBID_UNSOURCED_EARTH")
    return out


def position_only_move(
    base: NativeV5Assembly,
    movements: tuple[tuple[str, int, int], ...],
) -> NativeV5Assembly:
    """Reposition only real parts on 2.5mm grid; origin Net unchanged."""
    if not movements:
        return base
    if len({row[0] for row in movements}) != len(movements):
        raise ValueError("V5_CANDIDATE_DUPLICATE_MOVE")
    if any(
        ref not in COMPACT_A3_MM or type(dx) is not int or type(dy) is not int
        or abs(dx) > 30 or abs(dy) > 30
        or dx * 1000 % 2500 != 0 or dy * 1000 % 2500 != 0
        for ref, dx, dy in movements
    ):
        raise ValueError("V5_CANDIDATE_MOVE_MUST_BE_SOURCED_2P5MM_GRID")
    offsets = {ref: Point(dx * 1000, dy * 1000)
               for ref, dx, dy in movements}
    moved = tuple(
        replace(component, origin=component.origin + offsets[component.reference])
        if component.reference in offsets else component
        for component in base.circuit.components
    )
    ic_record = base.owner_ic_record
    if "DA1" in offsets:
        ic_record = replace(
            ic_record,
            placements=tuple(
                replace(placement, origin=placement.origin + offsets["DA1"])
                for placement in ic_record.placements
            ),
        )
    bind = import_module(
        "gost_schematic.catalog.source_profiles"
    ).bind_tl494_source
    result = replace(
        base, circuit=Circuit(moved, base.circuit.nets),
        owner_ic_record=ic_record,
        source_UGO_bindings=tuple(bind(
            moved, base.parts, base.symbols,
            allow_relayout=True,  # Explicit NEW A3 candidate, not source change
        )),
    )
    result.verify()
    if result.circuit.nets != base.circuit.nets:
        raise AssertionError("V5_CANDIDATE_POSITION_MOVED_NET")
    for before, after in zip(
        base.circuit.components, result.circuit.components, strict=True
    ):
        if (
            before.reference != after.reference
            or before.part_id != after.part_id
            or before.nominal != after.nominal
            or before.transform != after.transform
        ):
            raise AssertionError("V5_CANDIDATE_NOT_POSITION_ONLY")
    return result


def load_original_owner_fixture() -> tuple[dict, object]:
    owner = import_module("examples.tl494_cycle9_circuit_integration")
    binding, frozen = owner.build_frozen_photo_23()
    owner.assert_frozen_photo_topology(binding, frozen)
    if (
        owner.FROZEN_SOURCE_COMMIT != SOURCE_SHA
        or owner.FROZEN_FIXTURE_GIT_BLOB_SHA1 != EXPECTED_FIXTURE_GIT_SHA1
    ):
        raise ValueError("V5_CANDIDATE_OWNER_SOURCE_SHA_MISMATCH")
    assert binding.contact(PinRef("DA1", "3")).electrical_type.value == "input"
    assert binding.contact(PinRef("DA1", "13")).electrical_type.value == "input"
    return frozen, binding


def candidate_priority(frozen: dict, key: str) -> tuple[str, ...]:
    raw = frozen["nets"]
    if key == "source":
        priority = REAL_SOURCE_NAMES
    elif key == "short-first":
        priority = tuple(sorted(raw, key=lambda name: (len(raw[name]), name)))
    elif key == "control-first":
        control = ("OSCILLATOR_RT", "OSCILLATOR_CT", "FEEDBACK",
                   "RC_CORRECTION", "SOFT_START", "ERROR_INPUT",
                   "CONTROL_REFERENCE", "GATE_DRIVE")
        priority = (*control, *(name for name in REAL_SOURCE_NAMES
                                if name not in control))
    else:
        raise ValueError("V5_CANDIDATE_UNRECOGNIZED_ROUTE_PRIORITY")
    if set(priority) != set(raw) or len(priority) != 15:
        raise ValueError("V5_CANDIDATE_NOT_15_ORIGINAL_NET_PRIORITIES")
    return tuple(priority)


def _build_obstacles(assembly, net_circuit, font_file):
    inspection = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    style = inspection.style
    measurer = PillowTextMeasurer()
    bridge = import_module(
        "gost_schematic.electrical.ic_paint_bridge"
    ).propose_ic_paint_binding(
        assembly.owner_ic_record, style, measurer
    )
    bridge.verify_endpoints()
    render = import_module(
        "gost_schematic.rendering.ic_rectangular"
    ).render_resolved_ic(
        bridge.views[0], style, measurer, glyph_detail=True
    )
    da1 = next(c for c in net_circuit.components if c.reference == "DA1")
    symbol = _owner_ic_obstacle(bridge.views[0], render.svg, da1)
    symbols = dict(assembly.symbols)
    symbols["reference.tl494cn"] = symbol
    exact_pa_int = tuple(
        MeasuredInkGuard(ink.owner, ink.box.expanded(500))
        for ink in render.ink
        if ink.kind in (
            "refdes", "pin-label", "pin-number",
            "function", "main-text", "field-text",
        )
    )
    sheet = layout_sheet(net_circuit, symbols, style, measurer)
    footprint = actual_component_occupied_mm(assembly, symbols)
    guards = (*exact_pa_int, *sheet.placements)
    if len(bridge.views[0].pins) != 16:
        raise AssertionError("V5_CANDIDATE_PAINT_LOST_16_PINS")
    return symbols, guards, sheet, footprint, style


def score_route(report: dict) -> tuple[int, int, int, int, int]:
    """Deterministic ranking of partial evidence; never a release decision."""
    trees = report.get("net_trees", ())
    complete = sum(tree["complete"] for tree in trees)
    attached = sum(len(tree["connected_pin_refs"]) for tree in trees)
    drc = report.get("drc") or {}
    return (
        complete, attached,
        -int(drc.get("error_count", 10**9)),
        -len(report.get("diagnostics", ())),
        -sum(tree["segments"] for tree in trees),
    )


def run_candidate(
    font_file: Path,
    config: Candidate,
    *,
    node_cap: int = 25000,
    frozen: dict | None = None,
    owner_binding: object | None = None,
) -> dict:
    """Attempt EVERY original named Net, preserving even failed PinRefs."""
    if type(node_cap) is not int or not 100 <= node_cap <= 100000:
        raise ValueError("V5_CANDIDATE_INVALID_NODE_BUDGET")
    if frozen is None or owner_binding is None:
        frozen, owner_binding = load_original_owner_fixture()
    positioned = position_only_move(compact_source_assembly(), config.move_mm)
    net_circuit = restore_original_named_nets(positioned, frozen)
    source_named = _pins(net_circuit.nets)
    typed_owner = _pins(owner_binding.circuit.nets)
    if source_named != typed_owner:
        raise ValueError("V5_CANDIDATE_REAL_IC_OWNER_NET_MISMATCH")
    symbols, guards, layout, footprint, style = _build_obstacles(
        positioned, net_circuit, font_file
    )
    reason = None
    if not layout.valid:
        reason = "COMPONENT_OR_TEXT_LAYOUT_REJECTED"
    if not footprint["A3_capacity_fit"]:
        reason = "COMPACT_A3_REAL_INK_NOT_FIT"
    if reason is not None:
        return {
            "key": config.key,
            "status": "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT",
            "reason": reason,
            "score": None,
            "source_nets": source_named,
            "Net_membership_SHA256": _digest(source_named),
            "source_unchanged": True,
            "a3": footprint,
            "layout_valid": layout.valid,
            "layout_error_codes": [
                x.code for x in layout.diagnostics
                if x.severity.value == "error"
            ],
            "routes_attempted": 0, "routed_net_count": 0,
            "print_after_released": False,
            "technical_route_eligible": False,
        }
    router = import_module(
        "gost_schematic.engines.multiterminal_router"
    ).route_circuit_net_trees
    result = router(
        net_circuit, positioned.parts, symbols,
        page_box=Box(0, 0, *A3_LANDSCAPE_UM),
        annotation_placements=guards, priority=config.priority,
        search_node_cap=node_cap, stop_on_first_failure=False,
    )
    # An owner's partial graph can be DRC=0 because failed tree segments
    # are NOT accepted. Do not pretend that means all 15 original Nets PASS.
    report = result.as_dict()
    seen_names = {tree["net"] for tree in report["net_trees"]}
    if len(report["net_trees"]) != 15 or seen_names != set(source_named):
        raise AssertionError("V5_CANDIDATE_ROUTER_SILENTLY_SKIPPED_NET")
    for tree in report["net_trees"]:
        name = tree["net"]
        if tree["pin_refs"] != list(source_named[name]):
            raise AssertionError("V5_CANDIDATE_OWNER_ROUTER_PINREF_DRIFT:" + name)
        if not set(tree["connected_pin_refs"]) <= set(source_named[name]):
            raise AssertionError("V5_CANDIDATE_FAKE_ATTACHED_PINREF:" + name)
    if _pins(net_circuit.nets) != source_named or _pins(
        positioned.circuit.nets
    ) != {
        NET_RENAMES.get(name, name): pins
        for name, pins in source_named.items()
    }:
        raise AssertionError("V5_CANDIDATE_ROUTING_MUTATED_SOURCE_NETS")
    scores = score_route(report)
    route_eligible = bool(
        report["complete"] and result.print_pass
        and report["routed_net_count"] == 15
        and report["drc"] is not None
        and report["drc"]["error_count"] == 0
        and footprint["A3_capacity_fit"] and layout.valid
        and sum(len(tree["connected_pin_refs"])
                for tree in report["net_trees"]) == 62
    )
    return {
        "key": config.key,
        "status": (
            "ROUTED_15_OF_15_QA_REQUIRED" if route_eligible else
            "BLOCKED_PARTIAL_ROUTING_NO_PRINT"
        ),
        "owner_router_report": report,
        "priority": list(config.priority),
        "moves_mm": [list(move) for move in config.move_mm],
        "source_nets": source_named,
        "Net_membership_SHA256": _digest(source_named),
        "source_unchanged": True,
        "a3": footprint,
        "annotation_guards": len(guards),
        "layout_valid": layout.valid,
        "font_sha256": style.font_sha256,
        "score": list(scores),
        "routes_attempted": len(report["net_trees"]),
        "routed_net_count": report["routed_net_count"],
        "technical_route_eligible": route_eligible,
        "print_after_released": False,
        "named_net_status": {
            tree["net"]: {
                "complete": tree["complete"],
                "connected": tree["connected_pin_refs"],
                "expected": tree["pin_refs"],
                "segments": tree["segments"],
                "diagnostics": tree["diagnostics"],
            }
            for tree in report["net_trees"]
        },
        "accepted_graph_nonprintable": {
            "total_segment_count": len(result.graph.segments),
            "total_manhattan_length_mm": round(sum(
                abs(w.start.x - w.end.x) + abs(w.start.y - w.end.y)
                for w in result.graph.segments
            ) / 1000, 3),
            "source_original_wire_count": 91,
            "historical_negative_not_overwritten": True,
            "segments_um": [
                {
                    "net": wire.net_name,
                    "start": [wire.start.x, wire.start.y],
                    "end": [wire.end.x, wire.end.y],
                }
                for wire in result.graph.segments
            ],
            "junctions_um": [
                [p.x, p.y] for p in result.graph.junctions
            ],
            "status": "DIAGNOSTIC_ONLY_NOT_PRINT_AFTER",
        },
    }


def drive_candidates(
    font_file: Path, output_file: Path, *,
    variants: tuple[str, ...] = ("source",),
    node_cap: int = 25000,
) -> dict:
    """Current owner trial/snapshot + best partial evidence, no success fiction."""
    if not variants or len(variants) > 3 or len(set(variants)) != len(variants):
        raise ValueError("V5_CANDIDATE_INVALID_VARIANT_SET")
    frozen, owner_binding = load_original_owner_fixture()
    original = assemble_native_v5()
    original.verify()
    before_ink = _build_obstacles(
        original, original.circuit, font_file
    )[3]
    trials = [
        run_candidate(
            font_file, Candidate(key, candidate_priority(frozen, key)),
            node_cap=node_cap, frozen=frozen, owner_binding=owner_binding,
        )
        for key in variants
    ]
    # Verify each serialized accepted graph is a genuine typed PAINT input.
    # This is NOT a print approval; incomplete graphs stay blocked.
    for trial in trials:
        if trial.get("status") != "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT":
            rehydrate_verified_route_graph(trial, frozen["nets"])
    ranked = sorted(
        trials,
        key=lambda trial: (
            tuple(trial.get("score") or (-1, -1, -10**9, -10**9, -10**9)),
            -variants.index(trial["key"]),
        ),
        reverse=True,
    )
    best = ranked[0]
    source_nets = best["source_nets"]
    result = {
        "schema": "TL494_23_15_62_SOURCE_LOCKED_ROUTE_CANDIDATES_V1",
        "status": "DRAFT_TEST_ONLY",
        "source_reference_sha": SOURCE_SHA,
        "frozen_photo_fixture_git_blob": EXPECTED_FIXTURE_GIT_SHA1,
        "owner_exact_SHAs": OWNER_SHAS,
        "bom_count": 23,
        "net_count": len(source_nets),
        "physical_net_membership_count": sum(
            len(members) for members in source_nets.values()
        ),
        "original_net_names": list(frozen["nets"]),
        "internal_aliases_reverse": NET_RENAMES,
        "original_nets_SHA256": _digest(source_nets),
        "source_BOM": frozen["components"],
        "source_BOM_SHA256": _digest(frozen["components"]),
        "original_Netlist": frozen["nets"],
        "before_after_UGO_footprints": {
            "metric": "actual_symbol_stroked_component_envelopes_only",
            "excludes": "wire and sheet-border extents, text/photo overlay",
            "source_original": before_ink,
            "compact_candidate": best["a3"],
            "saved_width_mm": round(
                before_ink["width_mm"] - best["a3"]["width_mm"], 3
            ),
            "all_UGO_unscaled": True,
        },
        "source_photo_comparison": {
            "physical_BOM_refs": "EXACT_23_FROM_BYTE_PINNED_FIXTURE",
            "physical_Pins_and_Nets": "EXACT_62_IN_15_ORIGINAL_NAMED_NETS",
            "photographic_pixel_alignment": "NOT_AVAILABLE_UNVERIFIED",
            "actual_functional_behavior": "NOT_SIMULATED_OR_CERTIFIED",
            "symbol_GOST_approval": "DRAFT_NOT_APPROVED",
        },
        "negative_original_DRC_expected": ORIGINAL_BAD_DRC,
        "paper": "A3 landscape 420x297mm; 10mm margins; DRAFT",
        "candidates": trials,
        "best_evidence_variant": best["key"],
        "best_completed_nets": best["routed_net_count"],
        "qa_print_release": "BLOCKED_INDEPENDENT_QA_AND_ESKD",
        "actual_full_sheet_svg_or_png_emitted": False,
    }
    if result["net_count"] != 15 or result[
        "physical_net_membership_count"
    ] != 62:
        raise AssertionError("V5_CANDIDATE_SOURCE_COUNTS_DRIFT")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--node-cap", type=int, default=25000)
    parser.add_argument(
        "--variants", nargs="+", choices=("source", "short-first", "control-first"),
        default=("source",),
    )
    args = parser.parse_args()
    evidence = drive_candidates(
        args.font_file, args.output_file,
        variants=tuple(args.variants), node_cap=args.node_cap,
    )
    print(json.dumps({
        "HEAD_owner_shas": evidence["owner_exact_SHAs"],
        "best": evidence["best_evidence_variant"],
        "completed_nets": evidence["best_completed_nets"],
        "out": str(args.output_file),
        "print_release": evidence["qa_print_release"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
