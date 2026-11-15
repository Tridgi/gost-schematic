"""Cycle13 read-only physical UGO compatibility against exact NET/PAINT/IC/RECON HEADs.

Run inside an isolated checked-out owner commit with the YGO source-profile
modules overlaid only in a TEMPORARY GitHub Actions worktree. This intentionally
does NOT modify the source commit, any owner branch, or the frozen original.
"""
import argparse
import importlib
import json
import subprocess
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from math import isqrt
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


def parse_real_pin_coordinates(value: str) -> dict[str, tuple[int, int]]:
    """Strict pin-number / integer micrometre metadata, no duplicate alias."""
    if not isinstance(value, str) or not value:
        raise ValueError("UGO_PIN_METADATA_MISSING")
    result = {}
    for item in value.split(";"):
        pair = item.split(":")
        if len(pair) != 2 or not pair[0] or pair[0] in result:
            raise ValueError("UGO_PIN_METADATA_DUPLICATE_OR_INVALID_NUMBER")
        coords = pair[1].split(",")
        if len(coords) != 2:
            raise ValueError("UGO_PIN_METADATA_NOT_XY")
        try:
            xy = tuple(int(v) for v in coords)
        except ValueError as exc:
            raise ValueError("UGO_PIN_METADATA_NOT_INTEGER_MICROMETRES") from exc
        result[pair[0]] = xy
    return result


def _svg_decimal_um(value: str) -> int:
    """Only exact micrometre SVG positions, never float-round near matches."""
    try:
        um = Decimal(value) * 1000
        if not um.is_finite() or um != um.to_integral_value():
            raise ValueError("UGO_MARKER_NOT_EXACT_INTEGER_MICROMETRES")
        return int(um)
    except InvalidOperation as exc:
        raise ValueError("UGO_MARKER_INVALID_DECIMAL") from exc


def verify_real_pin_markers(root, expected: dict[str, tuple[int, int]], *,
                            diagnostic: bool) -> int:
    """Check green-pin diagnostic rect centre and pin IDs against real tips."""
    ns = "{http://www.w3.org/2000/svg}"
    markers = root.findall(f".//{ns}rect[@data-editor-target='true']")
    if not diagnostic:
        if markers:
            raise ValueError("UGO_CLEAN_SVG_CONTAINS_PIN_DEBUG_MARKER")
        return 0
    seen = set()
    for rect in markers:
        number = rect.get("data-physical-pin")
        if number not in expected or number in seen:
            raise ValueError("UGO_DEBUG_PIN_UNKNOWN_OR_DUPLICATED")
        seen.add(number)
        x = _svg_decimal_um(rect.get("x", ""))
        y = _svg_decimal_um(rect.get("y", ""))
        width = _svg_decimal_um(rect.get("width", ""))
        height = _svg_decimal_um(rect.get("height", ""))
        if ((width, height) != (1200, 1200)
            or (x + 600, y + 600) != expected[number]):
            raise ValueError("UGO_DEBUG_PIN_TIP_POSITION_MISMATCH")
    if seen != set(expected):
        raise ValueError("UGO_DEBUG_PHYSICAL_PIN_INVENTORY_MISMATCH")
    return len(seen)


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
                    pin.number: (pin.at.x, pin.at.y) for pin in posed.pins
                }
                declared = parse_real_pin_coordinates(
                    clean.attrib["data-real-pin-coordinates-um"]
                )
                debug_declared = parse_real_pin_coordinates(
                    diagnostic.attrib["data-real-pin-coordinates-um"]
                )
                if expected != declared or debug_declared != expected:
                    raise AssertionError(
                        f"PAINT physical source PinRef drift {binding.reference}"
                    )
                verify_real_pin_markers(clean, expected, diagnostic=False)
                marks = verify_real_pin_markers(
                    diagnostic, expected, diagnostic=True
                )
                if binding.reference == "VT1" and (
                    clean.attrib.get("data-source-dot") !=
                    "PHOTO_MATCH_DRAFT_NOT_VENDOR_PIN"
                ):
                    raise AssertionError("Source-specific VT1 real dot was lost")
                real_marks += marks
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

def source_pair_conservative_ink_gap_um(left, right) -> int:
    """Integer floor of conservative AABB ink separation; fail if shapes touch.

    This is ONLY a source-UGO pair preflight, not a formal 2/3/1mm whole-sheet
    DRC and not evidence of a complete all-15-Net graph.
    """
    if not left.ink_obstacles or not right.ink_obstacles:
        raise AssertionError("UGO_INK_EMPTY_OBSTACLES_ARE_NEVER_CLEAR")
    nearest_sq = None
    for a in left.ink_obstacles:
        for b in right.ink_obstacles:
            box_a, box_b = a.box, b.box
            dx = max(0, box_a.min_x - box_b.max_x,
                     box_b.min_x - box_a.max_x)
            dy = max(0, box_a.min_y - box_b.max_y,
                     box_b.min_y - box_a.max_y)
            value = dx * dx + dy * dy
            if nearest_sq is None or value < nearest_sq:
                nearest_sq = value
    return isqrt(nearest_sq)




def compare_native_recon_compact_source() -> dict:
    """Real RECON #115 compact assembly; no synthetic routing or print.

    This uses actual reference-based RECON owner code with original physical
    catalog graphics/IC metadata temporarily staged from their exact SHAs.
    Everything remains in detached worktrees; no owner file is committed.
    """
    from examples.tl494_v5.compact_layout import (
        A3_LANDSCAPE_UM,
        COMPACT_A3_MM,
        PRINT_MARGIN_UM,
        compact_source_assembly,
    )

    assembly = compact_source_assembly()
    assembly.verify()
    circuit = assembly.circuit
    if (len(circuit.components) != 23 or len(circuit.nets) != 15
        or sum(len(net.members) for net in circuit.nets) != 62
        or len(assembly.source_UGO_bindings) != 13):
        raise AssertionError("RECON_C13_FROZEN_23_15_62_OR_13_UGO_CHANGED")
    if COMPACT_A3_MM["X1"] != (17, 35) or (
        next(c for c in circuit.components if c.reference == "X1").origin
        != Point(17000, 35000)
    ):
        raise AssertionError("RECON_C13_X1_17MM_MARGIN_FIX_MISSING")
    assembly_nets = circuit.nets
    if {p.number for n in circuit.nets for p in n.members
        if p.reference == "DA1"} != {str(i) for i in range(1, 17)}:
        raise AssertionError("RECON_C13_16_ACTUAL_DA1_CONTACTS_MISSING")
    b = next((n for n in circuit.nets if n.name == "OUTPUT_NEG"), None)
    if b is None or {(p.reference, p.number) for p in b.members} != {
        ("FU1", "2"), ("X2", "1"), ("R5", "2"),
    } or len(b.members) != 3:
        raise AssertionError("RECON_C13_REAL_B_PHYSICAL_TIPS_CHANGED")
    # RECON's NativeV5Assembly.symbols does NOT contain the real DA1
    # rendered symbol: full 23-glyph paper bounds require a separately
    # signed PAINT IC glyph. Never invent that graphic just to pass CI.
    full_23_ink_gate = (
        "BLOCKED_REAL_DA1_RENDERED_SYMBOL_NOT_IN_SOURCE_ASSEMBLY"
        if "reference.tl494cn" not in assembly.symbols
        else "UNVERIFIED_FULL_PAINT_RENDER_AND_PRINT_DRC"
    )
    min_margin = PRINT_MARGIN_UM
    max_x, max_y = A3_LANDSCAPE_UM
    x1 = next(c for c in circuit.components if c.reference == "X1")
    x1_symbol = assembly.symbols.get(x1.part_id)
    if x1_symbol is None:
        raise AssertionError("RECON_C14_REAL_X1_GRAPHIC_MISSING")
    x1_ink = x1.transform.box(x1_symbol.stroked_bounds).translated(x1.origin)
    if not (min_margin <= x1_ink.min_x <= x1_ink.max_x <= max_x - min_margin
            and min_margin <= x1_ink.min_y <= x1_ink.max_y
            <= max_y - min_margin):
        raise AssertionError("RECON_C14_REAL_X1_GRAPHIC_OUTSIDE_A3_INSET")
    measured = {}
    compact_footprints = []
    all_poses = 0
    physical_tip_checks = 0
    source_ink_count = 0
    for binding in assembly.source_UGO_bindings:
        original = next(c for c in circuit.components
                        if c.reference == binding.reference)
        if binding.instance is not original:
            raise AssertionError(
                "RECON_C13_UGO_WAS_NOT_BOUND_TO_REAL_COMPONENT_INSTANCE: "
                + binding.reference
            )
        current = source_footprint(binding)
        compact_footprints.append(current)
        record = footprint_record(current)
        raw = record["rendered_ink_bounds_um"]
        if not (min_margin <= raw[0] <= raw[2] <= max_x - min_margin
                and min_margin <= raw[1] <= raw[3] <= max_y - min_margin):
            raise AssertionError(
                "RECON_C13_PRINTED_SOURCE_UGO_EXCEEDS_A3_MARGINS: "
                + binding.reference + ":" + str(raw)
            )
        if record["origin_um"] != [original.origin.x, original.origin.y]:
            raise AssertionError("RECON_C13_SOURCE_UGO_ORIGIN_REASSIGNED")
        if record["symbol_revision"] != binding.symbol.revision:
            raise AssertionError("RECON_C13_GLYPH_REVISION_CHANGED")
        measured[binding.reference] = {
            "symbol_id": record["symbol_id"],
            "origin_um": record["origin_um"],
            "rendered_ink_bounds_um": raw,
            "true_leads": record["real_leads"],
            "footprint_sha256": record["footprint_sha256"],
            "status": record["status"],
        }
        for mirror in (False, True):
            for angle in (0, 90, 180, 270):
                component = replace(
                    original, transform=Transform(angle, mirror)
                )
                points = component.pin_positions(binding.symbol)
                moved = replace(
                    binding,
                    instance=component,
                    pin_positions=tuple(
                        points[pin.number] for pin in binding.part.pins
                    ),
                )
                fp = source_footprint(moved)
                if len(fp.lead_obstacles) != len(binding.part.pins):
                    raise AssertionError("RECON_C13_D4_TRUE_LEAD_LOSS")
                if tuple(lead.pin_ref for lead in fp.lead_obstacles) != (
                    binding.pin_refs
                ):
                    raise AssertionError("RECON_C13_D4_PINREF_REORDERED")
                if tuple(lead.pin_ref.number for lead in fp.lead_obstacles) != (
                    tuple(pin.number for pin in binding.part.pins)
                ):
                    raise AssertionError("RECON_C13_D4_PHYSICAL_NUMBER_REMAP")
                if any(
                    lead.pin_ref.reference != original.reference
                    or points[lead.pin_ref.number] not in (
                        lead.segment.start, lead.segment.end
                    )
                    for lead in fp.lead_obstacles
                ):
                    raise AssertionError("RECON_C13_D4_LEAD_TIP_DISCONNECTED")
                physical_tip_checks += len(fp.lead_obstacles)
                source_ink_count += len(fp.ink_obstacles)
                all_poses += 1
    pair_gaps = {
        (left.reference, right.reference):
        source_pair_conservative_ink_gap_um(left, right)
        for i, left in enumerate(compact_footprints)
        for right in compact_footprints[i + 1:]
    }
    if len(pair_gaps) != 78:
        raise AssertionError("RECON_C13_DISTINCT_SOURCE_UGO_PAIR_LOSS")
    closest_pair, minimum_ink_gap_um = min(
        pair_gaps.items(), key=lambda item: (item[1], item[0])
    )
    # Conservative 2mm source-glyph engineering preflight. Full ESKD still
    # owns all 253 printed 23-part pairs, 1mm text and 3mm wire-edge checks.
    if minimum_ink_gap_um < 2000:
        raise AssertionError(
            "RECON_C13_TRUE_UGO_PRINTED_INK_AABB_GAP_LT_2MM: "
            + str((closest_pair, minimum_ink_gap_um))
        )
    if (len(measured) != 13 or all_poses != 104
        or physical_tip_checks != 224
        or circuit.nets is not assembly_nets):
        raise AssertionError("RECON_C13_REAL_UGO_OR_NET_IDENTITY_DRIFT")

    # Negative control: reproduce the historical compact X1=16mm candidate
    # *only in memory*; it must NOT pass the current physical margin proof.
    old_x1 = replace(x1, origin=Point(16000, x1.origin.y))
    old_ink = old_x1.transform.box(x1_symbol.stroked_bounds).translated(
        old_x1.origin
    )
    if old_ink.min_x >= min_margin:
        raise AssertionError(
            "RECON_C14_NEGATIVE_X1_16MM_UNEXPECTEDLY_WITHIN_MARGIN"
        )
    if old_ink.min_x != x1_ink.min_x - 1000:
        raise AssertionError("RECON_C14_X1_GEOMETRY_NOT_EXACT_1MM_TRANSLATION")

    return {
        "consumer": "RECON_PR115_ACTUAL_COMPACT_A3_PHYSICAL_UGO",
        "source_profiles": 13,
        "real_components": 23,
        "real_nets": 15,
        "real_net_PinRef_memberships": 62,
        "DA1_numbered_real_pins": 16,
        "D4_true_owner_comparisons": all_poses,
        "D4_true_physical_lead_tip_checks": physical_tip_checks,
        "D4_actual_ink_primitives_audited": source_ink_count,
        "source_13_distinct_printed_ink_pairs": len(pair_gaps),
        "conservative_min_source_pair_ink_gap_um": minimum_ink_gap_um,
        "conservative_min_source_pair_names": list(closest_pair),
        "source_ink_2mm_scope": "PRECHECK_ONLY_NOT_23_PART_ESKD_DRC",
        "X1_new_true_origin_um": [17000, 35000],
        "X1_old_16mm_negative": "REJECTED_OUTSIDE_A3_PRINT_MARGIN",
        "X1_true_source_ink_box_um": _box(x1_ink),
        "X1_old_true_source_ink_box_um": _box(old_ink),
        "whole_23_component_printed_bounds": full_23_ink_gate,
        "source_13_real_compact_footprints": measured,
        "graphical_b_stub_strokes_printed": False,
        "status": "PASS_RECON_COMPACT_SOURCE_UGO_NOT_COMPLETE_PRINT",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", choices=("net", "paint", "ic", "recon"), required=True)
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
    elif args.owner == "ic":
        report = compare_native_ic_typed_source()
    else:
        report = compare_native_recon_compact_source()
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
