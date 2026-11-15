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
import re
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
# Actual immutable artifact bytes from owner NET114 run 43654672504,
# independently compared between Python 3.12 and 3.13.
PINNED_ROUTER_SHA = "5c6feb90580ed846aa297c71d3c91afacfc3f0bc"
PINNED_RECON_SHA = "e56397300875ac155a316a9bfebe2601358a4147"
PINNED_OWNER_BLOBS = {
    "TL494-compact-A3-clean.svg":
        "1dee3658a93d2d437bdb4944d4779369890d8819ecb9e7b5f0b38d0fa8b9d0ac",
    "TL494-compact-A3-diagnostic.svg":
        "5e5c4b4879166c7f8dd2adbf54467240605750f7a37fd9262467bbff8f352baf",
    "TL494-compact-A3-clean-300dpi.png":
        "8d6a8dd0b2ec1fdbd39b01bed739cd124844078be28b4b06ac44d6651791ffcc",
    "TL494-compact-A3-diagnostic-300dpi.png":
        "0b6c0e0df825557887a5aa145e7bcaefd916a9f09e4e3546bc395a356173530f",
    "TL494-compact-A3-route-drc.json":
        "f13cf3e4a06c19a36abb4748268ce5cfe25d893474c3690aab7076ec620b1dd0",
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


def _verify_pinned_owner_bytes(folder: Path) -> None:
    """Reject edited evidence, byte drift, or mixing Python owner archives."""
    for name, digest in PINNED_OWNER_BLOBS.items():
        path = folder / name
        require(path.is_file(), "PINNED_OWNER_REAL_ARTIFACT_MISSING")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                "PINNED_OWNER_REAL_ARTIFACT_SHA256_MISMATCH")


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


def _source_model(manifest: dict, original: dict) -> dict:
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
    # Immutable original e695c415 ... file, verified with git hash-object in CI.
    # A global count + empty owner diff cannot detect a swapped physical pin.
    require(original.get("full_component_count") == 23
            and original.get("net_count") == 15
            and original.get("physical_pin_memberships") == 62
            and original.get("routed") is False
            and original.get("rendered_full_e3") is False,
            "ORIGINAL_FROZEN_TYPED_MODEL_INVALID")
    source_parts = {row["ref"] for row in original["elements"]}
    require(len(source_parts) == 23, "ORIGINAL_PART_REFERENCES_NOT_23")
    # Validate the physical PinRef inventory BEFORE comparing its owner Net
    # assignment. A missing/duplicated tip must fail with its specific
    # physical-inventory reason; a 62/62 preserving cross-Net swap still fails
    # the independent frozen per-Net comparison below.
    require(all(isinstance(pins, list) and all(isinstance(p, str)
                and p.count(".") == 1 and all(p.split("."))
                for p in pins) for pins in rows.values()),
            "SOURCE_PHYSICAL_PINREF_PAYLOAD_INVALID")
    refs = [p for pins in rows.values() for p in pins]
    require(len(refs) == len(set(refs)) == 62, "SOURCE_62_PINREFS_NOT_UNIQUE")
    refs_da = {p.split(".", 1)[1] for p in refs if p.startswith("DA1.")}
    require(refs_da == {str(i) for i in range(1, 17)},
            "REAL_DA1_ALL_16_PHYSICAL_PINS_REQUIRED")
    require(all(pin.split(".", 1)[0] in source_parts for pin in refs),
            "ORIGINAL_UNKNOWN_COMPONENT_PINREF")
    require("COMMON" in names and not names.intersection({"PE", "CHASSIS", "EARTH"}),
            "COMMON_0V_FAKED_AS_PROTECTIVE_EARTH")
    expected_nets = {
        name: sorted(pins) for name, pins in original["nets"].items()
    }
    actual_nets = {
        SOURCE_ALIASES.get(name, name): sorted(pins)
        for name, pins in rows.items()
    }
    require(actual_nets == expected_nets,
            "ORIGINAL_15_NET_PINREF_MEMBERSHIPS_DRIFT")
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
        "original_pinref_memberships_exact_after_alias": True,
        "physical_pinrefs": len(refs),
        "da1_pin_numbers": sorted(refs_da, key=int),
    }


def _source_ygo_current_review(profile: dict, owner_head: str) -> dict:
    """Exact read-only current YGO owner source selection, NOT GOST approval."""
    require(profile.get("reference_sha") == FROZEN,
            "YGO_CURRENT_SOURCE_REFERENCE_SHA_MISMATCH")
    require(profile.get("status") == "DRAFT", "YGO_CURRENT_UNPROVEN_APPROVAL")
    rows = profile.get("profiles")
    require(isinstance(rows, list) and len(rows) == 13,
            "YGO_CURRENT_NOT_13_SOURCE_UGO")
    indexed = {x.get("reference"): x for x in rows}
    require(len(indexed) == 13 and set(indexed) == set(SOURCE_UGO),
            "YGO_CURRENT_PROFILE_REF_INVENTORY_CHANGED")
    require(all(indexed[ref].get("symbol_id") == symbol
                for ref, symbol in SOURCE_UGO.items()),
            "YGO_CURRENT_SCHOTTKY_MOS_CAP_FERRO_ID_DRIFT")
    require(all(str(x.get("normative_verdict", "")).startswith("BLOCKED")
                for x in indexed.values()),
            "YGO_CURRENT_FIGURE_SIGNOFF_NOT_EVIDENCED")
    return {
        "actual_ygo_head_sha": owner_head,
        "sources_13": 13,
        "source_figure_verdict": "BLOCKED_NOT_CALIBRATED_1TO1",
        "formal_approved": 0,
        "exact_catalog_ids": dict(SOURCE_UGO),
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


def all_parallel_ink_3mm_scope(wires: list[dict]) -> dict:
    """3mm adjacent connection lines irrespective of electrical Net identity.

    Two noncoincident parallel printed wires may have the SAME named Net.
    ГОСТ 2.701-2008 §5.3.4 does not exempt these two strokes; the earlier
    distinct-Net audit alone is not a full 3mm assertion. Coincident ink is
    a duplicate-segment DRC problem, not spacing between two adjacent lines.
    """
    count_same = 0
    count_cross = 0
    observations: list[tuple[float, str, str, int, int]] = []
    for a, b in combinations(wires, 2):
        x, y, xx, yy = a["coords"]
        u, v, uu, vv = b["coords"]
        h = (y == yy and v == vv and
             min(max(x, xx), max(u, uu)) > max(min(x, xx), min(u, uu)))
        vert = (x == xx and u == uu and
                min(max(y, yy), max(v, vv)) > max(min(y, yy), min(v, vv)))
        if not (h or vert):
            continue
        center = abs(y - v if h else x - u)
        if center == 0:
            continue  # Not two distinct parallel ink strokes.
        gap = center - (a["stroke"] + b["stroke"]) / 2
        count_same += a["net"] == b["net"]
        count_cross += a["net"] != b["net"]
        observations.append((gap, a["net"], b["net"], a["index"], b["index"]))
    require(bool(observations), "NO_REAL_PARALLEL_CONNECTION_LINES_INSPECTED")
    return {
        "all_noncoincident_overlapping_projection_pairs": len(observations),
        "same_net_pairs": count_same,
        "different_net_pairs": count_cross,
        "minimum_printed_edge_gap_um": round(min(x[0] for x in observations)),
        "below_3mm": [
            {"nets": [n, m], "indices": [i, j], "gap_um": round(g)}
            for g, n, m, i, j in observations if g < 3000
        ],
        "verdict": (
            "PASS_SOURCE_PARTIAL_ALL_NONCOINCIDENT_PARALLEL_CONNECTIONS"
            if all(x[0] >= 3000 for x in observations)
            else "FAIL_ADJACENT_PARALLEL_PRINTED_3MM"
        ),
        "scope": "DISTINCT_INK_PARALLEL_HV_PROJECTION_OVERLAP_SAME_AND_CROSS_NET",
    }


def _conservative_ugo_envelope(group: ET.Element) -> tuple[int, int, int, int]:
    """Stroke-expanded conservative AABB (um), no pretend font/pixel parity.

    Lines and rectangles are exact for their bounding boxes. SVG arc bounding
    is DELIBERATELY enlarged by its radii, so a PASS certifies a lower bound
    even though the enclosed box can be bigger than real rendered ink.
    Unknown paths must fail rather than be silently skipped.
    """
    primitive_boxes: list[tuple[float, float, float, float]] = []

    def walk(element: ET.Element, stroke_width: str | None) -> None:
        stroke_width = element.get("stroke-width", stroke_width)
        kind = element.tag.removeprefix(SVG)
        require(kind in {"g", "line", "rect", "path", "circle", "text"},
                "UGO_UNRECOGNIZED_RENDERED_INK_PRIMITIVE")
        if kind == "text":
            # Real DA1 text is audited separately with data-ink-um.
            # Catalog UGO must never smuggle unsupported SVG text.
            require(group.get("data-owner") == "DA1",
                    "UGO_CATALOG_TEXT_INSTEAD_OF_NATIVE_ANNOTATION")
        if kind in {"line", "rect", "path", "circle"}:
            require(stroke_width is not None,
                    "UGO_PRIMITIVE_UNPINNED_STROKE_WIDTH")
            try:
                half = float(stroke_width) / 2
                require(math.isfinite(half) and 0.1 <= half <= 0.5,
                        "UGO_PRIMITIVE_STROKE_NOT_0P2_TO_1MM")
                if kind == "line":
                    x, y, xx, yy = (
                        float(element.get(key, ""))
                        for key in ("x1", "y1", "x2", "y2")
                    )
                    bound = (
                        min(x, xx) - half, min(y, yy) - half,
                        max(x, xx) + half, max(y, yy) + half,
                    )
                elif kind == "rect":
                    x, y, width, height = (
                        float(element.get(key, ""))
                        for key in ("x", "y", "width", "height")
                    )
                    require(width > 0 and height > 0,
                            "UGO_RECT_NONPOSITIVE_SIZE")
                    bound = (x-half, y-half, x+width+half, y+height+half)
                elif kind == "circle":
                    x, y, radius = (
                        float(element.get(key, ""))
                        for key in ("cx", "cy", "r")
                    )
                    require(radius > 0, "UGO_CIRCLE_NONPOSITIVE_RADIUS")
                    bound = (
                        x-radius-half, y-radius-half,
                        x+radius+half, y+radius+half,
                    )
                else:
                    path = element.get("d", "")
                    require(bool(re.fullmatch(
                        r"M\s+[-+\d.]+\s+[-+\d.]+\s+A\s+"
                        r"[-+\d.]+\s+[-+\d.]+\s+[-+\d.]+\s+"
                        r"[01]\s+[01]\s+[-+\d.]+\s+[-+\d.]+",
                        path,
                    )), "UGO_ARC_PATH_NOT_SIMPLE_SOURCE_ARC")
                    nums = [float(x) for x in re.findall(
                        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", path
                    )]
                    require(len(nums) == 9,
                            "UGO_ARC_NUMERIC_FORM_NOT_PINNED")
                    x, y, rx, ry, rotation, _, _, xx, yy = nums
                    require(rx > 0 and ry > 0,
                            "UGO_ARC_NONPOSITIVE_RADIUS")
                    # This proof models only the eight exact original L1/L2
                    # circular R2 no-rotation arcs. A rotated ellipse can
                    # exceed the rectangular rx/ry endpoint envelope;
                    # rejecting it is mandatory before claiming 2mm PASS.
                    require(rotation == 0 and rx == ry,
                            "UGO_ARC_NONCIRCULAR_NOT_CALIBRATED")
                    bound = (
                        min(x, xx)-rx-half, min(y, yy)-ry-half,
                        max(x, xx)+rx+half, max(y, yy)+ry+half,
                    )
                require(all(math.isfinite(v) for v in bound),
                        "UGO_PRIMITIVE_NONFINITE_GEOMETRY")
                primitive_boxes.append(bound)
            except (TypeError, ValueError, OverflowError) as exc:
                if isinstance(exc, EvidenceError):
                    raise
                raise EvidenceError("UGO_PRIMITIVE_MALFORMED_COORDINATES") from exc
        for child in element:
            walk(child, stroke_width)

    walk(group, None)
    require(primitive_boxes, "UGO_WITH_NO_REAL_STROKED_PRIMITIVE")
    # Floor min and ceil max are conservative at integer-um precision.
    return (
        math.floor(min(b[0] for b in primitive_boxes)*1000),
        math.floor(min(b[1] for b in primitive_boxes)*1000),
        math.ceil(max(b[2] for b in primitive_boxes)*1000),
        math.ceil(max(b[3] for b in primitive_boxes)*1000),
    )


def distinct_ugo_2mm_envelopes(root: ET.Element) -> dict:
    """Conservative ink envelope check for all 22 UGO and true DA1.

    A rectangle envelope may overestimate actual ink, so a <2mm envelope
    is INCONCLUSIVE, not automatic normative FAIL. >=2mm guarantees actual
    primitive ink separation for the modeled shapes, excluding text.
    """
    groups = {
        g.get("data-reference"): g
        for g in root.findall(f".//{SVG}g[@data-layer='symbols']")
    }
    require(len(groups) == 22 and None not in groups,
            "UGO_22_CATALOG_GLYPH_GROUPS_REQUIRED")
    ic = [g for g in root.iter(f"{SVG}g") if g.get("data-owner") == "DA1"
          and g.get("data-ink-source") == "real-native-PAINT-original-16leads"]
    require(len(ic) == 1 and "DA1" not in groups,
            "UGO_PHYSICAL_DA1_REQUIRED_SEPARATELY")
    groups["DA1"] = ic[0]
    ink = {name: _conservative_ugo_envelope(g) for name, g in groups.items()}
    candidates = []
    uncertain = []
    for left, right in combinations(sorted(ink), 2):
        a, b = ink[left], ink[right]
        dx = max(0, a[0]-b[2], b[0]-a[2])
        dy = max(0, a[1]-b[3], b[1]-a[3])
        distance_um = math.hypot(dx, dy)
        candidates.append((distance_um, left, right))
        if distance_um < 2000:
            uncertain.append({
                "reference_pair": [left, right],
                "conservative_lower_bound_um": round(distance_um),
            })
    require(len(candidates) == 253,
            "UGO_EXPECTED_ALL_23_DISTINCT_PAIRS_NOT_EVALUATED")
    return {
        "actual_distinct_symbol_count": 23,
        "all_distinct_symbol_pairs": len(candidates),
        "minimum_conservative_ink_gap_um": round(min(c[0] for c in candidates)),
        "minimum_pair": list(min(candidates)[1:]),
        "potentially_close_or_overlapping_envelopes": uncertain,
        "verdict": (
            "PASS_CONSERVATIVE_2MM_23_UGO_PARTIAL_SOURCE_PRINT"
            if not uncertain else "BLOCKED_CONSERVATIVE_AABB_NOT_EXACT_INK"
        ),
        "limitations": "UGO stroke primitives only; font ink, new full route "
                       "and formal GOST source figure signoff NOT certified",
    }


def source_ugo_parallel_1mm_scope(root: ET.Element) -> dict:
    """Only non-touching co-projected parallel straight strokes within one UGO.

    Do NOT apply 1mm to connected intentional graphical joints or label ink,
    and do NOT claim this excludes 1mm violations in non-parallel/arc pairs.
    """
    tested: list[tuple[float, str, int, int]] = []
    for group in root.findall(f".//{SVG}g[@data-layer='symbols']"):
        ref = group.get("data-reference")
        default = group.get("stroke-width")
        lines = []
        for index, primitive in enumerate(group.iter(f"{SVG}line")):
            try:
                x, y, xx, yy = (round(float(primitive.get(k, "")) * 1000)
                                for k in ("x1", "y1", "x2", "y2"))
                width = round(float(primitive.get("stroke-width", default))*1000)
            except (TypeError, ValueError, OverflowError) as exc:
                raise EvidenceError("UGO_PARALLEL_LINE_INVALID") from exc
            require(200 <= width <= 1000, "UGO_PARALLEL_LINE_STROKE_INVALID")
            if (x == xx) == (y == yy):
                # Non-orthogonal MOS/SCHOTTKY arrow strokes need a separate
                # geometry-specific audit, never certify them by this subset.
                continue
            lines.append((index, x, y, xx, yy, width))
        for a, b in combinations(lines, 2):
            i, x, y, xx, yy, w = a
            j, u, v, uu, vv, q = b
            horizontal = (y == yy and v == vv
                          and min(max(x, xx), max(u, uu))
                          > max(min(x, xx), min(u, uu)))
            vertical = (x == xx and u == uu
                        and min(max(y, yy), max(v, vv))
                        > max(min(y, yy), min(v, vv)))
            if not (horizontal or vertical):
                continue
            center_distance = abs(y-v) if horizontal else abs(x-u)
            if center_distance <= (w + q)/2:
                # Coincident/intersecting segments are deliberate single-line
                # joins or overlap; require true primitive graph audit later.
                continue
            tested.append((center_distance - (w + q)/2, ref, i, j))
    require(bool(tested), "UGO_1MM_REAL_PARALLEL_SAMPLE_MISSING")
    tightest = min(tested)
    return {
        "source_catalog_parallel_nonjoined_pairs": len(tested),
        "minimum_printed_edge_um": round(tightest[0]),
        "minimum_owner": tightest[1],
        "below_one_mm": [
            {"owner": ref, "line_indices": [i, j], "gap_um": round(gap)}
            for gap, ref, i, j in tested if gap < 1000
        ],
        "scope": "NONTOUCHING_PARALLEL_SAME_CATALOG_UGO_STROKES_ONLY",
        "verdict": (
            "PASS_1MM_RESTRICTED_PARALLEL_UGO_ONLY"
            if all(t[0] >= 1000 for t in tested)
            else "FAIL_1MM_RESTRICTED_PARALLEL_UGO"
        ),
    }


def type_a_physical_text_and_paper_scope(root: ET.Element) -> dict:
    """Validate 34 original PAINT IC measured ink boxes and true Type A.

    Reject fake calibrated family, fake 300DPI paper size or hidden invalid
    IC glyph geometry. 39 catalog annotation labels have no exact ink boxes
    in this owner SVG, so 1mm text/UGO clearance remains explicitly BLOCKED.
    """
    view = _dimension_mm(root)
    annotations = root.findall(f".//{SVG}text[@data-layer='annotations']")
    ic_text = root.findall(f".//{SVG}text[@data-layer='ic-text']")
    require(len(annotations) == 39 and len(ic_text) == 34,
            "OWNER_TYPE_A_EXPECTED_39_PLUS_34_TEXT_GLYPHS")
    require(all(text.get("font-family") == "OpenGOST type A"
                and text.get("font-size") == "5.48"
                and text.get("stroke") == "none"
                for text in (*annotations, *ic_text)),
            "TRUE_TYPE_A_FAMILY_AND_METRICS_INK_DRIFT")
    require(all(text.get("data-font-sha256") == FONT_SHA for text in annotations),
            "ANNOTATION_TYPE_A_AUTHENTIC_FONT_SHA_REQUIRED")
    require(all(text.get("data-ink-um") is None for text in annotations),
            "CATALOG_TEXT_INK_PROVENANCE_UNEXPECTED_DRIFT")
    boxes = []
    for t in ic_text:
        raw = t.get("data-ink-um", "")
        try:
            values = tuple(int(v) for v in raw.split(","))
        except ValueError as exc:
            raise EvidenceError("IC_NATIVE_TYPE_A_MEASURED_INK_MALFORMED") from exc
        require(len(values) == 4
                and values[2] > values[0] and values[3] > values[1],
                "IC_NATIVE_TYPE_A_MEASURED_INK_MALFORMED")
        boxes.append((t.get("data-owner"), values))
    gaps = []
    for (left, a), (right, b) in combinations(boxes, 2):
        dx = max(0, a[0]-b[2], b[0]-a[2])
        dy = max(0, a[1]-b[3], b[1]-a[3])
        gaps.append((math.hypot(dx, dy), left, right))
    require(len(gaps) == 561, "IC_MEASURED_TEXT_34_PAIR_COUNT_DRIFT")
    require(all(math.isfinite(x[0]) and x[0] > 0 for x in gaps),
            "IC_NATIVE_TYPE_A_GLYPHS_OVERLAP_OR_INVALID")
    # A3 is 420x297mm, but the inspected older owner SVG is deliberately
    # content-cropped 402.6x244.052. The requested editorial 10mm margin
    # must be tested against *absolute* page (0,0), not cropped viewport.
    a3_nominal = (420.0, 297.0)
    a3_true_sheet = (
        abs(view[0]) < 0.001 and abs(view[1]) < 0.001
        and abs(view[2]-a3_nominal[0]) < 0.001
        and abs(view[3]-a3_nominal[1]) < 0.001
    )
    require(root.get("data-draft-paper") == "A3"
            and root.get("data-page-frame-has-violations") == "true"
            and not a3_true_sheet,
            "OLD_PARTIAL_CROPPED_A3_FRAME_NEGATIVE_CONTROL_LOST")
    require(root.get("data-release") == "BLOCKED_PARTIAL",
            "CROPPED_A3_MASQUERADES_AS_REAL_ISSUABLE_SHEET")
    return {
        "calibrated_project_font_family": "OpenGOST type A",
        "type_a_font_sha256": FONT_SHA,
        "annotation_glyphs": len(annotations),
        "measured_native_ic_glyphs": len(ic_text),
        "measured_ic_glyph_pairs": len(gaps),
        "measured_ic_min_glyph_gap_um": round(min(g[0] for g in gaps)),
        "catalog_text_measured_ink_bboxes": "BLOCKED_OWNER_NO_INK_BOX",
        "editorial_10mm_A3_true_page": "FAIL_SOURCE_OWNER_CROPPED_OLD_A3",
        "viewbox_mm": view,
        "a3_physical_page_420x297": a3_true_sheet,
        "nonphysical_source_b_strokes": "BLOCKED_OWNER_NEEDS_REAL_STUB_GEOMETRY",
        "font_formal_GOST_compliance": "BLOCKED_NO_PRIMARY_FIGURE_SCAN_SIGNOFF",
    }


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


def audit(folder: Path, original_netlist: Path,
          ygo_profile: Path, ygo_head: str) -> dict:
    _verify_pinned_owner_bytes(folder)
    manifest = _read_json(folder / f"{BASENAME}-route-drc.json")
    require(manifest.get("owner_router_sha") == PINNED_ROUTER_SHA
            and manifest.get("reference_recon_sha") == PINNED_RECON_SHA,
            "CURRENT_EVIDENCE_OWNER_SHA_NOT_THIS_PINNED_RUN")
    source = _source_model(manifest, _read_json(original_netlist))
    current_ygo = _source_ygo_current_review(_read_json(ygo_profile), ygo_head)
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
    ugo_2mm = distinct_ugo_2mm_envelopes(
        _svg(folder / f"{BASENAME}-clean.svg")
    )
    require(ugo_2mm["verdict"].startswith("PASS_"),
            "ACTUAL_OWNER_2MM_UGO_ENVELOPE_POTENTIAL_VIOLATION")
    clean_root = _svg(folder / f"{BASENAME}-clean.svg")
    intra_1mm = source_ugo_parallel_1mm_scope(clean_root)
    require(not intra_1mm["below_one_mm"],
            "ACTUAL_SOURCE_UGO_PARALLEL_1MM_INK_GAP_FAILED")
    print_text_and_page = type_a_physical_text_and_paper_scope(clean_root)
    all_gaps = all_parallel_ink_3mm_scope(clean_wires)
    require(not all_gaps["below_3mm"],
            "ACTUAL_PARTIAL_3MM_ALL_CONNECTIONS_INK_GAP_FAILED")
    gaps = parallel_gaps(clean_wires)
    require(not gaps["hard_3mm_edge_violations"],
            "ACTUAL_PARTIAL_ROUTE_3MM_DISTINCT_NET_PARALLEL_FAILED")
    return {
        "schema_version": 1, "source_frozen_sha": FROZEN,
        "owner_router_sha": manifest["owner_router_sha"],
        "reference_recon_sha": manifest["reference_recon_sha"],
        "exact_owner_run": 43654672504,
        "owner_3p12_3p13_artifact_bytes_identical": True,
        "latest_owner_HEAD_acceptance": "BLOCKED_NEW_HEAD_SEPARATE_RUN_REQUIRED",
        "source_inventory": source, "routed_graph": route,
        "current_owner_ygo_source_review": current_ygo,
        "printed_parallel_edge_3mm": gaps,
        "printed_all_parallel_3mm_same_and_different_nets": all_gaps,
        "measured_distinct_ugo_2mm_envelopes": ugo_2mm,
        "measured_same_ugo_parallel_1mm_subset": intra_1mm,
        "real_type_a_paper_and_text_scope": print_text_and_page,
        "actual_real_svg_png": variants,
        "checks": {
            "new_partial_native_svg_300dpi": "PASS_DRAFT_PARTIAL_ONLY",
            "real_original_exact_named_net_export": source["source_name_parity"],
            "minimum_3mm_distinct_parallel_ink": "PASS_PARTIAL_ONLY",
            "minimum_3mm_same_and_cross_net_parallel_ink": all_gaps["verdict"],
            "two_mm_separate_UGO": ugo_2mm["verdict"],
            "one_mm_same_UGO_strokes": intra_1mm["verdict"],
            "one_mm_all_UGO_primitive_strokes": "BLOCKED_NOT_FULL_PRIMITIVE_AUDIT",
            "real_paper_margin_print": print_text_and_page[
                "editorial_10mm_A3_true_page"
            ],
            "type_a_glyph_ink": "PASS_NATIVE_IC_ONLY_TEXT_ANNOTATION_BLOCKED",
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
    parser.add_argument("--original-netlist", type=Path, required=True)
    parser.add_argument("--ygo-profile", type=Path, required=True)
    parser.add_argument("--ygo-head", required=True)
    args = parser.parse_args()
    result = audit(args.folder, args.original_netlist,
                   args.ygo_profile, args.ygo_head)
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
