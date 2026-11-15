"""Independent QA of REAL NET114 TL494 compact native source/after artifacts.

This is an acceptance gate, not a router or image compositor. A partial
graph can PASS source fidelity while ALWAYS remaining BLOCKED for print.
No repair of SVG, physical pins, Net names, UGO, or source photograph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

S = "{http://www.w3.org/2000/svg}"
SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FIXTURE_GIT_BLOB_SHA1 = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
FONT_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
RAW_ALIASES = {
    "a_INPUT_PLUS": "INPUT_POS",
    "TRANSFER": "ENERGY_TRANSFER",
    "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
}
OLD_DRC = {"wire_segments": 91, "drc_errors": 9, "drc_warnings": 32}


class SourceContractViolation(AssertionError):
    """A claim contradicts physical source, native route or print gate."""


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise SourceContractViolation(marker)


def original_source_fixture(path: Path) -> dict:
    payload = path.read_bytes()
    signature = hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + bytes((0,)) + payload
    ).hexdigest()
    require(signature == FIXTURE_GIT_BLOB_SHA1,
            "QA_C12_ORIGINAL_FIXTURE_GIT_BLOB_CHANGED")
    data = json.loads(payload)
    require(len(data["components"]) == 23 and len(data["nets"]) == 15
            and sum(len(m) for m in data["nets"].values()) == 62,
            "QA_C12_ORIGINAL_REAL_SOURCE_NOT_23_15_62")
    unique = {pin for pins in data["nets"].values() for pin in pins}
    require(len(unique) == 62 and
            {f"DA1.{i}" for i in range(1, 17)} <= unique,
            "QA_C12_ORIGINAL_PINREF_IDENTITY_DRIFT")
    require(set(RAW_ALIASES) <= set(data["nets"]),
            "QA_C12_ORIGINAL_A_TRANSFER_B_MISSING")
    return data


def validate_report(report: dict, source: dict, *, exact_net_sha: str,
                    exact_recon_sha: str) -> dict:
    """Check genuine source Net trees, accepted graph and fail-closed release."""
    require(report.get("source_sha") == SOURCE_SHA and
            report.get("owner_router_sha") == exact_net_sha and
            report.get("reference_recon_sha") == exact_recon_sha,
            "QA_C12_WRONG_NET_RECON_OR_ORIGINAL_SOURCE_SHA")
    require((
        report.get("source_components"), report.get("source_nets"),
        report.get("physical_DA1_pin_count"),
        report.get("all_Circuit_PinRef_memberships"),
    ) == (23, 15, 16, 62), "QA_C12_MISSING_PHYSICAL_23_15_16_62")
    require(report.get("source_net_diff") == {
        "added": [], "removed": [], "physical_members_changed": [],
    }, "QA_C12_SOURCE_NETS_REWRITTEN")
    canonical = {
        RAW_ALIASES.get(name, name): tuple(members)
        for name, members in source["nets"].items()
    }
    require(len(canonical) == 15,
            "QA_C12_ORIGINAL_NAMED_NET_ALIAS_COLLISION")
    actual = report.get("net_members", {})
    require(set(actual) == set(canonical) and all(
        tuple(actual[name]) == members
        for name, members in canonical.items()
    ), "QA_C12_SOURCE_NAMED_NET_OR_PINREF_CHANGED")
    require(report.get("known_bad_original_source") is not None,
            "QA_C12_OLD_9_32_NEGATIVE_CONTROL_REMOVED")
    negative = report["known_bad_original_source"]
    for key, value in OLD_DRC.items():
        require(negative.get(key) == value,
                "QA_C12_ORIGINAL_ERROR_OR_WARNING_FORGED_GREEN")
    require(report.get("font_sha256") == FONT_SHA256,
            "QA_C12_FONT_NOT_PINNED_GOST_TYPE_A")
    require(report.get("real_PAINT_leads") == 16 and
            report.get("real_source_UGO_draft_count") == 13 and
            report.get("VT1_source_UGO_normative_approved") is False,
            "QA_C12_PIN_LOST_OR_DRAFT_UGO_FALSIFIED")
    require(report.get("editor_targets") == {
        "physical_tip_count": 16, "only_in_diagnostic": True,
        "source": "typed-native-PinRef-and-original-Circuit.Net",
    }, "QA_C12_FORGED_EDITOR_SQUARES")
    routing = report.get("routing")
    require(isinstance(routing, dict) and
            routing.get("source_net_count") == 15 and
            routing.get("source_pin_count") == 62 and
            len(routing.get("net_trees", ())) == 15,
            "QA_C12_MISSING_FULL_NET_TREE_INVENTORY")
    trees = routing["net_trees"]
    require({t.get("net") for t in trees} == set(canonical),
            "QA_C12_NET_TREE_NAME_OR_DUPLICATE_INVALID")
    for tree in trees:
        name = tree["net"]
        pins = tuple(tree.get("pin_refs", ()))
        connected = tuple(tree.get("connected_pin_refs", ()))
        require(pins == canonical[name] and
                len(connected) == len(set(connected)) and
                set(connected) <= set(pins),
                "QA_C12_NET_TREE_PHYSICAL_PINREF_LIE")
        complete = not tree.get("diagnostics") and connected == pins
        require(tree.get("complete") is complete and
                tree.get("print_pass") is False,
                "QA_C12_NET_TREE_FALSE_CONNECTED_OR_PRINT")
        require(type(tree.get("segments")) is int and
                tree["segments"] >= 0 and
                type(tree.get("length_um")) is int and
                tree["length_um"] >= 0,
                "QA_C12_NET_TREE_SEGMENT_OR_LENGTH_INVALID")
    connected_nets = sum(t["complete"] for t in trees)
    wire_count = sum(t["segments"] for t in trees if t["complete"])
    require(0 <= connected_nets <= 15 and
            connected_nets == routing.get("routed_net_count") ==
            report.get("routed_nets") and
            routing.get("graph_segments") == wire_count ==
            report.get("routed_segments"),
            "QA_C12_FAKE_ALL_15_OR_WIRE_COUNT")
    actual_drc = report.get("new_after_drc")
    require(isinstance(actual_drc, dict) and
            actual_drc.get("checked_symbol_geometry") is True and
            actual_drc.get("checked_measured_text") is True and
            actual_drc.get("wire_count") == wire_count,
            "QA_C12_MEASURED_FULL_SYMBOL_TEXT_DRC_NOT_EXECUTED")
    findings = actual_drc.get("findings")
    require(isinstance(findings, list) and
            actual_drc.get("error_count") ==
            sum(f.get("severity") == "error" for f in findings)
            and actual_drc.get("warning_count") ==
            sum(f.get("severity") == "warning" for f in findings),
            "QA_C12_SOURCE_DRC_ERROR_COUNT_FORGED")
    require(report.get("measured_annotation_guards", 0) >= 39 and
            report.get("independent_QA_approved") is False and
            report.get("certified_UGO") is False and
            report.get("print_pass") is False,
            "QA_C12_PREMATURE_ESKD_OR_QA_RELEASE")
    if connected_nets < 15:
        require(routing.get("complete") is False and
                routing.get("print_pass") is False and
                report.get("geom_drc_pass") is False and
                report.get("status") == "BLOCKED_PARTIAL_NOT_PRINTABLE",
                "QA_C12_PARTIAL_ROUTE_WITH_ZERO_DRC_FAKED_SUCCESS")
    require(report.get("verified_legacy_illegal_W2", {}).get("preflight") ==
            "REJECTED_INK_INTERSECTION",
            "QA_C12_W2_CROSS_DA1_UNSAFE_LEAD_NOT_REJECTED")
    return {
        "source_sha": SOURCE_SHA, "net_owner_sha": exact_net_sha,
        "recon_owner_sha": exact_recon_sha,
        "source_parts": 23, "real_named_nets": 15, "pinrefs": 62,
        "da1_physical_pins": 16,
        "original_b_continuation": "SOURCE_ONLY_SEPARATE_TWO_NONPHYSICAL",
        "routed_complete": connected_nets,
        "unrouted": sorted(t["net"] for t in trees if not t["complete"]),
        "accepted_wire_segments": wire_count,
        "real_new_graph_drc_errors": actual_drc["error_count"],
        "source_original_bad_DRC": OLD_DRC,
        "full_print_approved": False,
        "release": "BLOCKED_UNTIL_15_15_AND_FINAL_QA_AND_GOST",
    }


def check_svg_png(directory: Path, report: dict, paper: str) -> dict:
    """Native SHEET artwork and stamped 300 DPI; no raster fabrication."""
    summary = {}
    for mode in ("clean", "diagnostic"):
        stem = f"TL494-compact-{paper}-{mode}"
        svg_path = directory / (stem + ".svg")
        png_path = directory / (stem + "-300dpi.png")
        raw = svg_path.read_bytes()
        root = ET.fromstring(raw)
        require(root.tag == S + "svg" and
                root.get("data-release") == "BLOCKED_PARTIAL" and
                root.get("data-draft-paper") == paper and
                root.get("data-owner-router-sha") ==
                report["owner_router_sha"] and
                root.get("data-physical-net-diff") == "ZERO",
                "QA_C12_NATIVE_SHEET_PARTIAL_PRINT_OR_SOURCE_FORGED")
        lines = root.findall(f".//{S}line[@data-layer='wires']")
        require(len(lines) == report["routed_segments"] and
                all(x.get("data-net") in report["net_members"]
                    for x in lines),
                "QA_C12_SVG_NOT_REAL_ROUTED_NET_LINES")
        source_ic = root.find(
            f".//{S}g[@data-ink-source='real-native-PAINT-original-16leads']"
        )
        require(source_ic is not None and
                len(source_ic.findall(
                    f".//{S}g[@data-layer='ic-physical-pin-leads']/{S}line"
                )) == 16, "QA_C12_MISSING_REAL_PHYSICAL_DA1_INK")
        layer = root.find(f".//{S}g[@data-layer='editor-connection-targets']")
        require((layer is None) == (mode == "clean"),
                "QA_C12_CLEAN_DIAGNOSTIC_EDITOR_POLICY_WRONG")
        if mode == "diagnostic":
            markers = layer.findall(S + "rect")
            require(len(markers) == 16 and
                    {r.get("data-pin-ref") for r in markers} ==
                    {f"DA1.{n}" for n in range(1, 17)} and
                    all(r.get("fill") == "#148645" for r in markers)
                    and layer.get("data-physical-print") == "false",
                    "QA_C12_EDITOR_COPPER_PINS_NOT_16_GREEN_TIPS")
        width, height = root.get("width"), root.get("height")
        require(width.endswith("mm") and height.endswith("mm"),
                "QA_C12_SVG_NOT_PHYSICAL_MM")
        mm = (float(width[:-2]), float(height[:-2]))
        require(all(d > 0 for d in mm), "QA_C12_NONPHYSICAL_PAGE")
        with Image.open(png_path) as img:
            require(img.format == "PNG", "QA_C12_NO_REAL_300DPI_PNG")
            expected_pixels = tuple(
                round(d / 25.4 * 300) for d in mm
            )
            require(all(abs(a - b) <= 3 for a, b in zip(
                img.size, expected_pixels, strict=True
            )), "QA_C12_RASTER_NOT_MATCH_SVG_MM_300DPI")
            dpi = img.info.get("dpi")
            require(dpi is not None and
                    all(abs(value - 300) < 1 for value in dpi),
                    "QA_C12_PNG_HAS_NO_REAL_DPI_METADATA")
        summary[mode] = {
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "real_svg_size_mm": list(mm), "png_300dpi_pixels": expected_pixels,
            "physical_leads": 16,
            "diagnostic_markers": 16 if mode == "diagnostic" else 0,
            "actual_new_wires": len(lines),
            "print_approval": "BLOCKED",
        }
    return summary


def adversarial_source_claims(report: dict, source: dict, *,
                              net_sha: str, recon_sha: str) -> dict:
    """Each independent fault MUST fail even if the real route is partial."""
    def alter_net(a):
        a["net_members"]["INPUT_POS"][0] = "DA1.999"

    attacks = {
        "fake_15_routed": lambda a: a.update(routed_nets=15),
        "zero_drc_promoted_as_success": lambda a: a.update(
            print_pass=True, geom_drc_pass=True
        ),
        "false_complete_route": lambda a: a["routing"].update(
            complete=True, print_pass=True
        ),
        "missing_source_component": lambda a: a.update(source_components=22),
        "source_original_9_drc_removed": lambda a: a[
            "known_bad_original_source"].update(drc_errors=0),
        "rewrote_original_a_PIN": alter_net,
        "foreign_PE_net": lambda a: a["net_members"].update(
            PE=["DA1.3"]
        ),
        "faked_62_net_members": lambda a: a.update(
            all_Circuit_PinRef_memberships=61
        ),
        "faked_source_sha": lambda a: a.update(source_sha="0" * 40),
        "faked_router_sha": lambda a: a.update(owner_router_sha="0" * 40),
        "tampered_one_real_tree": lambda a: a["routing"][
            "net_trees"][0]["pin_refs"].append("DA1.123"),
        "missing_symbol_ink_drc": lambda a: a["new_after_drc"].update(
            checked_symbol_geometry=False
        ),
        "missing_measured_label_drc": lambda a: a[
            "new_after_drc"].update(checked_measured_text=False),
        "forged_native_wire_count": lambda a: a.update(
            routed_segments=report["routed_segments"] + 1
        ),
        "fake_factory_16_leads": lambda a: a.update(
            real_PAINT_leads=15
        ),
        "released_unapproved_source_UGO": lambda a: a.update(
            certified_UGO=True
        ),
    }
    results = {}
    for name, mutation in attacks.items():
        falsified = deepcopy(report)
        mutation(falsified)
        try:
            validate_report(
                falsified, source, exact_net_sha=net_sha,
                exact_recon_sha=recon_sha,
            )
        except SourceContractViolation:
            results[name] = "REJECTED_BY_INDEPENDENT_QA"
        else:
            raise SourceContractViolation(
                "QA_C12_ADVERSARIAL_SOURCE_BYPASS:" + name
            )
    require(len(results) == 16, "QA_C12_NOT_ALL_NEGATIVES_EXECUTED")
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-fixture", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--paper", choices=("A3", "A2"), required=True)
    p.add_argument("--net-sha", required=True)
    p.add_argument("--recon-sha", required=True)
    p.add_argument("--qa-report", type=Path, required=True)
    args = p.parse_args()
    source = original_source_fixture(args.source_fixture)
    path = args.output_dir / f"TL494-compact-{args.paper}-route-drc.json"
    actual = json.loads(path.read_text(encoding="utf-8"))
    validation = validate_report(
        actual, source, exact_net_sha=args.net_sha,
        exact_recon_sha=args.recon_sha,
    )
    validation["real_render_artifacts"] = check_svg_png(
        args.output_dir, actual, args.paper,
    )
    validation["sixteen_adversarial_mutations"] = adversarial_source_claims(
        actual, source, net_sha=args.net_sha, recon_sha=args.recon_sha,
    )
    args.qa_report.parent.mkdir(parents=True, exist_ok=True)
    args.qa_report.write_text(
        json.dumps(validation, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    print("QA_CYCLE12_SOURCE_NATIVE_ROUTE_AUDIT " + json.dumps(
        validation, ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
