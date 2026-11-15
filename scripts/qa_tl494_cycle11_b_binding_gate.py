"""Independent C11 actual-source TL494 nonphysical b continuation QA.

Compares RECON's newly rebound b-X2/b-R5 typed marker coordinates against
original e695 real SOURCE NetContinuationProject vectors and actual compact
ComponentInstance GraphicPins. Never synthesizes Net members, edits SVG,
accepts a photo guess or releases a partially routed sheet.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from examples.render_tl494_full_native_cycle9 import (
    _compose_frozen_circuit_with_real_type_a,
)
from examples.tl494_named_photo_sheet import compose_circuit
from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.route_candidate_driver import (
    ORIGINAL_BAD_DRC,
    OWNER_SHAS,
    load_original_owner_fixture,
    restore_original_named_nets,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font

RECON_SHA = "65b68cdd89ac0c2ae0b137228da61a17ac78d339"
ORIGINAL_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
PHYSICAL_B = {"FU1.2", "X2.1", "R5.2"}
B_STUBS = {"b-X2": "X2.1", "b-R5": "R5.2"}
A3 = (420000, 297000)
MARGIN = 10000


class BContractFailure(AssertionError):
    """A forged source, physical marker, or premature print claim."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise BContractFailure(code)


def immutable_expected(font_file: Path) -> dict:
    """Derive source b vectors from E695 native DATA, not a screenshot."""
    # E695's obsolete `OpenGost Type A TT` family selector must be adapted
    # ONLY at the original source function boundary to genuine verified
    # OpenGOST type A. PAINT's existing scoped adapter restores the selector
    # afterwards and never edits original geometry, wires or font bytes.
    original = _compose_frozen_circuit_with_real_type_a(
        compose_circuit, font_file,
    )[-1]
    assembly = compact_source_assembly()
    assembly.verify()
    frozen, _typed_ti = load_original_owner_fixture()
    circuit = restore_original_named_nets(assembly, frozen)
    require(len(circuit.components) == 23 and len(circuit.nets) == 15 and
            sum(len(n.members) for n in circuit.nets) == 62,
            "QA_B_NOT_REAL_ORIGINAL_23_15_62")
    require({n.name for n in circuit.nets} == set(frozen["nets"]),
            "QA_B_ORIGINAL_SOURCE_NET_NAMES_NOT_IMMUTABLE")
    source_ids = {endpoint.id: endpoint for endpoint in original.endpoints}
    require(set(source_ids) == set(B_STUBS) and
            len(original.stubs) == 2,
            "QA_B_FROZEN_SOURCE_NOT_TWO_TYPED_MARKERS")
    references = {comp.reference: comp for comp in circuit.components}
    expected_markers = {}
    expected_stubs = {}
    for stub in original.stubs:
        expected_pin = B_STUBS.get(stub.endpoint_id)
        require(expected_pin == f"{stub.pin.reference}.{stub.pin.number}",
                "QA_B_FROZEN_STUB_WRONG_PINREF")
        comp = references[stub.pin.reference]
        part = assembly.parts[comp.part_id]
        symbol = assembly.symbols[part.symbol_id]
        real_tip = comp.pin_positions(symbol)[stub.pin.number]
        delta_x = stub.end.x - stub.start.x
        delta_y = stub.end.y - stub.start.y
        require(delta_x == 0 or delta_y == 0,
                "QA_B_SOURCE_NONORTHOGONAL_STUB")
        new_end = (real_tip.x + delta_x, real_tip.y + delta_y)
        require(MARGIN <= new_end[0] <= A3[0] - MARGIN and
                MARGIN <= new_end[1] <= A3[1] - MARGIN,
                "QA_B_REBOUND_MARKER_OUTSIDE_REAL_A3_MARGIN")
        expected_markers[stub.endpoint_id] = list(new_end)
        expected_stubs[expected_pin] = {
            "start": [real_tip.x, real_tip.y],
            "end": list(new_end),
        }
    expected_nets = {
        net.name: [f"{p.reference}.{p.number}" for p in net.members]
        for net in circuit.nets
    }
    b = expected_nets["b_NEGATIVE_OUTPUT"]
    require(set(b) == PHYSICAL_B and len(b) == 3,
            "QA_B_ACTUAL_E695_NET_NOT_PHYSICAL_FU1_X2_R5")
    return {
        "actual_source_named_net_memberships": expected_nets,
        "b_markers_from_frozen_vectors": expected_markers,
        "b_stubs_from_actual_compact_PinRef": expected_stubs,
        "actual_source_original_reference": ORIGINAL_SHA,
    }


def audit_real_b(report: dict, expected: dict) -> dict:
    """Fail closed on off-by-1µm and nominally plausible false b labels."""
    require(isinstance(report, dict) and
            report.get("schema") ==
            "C11_SOURCE_LOCKED_SIGNED_DA1_B_CONTINUATION_V1",
            "QA_B_WRONG_CURRENT_RECON_SCHEMA")
    require(report.get("status") ==
            "PASS_SOURCE_BINDING_ONLY_NOT_15_NET_PRINT",
            "QA_B_SOURCE_BINDING_NOT_ONLY_SOURCE_VALIDATED")
    require(report.get("immutable_original_commit") == ORIGINAL_SHA and
            report.get("owner_exact_HEADs") == OWNER_SHAS,
            "QA_B_SOURCE_OR_EMBEDDED_OWNER_SHA_WRONG")
    require((
        report.get("frozen_source_components"),
        report.get("frozen_source_Net_count"),
        report.get("frozen_source_physical_memberships"),
        report.get("manufacturer_DA1_physical_pin_count"),
    ) == (23, 15, 62, 16), "QA_B_23_15_62_16_CHART_COUNT_FALSE")
    require(report.get("true_original_nets") ==
            expected["actual_source_named_net_memberships"],
            "QA_B_HISTORICAL_SOURCE_PHYSICAL_TOPOLOGY_CHANGED")
    require(report.get("signed_source_Circuit_Nets_identical") is True and
            report.get("before_legacy_DA1_part_id") == "reference.tl494cn"
            and report.get("after_signed_DA1_part_id") ==
            "ti.tl494cn.pdip16",
            "QA_B_MANUFACTURER_PART_CANONICAL_BRIDGE_LOST")
    require(report.get("original_bad_DRC_negative") == ORIGINAL_BAD_DRC and
            ORIGINAL_BAD_DRC == {
                "error_count": 9, "warning_count": 32,
                "segments": 91, "junctions": 37,
            }, "QA_B_OLD_9_ERROR_32_WARN_DETECTOR_REMOVED")
    require(report.get("source_b_nonphysical_Net") == "b_NEGATIVE_OUTPUT"
            and set(report.get("source_b_physical_members", [])) == PHYSICAL_B
            and len(report.get("source_b_physical_members", [])) == 3,
            "QA_B_CONTINUATION_FABRICATED_EXTRA_ELECTRICAL_NET")
    require(report.get("source_b_marker_um") ==
            expected["b_markers_from_frozen_vectors"],
            "QA_B_GREEN_SOURCE_LABEL_ANCHOR_NOT_PIN_DERIVED")
    require(report.get("source_b_stubs_um") ==
            expected["b_stubs_from_actual_compact_PinRef"],
            "QA_B_REBOUND_VECTOR_CHANGED_BY_ARTWORK_GUESS")
    require(report.get("b_marker_continuations_are_NOT_new_physical_Nets")
            is True and report.get("full_15_Net_route_proven") is False and
            report.get("full_clean_SVG_or_300DPI_PNG_released") is False and
            report.get("full_A3_print_and_photo_1_to_1") == "BLOCKED" and
            report.get("GOST_normative_source_UGO_status") ==
            "DRAFT_UNAPPROVED",
            "QA_B_SOURCE_EVIDENCE_PREMATURE_PRINT_APPROVAL")
    pins = report.get("signed_DA1_pin_contacts")
    require(isinstance(pins, list) and len(pins) == 16 and
            {item.get("number") for item in pins} ==
            {str(i) for i in range(1, 17)},
            "QA_B_PHYSICAL_DA1_SOURCE_LOST_16_TIPS")
    actual = {r["number"]: r for r in pins}
    for num, name in (("3", "FEEDBACK"), ("13", "OUTPUT CTRL")):
        require(actual[num].get("manufacturer_name") == name and
                actual[num].get("electrical_type") == "input" and
                actual[num].get("owner_Net") in
                expected["actual_source_named_net_memberships"],
                "QA_B_DA1_FB_OC_MANUFACTURER_ROLE_DRIFT")
    return {
        "source": ORIGINAL_SHA,
        "recon_source_sha": RECON_SHA,
        "physical_parts": 23, "actual_named_net_count": 15,
        "physical_net_memberships": 62, "DA1_manufacturer_leads": 16,
        "b_source_reference": "b_NEGATIVE_OUTPUT",
        "b_X2_R5_real_typed_marker_count": 2,
        "markers_um": expected["b_markers_from_frozen_vectors"],
        "stub_source": "TRUE_E695_SOURCE_VECTOR_PLUS_NEW_GRAPHICPIN",
        "b_did_not_create_a_new_Net": True,
        "manufacturer_signed_FB_OC": "INPUT",
        "whole_sheet_print_release": "BLOCKED_15_OF_15_AND_FINAL_DRC",
        "pixel_source_photo_parity": "BLOCKED_NO_AUTHORITATIVE_IMAGE",
    }


def live_real_rebinding_gate(font_file: Path, expected: dict) -> dict:
    """Execute actual RECON b owner with original authoritative source values.

    This independent gate works even while the optional RECON convenience
    JSON preflight has a legacy font-name mismatch. All native production
    operations remain owner source, never a QA-authored wire/SVG.
    """
    from dataclasses import replace

    from examples.tl494_v5.cycle11_b_continuation import rebind_true_source_b
    from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti

    from gost_schematic.core.geometry import Point
    from gost_schematic.electrical.netrefs import validate_net_continuations
    from gost_schematic.model.circuit import Circuit, Net

    original = _compose_frozen_circuit_with_real_type_a(
        compose_circuit, font_file,
    )[-1]
    assembly = compact_source_assembly()
    frozen, _ = load_original_owner_fixture()
    source = restore_original_named_nets(assembly, frozen)
    signed = bind_verified_compact_ti(assembly, source)
    signed.verify()
    actual = rebind_true_source_b(
        original, signed.signed.circuit, assembly.symbols,
    )
    physically_mapped = {p.id: [p.anchor.x, p.anchor.y]
                         for p in actual.endpoints}
    stubs = {
        f"{s.pin.reference}.{s.pin.number}": {
            "start": [s.start.x, s.start.y],
            "end": [s.end.x, s.end.y],
        } for s in actual.stubs
    }
    require(physically_mapped == expected["b_markers_from_frozen_vectors"]
            and stubs == expected["b_stubs_from_actual_compact_PinRef"],
            "QA_B_LIVE_RECON_REAL_STUB_REBIND_NOT_FROZEN_VECTOR")
    require(actual.circuit.nets is signed.signed.circuit.nets
            and actual.nets[0].net_name == "b_NEGATIVE_OUTPUT"
            and len(actual.endpoints) == 2
            and len(actual.stubs) == 2,
            "QA_B_LIVE_OWNER_CHANGED_SOURCE_NET_OR_COUNT")
    require(validate_net_continuations(
        actual, physical_pin_anchors={s.pin: s.start for s in actual.stubs},
    ) == (), "QA_B_LIVE_OWNER_CONTINUATION_SOURCE_VALIDATION")
    negative = {}
    # The source authority is the old physical stub vector, not copied
    # marker text or a cosmetically convenient new electrical Net.
    altered = replace(original, endpoints=tuple(
        replace(p, anchor=Point(p.anchor.x + 1, p.anchor.y))
        if p.id == "b-X2" else p for p in original.endpoints
    ))
    try:
        rebind_true_source_b(altered, signed.signed.circuit, assembly.symbols)
    except ValueError as exc:
        require(str(exc).startswith("TL494_C11_B_"),
                "QA_B_MUTATED_ORIGINAL_WRONG_REJECTION")
        negative["old_source_marker_1um_displacement"] = "REJECTED"
    else:
        raise BContractFailure("QA_B_SOURCE_MARKER_FORGERY_ACCEPTED")
    b_changed = Circuit(
        signed.signed.circuit.components,
        tuple(Net("PE", n.members) if n.name == "b_NEGATIVE_OUTPUT"
              else n for n in signed.signed.circuit.nets),
    )
    try:
        rebind_true_source_b(original, b_changed, assembly.symbols)
    except ValueError as exc:
        require(str(exc).startswith("TL494_C11_B_"),
                "QA_B_FOREIGN_NET_WRONG_REJECTION")
        negative["fake_PE_replacing_b"] = "REJECTED"
    else:
        raise BContractFailure("QA_B_FAKE_PE_SOURCE_NET_ACCEPTED")
    moved = replace(
        signed.signed.circuit,
        components=tuple(
            replace(c, origin=Point(470000, c.origin.y))
            if c.reference == "X2" else c
            for c in signed.signed.circuit.components
        ),
    )
    try:
        rebind_true_source_b(original, moved, assembly.symbols)
    except ValueError as exc:
        require("OUTSIDE_COMPACT_A3_MARGIN" in str(exc),
                "QA_B_A3_MARGIN_WRONG_REJECTION")
        negative["X2_outside_A3_real_margin"] = "REJECTED"
    else:
        raise BContractFailure("QA_B_UNSAFE_OFF_PAGE_STUB_ACCEPTED")
    return {
        "live_original_e695_original_source": ORIGINAL_SHA,
        "live_RECON_sha": RECON_SHA,
        "actual_production_RECON_b_rebinding": "PASS_TYPED_SOURCE_ONLY",
        "actual_source_signed_manufacturer_IC": "ti.tl494cn.pdip16",
        "actual_b_marker_counts": 2,
        "source_15_named_nets_and_62_PinRefs_unchanged": True,
        "source_b_marker_real_coordinates_um": physically_mapped,
        "negative_real_source_rejections": negative,
        "print_15Net_approval": "NO_GO_UNTIL_REAL_ROUTED_AFTER",
    }


def adversarial_b_failures(authentic: dict, expected: dict) -> dict:
    """Only clone JSON evidence in memory; never edit a real owner image."""
    cases = {
        "one_um_b_X2_marker_shift": lambda a: a["source_b_marker_um"][
            "b-X2"].__setitem__(0, a["source_b_marker_um"]["b-X2"][0] + 1),
        "one_um_b_R5_stub_shift": lambda a: a["source_b_stubs_um"][
            "R5.2"]["end"].__setitem__(
                1, a["source_b_stubs_um"]["R5.2"]["end"][1] + 1,
            ),
        "swapped_b_marker_addresses": lambda a: a[
            "source_b_marker_um"].update({
                "b-X2": a["source_b_marker_um"]["b-R5"],
                "b-R5": a["source_b_marker_um"]["b-X2"],
            }),
        "forged_b_physical_pinref": lambda a: a[
            "source_b_physical_members"].append("DA1.999"),
        "renamed_b_net_to_PE": lambda a: a.update(
            source_b_nonphysical_Net="PE",
        ),
        "removed_continuation_stub": lambda a: a[
            "source_b_stubs_um"].pop("X2.1"),
        "fake_old_known_bad_DRC_green": lambda a: a[
            "original_bad_DRC_negative"].update(error_count=0),
        "claimed_15_of_15": lambda a: a.update(full_15_Net_route_proven=True),
        "TI_FB_role_forged_OUTPUT": lambda a: next(
            item for item in a["signed_DA1_pin_contacts"]
            if item["number"] == "3"
        ).update(electrical_type="output"),
        "source_manufacturer_part_ID_forged": lambda a: a.update(
            after_signed_DA1_part_id="reference.tl494cn",
        ),
        "duplicate_DA1_physical_contact": lambda a: a[
            "signed_DA1_pin_contacts"].append(
                deepcopy(a["signed_DA1_pin_contacts"][0]),
            ),
        "fake_print_released": lambda a: a.update(
            full_clean_SVG_or_300DPI_PNG_released=True,
        ),
    }
    outcome = {}
    for name, mutate in cases.items():
        forged = deepcopy(authentic)
        mutate(forged)
        try:
            audit_real_b(forged, expected)
        except BContractFailure:
            outcome[name] = "REJECTED_BY_SOURCE_TRUE_CONTRACT"
        else:
            raise BContractFailure("QA_B_NEGATIVE_MUTATION_BYPASSED:" + name)
    require(len(outcome) == 12, "QA_B_NOT_ALL_12_NEGATIVES_EXECUTED")
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recon-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--direct-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    def head(path: Path) -> str:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    require(head(args.source_root) == ORIGINAL_SHA and
            head(args.recon_root) == RECON_SHA,
            "QA_B_SOURCE_OR_RECON_GIT_SHA_NOT_PINNED")
    font = inspect_type_a_font(
        args.font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    require(font.measured_cap_height_um == 3500,
            "QA_B_TYPE_A_FONT_NOT_TRUE_CAP_HEIGHT")
    expected = immutable_expected(args.font_file)
    if args.direct_only:
        result = {
            "actual_live_owner_code": live_real_rebinding_gate(
                args.font_file, expected,
            ),
            "no_hand_edited_SVG_or_fake_photo_source": True,
            "print_or_UGO_approval": "NO_GO_NOT_A_ROUTED_SHEET",
        }
    else:
        require(args.evidence is not None and args.evidence.is_file(),
                "QA_B_NO_GENUINE_OWNER_EVIDENCE_FILE")
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        require(evidence.get("GOST_A_font_SHA256") == font.style.font_sha256,
                "QA_B_SOURCE_FONT_PROVENANCE_DRIFT")
        result = {
            "source_verification": audit_real_b(evidence, expected),
            "twelve_hostile_genuine_source_mutations":
                adversarial_b_failures(evidence, expected),
            "no_hand_edited_SVG_or_fake_photo_source": True,
            "print_or_UGO_approval": "NO_GO_NOT_A_ROUTED_SHEET",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False,
    ) + "\n", encoding="utf-8")
    print("QA92_CYCLE11_REAL_B_SOURCE_CONTINUATION " + json.dumps(
        result, ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
