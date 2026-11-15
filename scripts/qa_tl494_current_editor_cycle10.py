"""QA for CURRENT native ELEKTRIK 16-pin typed contact manifest.

Owner code is source-pinned separately in CI. All tests use the actual
23-component frozen photographed Circuit and TI contact metadata; no fake
standalone good device or fictional net is accepted as release proof.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from gost_schematic.electrical.ic_editor_targets import (
    IcEditorContactManifest,
    make_ic_editor_manifest,
    make_paint_editor_targets,
    verify_ic_editor_manifest,
)
from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding

from gost_schematic.core.geometry import Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

FROZEN_SOURCE = "e695c415fdced164b0e0c39c5249d030795a0aa6"
IC_CURRENT_SHA = "3c2121ad918e4a877c031d47853f2ba9e74e7a24"
IC_CYCLE11_LIVE_SHA = "1e4baf7ea713f649e0dabb4d6119e97281901f03"


def require(ok, code):
    if not ok:
        raise AssertionError(code)


def validate_real_manifest(font: Path) -> dict:
    from examples.tl494_cycle9_circuit_integration import (
        assert_frozen_photo_topology,
        build_frozen_photo_23,
    )

    binding, frozen = build_frozen_photo_23()
    assert_frozen_photo_topology(binding, frozen)
    circuit = binding.circuit
    require(len(circuit.components) == 23 and len(circuit.nets) == 15 and
            sum(len(n.members) for n in circuit.nets) == 62,
            "QA_IC_EDITOR_NO_FROZEN_23_15_62")
    inspected = inspect_type_a_font(font, h_um=3500)
    require(inspected.measured_cap_height_um == 3500,
            "QA_IC_EDITOR_REAL_TYPE_A_NOT_3P5MM")
    proposal = propose_ic_paint_binding(
        binding.record, inspected.style, PillowTextMeasurer(),
    )
    proposal.verify_endpoints()
    manifest = make_ic_editor_manifest(proposal, circuit)
    verify_ic_editor_manifest(proposal, manifest, circuit)
    contacts = manifest.contacts
    require(len(contacts) == 16 and
            {c.pin_ref for c in contacts} ==
            {PinRef("DA1", str(i)) for i in range(1, 17)},
            "QA_IC_EDITOR_NO_16_PHYSICAL_PINS")
    nets = {pin: net.name for net in circuit.nets for pin in net.members}
    for contact in contacts:
        require(contact.net_id == nets[contact.pin_ref] and
                contact.connectable and contact.reason is None,
                "QA_IC_EDITOR_PHYSICAL_NET_NOT_AUTHORITY")
    require(next(c for c in contacts if c.pin_ref.number == "3").role == "in"
            and next(c for c in contacts if c.pin_ref.number == "13").role == "in",
            "QA_IC_EDITOR_FB_OR_OC_INPUT_CORRUPTED")
    per_view = make_paint_editor_targets(proposal, manifest, circuit)
    require(sum(map(len, per_view)) == 16 and len(per_view) == 1,
            "QA_IC_EDITOR_PAINT_DROPPED_PHYSICAL_CONTACT")
    return {"binding": proposal, "circuit": circuit,
            "manifest": manifest, "nets": nets,
            "font_sha256": inspected.style.font_sha256}


def negative_cases(data: dict) -> dict:
    binding = data["binding"]
    circuit = data["circuit"]
    original = data["manifest"]
    targets = original.contacts
    at = next(i for i, c in enumerate(targets) if c.physical_number == "3")
    src = targets[at]
    require(src.net_id is not None and src.connectable,
            "QA_IC_EDITOR_SOURCE_FB_ALREADY_INVALID")
    mutations = {
        "fake_net": lambda c: replace(c, net_id="FORGED_NET"),
        "one_um_anchor": lambda c: replace(
            c, anchor=Point(c.anchor.x + 1, c.anchor.y),
        ),
        "false_nc": lambda c: replace(
            c, connectable=False, reason="NC_PHYSICAL_PIN",
        ),
        "wrong_type_role": lambda c: replace(c, role="out"),
        "wrong_pinref": lambda c: replace(
            c, pin_ref=PinRef("DA1", "999"), physical_number="999",
        ),
        "wrong_logical_unit": lambda c: replace(
            c, unit_id="WRONG_U",
        ),
    }
    results = {}
    for key, change in mutations.items():
        try:
            altered = list(targets)
            altered[at] = change(src)
            forged = IcEditorContactManifest(tuple(altered))
            verify_ic_editor_manifest(binding, forged, circuit)
        except (ValueError, TypeError) as exc:
            require(str(exc).startswith(("IC_EDITOR_", "IC_")),
                    "QA_IC_EDITOR_REJECTED_WITH_UNRELATED_ERROR:" + key)
            results[key] = "REJECTED_BY_REAL_PRODUCTION_OWNER"
        else:
            raise AssertionError("QA_IC_EDITOR_FRAUD_ACCEPTED:" + key)
    for key, forged in {
        "missing_terminal": tuple(targets[:-1]),
        "duplicated_terminal": (*targets, targets[0]),
    }.items():
        try:
            verify_ic_editor_manifest(
                binding, IcEditorContactManifest(forged), circuit,
            )
        except (ValueError, TypeError) as exc:
            require(str(exc).startswith("IC_EDITOR_"),
                    "QA_IC_EDITOR_INVENTORY_WRONG_DIAGNOSTIC:" + key)
            results[key] = "REJECTED_BY_REAL_PRODUCTION_OWNER"
        else:
            raise AssertionError("QA_IC_EDITOR_INVENTORY_ACCEPTED:" + key)
    require(len(results) == 8, "QA_IC_EDITOR_WRONG_NEGATIVE_CASE_COUNT")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-file", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cycle11", action="store_true")
    ap.add_argument("--expected-owner-sha",
                    help="Exact independently pinned Git owner SHA for Cycle11")
    args = ap.parse_args()
    active = (
        args.expected_owner_sha or IC_CYCLE11_LIVE_SHA
        if args.cycle11 else IC_CURRENT_SHA
    )
    require(not args.expected_owner_sha or (
        args.cycle11 and len(args.expected_owner_sha) == 40
        and all(c in "0123456789abcdef" for c in args.expected_owner_sha)
    ), "QA_IC_EDITOR_OWNER_SHA_ARGUMENT_NOT_EXACT")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True,
    ).strip()
    require(head == active, "QA_IC_EDITOR_WRONG_OWNER_GIT_HEAD")
    data = validate_real_manifest(args.font_file)
    bad = negative_cases(data)
    report = {
        "source": FROZEN_SOURCE,
        "current_IC_owner_sha": active,
        "parts": 23, "nets": 15, "PinRef_memberships": 62,
        "manufacturer_TL494_16_contacts": 16,
        "feedback_input": True, "output_ctrl_input": True,
        "real_Type_A_sha256": data["font_sha256"],
        "real_typed_manifest": "PASS",
        "adversarial_cases": bad,
        "old_low_level_editor_four_bypasses":
            "SEPARATE_HISTORICAL_FAIL_NOT_RELABELED",
        "print_release": "BLOCKED_15_NET_A3_AND_PHOTO",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        report, ensure_ascii=False, sort_keys=True, indent=2,
    ) + "\n", encoding="utf-8")
    print("QA92_CURRENT_REAL_16PIN_EDITOR " +
          json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
