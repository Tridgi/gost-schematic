"""Independent ESKD Cycle12 print-source gate for real owner NEW-route files.

This reads a pinned owner-produced Circuit/ExternalWireGraph manifest and actual
SVG/PNG, not hand-redrawn artwork. A partial graph is NEVER a printable PASS.
1/2-mm whole-sheet glyph distances and user-photo parity remain unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

FROZEN = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
SVG = "{http://www.w3.org/2000/svg}"
BASENAME = "TL494-compact-A3"
SOURCE_NETS = {
    "a_INPUT_PLUS", "SWITCH", "TRANSFER", "OUT_BEFORE_FUSE",
    "b_NEGATIVE_OUTPUT", "GATE_DRIVE", "CONTROL_REFERENCE",
    "SOFT_START", "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK",
    "ADJUSTED_DIVIDER", "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
}
SOURCE_ALIASES = {
    "INPUT_POS": "a_INPUT_PLUS",
    "ENERGY_TRANSFER": "TRANSFER",
    "OUTPUT_NEG": "b_NEGATIVE_OUTPUT",
}
SOURCE_UGO = {
    "VD1": "diode.schottky", "VT1": "transistor.mosfet_n_enh",
    "C1": "capacitor.polarized", "C2": "capacitor.polarized",
    "C3": "capacitor.polarized", "C4": "capacitor.fixed",
    "C5": "capacitor.polarized", "C6": "capacitor.polarized",
    "C7": "capacitor.fixed", "L1": "inductor.ferromagnetic",
    "L2": "inductor.ferromagnetic", "R5": "resistor.variable",
    "FU1": "fuse.general",
}
FAILED_SOURCE_NETS = {
    "GATE_DRIVE", "CONTROL_REFERENCE", "FEEDBACK", "OSCILLATOR_RT",
    "COMMON",
}


class EvidenceError(ValueError):
    """Counterfeit or inconsistent evidence, never a source-rule waiver."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _read_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError("REAL_OWNER_MANIFEST_MISSING_OR_INVALID") from exc
    require(isinstance(obj, dict), "MANIFEST_NOT_OBJECT")
    return obj


def _svg(path: Path) -> ET.Element:
    try:
        return ET.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ET.ParseError) as exc:
        raise EvidenceError("REAL_OWNER_SVG_MISSING_OR_INVALID") from exc


def _dimension_mm(root: ET.Element) -> tuple[float, float, float, float]:
    try:
        wh = [float(root.get(n, "").removesuffix("mm")) for n in ("width", "height")]
        view = [float(x) for x in root.get("viewBox", "").split()]
    except ValueError as exc:
        raise EvidenceError("REAL_PHYSICAL_SVG_MM_INVALID") from exc
    require(all(root.get(n, "").endswith("mm") for n in ("width", "height"))
            and len(view) == 4 and all(math.isfinite(v) for v in (*wh, *view))
            and all(v > 0 for v in wh), "REAL_PHYSICAL_SVG_MM_INVALID")
    require(abs(wh[0] - view[2]) < 0.005 and abs(wh[1] - view[3]) < 0.005,
            "REAL_PHYSICAL_MM_VIEWBOX_SCALE_CHANGED")
    return tuple(view)


def _source_model(manifest: dict) -> dict:
    require(manifest.get("source_sha") == FROZEN, "FROZEN_SOURCE_SHA_CHANGED")
    require(
        (manifest.get("source_components"), manifest.get("source_nets"),
         manifest.get("all_Circuit_PinRef_memberships"),
         manifest.get("physical_DA1_pin_count")) == (23, 15, 62, 16),
        "REAL_SOURCE_23_15_62_16_CONTRACT_FAILED",
    )
    require(manifest.get("font_sha256") == FONT_SHA, "TRUE_TYPE_A_FONT_SHA_MISSING")
    rows = manifest.get("net_members")
    require(isinstance(rows, dict) and len(rows) == 15,
            "REAL_SOURCE_NETS_NOT_15_UNIQUE")
    names = set(rows)
    assert len(SOURCE_NETS) == 15
    canonical = {SOURCE_ALIASES.get(n, n) for n in names}
    require(canonical == SOURCE_NETS, "SOURCE_NET_NAMES_NOT_REVERSIBLY_MAPPABLE")
    require("COMMON" in names and not names.intersection({"PE", "CHASSIS", "EARTH"}),
            "COMMON_0V_FAKED_AS_PROTECTIVE_EARTH")
    refs = [p for pins in rows.values() for p in pins]
    require(len(refs) == len(set(refs)) == 62, "SOURCE_62_PINREFS_NOT_UNIQUE")
    refs_da = {p.split(".", 1)[1] for p in refs if p.startswith("DA1.")}
    require(refs_da == {str(i) for i in range(1, 17)},
            "REAL_DA1_ALL_16_PHYSICAL_PINS_REQUIRED")
    require(manifest.get("source_net_diff") ==
            {"added": [], "removed": [], "physical_members_changed": []},
            "OWNER_ROUTER_SOURCE_NET_DIFF_NOT_ZERO")
    return {
        "source_named_nets": sorted(canonical),
        "observed_owner_named_nets": sorted(names),
        "alias_pairs": dict(SOURCE_ALIASES),
        "source_name_parity": (
            "PASS_EXACT" if names == SOURCE_NETS
            else "BLOCKED_REVERSIBLE_ALIAS_MUST_BE_SIGNED_AT_EXPORT"
        ),
        "physical_pinrefs": len(refs),
        "da1_pin_numbers": sorted(refs_da, key=int),
    }


def _route(manifest: dict) -> dict:
    router = manifest.get("routing", {})
    trees = router.get("net_trees", [])
    require(len(trees) == 15, "REAL_ROUTER_NOT_ALL_15_NET_TREES_REPORTED")
    require(manifest.get("routed_nets") == sum(t.get("complete") is True for t in trees),
            "ROUTED_15_COUNT_INCONSISTENT_WITH_TREES")
    require(router.get("routed_net_count") == manifest["routed_nets"],
            "ROUTER_ROUTE_COUNT_MISMATCH")
    require(router.get("source_pin_count") == 62
            and router.get("source_net_count") == 15,
            "ROUTER_SOURCE_SIGNATURE_MISMATCH")
    require(manifest.get("routed_segments") == router.get("graph_segments"),
            "ROUTER_SEGMENTS_DISAGREE")
    require(manifest.get("routed_nets") < 15 and not router.get("complete")
            and not router.get("print_pass") and router.get("blocked_release")
            and not manifest.get("print_pass"),
            "PARTIAL_ROUTE_FALSE_PRINT_ACCEPTANCE")
    require(manifest.get("status") == "BLOCKED_PARTIAL_NOT_PRINTABLE",
            "PARTIAL_ROUTE_WRONG_SOURCE_STATUS")
    require(manifest.get("new_after_drc", {}).get("wire_count")
            == manifest.get("routed_segments"), "DRC_GRAPH_SEGMENTS_MISMATCH")
    require(manifest.get("actual_new_drc_errors") == [],
            "ACTUAL_NEW_ROUTE_DRC_ERRORS_NOT_SILENTLY_IGNORED")
    require(manifest.get("after_erc_errors") != [],
            "PARTIAL_ROUTE_FALSE_COMPLETE_ERC")
    require(manifest.get("source_components") == 23
            and manifest.get("known_bad_original_source", {}).get("drc_errors") == 9
            and manifest["known_bad_original_source"].get("drc_warnings") == 32
            and manifest["known_bad_original_source"].get("wire_segments") == 91,
            "FROZEN_NEGATIVE_CONTROL_MISSING")
    require(manifest.get("independent_QA_approved") is False
            and manifest.get("certified_UGO") is False,
            "UNPROVEN_QA_GOST_APPROVAL")
    require(manifest.get("real_source_UGO_draft_count") == 13,
            "SOURCE_13_UGO_DRAFT_COUNT_CHANGED")
    proofs = manifest.get("actual_source_UGO_authority", {})
    require(set(proofs) == set(SOURCE_UGO)
            and all(proofs[ref]["symbol_id"] == symbol
                    and proofs[ref]["status"].lower() == "draft"
                    for ref, symbol in SOURCE_UGO.items()),
            "SOURCE_UGO_OWNER_IDS_OR_DRAFT_CHANGED")
    # Machine-checkable distinction: the source b-X2 / b-R5 graphics cannot
    # be inferred from printed text, reconnected, or claimed on this A3.
    require(manifest.get("image_scope", "").startswith("Native Circuit+new"),
            "OWNER_IMAGE_SCOPE_MUST_BE_NATIVE_TYPED")
    return {
        "complete": manifest["routed_nets"],
        "required": 15,
        "segments_new": manifest["routed_segments"],
        "source_old_segments": 91,
        "failed_nets": sorted(
            name.split(":", 1)[0] for name in manifest.get("reason", [])
        ),
        "route_completeness": "BLOCKED_NOT_15_OF_15",
        "geometric_DRC_on_partial_graph_only":
            manifest["new_after_drc"]["error_count"],
        "source_b_relocated": "BLOCKED_NO_SIGNED_LOCATION",
        "source_UGO_figure_1to1": "BLOCKED_NO_INDEPENDENT_SCAN_OVERLAY",
    }


def _wires(root: ET.Element) -> list[dict]:
    rendered = root.findall(f".//{SVG}line[@data-layer='wires']")
    result = []
    for index, e in enumerate(rendered):
        require(e.get("data-wire-index") == str(index),
                "WIRE_INDEX_CHANGED_OR_DUPLICATED")
        try:
            x, y, xx, yy = (
                round(float(e.get(key, "")) * 1000)
                for key in ("x1", "y1", "x2", "y2")
            )
            w = round(float(e.get("stroke-width", "")) * 1000)
        except ValueError as exc:
            raise EvidenceError("OWNER_WIRE_GEOMETRY_UNREADABLE") from exc
        require((x == xx) != (y == yy), "ONLY_ORTHOGONAL_NONZERO_WIRES")
        require(200 <= w <= 1000, "GOST_WIRE_STROKE_OUTSIDE_0P2_TO_1MM")
        result.append({"net": e.get("data-net"), "index": index,
                       "coords": (x, y, xx, yy), "stroke": w})
    return result


def parallel_gaps(wires: list[dict]) -> dict:
    tested = 0
    violations = []
    for a, b in combinations(wires, 2):
        if a["net"] == b["net"]:
            continue
        x, y, xx, yy = a["coords"]
        u, v, uu, vv = b["coords"]
        horizontal = y == yy and v == vv and (
            min(max(x, xx), max(u, uu)) > max(min(x, xx), min(u, uu))
        )
        vertical = x == xx and u == uu and (
            min(max(y, yy), max(v, vv)) > max(min(y, yy), min(v, vv))
        )
        if not (horizontal or vertical):
            continue  # X/T crossings have no blanket 3mm rule.
        tested += 1
        edge = abs(y - v if horizontal else x - u) - (
            a["stroke"] + b["stroke"]
        ) / 2
        if edge < 3000:
            violations.append({"segments": [a["index"], b["index"]],
                               "edge_gap_um": edge,
                               "nets": [a["net"], b["net"]]})
    return {"distinct_net_parallel_projected_pairs": tested,
            "hard_3mm_edge_violations": violations,
            "rule": "PROJECTED_OVERLAP_PARALLEL_DIFFERENT_NET_ONLY"}


def _svg_page(root: ET.Element, *, diagnostic: bool,
              manifest: dict) -> tuple[dict, list[ET.Element]]:
    view = _dimension_mm(root)
    require(root.get("data-release") == "BLOCKED_PARTIAL",
            "PARTIAL_SVG_MASQUERADES_AS_RELEASE")
    require(root.get("data-physical-net-diff") == "ZERO",
            "SVG_NET_IDENTITY_DIFF_NOT_ZERO")
    groups = root.findall(f".//{SVG}g[@data-layer='symbols']")
    source_refs = {g.get("data-reference") for g in groups}
    require(len(groups) == 22 and len(source_refs) == 22
            and "DA1" not in source_refs,
            "EXPECTED_22_REAL_PASSIVES_PLUS_DA1_IN_SEPARATE_LAYER")
    ic = [g for g in root.findall(f".//{SVG}g") if g.get("data-owner") == "DA1"
          and g.get("data-ink-source") == "real-native-PAINT-original-16leads"]
    require(len(ic) == 1, "REAL_TL494_PAINT_COMPONENT_GLYPH_MISSING")
    pin_leads = ic[0].findall(f".//{SVG}line[@data-real-anchor='true']")
    require(len(pin_leads) == 16
            and {p.get("data-pin-number") for p in pin_leads} ==
            {str(i) for i in range(1, 17)},
            "DA1_TRUE_16_NATIVE_PHYSICAL_LEADS_MISSING")
    pwm = [n for n in ic[0].findall(f".//{SVG}text")
           if n.get("data-kind") == "function"
           and "".join(n.itertext()).strip() == "PWM"]
    require(len(pwm) == 1 and
            pwm[0].get("transform", "").startswith("matrix(0 -1 1 0 "),
            "PWM_NOT_BOTTOM_UP_NATIVE_TEXT")
    fonts = root.findall(f".//{SVG}text[@data-layer='annotations']")
    require(len(fonts) > 30 and all(
        f.get("data-font-sha256") == FONT_SHA
        and f.get("font-family") == "OpenGOST type A" for f in fonts),
        "SOURCE_TRUE_TYPE_A_GLYPH_FONT_NOT_PINNED")
    targets = [n for n in root.findall(f".//{SVG}rect")
               if n.get("data-pin-ref", "").startswith("DA1.")]
    require(len(targets) == (16 if diagnostic else 0),
            "CLEAN_DEBUG_TRUE_PINREF_SQUARES_WRONG")
    if diagnostic:
        require({n.get("data-pin-ref") for n in targets} ==
                {f"DA1.{i}" for i in range(1, 17)},
                "DEBUG_PHYSICAL_PINREF_NUMBERS_CHANGED")
        for n in targets:
            cx = (float(n.get("x")) + float(n.get("width")) / 2) * 1000
            cy = (float(n.get("y")) + float(n.get("height")) / 2) * 1000
            require(abs(cx - int(n.get("data-external-anchor-x-um"))) < 0.01
                    and abs(cy - int(n.get("data-external-anchor-y-um"))) < 0.01,
                    "DEBUG_SQUARE_NOT_AT_PHYSICAL_PIN_ANCHOR")
    wires = _wires(root)
    require(len(wires) == manifest["routed_segments"],
            "SVG_ACTUAL_NEW_GRAPH_WIRE_COUNT_MISMATCH")
    return {"physical_viewbox_mm": view,
            "22_catalog_plus_one_true_ic": 23,
            "source_real_ic_leads": 16,
            "new_graph_wires": len(wires),
            "type_a_annotated_text_count": len(fonts)}, targets


def _png(path: Path, view: tuple[float, float, float, float],
         targets: list[ET.Element], diagnostic: bool) -> None:
    require(path.is_file(), "REAL_300DPI_PNG_MISSING")
    with Image.open(path) as im:
        require(im.format == "PNG", "RASTER_NOT_PNG")
        expect_w = round(view[2] * 300 / 25.4)
        expect_h = round(view[3] * 300 / 25.4)
        require(abs(im.width - expect_w) <= 1
                and abs(im.height - expect_h) <= 1,
                "PNG_NOT_TRUE_PHYSICAL_300DPI")
        rgb = im.convert("RGB")
        if not diagnostic:
            r, g, b = rgb.split()
            require(ImageChops.difference(r, g).getbbox() is None
                    and ImageChops.difference(r, b).getbbox() is None,
                    "CLEAN_PNG_LEAKS_COLORED_EDITOR_OVERLAY")
        for n in targets:
            x = round((float(n.get("x")) +
                       float(n.get("width")) / 2 - view[0]) *
                      im.width / view[2])
            y = round((float(n.get("y")) +
                       float(n.get("height")) / 2 - view[1]) *
                      im.height / view[3])
            require(0 <= x < im.width and 0 <= y < im.height,
                    "PINREF_SQUARE_OUTSIDE_PHYSICAL_RASTER")
            r, g, b = rgb.getpixel((x, y))
            require(g > r + 35 and g > b + 20,
                    "PHYSICAL_PINREF_DEBUG_GREEN_OCCLUDED")


def audit(folder: Path) -> dict:
    manifest = _read_json(folder / f"{BASENAME}-route-drc.json")
    source = _source_model(manifest)
    route = _route(manifest)
    for key in FAILED_SOURCE_NETS:
        require(any(reason.startswith(f"{key}:") for reason in manifest["reason"]),
                "KNOWN_FAILED_NET_OMITTED_FROM_PREVIEW")
    require(set(route["failed_nets"]) == FAILED_SOURCE_NETS,
            "KNOWN_FAILED_NET_COUNT_NOT_FIVE")
    variants: dict[str, dict] = {}
    clean_wires = None
    for mode in ("clean", "diagnostic"):
        path = folder / f"{BASENAME}-{mode}.svg"
        root = _svg(path)
        details, targets = _svg_page(root, diagnostic=mode == "diagnostic",
                                     manifest=manifest)
        _png(folder / f"{BASENAME}-{mode}-300dpi.png",
             details["physical_viewbox_mm"], targets, mode == "diagnostic")
        details["sha256_svg"] = hashlib.sha256(path.read_bytes()).hexdigest()
        details["sha256_png"] = hashlib.sha256(
            (folder / f"{BASENAME}-{mode}-300dpi.png").read_bytes()
        ).hexdigest()
        variants[mode] = details
        wires = _wires(root)
        if clean_wires is not None:
            require(clean_wires == wires, "CLEAN_DEBUG_WIRE_GRAPH_CHANGED")
        else:
            clean_wires = wires
    gaps = parallel_gaps(clean_wires)
    require(not gaps["hard_3mm_edge_violations"],
            "ACTUAL_PARTIAL_ROUTE_3MM_DISTINCT_NET_PARALLEL_FAILED")
    return {
        "schema_version": 1, "source_frozen_sha": FROZEN,
        "owner_router_sha": manifest["owner_router_sha"],
        "reference_recon_sha": manifest["reference_recon_sha"],
        "source_inventory": source, "routed_graph": route,
        "printed_parallel_edge_3mm": gaps, "actual_real_svg_png": variants,
        "checks": {
            "new_partial_native_svg_300dpi": "PASS_DRAFT_PARTIAL_ONLY",
            "real_original_exact_named_net_export": source["source_name_parity"],
            "minimum_3mm_distinct_parallel_ink": "PASS_PARTIAL_ONLY",
            "two_mm_separate_UGO": "BLOCKED_NOT_FULL_PRIMITIVE_AUDIT",
            "one_mm_same_UGO_strokes": "BLOCKED_NOT_FULL_PRIMITIVE_AUDIT",
            "source_b_X2_R5_compact": "BLOCKED_NEEDS_SIGNED_REBIND",
            "source_photo_bitmap_overlay": "BLOCKED_NO_AUTHORITATIVE_IMAGE",
            "13_ugo_normative_approval": "BLOCKED_ALL_DRAFT",
            "overall_15_Net_print": "FAIL_ROUTE_INCOMPLETE",
            "false_zero_DRC_clearance": "REJECT_PARTIAL_GRAPH",
        },
        "release_verdict": "NO_GO_SOURCE_UNROUTED_AND_NOT_CERTIFIED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.folder)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False,
                                    sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["release_verdict"],
                      "routed": result["routed_graph"]["complete"],
                      "real_svg_png": len(result["actual_real_svg_png"]),
                      "3mm_bad": len(result["printed_parallel_edge_3mm"]
                                      ["hard_3mm_edge_violations"])}))


if __name__ == "__main__":
    main()
