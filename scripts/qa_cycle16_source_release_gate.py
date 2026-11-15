"""Fail-closed QA release verifier for actual owner Cycle15 TL494 artifacts.

This never renders a substitute circuit. A complete source-named electrical
graph and an independent ESKD full-sheet report are both mandatory. Partial
routes can be EXPECTED as negative CI fixtures without accepting their print.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

ORIGINAL = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
NAMES = frozenset((
    "a_INPUT_PLUS", "SWITCH", "TRANSFER", "OUT_BEFORE_FUSE",
    "b_NEGATIVE_OUTPUT", "GATE_DRIVE", "CONTROL_REFERENCE", "SOFT_START",
    "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK", "ADJUSTED_DIVIDER",
    "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
))
SVG = "{http://www.w3.org/2000/svg}"


class ReleaseIntegrityError(AssertionError):
    """Source, artifact, trust or geometry evidence is inconsistent."""


class ReleaseBlocked(RuntimeError):
    """Authentic candidate is incomplete; this is a mandatory NO-GO."""


def demand(ok: bool, code: str) -> None:
    if not ok:
        raise ReleaseIntegrityError(code)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    demand(isinstance(value, dict), "QA_C16_DOCUMENT_NOT_OBJECT")
    return value


def mm_um(value: str | None) -> int:
    try:
        um = Decimal(str(value)) * 1000
        if not um.is_finite() or um != int(um):
            raise ValueError()
        return int(um)
    except (InvalidOperation, TypeError, ValueError):
        raise ReleaseIntegrityError("QA_C16_SVG_NOT_INTEGER_MICROMETRES") from None


def inspect_svg(
    path: Path, mode: str, original: dict[str, list[str]],
    b_stubs: dict, count: int, allow_partial: bool,
) -> tuple[str, dict]:
    root = ET.fromstring(path.read_bytes())
    demand(root.tag == SVG + "svg", "QA_C16_NOT_NATIVE_SVG")
    demand(root.get("data-original-source-names-restored-in-manifest") == "true"
           and root.get("data-source-physical-pinrefs") == "62"
           and root.get("data-source-electrical-net-count") == "15",
           "QA_C16_SOURCE_MANIFEST_ORIGINAL_NAMES_NOT_PRESERVED")
    if count != 15:
        demand(root.get("data-release") == "BLOCKED_PARTIAL",
               "QA_C16_PARTIAL_SVG_FALSIFIED_RELEASE")

    b = root.findall(".//" + SVG + "line[@data-layer='nonphysical-continuation-stub']")
    demand(len(b) == 2, "QA_C16_NOT_EXACTLY_TWO_NONCONDUCTIVE_B_STUBS")
    found = set()
    for line in b:
        demand(line.get("data-connectable") != "true",
               "QA_C16_B_GRAPHICS_FALSELY_ELECTRIC")
        xy = tuple(mm_um(line.get(key)) for key in ("x1", "y1", "x2", "y2"))
        found.add(xy)
    signed = {
        (*values["start"], *values["end"])
        for values in b_stubs.values()
    }
    demand(found == signed and len(found) == 2,
           "QA_C16_B_STUB_1UM_OR_POSITION_CHANGED")

    leads = root.findall(".//" + SVG + "g[@data-layer='ic-physical-pin-leads']/"
                         + SVG + "line")
    demand(len(leads) == 16 and
           {line.get("data-pin-number") for line in leads} ==
           {str(i) for i in range(1, 17)},
           "QA_C16_REAL_MANUFACTURER_16_PIN_LEADS_NOT_PRESENT")
    targets = root.findall(".//" + SVG + "g[@data-layer='editor-connection-targets']/"
                           + SVG + "rect")
    demand(len(targets) == (16 if mode == "diagnostic" else 0),
           "QA_C16_EDITOR_GREEN_MODE_POLICY")
    pin_net = {
        pin: name for name, pins in original.items() for pin in pins
    }
    for marker in targets:
        pin = marker.get("data-pin-ref")
        demand(pin in pin_net and
               marker.get("data-net-id") == pin_net[pin] and
               marker.get("data-connectable") == "true" and
               marker.get("fill") == "#148645",
               "QA_C16_FOREIGN_GREEN_NET_OR_ILLUSORY_CONTACT")
    ink_wires = root.findall(".//" + SVG + "line[@data-layer='wires']")
    # Explicitly never infer full electrical connectivity from SVG line count.
    return sha(path), {
        "manufacturer_leads": len(leads),
        "editor_marks": len(targets),
        "non_electrical_b_strokes": len(b),
        "drawn_wires": len(ink_wires),
        "sha256": sha(path),
    }


def audit(
    manifest_path: Path,
    witness_path: Path,
    witness_sha: str,
    font_path: Path,
    *,
    png_clean: Path | None = None,
    png_diagnostic: Path | None = None,
    eskd_report: Path | None = None,
    eskd_sha: str | None = None,
) -> dict:
    demand(sha(witness_path) == witness_sha,
           "QA_C16_IMMUTABLE_SOURCE_WITNESS_SHA_MISMATCH")
    demand(sha(font_path) == FONT_SHA, "QA_C16_REAL_TYPE_A_FONT_SHA_MISMATCH")
    source = load(witness_path)
    manifest = load(manifest_path)
    demand(source.get("immutable_original_commit") == ORIGINAL and
           source.get("frozen_source_components") == 23 and
           source.get("frozen_source_Net_count") == 15 and
           source.get("frozen_source_physical_memberships") == 62 and
           source.get("manufacturer_DA1_physical_pin_count") == 16,
           "QA_C16_SOURCE_WITNESS_NOT_AUTHENTIC_FROZEN_E695")
    original = source.get("true_original_nets")
    demand(type(original) is dict and set(original) == NAMES and
           all(type(v) is list and v and
               all(type(pin) is str for pin in v) for v in original.values()) and
           sum(len(v) for v in original.values()) == 62 and
           sum(p.startswith("DA1.") for v in original.values() for p in v) == 16,
           "QA_C16_ORIGINAL_15_NAMES_62_PINREFS_BAD")
    every_pin = [p for v in original.values() for p in v]
    demand(len(every_pin) == len(set(every_pin)),
           "QA_C16_SOURCE_PINREF_MULTIPLE_NETS")
    demand(source.get("source_b_nonphysical_Net") == "b_NEGATIVE_OUTPUT" and
           source.get("b_marker_continuations_are_NOT_new_physical_Nets") is True,
           "QA_C16_B_SOURCE_IS_NOT_NON_ELECTRICAL")
    b_stubs = source.get("source_b_stubs_um")
    demand(isinstance(b_stubs, dict) and set(b_stubs) == {"X2.1", "R5.2"} and
           all(type(row) is dict and
               set(row) >= {"start", "end"} and
               len(row["start"]) == len(row["end"]) == 2
               for row in b_stubs.values()),
           "QA_C16_TWO_TRUE_B_SOURCE_STUBS_MISSING")
    demand(manifest.get("schema") ==
           "GOST_TL494_CYCLE15_ONE_COMMAND_SOURCE_LOCKED_DELIVERY_V1" and
           manifest.get("source_sha") == ORIGINAL and
           manifest.get("source_font_sha256") == FONT_SHA and
           manifest.get("source_23_components") == 23 and
           manifest.get("source_16_signed_DA1") == 16 and
           manifest.get("required_original_nets") == 15,
           "QA_C16_OWNER_C15_SOURCE_OR_FONT_WRONG")
    demand(set(manifest.get("source_15_literal_names", ())) == NAMES and
           manifest.get("source_62_physical_pinrefs") == original,
           "QA_C16_OWNER_NET_NAMES_OR_62_MEMBERSHIPS_SPOOFED")
    progress = manifest.get("original_named_net_route_progress")
    demand(isinstance(progress, dict) and set(progress) == NAMES,
           "QA_C16_ROUTER_OMITTED_NAMED_SOURCE_TREE")
    completed = 0
    for net, item in progress.items():
        demand(type(item) is dict and type(item.get("complete")) is bool and
               item.get("source_pinrefs") == original[net] and
               isinstance(item.get("connected_pinrefs"), list),
               "QA_C16_NET_TREE_MISSING_REAL_PINREF_PROOF")
        connected = item["connected_pinrefs"]
        demand(len(connected) == len(set(connected)) and
               set(connected) <= set(original[net]),
               "QA_C16_CONNECTED_FOREIGN_PINREF")
        if item["complete"]:
            completed += 1
            demand(set(connected) == set(original[net]),
                   "QA_C16_FAKE_COMPLETE_NET_TREE_HAS_MISSING_PINREFS")
    demand(completed == manifest.get("completed_original_nets"),
           "QA_C16_ROUTE_HEADER_15_FOR_PARTIAL_GRAPH")

    files = manifest.get("artifacts")
    demand(isinstance(files, dict), "QA_C16_OWNER_FILES_NOT_SIGNED")
    root = manifest_path.resolve().parent
    report_artifacts = {}
    for filename, record in files.items():
        demand(type(filename) is str and "/" not in filename and
               "\\" not in filename and filename not in (".", "..") and
               type(record) is dict and type(record.get("sha256")) is str,
               "QA_C16_ARTIFACT_TRAVERSAL_OR_SHA_ABSENT")
        path = root / (("native/" if filename.endswith("-route-drc.json")
                       else "") + filename)
        demand(path.is_file() and sha(path) == record["sha256"],
               "QA_C16_OWNER_ARTIFACT_HASH_INVALID:" + filename)
        report_artifacts[filename] = record["sha256"]
    fmt = manifest.get("route_config", {}).get("format")
    demand(fmt in ("A3", "A2"), "QA_C16_UNKNOWN_NATIVE_SHEET")
    views = {}
    for mode in ("clean", "diagnostic"):
        name = f"TL494-{fmt}-{mode}-source-b.svg"
        demand(name in files, "QA_C16_REAL_SOURCE_SVG_NOT_IN_ARTIFACTS")
        _, views[mode] = inspect_svg(
            root / name, mode, original, b_stubs,
            completed, allow_partial=completed != 15,
        )
        demand(views[mode]["drawn_wires"] ==
               manifest.get("routed_native_segments"),
               "QA_C16_ROUTE_WIRE_COUNT_NOT_NATIVE_GRAPH")

    outcome = {
        "schema": "QA_CYCLE16_SOURCE_RELEASE_GATE_V1",
        "immutable_source": ORIGINAL,
        "source_witness_sha256": witness_sha,
        "manifest_sha256": sha(manifest_path),
        "producer_sha": manifest.get("owner_exact_shas"),
        "font_sha256": FONT_SHA,
        "source_components": 23,
        "source_nets": 15,
        "original_pinrefs": 62,
        "real_da1_pins": 16,
        "completed_source_nets": completed,
        "drawn_segments": manifest.get("routed_native_segments"),
        "native_partial_drc_errors": manifest.get("routed_native_drc_errors"),
        "signed_owner_artifacts": report_artifacts,
        "actual_svg_views": views,
        "print_approval": "NO_GO",
    }
    if completed != 15:
        raise ReleaseBlocked(
            "QA_C16_NO_GO_INCOMPLETE_" + str(completed) + "_OF_15"
        )
    demand(manifest.get("routed_native_drc_errors") == 0 and
           manifest.get("native_paper_frame_errors") == [],
           "QA_C16_FULL_GRAPH_PHYSICAL_DRC_OR_FRAME_FAILURE")
    demand(png_clean is not None and png_diagnostic is not None,
           "QA_C16_REAL_PNG300_MISSING")
    from PIL import Image
    for png in (png_clean, png_diagnostic):
        demand(png.is_file(), "QA_C16_PNG_NOT_PRESENT")
        with Image.open(png) as image:
            expected = ((4961, 3508) if fmt == "A3" else (7016, 4961))
            dpi = image.info.get("dpi")
            demand(image.size == expected and dpi is not None and
                   all(abs(n - 300) < 1 for n in dpi),
                   "QA_C16_WRONG_REAL_300DPI_PAGE")
        outcome.setdefault("validated_300dpi_png_sha256", []).append(sha(png))
    demand(eskd_report is not None and eskd_sha is not None and
           sha(eskd_report) == eskd_sha,
           "QA_C16_MISSING_PINNED_INDEPENDENT_ESKD_PROOF")
    proof = load(eskd_report)
    demand(proof.get("original_source_sha") == ORIGINAL and
           proof.get("clean_svg_sha256") == views["clean"]["sha256"] and
           proof.get("diagnostic_svg_sha256") == views["diagnostic"]["sha256"] and
           proof.get("full_post_render_3_2_1mm_error_count") == 0 and
           proof.get("all_real_text_and_UGO_ink_checked") is True and
           proof.get("all_15_original_source_trees_approved") is True,
           "QA_C16_ESKD_FULL_SHEET_GLOBAL_GATE_NOT_ATTESTED")
    outcome["print_approval"] = "PASS_QA_SOURCE_AND_INDEPENDENT_ESKD"
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-witness", type=Path, required=True)
    parser.add_argument("--source-witness-sha256", required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--png-clean", type=Path)
    parser.add_argument("--png-diagnostic", type=Path)
    parser.add_argument("--eskd-report", type=Path)
    parser.add_argument("--eskd-report-sha256")
    parser.add_argument("--expect-blocked", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(
            args.manifest, args.source_witness,
            args.source_witness_sha256, args.font_file,
            png_clean=args.png_clean, png_diagnostic=args.png_diagnostic,
            eskd_report=args.eskd_report, eskd_sha=args.eskd_report_sha256,
        )
    except ReleaseBlocked as exc:
        if not args.expect_blocked:
            raise SystemExit(str(exc)) from None
        report = {
            "schema": "QA_CYCLE16_SOURCE_RELEASE_GATE_V1",
            "status": "EXPECTED_BLOCKED_NOT_PRINT_RELEASE",
            "reason": str(exc),
            "manifest_sha256": sha(args.manifest),
        }
    except (ReleaseIntegrityError, OSError, ValueError) as exc:
        raise SystemExit("QA_C16_INTEGRITY_FAIL:" + str(exc)) from None
    else:
        if args.expect_blocked:
            raise SystemExit("QA_C16_EXPECT_BLOCKED_BUT_ALREADY_FULLY_APPROVED")
        report["status"] = "FULL_RELEASE_APPROVED_BY_PINNED_PROOFS"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
