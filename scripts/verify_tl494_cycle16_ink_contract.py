"""Fail-closed Cycle16 comparison of real TL494 source ink across render platforms.

The Windows-signed frozen artifact and Linux PIL font bounds may differ by
tens of micrometres with the same pinned Type A font. A text-width difference
is NOT a physical-pin drift. Every electrical pin, primitive ink AABB, D4
transform, owner and source topology is still compared at integer 1 um
precision. This verifier is not global print DRC or route approval.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


class InkContractMismatch(ValueError):
    """Physical contract or text anchor failed closed."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InkContractMismatch(reason)


def box(value: object, path: str) -> tuple[int, int, int, int]:
    require(
        isinstance(value, list) and len(value) == 4
        and all(type(v) is int for v in value),
        "UGO_C16_INVALID_MEASURED_BOX:" + path,
    )
    x0, y0, x1, y1 = value
    require(x0 <= x1 and y0 <= y1, "UGO_C16_REVERSED_MEASURED_BOX:" + path)
    return x0, y0, x1, y1


def validate_text(snapshot: dict, name: str) -> list[dict]:
    guards = snapshot.get("actual_PAINT_TypeA_text_guards")
    require(isinstance(guards, list) and len(guards) == 73,
            "UGO_C16_TRUE_73_TYPE_A_GUARDS_REQUIRED:" + name)
    require(snapshot.get("actual_PAINT_TypeA_label_guard_count") == 73,
            "UGO_C16_TYPE_A_COUNT_DRIFT:" + name)
    expected_min_y = 297000
    fit = True
    for index, guard in enumerate(guards):
        path = f"{name}.text[{index}]"
        require(isinstance(guard, dict), "UGO_C16_INVALID_TEXT_GUARD:" + path)
        require(set(guard) == {
            "owner", "kind", "collision_box_um", "actual_ink_box_um",
            "printed_text",
        }, "UGO_C16_TEXT_SCHEMA_DRIFT:" + path)
        require(isinstance(guard["owner"], str) and guard["owner"],
                "UGO_C16_TEXT_OWNER_UNKNOWN:" + path)
        require(isinstance(guard["kind"], str) and guard["kind"],
                "UGO_C16_TEXT_KIND_UNKNOWN:" + path)
        x0, y0, x1, y1 = box(guard["collision_box_um"], path)
        require(x0 < x1 and y0 < y1,
                "UGO_C16_ZERO_TEXT_BOUNDS:" + path)
        if guard["actual_ink_box_um"] is not None:
            box(guard["actual_ink_box_um"], path + ".actual_ink")
        expected_min_y = min(expected_min_y, y0)
        fit &= (
            x0 >= 10000 and y0 >= 10000 and
            x1 <= 410000 and y1 <= 287000
        )
    require(snapshot.get("minimum_text_collision_y_um") == expected_min_y,
            "UGO_C16_TEXT_MIN_Y_NOT_MEASURED:" + name)
    require(snapshot.get("project_10mm_text_collision_frame_fit") is fit,
            "UGO_C16_TEXT_FRAME_FIT_FORGED:" + name)
    return guards


def verify_contract(
    expected: dict, actual: dict, *, actual_recon_sha: str,
) -> dict:
    """Allow only OS-specific Type A extents; reject any physical drift."""
    require(len(actual_recon_sha) == 40 and
            all(c in "0123456789abcdef" for c in actual_recon_sha),
            "UGO_C16_RECON_SHA_REQUIRED")
    require(expected.get("recon_exact_sha") != "" and
            actual.get("recon_exact_sha") == actual_recon_sha,
            "UGO_C16_RECON_OWNER_SHA_MISMATCH")
    require(actual.get("source_reference_sha") ==
            "e695c415fdced164b0e0c39c5249d030795a0aa6",
            "UGO_C16_FROZEN_SOURCE_DRIFT")
    require(actual.get("font_type_a_sha256") ==
            "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a",
            "UGO_C16_UNPINNED_FONT")
    require(actual.get("route_15_net_pass") is False and
            actual.get("DRC_full_print_pass") is False,
            "UGO_C16_FALSE_PRINT_RELEASE")
    require(actual.get("normative_status") == "36_DRAFT_0_APPROVED",
            "UGO_C16_GLYPH_CERTIFICATION_FORGED")

    before = copy.deepcopy(expected)
    after = copy.deepcopy(actual)
    # RECON moves forward independently. Its SHA may advance while its
    # physical producer/consumer contract is strictly identical.
    after["recon_exact_sha"] = before["recon_exact_sha"]
    text_changed = 0
    for key in ("control", "moved_R2_Y_2p5_C1_Y_2p5"):
        a, b = before.get(key), after.get(key)
        require(isinstance(a, dict) and isinstance(b, dict),
                "UGO_C16_MISSING_REAL_LAYOUT:" + key)
        text_a = validate_text(a, "baseline." + key)
        text_b = validate_text(b, "current." + key)
        for index, (left, right) in enumerate(zip(text_a, text_b)):
            path = f"{key}.text[{index}]"
            for field in ("owner", "kind", "printed_text"):
                require(left[field] == right[field],
                        "UGO_C16_TEXT_IDENTITY_DRIFT:" + path + "." + field)
            for field in ("collision_box_um", "actual_ink_box_um"):
                lhs, rhs = left[field], right[field]
                require((lhs is None) == (rhs is None),
                        "UGO_C16_UNKNOWN_TEXT_INK:" + path)
                if lhs is None:
                    continue
                ax0, ay0, ax1, ay1 = box(lhs, path)
                bx0, by0, bx1, by1 = box(rhs, path)
                # Width/height are computed by different raster/font backends;
                # their centre must remain EXACT, not within a tolerance.
                require(
                    (ax0 + ax1, ay0 + ay1) ==
                    (bx0 + bx1, by0 + by1),
                    "UGO_C16_TEXT_ANCHOR_1UM_DRIFT:" + path,
                )
                if lhs != rhs:
                    text_changed += 1
        # All real 23 symbol primitives/pins/positions and original net
        # members continue to use strict equality without ANY tolerance.
        a["actual_PAINT_TypeA_text_guards"] = []
        b["actual_PAINT_TypeA_text_guards"] = []
        a["minimum_text_collision_y_um"] = 0
        b["minimum_text_collision_y_um"] = 0
        require(
            a["project_10mm_text_collision_frame_fit"] ==
            b["project_10mm_text_collision_frame_fit"],
            "UGO_C16_TYPE_A_FRAME_VERDICT_CHANGED:" + key,
        )
    require(before == after, "UGO_C16_PHYSICAL_INK_OR_NET_DRIFT")
    control, moved = actual["control"], actual["moved_R2_Y_2p5_C1_Y_2p5"]
    for snap in (control, moved):
        require(snap["real_part_count"] == 23 and
                snap["real_net_count"] == 15 and
                snap["real_pin_ref_memberships"] == 62 and
                snap["DA1_physical_contact_count"] == 16 and
                snap["source_glyph_instances"] == 13,
                "UGO_C16_SOURCE_23_15_62_16_13_REQUIRED")
        require(len(snap["parts"]) == 23 and
                len(snap["original_named_nets"]) == 15,
                "UGO_C16_ALL_REAL_SOURCE_RECORDS_REQUIRED")
        refs = [
            p["pin_ref"] for component in snap["parts"].values()
            for p in component["real_physical_contacts"]
        ]
        require(len(refs) == 62 and len(set(refs)) == 62,
                "UGO_C16_DUPLICATE_OR_MISSING_PIN_REF")
        require(snap["terminal_stroke_width_um"] == 300,
                "UGO_C16_STROKE_WIDTH_DRIFT")
    require(control["project_10mm_text_collision_frame_fit"] is False and
            moved["project_10mm_text_collision_frame_fit"] is True,
            "UGO_C16_TYPE_A_C1_FRAME_NOT_REPAIRED")
    return {
        "result": "PASS_SOURCE_PHYSICAL_GEOMETRY_NOT_FULL_PRINT",
        "source_parts": 23,
        "source_nets": 15,
        "physical_pin_refs": 62,
        "DA1_real_pins": 16,
        "source_ugo_instances": 13,
        "measured_text_guards_per_layout": 73,
        "type_a_os_specific_box_variations": text_changed,
        "text_anchor_drift_um": 0,
        "physical_1um_coordinate_tolerance": 0,
        "baseline_recon_sha": expected["recon_exact_sha"],
        "current_recon_sha": actual_recon_sha,
        "full_route_pass": False,
        "full_print_pass": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--owner-recon-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    current = json.loads(args.current.read_text(encoding="utf-8"))
    report = verify_contract(
        baseline, current, actual_recon_sha=args.owner_recon_sha,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
