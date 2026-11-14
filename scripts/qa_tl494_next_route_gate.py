"""Independent source-locked TL494 15-Net routing gate; NO paper release.

This checks genuine owner route-report DATA against the immutable reference
Circuit. Success of the structural check is not an endorsement of an image,
photo parity, ESKD certification, or the absence of independently untested
wire/symbol/text collisions. A future full candidate must also pass visual QA.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from copy import deepcopy
from pathlib import Path

FROZEN_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
RECON_SHA = "fa36620877c244e24fccaad8d0bb00133bec52ef"
ROUTER_SHA = "b3a8263944c5a687492a49555d8149e538f0902b"
PAINT_SHA = "161c31bd0b538c6e827341ae465c3b3a59f6637d"
IC_SHA = "b28428d94218cac777a28897ce9176285d0fab0b"
EMPTY_DELTA = {"added": [], "removed": [], "modified_physical_PinRef": []}


class GateError(AssertionError):
    """Invalid, internally inconsistent or fabricated release evidence."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GateError(code)


def frozen_membership() -> dict[str, frozenset[str]]:
    """Import the ORIGINAL real 23/15 Python source, not synthetic test nets."""
    from scripts.qa_tl494_router_contract import source_model

    original = source_model()
    return {net["name"]: frozenset(net["members"]) for net in original["nets"]}


def inspect_route(
    report: dict, source: dict[str, frozenset[str]],
    *, exact_router_sha: str = ROUTER_SHA,
) -> dict:
    """Recompute route-completeness claims from individual actual net trees.

    Returns BLOCKED for an honest partial route; raises on invented/stale
    topology or inconsistent success claims. Never returns PRINT_PASS.
    """
    require(isinstance(report, dict), "QA_ROUTE_REPORT_NOT_OBJECT")
    require(len(source) == 15, "QA_FROZEN_SOURCE_NOT_15_NETS")
    require(report.get("source_sha") == FROZEN_SHA,
            "QA_ROUTE_SOURCE_SHA_NOT_FROZEN")
    require(report.get("owner_router_sha") == exact_router_sha,
            "QA_ROUTE_OWNER_SHA_STALE")
    require(report.get("origin_component_count") == 23,
            "QA_ROUTE_COMPONENT_COUNT_DRIFT")
    require(report.get("origin_net_count") ==
            report.get("source_net_count") == 15,
            "QA_ROUTE_DECLARED_NET_COUNT_DRIFT")
    pin_count = sum(len(pins) for pins in source.values())
    require(pin_count == 62 and report.get("source_pin_count") == pin_count,
            "QA_ROUTE_SOURCE_62_PHYSICAL_MEMBERSHIPS_LOST")
    require(report.get("DA1_real_anchor_count") == 16,
            "QA_ROUTE_TL494_PHYSICAL_16_TIPS_MISSING")
    require(report.get("net_diff") == EMPTY_DELTA,
            "QA_ROUTE_NET_IDENTITY_DELTA_OR_WRONG_FORMAT")
    require(report.get("old_source_negative_drc") == {
        "errors": 9, "warnings": 32, "segments": 91, "junctions": 37,
    }, "QA_KNOWN_BAD_ORIGINAL_CHANGED")
    trees = report.get("net_trees")
    require(isinstance(trees, list), "QA_ROUTE_NO_PHYSICAL_TREE_EXPORT")
    observed: set[str] = set()
    complete = 0
    incomplete = []
    for tree in trees:
        require(isinstance(tree, dict), "QA_ROUTE_BAD_TREE")
        name = tree.get("net")
        require(isinstance(name, str) and name in source and
                name not in observed, "QA_ROUTE_UNKNOWN_DUPLICATE_NET")
        observed.add(name)
        refs = tree.get("pin_refs")
        connected = tree.get("connected_pin_refs")
        require(isinstance(refs, list) and isinstance(connected, list),
                "QA_ROUTE_NO_REAL_TREE_PINREFS")
        require(len(refs) == len(set(refs)) and set(refs) == source[name],
                "QA_ROUTE_PHYSICAL_PINREF_DELTA")
        require(len(connected) == len(set(connected)) and
                set(connected) <= source[name],
                "QA_ROUTE_FORGED_OR_DUPLICATE_CONNECTED_PIN")
        done = tree.get("complete")
        require(type(done) is bool, "QA_ROUTE_NONBOOLEAN_TREE_COMPLETENESS")
        require(not done or set(connected) == source[name],
                "QA_ROUTE_UNCONNECTED_PIN_CLAIMED_COMPLETE")
        require(not done or not tree.get("diagnostics"),
                "QA_ROUTE_TREE_CLAIMED_COMPLETE_WITH_ERRORS")
        if done:
            complete += 1
        else:
            incomplete.append(name)
        require(tree.get("print_pass") is False,
                "QA_ROUTE_TREE_PREVIEW_FORGED_PRINT_PASS")
    require(type(report.get("routed_net_count")) is int and
            complete == report["routed_net_count"],
            "QA_ROUTE_SUMMARY_DISAGREES_WITH_TREES")
    require(type(report.get("graph_segments")) is int and
            report["graph_segments"] >= 0 and
            type(report.get("graph_junctions")) is int and
            report["graph_junctions"] >= 0,
            "QA_ROUTE_GRAPH_COUNTS_INVALID")
    drc = report.get("drc")
    require(isinstance(drc, dict), "QA_ROUTE_MISSING_OWNER_DRC")
    require(drc.get("component_count") == 23 and
            drc.get("net_count") == 15 and
            drc.get("wire_count") == report["graph_segments"] and
            drc.get("explicit_junctions") == report["graph_junctions"],
            "QA_ROUTE_DRC_NOT_EVALUATING_GENERATED_GRAPH")
    findings = drc.get("findings")
    require(isinstance(findings, list) and
            all(isinstance(f, dict) and
                f.get("severity") in ("error", "warning") for f in findings),
            "QA_ROUTE_DRC_MALFORMED_FINDINGS")
    actual_errors = sum(f["severity"] == "error" for f in findings)
    require(type(drc.get("error_count")) is int and
            drc["error_count"] == actual_errors and
            drc.get("valid") is (actual_errors == 0),
            "QA_ROUTE_DRC_COUNT_OR_VALIDITY_LIED")
    for key in ("checked_symbol_geometry", "checked_measured_text"):
        require(type(drc.get(key)) is bool,
                "QA_ROUTE_DRC_COVERAGE_NOT_EXPLICIT_" + key)
    diagnostics = report.get("diagnostics")
    require(isinstance(diagnostics, list), "QA_ROUTE_NO_DIAGNOSTICS")
    routes_complete = (
        len(trees) == len(source) and observed == set(source)
        and complete == len(source) and not diagnostics
    )
    require(report.get("complete") is routes_complete,
            "QA_ROUTE_COMPLETE_CLAIM_DISAGREES_WITH_TREE_COUNT")
    geometry_complete = (drc["checked_symbol_geometry"] and
                         drc["checked_measured_text"])
    eligible = routes_complete and actual_errors == 0 and geometry_complete
    require(report.get("print_pass") is eligible,
            "QA_ROUTE_PRINT_PREFLIGHT_FLAG_INCONSISTENT")
    require(report.get("blocked_release") is (not eligible),
            "QA_ROUTE_BLOCKED_RELEASE_FLAG_FORGED")
    if "technical_route_eligible" in report:
        # Reference-specific extra constraints may veto a technically valid
        # router; they cannot release a structurally unsafe one.
        require(report["technical_route_eligible"] is not True or eligible,
                "QA_ROUTE_REFERENCE_FALSE_ELIGIBILITY")
    require(report.get("print_after_released") is False,
            "QA_ROUTE_PREVIEW_NOT_AN_APPROVED_PRINT_ARTIFACT")
    reasons = []
    if len(trees) != 15:
        reasons.append(f"ONLY_{len(trees)}_OF_15_NET_TREE_RECORDS")
    if complete != 15:
        reasons.append(f"ONLY_{complete}_OF_15_NETS_COMPLETE")
    if actual_errors:
        reasons.append(f"NEW_ROUTE_DRC_{actual_errors}_ERRORS")
    if not drc["checked_symbol_geometry"]:
        reasons.append("SYMBOL_GEOMETRY_UNCHECKED")
    if not drc["checked_measured_text"]:
        reasons.append("MEASURED_TEXT_UNCHECKED")
    if diagnostics:
        reasons.append("ROUTER_DIAGNOSTICS_PRESENT")
    return {
        "status": "TECHNICAL_ROUTE_ELIGIBLE_NOT_PRINT_RELEASE" if eligible
        else "BLOCKED_NO_PRINT_RELEASE",
        "source_sha": FROZEN_SHA,
        "actual_route_sha": exact_router_sha,
        "parts": 23,
        "source_nets": 15,
        "source_pinref_memberships": 62,
        "tl494_physical_pins": 16,
        "routed_nets": complete,
        "unrouted_net_names": sorted(set(source) - observed | set(incomplete)),
        "new_route_drc_errors": actual_errors,
        "checked_symbol_geometry": drc["checked_symbol_geometry"],
        "checked_measured_text": drc["checked_measured_text"],
        "reason_codes": reasons,
        "print_release": "NO_GO_UNTIL_REAL_RENDER_AND_INDEPENDENT_QA",
    }


def negative_mutations(source: dict[str, frozenset[str]]) -> dict[str, str]:
    """A correct unit harness is not a positive TL494 print fixture."""
    names = sorted(source)
    trees = [
        {"net": name, "pin_refs": sorted(source[name]),
         "connected_pin_refs": sorted(source[name]), "complete": True,
         "diagnostics": [], "print_pass": False}
        for name in names
    ]
    pristine = {
        "source_sha": FROZEN_SHA,
        "owner_router_sha": ROUTER_SHA,
        "origin_component_count": 23,
        "origin_net_count": 15,
        "source_net_count": 15,
        "source_pin_count": 62,
        "DA1_real_anchor_count": 16,
        "net_diff": deepcopy(EMPTY_DELTA),
        "old_source_negative_drc": {
            "errors": 9, "warnings": 32, "segments": 91, "junctions": 37,
        },
        "net_trees": trees,
        "routed_net_count": 15,
        "graph_segments": 10,
        "graph_junctions": 0,
        "diagnostics": [],
        "complete": True,
        "print_pass": True,
        "blocked_release": False,
        "print_after_released": False,
        "drc": {
            "component_count": 23, "net_count": 15, "wire_count": 10,
            "explicit_junctions": 0, "error_count": 0, "valid": True,
            "findings": [], "checked_symbol_geometry": True,
            "checked_measured_text": True,
        },
    }
    # Only tests metadata consistency, NEVER physical conductor geometry.
    require(inspect_route(pristine, source)["status"].startswith("TECHNICAL_"),
            "QA_POSITIVE_SCHEMA_CONTRACT_BROKEN")
    cases = {
        "fourteen_nets": lambda v: v["net_trees"].pop(),
        "false_routed_count": lambda v: v.update(routed_net_count=15+1),
        "missing_connected_pinref": lambda v:
            v["net_trees"][0]["connected_pin_refs"].pop(),
        "wrong_net_ref": lambda v:
            v["net_trees"][0]["pin_refs"].append("DA1.999"),
        "duplicate_tree": lambda v:
            v["net_trees"].append(deepcopy(v["net_trees"][0])),
        "torn_source_sha": lambda v: v.update(source_sha="untrusted"),
        "wrong_route_sha": lambda v: v.update(owner_router_sha="untrusted"),
        "source_net_mutation": lambda v:
            v["net_diff"]["modified_physical_PinRef"].append("DA1.3"),
        "fake_drc_zero": lambda v:
            v["drc"]["findings"].append({"severity": "error", "code": "SHORT"}),
        "unverified_symbol_ink": lambda v:
            v["drc"].update(checked_symbol_geometry=False),
        "unverified_measured_text": lambda v:
            v["drc"].update(checked_measured_text=False),
        "false_15net_success": lambda v:
            v["net_trees"][0].update(complete=False),
        "premature_print_release": lambda v:
            v.update(print_after_released=True),
    }
    out = {}
    for name, mutation in cases.items():
        altered = deepcopy(pristine)
        mutation(altered)
        if name in ("unverified_symbol_ink", "unverified_measured_text"):
            # Some claims are internally honest BLOCKED, not malformed.
            altered["print_pass"] = False
            altered["blocked_release"] = True
            verdict = inspect_route(altered, source)
            require(verdict["status"] == "BLOCKED_NO_PRINT_RELEASE",
                    "QA_UNCHECKED_INK_NOT_BLOCKED")
            out[name] = "BLOCKED_AS_REQUIRED"
            continue
        try:
            inspect_route(altered, source)
        except GateError:
            out[name] = "REJECTED_AS_REQUIRED"
        else:
            raise GateError("QA_NEGATIVE_BYPASS_" + name)
    # Genuine 8/15 snapshot must be non-release, not mistaken for 15/15.
    partial = deepcopy(pristine)
    for row in partial["net_trees"][8:]:
        row["complete"] = False
        row["connected_pin_refs"] = []
        row["diagnostics"] = ["ROUTE_NO_LEGAL_PATH"]
    partial["routed_net_count"] = 8
    partial["complete"] = False
    partial["diagnostics"] = ["PARTIAL_ROUTE"]
    partial["print_pass"] = False
    partial["blocked_release"] = True
    partial["drc"]["checked_measured_text"] = False
    result = inspect_route(partial, source)
    require(result["routed_nets"] == 8 and
            result["status"] == "BLOCKED_NO_PRINT_RELEASE",
            "QA_EIGHT_OF_FIFTEEN_FAKE_PRINT_RELEASE")
    out["8_of_15_explicit_no_go"] = "BLOCKED_AS_REQUIRED"
    return out


def _sha(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--route-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(_sha(args.frozen_root) == FROZEN_SHA,
            "QA_FROZEN_GIT_CHECKOUT_SHA_CHANGED")
    source = frozen_membership()
    report = {
        "status": "QA_CONTRACT_TESTED_NEW_ROUTE_NOT_SUPPLIED",
        "frozen_git_sha": FROZEN_SHA,
        "negative_mutations": negative_mutations(source),
        "actual_candidate": "BLOCKED_ABSENT_OWNER_ARTIFACT",
        "release": "NO_GO",
    }
    if args.route_report:
        real = json.loads(args.route_report.read_text(encoding="utf-8"))
        report["actual_candidate"] = inspect_route(real, source)
        report["status"] = "REAL_OWNER_ROUTE_INDEPENDENTLY_INSPECTED"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("QA92_NEXT_ROUTE " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
