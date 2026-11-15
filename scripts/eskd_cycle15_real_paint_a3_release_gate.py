"""Independent ESKD C15 gate for ACTUAL PAINT A3 artifact: no synthetic artwork.

Consumes real clean/diagnostic SVG and PNG300 plus actual BOM, Netlist and
owner router DRC. Source-pinned strict 23/15/62/16, signed b physical local
strokes, Type A and 3/2/1mm scoped printed ink. Incomplete graphs cannot PASS.
CLI exits 0 for a demonstrably BLOCKED source only with --expect-blocked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import ContinuationStub
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from scripts.eskd_cycle12_routed_source_gate import (
    _conservative_ugo_envelope,
    all_parallel_ink_3mm_scope,
    source_ugo_parallel_1mm_scope,
)
from scripts.eskd_cycle13_signed_b_print_gate import (
    FROZEN_SOURCE_NETS,
    FONT_SHA,
    audit_source_b_printed_lines,
)

NS = "{http://www.w3.org/2000/svg}"
ROOT = "TL494_COMPACT_A3_NEW_ROUTE_BLOCKED"
FROZEN = "e695c415fdced164b0e0c39c5249d030795a0aa6"


class NativeReleaseError(ValueError):
    """A claimed input is not an authentic or independently checkable owner file."""


def check(value: bool, code: str) -> None:
    if not value:
        raise NativeReleaseError(code)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(folder: Path, manifest: dict) -> Circuit:
    netlist = _json(folder / "TL494_COMPACT_A3_SOURCE_NETLIST_DRAFT.json")
    bom = _json(folder / "TL494_COMPACT_A3_SOURCE_BOM_DRAFT.json")
    check(netlist.get("source_sha") == bom.get("source_sha") == FROZEN,
          "FROZEN_SOURCE_E695_REQUIRED")
    check(netlist.get("print_approved") is False
          and bom.get("print_approved") is False,
          "DRAFT_SOURCE_EXPORT_IMPERSONATES_APPROVED")
    check(len(bom["components"]) == 23 and len(netlist["nets"]) == 15,
          "ORIGINAL_COMPONENTS_23_NETS_15_REQUIRED")
    refs = [item["reference"] for item in bom["components"]]
    check(len(set(refs)) == 23, "SOURCE_COMPONENT_DUPLICATES")
    members = {
        item["name"]: tuple(sorted(
            f"{p['reference']}.{p['number']}" for p in item["pinrefs"]
        )) for item in netlist["nets"]
    }
    check(len(members) == len(netlist["nets"]) == 15 and
          members == {key: tuple(sorted(value))
                      for key, value in FROZEN_SOURCE_NETS.items()},
          "FROZEN_15_EXACT_NET_MEMBER_SETS_REQUIRED")
    all_pins = [p for pins in members.values() for p in pins]
    check(len(all_pins) == len(set(all_pins)) == 62, "FROZEN_62_UNIQUE_PINREF")
    check(set(refs) == {p.partition(".")[0] for p in all_pins},
          "FROZEN_23_COMPONENT_REFERENCE_IDENTITY")
    check({p.partition(".")[2] for p in all_pins if p.startswith("DA1.")} ==
          {str(n) for n in range(1, 17)}, "TI_DA1_ALL_16_PHYSICAL_PINS_REQUIRED")
    check("COMMON" in members and "PE" not in members and "CHASSIS" not in members,
          "COMMON_NOT_PROTECTIVE_PE")
    circuit = Circuit(
        tuple(ComponentInstance(e["reference"], e["part_id"])
              for e in bom["components"]),
        tuple(Net(name, tuple(PinRef(*p.split(".", 1)) for p in pins))
              for name, pins in members.items()),
    )
    check(manifest.get("model_source") == FROZEN and
          manifest.get("source_components") == 23 and
          manifest.get("source_nets") == 15 and
          manifest.get("source_net_pinrefs") == 62 and
          manifest.get("manufacturer_DA1_physical_pin_count") == 16,
          "ROUTER_OWNER_SOURCE_PHYSICAL_CONTRACT_DRIFT")
    return circuit


def _real_stubs(manifest: dict) -> tuple[ContinuationStub, ...]:
    records = manifest.get("source_b_stubs_um")
    check(isinstance(records, dict) and set(records) == {"b-X2", "b-R5"},
          "OWNER_TWO_SOURCE_B_STUBS_REQUIRED")
    stubs = []
    for endpoint, item in sorted(records.items()):
        check(item.get("nonphysical") is True, "SOURCE_B_MUST_BE_NONPHYSICAL")
        stubs.append(ContinuationStub(
            item["source_stub_id"], endpoint,
            PinRef(*item["source_pin_ref"].split(".", 1)),
            Point(*item["start"]), Point(*item["end"]),
        ))
    return tuple(stubs)


def _wire_lines(root: ET.Element) -> list[dict]:
    result = []
    for line in root.findall(f".//{NS}line[@data-layer='wires']"):
        try:
            coords = tuple(round(float(line[k]) * 1000)
                           for k in ("x1", "y1", "x2", "y2"))
            stroke = round(float(line["stroke-width"]) * 1000)
            index = int(line["data-wire-index"])
        except (ValueError, KeyError, TypeError) as exc:
            raise NativeReleaseError("UNMEASURED_WIRE_NATIVE_SVG") from exc
        check(stroke == 300 and
              ((coords[0] == coords[2]) != (coords[1] == coords[3])),
              "ALL_PRINTED_WIRES_MUST_BE_ORTHOGONAL_0P3MM")
        result.append({
            "coords": coords, "stroke": stroke,
            "index": index, "net": line["data-net"],
        })
    check(len({x["index"] for x in result}) == len(result),
          "DUPLICATE_PRINT_WIRE_INDEX")
    return result


def _layout_measure(root: ET.Element) -> dict:
    groups = root.findall(f".//{NS}g[@data-layer='symbols']")
    symbol_refs = [g.get("data-reference") for g in groups]
    check(len(groups) == len(set(symbol_refs)) == 23
          and "DA1" in symbol_refs,
          "REAL_PAINT_23_PHYSICAL_SYMBOLS_REQUIRED")
    boxes = {
        g.get("data-reference"): _conservative_ugo_envelope(g)
        for g in groups
    }
    gaps = []
    for left, right in combinations(sorted(boxes), 2):
        a, b = boxes[left], boxes[right]
        dx = max(0, a[0] - b[2], b[0] - a[2])
        dy = max(0, a[1] - b[3], b[1] - a[3])
        gaps.append((round(math.hypot(dx, dy)), left, right))
    assert len(gaps) == 253
    internal_root = ET.Element(f"{NS}svg")
    for g in groups:
        if g.get("data-reference") != "DA1":
            internal_root.append(g)
    internal = source_ugo_parallel_1mm_scope(internal_root)
    return {
        "distinct_UGO_count": 23,
        "separate_UGO_checked_pairs": 253,
        "min_separate_UGO_ink_um": min(gaps)[0],
        "min_separate_UGO_pair": list(min(gaps)[1:]),
        "distinct_UGO_below_2mm": [
            {"pair": [a, b], "gap_um": d}
            for d, a, b in gaps if d < 2000
        ],
        "intra_UGO_subset": internal,
        "unverified_UGO_connected_arc_and_text_pairs":
            "BLOCKED_NOT_GLOBAL_1MM_OR_ANNOTATION_INK",
    }


def audit(folder: Path, *, artifact_run: int, paint_sha: str,
          expected_clean_sha: str) -> dict:
    folder = folder.resolve()
    cf = folder / f"{ROOT}_clean.svg"
    df = folder / f"{ROOT}_diagnostic.svg"
    manifest_file = folder / "TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json"
    manifest = _json(manifest_file)
    check(_sha(cf) == expected_clean_sha,
          "ACTUAL_PAINT_OWNER_CLEAN_SVG_SHA_MISMATCH")
    check(len(paint_sha) == 40 and all(c in "0123456789abcdef" for c in paint_sha),
          "ACTUAL_PAINT_HEAD_SHA_REQUIRED")
    circuit = _source(folder, manifest)
    stubs = _real_stubs(manifest)
    actual = {}
    wires = None
    for variant, path in (("clean", cf), ("diagnostic", df)):
        root = ET.parse(path).getroot()
        check(root.get("width") == "420mm" and
              root.get("height") == "297mm" and
              root.get("viewBox") == "0 0 420 297",
              "NOT_REAL_A3_420_X_297_1_TO_1")
        check(root.get("data-release") == "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
              and root.get("data-e3-normative-approval") == "DRAFT_NOT_APPROVED",
              "PARTIAL_SVG_FAKES_FULL_RELEASE")
        check(root.get("data-source-components") == "23" and
              root.get("data-source-nets") == "15",
              "SVG_FROZEN_SOURCE_COUNTS_MISSING")
        symbols = root.findall(f".//{NS}g[@data-layer='symbols']")
        pin_leads = root.findall(f".//{NS}line[@data-real-anchor='true']")
        check(len(pin_leads) == 16 and
              {e.get("data-pin-number") for e in pin_leads}
              == {str(x) for x in range(1, 17)},
              "TRUE_DA1_16_PIN_SVG_NOT_PRESENT")
        check(any(g.get("data-composed-engine") == "physical-ic-renderer"
                  for g in symbols if g.get("data-reference") == "DA1"),
              "REAL_DA1_UGO_NOT_NATIVE")
        annotations = root.findall(f".//{NS}text[@data-layer='annotations']")
        ic_texts = root.findall(f".//{NS}text[@data-layer='ic-text']")
        check(len(annotations) == 39 and len(ic_texts) == 34 and
              all(t.get("font-family") == "OpenGOST type A"
                  and t.get("data-font-sha256") == FONT_SHA for t in annotations)
              and all(t.get("font-family") == "OpenGOST type A"
                      and t.get("data-ink-um") for t in ic_texts),
              "SOURCE_TYPE_A_AUTHENTIC_TEXT_NOT_39_PLUS_34")
        b = audit_source_b_printed_lines(root, circuit, stubs)
        current_wires = _wire_lines(root)
        if wires is None:
            wires = current_wires
        else:
            check(wires == current_wires,
                  "CLEAN_DIAGNOSTIC_ACTUAL_ELECTRICAL_WIRES_DIFFER")
        png = folder / f"{ROOT}_{variant}-300dpi.png"
        with Image.open(png) as image:
            check(image.format == "PNG" and
                  (image.width, image.height) == (4961, 3508),
                  "ACTUAL_A3_PNG300_DIMENSIONS_MISMATCH")
            pixel_size = [image.width, image.height]
        actual[variant] = {
            "svg_sha256": _sha(path), "png_sha256": _sha(png),
            "pixel_size": pixel_size, "source_b": b,
        }
    check(len(wires) == manifest["route_segments"],
          "ROUTE_MANIFEST_AND_PRINTED_WIRE_COUNT_DIFFER")
    ink3 = all_parallel_ink_3mm_scope(wires)
    ink2_1 = _layout_measure(ET.parse(cf).getroot())
    route = manifest["router_attempt"]
    check(route["routed_net_count"] < 15 and route["complete"] is False,
          "PINNED_PARTIAL_OWNER_MASQUERADES_AS_COMPLETE")
    check(route["source_net_count"] == 15 and route["source_pin_count"] == 62,
          "ROUTE_MODEL_SOURCE_15_62_CHANGED")
    check(manifest["owner_preview_print_pass"] is False and
          manifest["real_print_release"] is False and
          manifest["gost_approved"] is False,
          "DRAFT_OWNER_IMPERSONATES_FULL_PRINT_APPROVAL")
    return {
        "schema": "ESKD_CYCLE15_REAL_CURRENT_PAINT_SIGNED_A3_GATE_V1",
        "artifact_provenance": {
            "github_actions_run": artifact_run, "paint_head_sha": paint_sha,
            "owner_ic_sha": manifest.get("IC97_owner_sha"),
            "owner_net_sha": manifest.get("NET114_owner_sha"),
            "owner_recon_sha": manifest.get("RECON115_owner_sha"),
            "manifest_sha256": _sha(manifest_file),
            "original_frozen_sha": FROZEN,
        },
        "real_files": actual,
        "original_physical_inventory": {"components": 23, "nets": 15,
                                        "pinrefs": 62, "DA1_pins": 16},
        "actual_new_route": {
            "routed_nets": route["routed_net_count"],
            "required_nets": 15, "real_printed_segment_count": len(wires),
            "junction_count": manifest["authored_junctions"],
            "electrical_errors": manifest.get("electrical_errors"),
            "owner_blockers": manifest.get("blockers"),
        },
        "scope_3mm_parallel_wires": ink3,
        "scope_2mm_distinct_and_1mm_internal_UGO": ink2_1,
        "source_C1_type_a_catalog_text_frame":
            "BLOCKED_SOURCE_SVG_ANNOTATIONS_LACK_MEASURED_INK_BBOX",
        "paper_A3_420x297_svg": "PASS_REAL_FULL_PAGE_CROP_NOT_USED",
        "project_10mm_C1_label":
            "BLOCKED_OWNER_RECON_MEASURED_C1_TOP_900UM_OUTSIDE",
        "full_source_photo_parity": "BLOCKED_AUTHORITATIVE_BITMAP_UNAVAILABLE",
        "full_post_render_3_2_1mm_global_DRC":
            "BLOCKED_ROUTE_INCOMPLETE_AND_UNMEASURED_ANNOTATION_INK",
        "normative_catalog_UGO_approved_count": 0,
        "release_verdict": "NO_GO_INCOMPLETE_ROUTE_NOT_NORMATIVE_PRINT",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--artifact-run", type=int, required=True)
    parser.add_argument("--paint-sha", required=True)
    parser.add_argument("--clean-sha", required=True)
    parser.add_argument("--expect-blocked", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(args.folder, artifact_run=args.artifact_run,
                       paint_sha=args.paint_sha,
                       expected_clean_sha=args.clean_sha)
    except (NativeReleaseError, ValueError, KeyError, OSError, ET.ParseError) as exc:
        raise SystemExit(f"ESKD_REAL_ARTIFACT_INTEGRITY_FAILURE:{exc}") from exc
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "release_verdict": report["release_verdict"],
        "routed_nets": report["actual_new_route"]["routed_nets"],
        "real_artifact_sha256": report["real_files"]["clean"]["svg_sha256"],
    }))
    if not args.expect_blocked:
        raise SystemExit(2)
    if report["release_verdict"] != "NO_GO_INCOMPLETE_ROUTE_NOT_NORMATIVE_PRINT":
        raise SystemExit("ESKD_EXPECTED_BLOCKED_ASSERTION_NOT_TRUE")


if __name__ == "__main__":
    main()
