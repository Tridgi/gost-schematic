"""Independent negative-source detector: expected historic defects != AFTER pass.

Runs on the complete actual original QA matrix. It does NOT change one
historic negative assertion, its exit code, or any source object. Unknown
failure, insufficient current owner integration, and missing reports FAIL.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FROZEN = "e695c415fdced164b0e0c39c5249d030795a0aa6"

CURRENT_REQUIRED = (
    "P0_EXACT_SOURCE_SHA",
    "P0_REAL_23_15_16_91",
    "P1_REAL_CATALOG_AND_48_D4",
    "P2_CURRENT_OWNER_IC_STANDALONE",
    "P2_CURRENT_OWNER_PAINT_ON_ACTUAL_DA1",
    "P2_REAL_FULL_NATIVE_OWNER_SHEET",
    "P2_CURRENT_OWNER_EDITOR_MANIFEST_NEGATIVES",
    "P2_REAL_FULL_NATIVE_8_D4",
    "P3_NEGATIVE_EXACT_UM",
)
HISTORICAL_BAD = (
    "P2_TI_PIN_ALIASES_AND_PWM",
    "P3_STROKE_AWARE_DRC",
    "P3_SYMBOL_AND_DA1_OBSTACLES",
)


def check(value: bool, error: str) -> None:
    if not value:
        raise AssertionError(error)


def diagnose(source: dict) -> dict:
    check(isinstance(source, dict) and source.get("reference") == FROZEN,
          "TRIAGE_UNTRUSTED_ORIGINAL_SHA")
    gates = source.get("gates")
    check(isinstance(gates, dict), "TRIAGE_NO_REAL_GATE_MATRIX")
    check(set(CURRENT_REQUIRED + HISTORICAL_BAD) <= set(gates),
          "TRIAGE_MANDATORY_NEGATIVE_ASSERTION_REMOVED")
    current = {name: gates[name].get("status") for name in CURRENT_REQUIRED}
    check(all(x == "PASS" for x in current.values()),
          "TRIAGE_CURRENT_OWNER_DOES_NOT_ALL_PASS")
    known_bad = {name: gates[name].get("status") for name in HISTORICAL_BAD}
    check(all(x == "FAIL" for x in known_bad.values()),
          "TRIAGE_ORIGINAL_DEFECT_DETECTOR_REGRESSED")
    # Old source geometrical errors are concrete, not a generic red job.
    geometric = gates["P3_STROKE_AWARE_DRC"].get("evidence")
    check(isinstance(geometric, dict) and
          geometric.get("parallel_violations_count") == 5 and
          len(geometric.get("parallel_wire_violations", ())) == 5,
          "TRIAGE_ORIGINAL_FIVE_PRINT_GAP_DEFECTS_NOT_DETECTED")
    symbols = gates["P3_SYMBOL_AND_DA1_OBSTACLES"].get("evidence")
    check(isinstance(symbols, dict) and
          symbols.get("ink_wire_intrusion_count", 0) > 0,
          "TRIAGE_ORIGINAL_TRUE_TEXT_COLLISIONS_LOST")
    ic = gates["P2_TI_PIN_ALIASES_AND_PWM"].get("evidence")
    checks = ic.get("checks") if isinstance(ic, dict) else None
    check(isinstance(checks, dict) and any(
        value == "FAIL" for value in checks.values()
    ), "TRIAGE_ORIGINAL_FEEDBACK_PWM_ERRORS_NOT_RECORDED")
    images = gates.get("P4_REAL_IMAGES", {})
    check(images.get("status") == "BLOCKED" and
          images.get("evidence", {}).get("photo_comparison_status")
          != "PASS_REAL_ORIGINAL_USER_IMAGE_COMPARED",
          "TRIAGE_FAKE_SOURCE_PHOTO_PARITY")
    check(source.get("status") == "NO_GO_DRAFT",
          "TRIAGE_ORIGINAL_PRINT_RELABELED_PASS")
    return {
        "frozen_bad_sha": FROZEN,
        "source_fixture": "KNOWN_BAD_PHYSICAL_LAYOUT",
        "detector_status": "DETECTOR_PASS",
        "original_print": "PRINT_NO_GO",
        "current_owner_native_rebuild": "PASS_DRAFT_ONLY",
        "new_optimized_15_net_route": "BLOCKED_NOT_THIS_FIXTURE",
        "historical_defects_detected": known_bad,
        "new_owner_gates": current,
        "source_photo_pixel_parity": "BLOCKED_NO_TRUSTED_IMAGE_BYTES",
        "negative_assertions_retained": True,
        "release": "NO_GO",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = json.loads(args.matrix.read_text(encoding="utf-8"))
    evaluated = diagnose(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evaluated, indent=2, sort_keys=True,
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("QA92_FROZEN_OLD_NEGATIVE_TRIAGE " +
          json.dumps(evaluated, ensure_ascii=False))


if __name__ == "__main__":
    main()
