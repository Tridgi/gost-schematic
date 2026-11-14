"""Cycle11 read-only consumer compatibility against REAL NET/PAINT owner worktrees.

Run inside an isolated checked-out owner commit with the YGO source-profile
modules overlaid only in a TEMPORARY GitHub Actions worktree. This intentionally
does NOT modify the source commit, any owner branch, or the frozen original.
"""
import argparse
import importlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from gost_schematic.catalog.source_footprints import (
    footprint_record,
    source_footprint,
    source_reference_symbol,
)
from gost_schematic.catalog.source_profiles import (
    PINNED_REFERENCE_SHA,
    bind_tl494_source,
    load_catalog_pair,
    read_source_manifest,
)
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance

YGO_SOURCE_PROFILES = 13
D4_TRANSFORMS = 8
WIRE_STROKE_UM = 300


def _source_data():
    manifest = read_source_manifest()
    assert manifest["reference_sha"] == PINNED_REFERENCE_SHA
    parts, symbols, instances = {}, {}, []
    for row in manifest["profiles"]:
        symbol, part = load_catalog_pair(row["symbol_id"])
        symbols[symbol.identifier] = symbol
        parts[part.identifier] = part
        instances.append(ComponentInstance(
            row["reference"], row["symbol_id"],
            Point(*(int(x * 1000) for x in row["source_layout_origin_mm"])),
            Transform(row["rotation"], row["mirror_x"]),
        ))
    return parts, symbols, tuple(instances)


def _point(p):
    return [p.x, p.y]


def _box(b):
    return [b.min_x, b.min_y, b.max_x, b.max_y]


def compare_native_net_strokes() -> dict:
    from gost_schematic.engines.multiterminal_router import _source_ink_obstacles

    parts, symbols, positions = _source_data()
    cases = 0
    pin_leads = 0
    max_box_difference_um = 0
    for mirror in (False, True):
        for angle in (0, 90, 180, 270):
            moved = tuple(replace(
                comp, transform=Transform(angle, mirror)
            ) for comp in positions)
            bound = bind_tl494_source(
                moved, parts, symbols, allow_relayout=True
            )
            # The VT1 photo-specific printed dot is shared with YGO footprint
            # model; NET must consume the SAME printed symbol, never silently
            # revert to the un-dotted catalog version.
            rendered_symbols = dict(symbols)
            rendered_symbols["transistor.mosfet_n_enh"] = source_reference_symbol(
                symbols["transistor.mosfet_n_enh"], "VT1"
            )
            observed = _source_ink_obstacles(
                Circuit(moved, ()), rendered_symbols,
                stroke_um=WIRE_STROKE_UM,
            )
            grouped = {}
            for item in observed:
                grouped.setdefault(item.owner, {})[item.primitive_index] = item
            assert len(grouped) == YGO_SOURCE_PROFILES
            for binding in bound:
                footprint = source_footprint(binding)
                assert len(footprint_record(footprint)["footprint_sha256"]) == 64
                native = grouped[binding.reference]
                assert len(native) == len(footprint.ink_obstacles), (
                    "NET skipped printed source ink: " + binding.reference
                )
                assert len(footprint.lead_obstacles) == len(binding.part.pins)
                for i, actual in enumerate(footprint.ink_obstacles):
                    node = native[i]
                    # NET calculates bounds after D4; YGO's existing layout
                    # transforms conservative pre-D4 AABB. Inclusive segment
                    # +1um rounding can differ by <=2um, never whole mm.
                    expected = _box(actual.box.expanded(WIRE_STROKE_UM // 2))
                    got = _box(node.collision_bounds)
                    diff = max(abs(a - b) for a, b in zip(expected, got, strict=True))
                    max_box_difference_um = max(max_box_difference_um, diff)
                    if diff > 2:
                        raise AssertionError(
                            f"NET printed UGO obstacle drift {binding.reference}"
                            f"/D4={angle},{mirror}/primitive={i}: "
                            f"YGO={expected} NET={got} delta_um={diff}"
                        )
                for lead in footprint.lead_obstacles:
                    node = native[lead.graphic_index]
                    if (node.permitted_pin != lead.pin_ref
                        or node.contact not in (lead.segment.start, lead.segment.end)
                        or node.graphic_stroke_um != lead.stroke_width_um):
                        raise AssertionError(
                            "NET native source lead/physical PinRef mismatch "
                            + lead.pin_ref.reference + "." + lead.pin_ref.number
                        )
                    pin_leads += 1
                cases += 1
    assert cases == YGO_SOURCE_PROFILES * D4_TRANSFORMS
    assert pin_leads == 28 * D4_TRANSFORMS
    return {
        "consumer": "NET_PR114_REAL_SOURCE_INK_OBSTACLES",
        "source_profiles": YGO_SOURCE_PROFILES,
        "D4_true_owner_comparisons": cases,
        "physical_pin_lead_checks": pin_leads,
        "max_AABB_drift_um": max_box_difference_um,
        "status": "PASS_TYPED_UGO_STROKES_NOT_GLOBAL_15_NET_ROUTE",
    }


def compare_native_paint_symbols() -> dict:
    from examples.review_tl494_ugo_source_cycle9 import _actual_root

    parts, symbols, positions = _source_data()
    checked = 0
    real_marks = 0
    for mirror in (False, True):
        for angle in (0, 90, 180, 270):
            transform = Transform(angle, mirror)
            bound = bind_tl494_source(
                tuple(replace(comp, transform=transform) for comp in positions),
                parts, symbols, allow_relayout=True,
            )
            for binding in bound:
                source_footprint(binding)
                clean, posed = _actual_root(
                    binding.symbol, binding.reference, transform,
                    diagnostic=False,
                )
                diagnostic, dbg_pose = _actual_root(
                    binding.symbol, binding.reference, transform,
                    diagnostic=True,
                )
                assert posed == dbg_pose
                expected = {
                    pin.number: _point(pin.at) for pin in posed.pins
                }
                declared = dict(
                    (number, [int(v) for v in xy.split(",")])
                    for number, xy in (
                        item.split(":", 1) for item in clean.attrib[
                            "data-real-pin-coordinates-um"
                        ].split(";")
                    )
                )
                if expected != declared:
                    raise AssertionError(
                        f"PAINT physical source PinRef drift {binding.reference}"
                    )
                ns = "{http://www.w3.org/2000/svg}"
                actual_clean = clean.findall(
                    f".//{ns}rect[@data-editor-target='true']"
                )
                actual_debug = diagnostic.findall(
                    f".//{ns}rect[@data-editor-target='true']"
                )
                if actual_clean or len(actual_debug) != len(binding.part.pins):
                    raise AssertionError(
                        f"PAINT physical debug marker count mismatch {binding.reference}"
                    )
                if binding.reference == "VT1" and (
                    clean.attrib.get("data-source-dot") !=
                    "PHOTO_MATCH_DRAFT_NOT_VENDOR_PIN"
                ):
                    raise AssertionError("Source-specific VT1 real dot was lost")
                real_marks += len(actual_debug)
                checked += 1
    assert checked == YGO_SOURCE_PROFILES * D4_TRANSFORMS
    assert real_marks == 28 * D4_TRANSFORMS
    # Merely importing whole-sheet owner API confirms its current typed name.
    module = importlib.import_module("gost_schematic.rendering.routed_native_sheet")
    assert callable(module.render_routed_native_sheet)
    return {
        "consumer": "PAINT_PR93_REAL_RENDERER",
        "source_profiles": YGO_SOURCE_PROFILES,
        "D4_true_owner_comparisons": checked,
        "diagnostic_only_real_pin_marks": real_marks,
        "status": "PASS_NATIVE_UGO_INK_NOT_FULL_15_NET_PRINT",
    }


def compare_native_ic_typed_source() -> dict:
    """Verify actual IC owner frozen 23/15/62/16 without reinterpreting it."""
    from gost_schematic.model.circuit import PinRef

    owner = importlib.import_module("examples.tl494_cycle9_circuit_integration")
    binding, source = owner.build_frozen_photo_23()
    owner.assert_frozen_photo_topology(binding, source)
    actual = binding.circuit
    assert len(actual.components) == 23
    assert len(actual.nets) == 15
    assert sum(len(net.members) for net in actual.nets) == 62
    assert len(binding.contacts) == 16
    assert {p.number for n in actual.nets for p in n.members
            if p.reference == "DA1"} == {str(x) for x in range(1, 17)}
    assert binding.contact(PinRef("DA1", "3")).electrical_type.value == "input"
    assert binding.contact(PinRef("DA1", "13")).electrical_type.value == "input"
    before = actual.nets
    parts, symbols, _ = _source_data()
    selected = bind_tl494_source(
        actual.components, parts, symbols, allow_relayout=True,
    )
    assert len(selected) == 13
    assert sum(len(p.pin_refs) for p in selected) == 28
    originals = {
        p.reference: p for p in selected
    }
    for item in actual.nets:
        for member in item.members:
            if member.reference in originals:
                assert member in originals[member.reference].pin_refs
    for item in selected:
        footprint = source_footprint(item)
        assert len(footprint_record(footprint)["footprint_sha256"]) == 64
    if actual.nets is not before:
        raise AssertionError("YGO source ink probe altered owner Circuit.Net")
    return {
        "consumer": "ELEKTRIK_IC_PR97_FROZEN_TYPED_PHOTO_CIRCUIT",
        "source_profiles": 13,
        "real_components": 23,
        "real_nets": 15,
        "real_net_PinRef_memberships": 62,
        "physical_DA1_pins": 16,
        "source_selected_physical_leads": 28,
        "status": "PASS_PHYSICAL_TYPE_BINDING_NOT_FULL_ROUTE_OR_PRINT",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=("net", "paint", "ic"), required=True)
    parser.add_argument("--owner-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != args.owner_sha:
        raise ValueError(
            f"OWNER_SHA_NOT_EXACT: expected {args.owner_sha}, actual {actual_sha}"
        )
    if len(args.owner_sha) != 40:
        raise ValueError("OWNER_COMMIT_SHA_MUST_BE_PINNED")
    if args.owner == "net":
        report = compare_native_net_strokes()
    elif args.owner == "paint":
        report = compare_native_paint_symbols()
    else:
        report = compare_native_ic_typed_source()
    report.update({
        "owner_sha": actual_sha,
        "source_sha": PINNED_REFERENCE_SHA,
        "release_verdict": "BLOCKED_INCOMPLETE_15_NET_ROUTE_AND_GOST_1TO1",
        "normative_status": "DRAFT_NOT_APPROVED",
        "route_15_net_pass": False,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
