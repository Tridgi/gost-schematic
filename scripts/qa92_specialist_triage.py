"""Separate old synthetic/low-level QA failure evidence from 16-pin current.

Never changes original assertions or treats unsafe low-level editor behavior
as accepted. Each historical negative remains visible and fails its original
workflow. This independent classification is only for coordinator triage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_LEGACY_PIN_GALLERY = {
    "ic-04-digital", "ic-04-vertical",
    "ic-08-analog", "ic-08-vertical",
    "ic-14-digital", "ic-14-vertical",
    "ic-40-digital", "ic-40-vertical",
    "ic-64-digital", "ic-64-vertical",
}
LOW_LEVEL_EDITOR_BYPASS = {
    "wrong_component",
    "missing_authoritative_point",
    "wrong_net",
    "false_nc_on_active_pin",
}


def check(condition: bool, diagnostic: str) -> None:
    if not condition:
        raise AssertionError(diagnostic)


def pins_report(report: dict) -> dict:
    gates = report.get("gates")
    check(isinstance(gates, dict), "QA_PIN_TRIAGE_NO_ACTUAL_GATES")
    required = {
        "P0_source_sha": "PASS",
        "P0_original_paint_gallery": "FAIL",
        "P0_typed_pinref_point_markers": "PASS",
        "P0_negative_cases": "FAIL",
        "P1_power_norm_scope": "PASS",
        "P3_merged_integration": "PASS",
    }
    for name, status in required.items():
        check(gates.get(name, {}).get("status") == status,
              "QA_PIN_UNEXPECTED_GATE:" + name)
    missing = gates["P0_original_paint_gallery"].get("diagnostic", "")
    bypass = gates["P0_negative_cases"].get("diagnostic", "")
    check(missing.startswith("OWNER_GALLERY_DIAGNOSTIC_SQUARES_MISSING: "),
          "QA_PIN_MISSING_GALLERY_NOT_ESTABLISHED")
    actual_missing = set(missing.split(": ", 1)[1].split(","))
    check(actual_missing == EXPECTED_LEGACY_PIN_GALLERY,
          "QA_PIN_GALLERY_FAILURE_CLASS_CHANGED")
    check(bypass.startswith("EDITOR_NEGATIVE_CONTRACT_BYPASS: "),
          "QA_PIN_LOW_LEVEL_NEGATIVE_ERROR_NOT_ESTABLISHED")
    actual_bypass = set(bypass.split(": ", 1)[1].split(","))
    check(actual_bypass == LOW_LEVEL_EDITOR_BYPASS,
          "QA_PIN_UNSAFE_EDITOR_CASES_CHANGED")
    check(report.get("all_release_checks_green") is False,
          "QA_PIN_REPORT_FORGED_SUCCESS")
    return {
        "legacy_gallery": "EXPECTED_10_MISSING_DIAGNOSTIC_SETS",
        "legacy_gallery_names": sorted(actual_missing),
        "unsafe_low_level_editor_contract": "FAIL_REAL_BYPASS",
        "unsafe_rejected_negative_names": sorted(actual_bypass),
        "typed_contact_binding": "PASS_IN_HISTORICAL_OWNER",
        "new_23_part_TI_physical_editor": "REQUIRES_SEPARATE_NEW_OWNER_GATE",
        "release": "NO_GO",
    }


def portrait_report(report: dict, details: dict) -> dict:
    gates = report.get("gates")
    check(isinstance(gates, dict), "QA_PORTRAIT_TRIAGE_NO_ACTUAL_GATES")
    for name in (
        "provenance_eskd", "catalog_15", "netrefs_real", "project_p11",
    ):
        check(gates.get(name, {}).get("status") == "PASS",
              "QA_PORTRAIT_UNEXPECTED_OTHER_GATE:" + name)
    check(gates.get("ic_function_90_0", {}).get("status") == "FAIL",
          "QA_PORTRAIT_OLD_SYNTHETIC_OVERFLOW_DISAPPEARED")
    cases = details.get("blocked")
    check(isinstance(cases, dict), "QA_PORTRAIT_NO_ACTUAL_SVG_PROOF")
    overflow = {
        key for key, error in cases.items()
        if key.startswith("ic-8-PWM-CONTROLLER-") and
        "IC_TEXT_OVERFLOW" in error
    }
    expected = {
        f"ic-8-PWM-CONTROLLER-{degree}-m{mirror}"
        for degree in (90, 270) for mirror in (0, 1)
    }
    check(overflow == expected, "QA_PORTRAIT_OLD_OVERFLOW_FOUR_CASES_CHANGED")
    check(len(cases) >= 4, "QA_PORTRAIT_D4_OVERFLOW_UNDERCOUNT")
    return {
        "old_synthetic_8pin_long_function": "BLOCKED_FAIL_CLOSED_BY_REAL_INK",
        "blocked_four_original_90_270_D4": sorted(overflow),
        "actual_16pin_TL494_P3_P13_and_PWM": "REQUIRES_SEPARATE_OWNER_GATE",
        "no_automatic_fit_or_forced_text_scaling": True,
        "release": "NO_GO",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("pins", "portrait"), required=True)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--detail", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    if args.kind == "pins":
        result = pins_report(matrix)
    else:
        check(args.detail is not None, "QA_PORTRAIT_NEEDS_TRUE_BLOCKED_MANIFEST")
        details = json.loads(args.detail.read_text(encoding="utf-8"))
        result = portrait_report(matrix, details)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True,
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("QA92_SPECIALIZED_NEGATIVE_CLASSIFICATION " +
          json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
