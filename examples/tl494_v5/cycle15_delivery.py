"""Source-locked TL494 real owner end-to-end delivery candidate (never fake PASS).

Runs real NET #114 route and native PAINT #93 SVG from one immutable 23/15/62
source model; appends exactly the two proven NON-electrical source-b markers
with PAINT's verified physical SVG compositor. Emits full original Net-name
machine mapping, physical PinRefs and exact blocked reasons on partial graphs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from examples.tl494_named_photo_sheet import compose_circuit
from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_b_continuation import rebind_true_source_b
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.native_circuit import NET_RENAMES
from examples.tl494_v5.route_candidate_driver import (
    OWNER_SHAS,
    SOURCE_SHA,
    load_original_owner_fixture,
    parse_candidate_moves,
    position_only_move,
    restore_original_named_nets,
    source_signed_ink_footprint,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG_NS = "http://www.w3.org/2000/svg"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def produce_delivery(
    output: Path,
    font_file: Path,
    *,
    page_format: str = "A3",
    component_moves: tuple = (("C1", 0, 2.5),),
    node_cap: int = 4000,
    priority_trials: int = 1,
    priority_offset: int = 3,
    physical_veto_restarts: int = 1,
    physical_ripup_attempts: int = 2,
) -> dict:
    """One genuine current-owner native route/render, with strict original IDs."""
    if page_format not in ("A3", "A2") or not 100 <= node_cap <= 100000:
        raise ValueError("C15_INVALID_PAPER_OR_SEARCH_BUDGET")
    if not 0 <= physical_ripup_attempts <= 5:
        raise ValueError("C15_UNBOUNDED_RIPUP")
    frozen, owner = load_original_owner_fixture()
    assembly = position_only_move(compact_source_assembly(), component_moves)
    original = restore_original_named_nets(assembly, frozen)
    original_members = {
        n.name: tuple(f"{p.reference}.{p.number}" for p in n.members)
        for n in original.nets
    }
    if (len(original.components), len(original.nets)) != (23, 15):
        raise ValueError("C15_ORIGINAL_23_15_DRIFT")
    if sum(map(len, original_members.values())) != 62:
        raise ValueError("C15_ORIGINAL_62_PHYSICAL_PINREF_DRIFT")
    if owner.circuit.nets != original.nets:
        raise ValueError("C15_OWNER_FROZEN_SOURCE_NET_MISMATCH")
    ti = bind_verified_compact_ti(assembly, original)
    ti.verify()
    symbols, physical_ink = source_signed_ink_footprint(assembly, font_file)
    from examples.tl494_v5.cycle14_pin_corridor_probe import measure_pin_corridors
    paper = measure_pin_corridors(
        font_file, page_format=page_format, move_mm=component_moves,
    )
    if (paper["original_nets"] != {
        k: list(v) for k, v in original_members.items()
    } or paper["true_nonphysical_b_labels_count"] != 2):
        raise ValueError("C15_PAPER_OR_B_PROOF_SOURCE_DRIFT")
    if not paper["measured_text_10mm_frame_fit"] or (
        not paper["absolute_10mm_component_ink_fit"]
    ):
        return _record_blocked_before_router(
            output, paper, original_members, font_file,
        )
    from examples import review_tl494_compact_cycle9 as owner_route
    real_factory = owner_route.compact_source_assembly
    # Adapt the owner-specific entrypoint to a genuine immutable moved
    # NativeV5Assembly; never edit owner files or substitute a router.
    owner_route.compact_source_assembly = lambda: assembly
    native_dir = output / "native"
    try:
        raw = owner_route.produce(
            native_dir,
            font_file,
            owner_sha=OWNER_SHAS["ELEKTRIK_NET_PR114"],
            reference_sha=SOURCE_SHA,
            page_format=page_format,
            node_cap=node_cap,
            priority_trials=priority_trials,
            priority_offset=priority_offset,
            physical_veto_restarts=physical_veto_restarts,
            physical_ripup_attempts=physical_ripup_attempts,
        )
    finally:
        owner_route.compact_source_assembly = real_factory
    if raw["source_sha"] != SOURCE_SHA or (
        raw["source_components"], raw["source_nets"],
        raw["all_Circuit_PinRef_memberships"], raw["physical_DA1_pin_count"],
    ) != (23, 15, 62, 16):
        raise ValueError("C15_ROUTED_NATIVE_SOURCE_IDENTITY_DRIFT")
    # The NET example still uses its compact internal INPUT_POS etc aliases.
    # Verify the exact original source named physical tuples are a bijection.
    expected_alias = {
        NET_RENAMES.get(name, name): members
        for name, members in original_members.items()
    }
    if len(expected_alias) != 15 or raw["net_members"] != {
        k: list(v) if isinstance(raw["net_members"].get(k), list) else v
        for k, v in expected_alias.items()
    }:
        raise ValueError("C15_NET_OWNER_MISMATCH_SOURCE_PINREFS_OR_ALIAS")
    reverse_alias = {
        NET_RENAMES.get(name, name): name
        for name in original_members
    }
    routed_names = set()
    net_evidence = {}
    for node in raw["routing"]["net_trees"]:
        alias = node["net"]
        if alias not in reverse_alias:
            raise ValueError("C15_OWNER_INSERTED_UNKNOWN_ELECTRICAL_NET")
        actual_name = reverse_alias[alias]
        if actual_name in routed_names:
            raise ValueError("C15_DUPLICATED_ORIGINAL_NET")
        routed_names.add(actual_name)
        net_evidence[actual_name] = {
            "owner_internal_alias": alias,
            "source_pinrefs": list(original_members[actual_name]),
            "complete": bool(node["complete"]),
            "connected_pinrefs": node["connected_pin_refs"],
            "diagnostics": node["diagnostics"],
            "segments": node["segments"],
        }
    if routed_names != set(original_members):
        raise ValueError("C15_ORIGINAL_NET_OMITTED")
    counted = sum(x["complete"] for x in net_evidence.values())
    if counted != raw["routed_nets"] or counted > 15:
        raise ValueError("C15_OWNER_ROUTE_COMPLETENESS_SPOOFED")
    true_b = rebind_true_source_b(
        compose_circuit(font_file)[-1], ti.signed.circuit, symbols,
    )
    from gost_schematic.rendering.ic_sheet_composition import (
        append_verified_sheet_continuations,
    )
    style = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    ).style
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for mode in ("clean", "diagnostic"):
        source_file = native_dir / (
            f"TL494-compact-{page_format}-{mode}.svg"
        )
        root = ET.fromstring(source_file.read_bytes())
        append_verified_sheet_continuations(
            root, ti.signed.circuit, true_b, style,
            diagnostic=(mode == "diagnostic"),
            symbols_by_part=symbols,
        )
        b_lines = root.findall(
            f".//{{{SVG_NS}}}line[@data-layer='nonphysical-continuation-stub']"
        )
        if len(b_lines) != 2:
            raise ValueError("C15_PAINT_2_TRUE_GRAPHICAL_B_STROKES_MISSING")
        # Typed native DA1 must have exactly 16 real leads, 0 editor marks
        # in clean and 16 *genuine* manufacturer targets in diagnostic SVG.
        leads = root.findall(
            f".//{{{SVG_NS}}}g[@data-layer='ic-physical-pin-leads']"
            f"/{{{SVG_NS}}}line"
        )
        layers = root.findall(
            f".//{{{SVG_NS}}}g[@data-layer='editor-connection-targets']"
        )
        editor = list(layers[0]) if len(layers) == 1 else []
        if len(leads) != 16 or (
            (mode == "clean" and layers)
            or (mode == "diagnostic" and (
                len(layers) != 1 or len(editor) != 16
                or {x.get("data-pin-ref") for x in editor}
                != {f"DA1.{i}" for i in range(1, 17)}
                or not all(x.get("fill") == "#148645" for x in editor)
            ))
        ):
            raise ValueError("C15_PAINT_16_NATIVE_CONTACTS_EDITOR_MODE_DRIFT")
        # Only metadata aliases are translated to original source names;
        # no electrical model, conductor, junction or SVG geometry is edited.
        for graphic in root.iter():
            for attribute in ("data-net-id", "data-net",
                              "data-net-name"):
                old_name = graphic.get(attribute)
                if old_name in reverse_alias:
                    graphic.set(attribute, reverse_alias[old_name])
        root.set("data-original-source-names-restored-in-manifest", "true")
        root.set("data-source-physical-pinrefs", "62")
        root.set("data-source-electrical-net-count", "15")
        # These are authentic partial route graphics, NOT final print.
        if counted != 15:
            root.set("data-release", "BLOCKED_PARTIAL")
        out_file = output / f"TL494-{page_format}-{mode}-source-b.svg"
        out_file.write_bytes(ET.tostring(
            root, encoding="utf-8", xml_declaration=True,
        ))
        artifacts[out_file.name] = {
            "sha256": _digest(out_file),
            "measured_b_graphic_strokes": len(b_lines),
            "release": "BLOCKED_PARTIAL" if counted != 15 else
                       "ROUTE_COMPLETE_INDEPENDENT_QA_PENDING",
        }
    raw_drc = native_dir / f"TL494-compact-{page_format}-route-drc.json"
    artifacts[raw_drc.name] = {
        "sha256": _digest(raw_drc), "kind": "real-owner-global-DRC",
    }
    manifest = {
        "schema": "GOST_TL494_CYCLE15_ONE_COMMAND_SOURCE_LOCKED_DELIVERY_V1",
        "source_sha": SOURCE_SHA,
        "owner_exact_shas": OWNER_SHAS,
        "source_font_sha256": _digest(font_file),
        "source_23_components": 23,
        "source_15_literal_names": list(original_members),
        "source_62_physical_pinrefs": original_members,
        "source_16_signed_DA1": 16,
        "source_b_nonphysical": paper["true_b_source_stubs"],
        "paper": paper,
        "native_ugo_bbox_um": physical_ink["bbox_um"],
        "route_config": {
            "format": page_format,
            "component_moves_mm": [
                [ref, str(dx), str(dy)]
                for ref, dx, dy in component_moves
            ],
            "node_cap": node_cap,
            "priority_trials": priority_trials,
            "priority_offset": priority_offset,
            "physical_veto_restarts": physical_veto_restarts,
            "physical_ripup_attempts": physical_ripup_attempts,
        },
        "original_named_net_route_progress": net_evidence,
        "completed_original_nets": counted,
        "required_original_nets": 15,
        "routed_native_segments": raw["routed_segments"],
        "routed_native_drc_errors": len(raw["actual_new_drc_errors"]),
        "native_paper_frame_errors": raw["paper_10mm_editorial_frame_violations"],
        "artifacts": artifacts,
        "full_SVG_PNG300_release": "BLOCKED_UNTIL_15_15_GLOBAL_DRC_QA",
        "source_photo_pixel_parity": "NOT_VERIFIED",
        "main_or_integration_merge": False,
    }
    dest = output / "C15_REAL_TL494_DELIVERY.json"
    dest.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    return manifest


def _record_blocked_before_router(
    output: Path, paper: dict, source: dict, font_file: Path,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "GOST_TL494_CYCLE15_SOURCE_FRAME_BLOCKED_V1",
        "source_sha": SOURCE_SHA,
        "source_original_net_names": list(source),
        "source_original_62_pinrefs": source,
        "source_font_sha256": _digest(font_file),
        "real_measured_text_frame_violations": paper[
            "measured_text_frame_violations"
        ],
        "full_SVG_PNG300_release": "BLOCKED_SOURCE_TEXT_FRAME",
        "completed_original_nets": 0,
        "route_not_invoked": True,
    }
    (output / "C15_REAL_TL494_DELIVERY.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--font-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--page-format", choices=["A3", "A2"], default="A3")
    p.add_argument("--move", action="append", default=[])
    p.add_argument("--node-cap", type=int, default=4000)
    p.add_argument("--priority-trials", type=int, default=1)
    p.add_argument("--priority-offset", type=int, default=3)
    p.add_argument("--physical-veto-restarts", type=int, default=1)
    p.add_argument("--physical-ripup-attempts", type=int, default=2)
    args = p.parse_args()
    record = produce_delivery(
        args.output, args.font_file, page_format=args.page_format,
        component_moves=parse_candidate_moves(tuple(args.move or ["C1:0:2.5"])),
        node_cap=args.node_cap,
        priority_trials=args.priority_trials,
        priority_offset=args.priority_offset,
        physical_veto_restarts=args.physical_veto_restarts,
        physical_ripup_attempts=args.physical_ripup_attempts,
    )
    print(json.dumps({
        "source": record["source_sha"],
        "completed": record["completed_original_nets"],
        "required": 15,
        "release": record["full_SVG_PNG300_release"],
        "manifest": str(args.output / "C15_REAL_TL494_DELIVERY.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
