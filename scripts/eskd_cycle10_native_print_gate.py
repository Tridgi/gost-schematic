"""ESKD Cycle10 independent evidence gate for REAL PAINT #93 native TL494 SVG.

Reads owner-rendered files; it never fabricates a vector drawing or rewires Nets.
Structural PASS is separate from source-layout DRC FAIL and normative BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
FROZEN_SOURCE = "e695c415fdced164b0e0c39c5249d030795a0aa6"
PAINT_HEAD = "32f2efb2cdcb561cb2567a54448381de3cb87832"
YGO_HEAD = "edc71a48035723d48a203ae2ea12588701f68ba8"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
PAINT_BASE = "TL494_native_23_bottom_to_top"
SOURCE_GAPS_UM = [700, 1450, 1700, 1700, 1950]


class PrintEvidenceError(ValueError):
    """Absent, contradictory or impossible owner evidence; never waive."""


def _insist(condition: bool, reason: str) -> None:
    if not condition:
        raise PrintEvidenceError(reason)


def _parse_svg(file: Path) -> ET.Element:
    try:
        return ET.fromstring(file.read_text(encoding="utf-8"))
    except (ET.ParseError, OSError, UnicodeError) as exc:
        raise PrintEvidenceError(f"SVG_UNREADABLE:{file.name}") from exc


def _svg_mm(root: ET.Element) -> tuple[float, float]:
    dimensions = []
    for axis in ("width", "height"):
        raw = root.get(axis, "")
        _insist(bool(re.fullmatch(r"\d+(?:\.\d+)?mm", raw)),
                f"SVG_PHYSICAL_MM_REQUIRED:{axis}")
        dimensions.append(float(raw[:-2]))
    _insist(all(math.isfinite(v) and v > 0 for v in dimensions),
            "SVG_PHYSICAL_DIMENSION_INVALID")
    view = [float(v) for v in root.get("viewBox", "").replace(",", " ").split()]
    _insist(len(view) == 4 and all(math.isfinite(v) for v in view),
            "SVG_VIEWBOX_INVALID")
    _insist(math.isclose(dimensions[0], view[2], abs_tol=0.005)
            and math.isclose(dimensions[1], view[3], abs_tol=0.005),
            "SVG_MM_VIEWBOX_SCALE_MISMATCH")
    return dimensions[0], dimensions[1]


def _reading_vector(function: ET.Element) -> tuple[float, float]:
    raw = function.get("transform", "")
    match = re.fullmatch(r"matrix\(([^)]+)\)", raw.strip())
    _insist(match is not None, "PWM_MISSING_MATRIX")
    try:
        values = [float(v) for v in re.split(r"[\s,]+", match.group(1).strip())]
    except ValueError as exc:
        raise PrintEvidenceError("PWM_MATRIX_MALFORMED") from exc
    _insist(len(values) == 6 and all(math.isfinite(v) for v in values),
            "PWM_MATRIX_NOT_AFFINE")
    a, b, c, d, _, _ = values
    _insist(math.isclose(a * d - b * c, 1, abs_tol=1e-8),
            "PWM_MATRIX_REFLECTION_OR_SCALE")
    return a, b


def _read_function(root: ET.Element) -> tuple[float, float]:
    functions = [
        node for node in root.findall(f".//{SVG}text")
        if node.get("data-layer") == "ic-text"
        and node.get("data-kind") == "function"
        and "".join(node.itertext()).strip() == "PWM"
    ]
    _insist(len(functions) == 1, "PWM_REAL_FUNCTION_GLYPH_MISSING_OR_DUPLICATED")
    return _reading_vector(functions[0])


def _source_profile(profile: dict) -> dict[str, dict]:
    _insist(profile["reference_sha"] == FROZEN_SOURCE,
            "YGO_PROFILE_FROZEN_SOURCE_MISMATCH")
    _insist(profile["status"] == "DRAFT", "YGO_PROFILE_UNEXPECTED_APPROVAL")
    result = {part["reference"]: part for part in profile["profiles"]}
    _insist(len(result) == 13 and len(profile["profiles"]) == 13,
            "YGO_PROFILE_NOT_13_SOURCE_INSTANCES")
    _insist(all(part["normative_verdict"].startswith("BLOCKED")
                for part in result.values()),
            "YGO_PROFILE_UNPROVEN_NORMATIVE_APPROVAL")
    return result


def _owner_facts(manifest: dict, profile: dict[str, dict]) -> None:
    checks = {
        "source_sha": FROZEN_SOURCE,
        "owner_catalog_sha": YGO_HEAD,
        "components": 23,
        "Nets": 15,
        "wires": 91,
        "explicit_junctions": 37,
        "font_sha256": FONT_SHA,
        "calibrated_type_a_h_mm": 3.5,
        "actual_ti_pin3_electrical": "input",
        "actual_ti_pin13_electrical": "input",
        "source_3mm_parallel_wire_failures": 5,
        "electrical_topology_changed": False,
        "route_drc_pass": False,
        "gost_ugo_approved": False,
        "native_b_graphics_from_typed_project": True,
        "fake_a_marker_created": False,
    }
    for name, expected in checks.items():
        _insist(manifest.get(name) == expected,
                f"PAINT_MANIFEST_{name.upper()}_CONTRADICTS_SOURCE")
    _insist(set(manifest["catalog_ugo_bindings"]) == set(profile),
            "PAINT_13_UGO_BINDINGS_NOT_YGO_SOURCE")
    _insist(len(manifest["catalog_ugo_bindings"]) == 13,
            "PAINT_CATALOG_DUPLICATE_SOURCE_PART")
    _insist(set(manifest["paint_authoritative_points"]) ==
            {str(i) for i in range(1, 17)},
            "PAINT_16_PIN_IDENTITY_LOST")
    _insist(set(manifest["original_b_continuations"]) == {"b-X2", "b-R5"},
            "PAINT_B_PAIR_MISSING_OR_FABRICATED")
    details = manifest["source_3mm_parallel_wire_details"]
    _insist(len(details) == 5, "SOURCE_PARALLEL_FINDING_COUNT_CHANGED")
    try:
        gaps = sorted(int(item["edge_gap_um"]) for item in details)
    except (KeyError, TypeError, ValueError) as exc:
        raise PrintEvidenceError("SOURCE_PARALLEL_GAP_NO_NUMERIC_PROOF") from exc
    _insist(gaps == SOURCE_GAPS_UM,
            "SOURCE_PARALLEL_NEGATIVE_GAP_CHANGED_OR_WAIVED")



def _actual_svg_3mm_violations(root: ET.Element) -> list[dict]:
    """Independent integer-micrometre reread of the ACTUAL owner printed lines.

    Applies 3mm to distinct-net parallel strokes with positive projected
    overlap only.  Crossings and same-Net T are not certified by this rule.
    """
    wires = root.findall(f".//{SVG}line[@data-layer='wires']")
    _insist(len(wires) == 91, "SVG_WIRE_DRC_REQUIRES_91_REAL_SEGMENTS")
    typed = []
    for index, line in enumerate(wires):
        _insist(line.get("data-wire-index") == str(index),
                "SVG_WIRE_INDEX_PROVENANCE_MISSING")
        _insist(line.get("data-net"), "SVG_WIRE_NET_MISSING")
        try:
            coords = tuple(round(float(line.get(key, "")) * 1000)
                           for key in ("x1", "y1", "x2", "y2"))
            stroke = round(float(line.get("stroke-width", "")) * 1000)
        except ValueError as exc:
            raise PrintEvidenceError("SVG_WIRE_GEOMETRY_NOT_NUMERIC") from exc
        _insist(stroke > 0 and 200 <= stroke <= 1000,
                "SVG_WIRE_STROKE_OUT_OF_GOST_0_2_TO_1_0_MM")
        x1, y1, x2, y2 = coords
        _insist((x1 == x2) != (y1 == y2),
                "SVG_WIRE_NOT_NONZERO_ORTHOGONAL")
        typed.append((coords, stroke, line.get("data-net")))
    failures = []
    for i, (a, wa, net_a) in enumerate(typed):
        x1, y1, x2, y2 = a
        for j in range(i + 1, len(typed)):
            b, wb, net_b = typed[j]
            if net_a == net_b:
                continue
            xx1, yy1, xx2, yy2 = b
            center_distance = None
            if y1 == y2 and yy1 == yy2 and y1 != yy1:
                overlap = (min(max(x1, x2), max(xx1, xx2))
                           - max(min(x1, x2), min(xx1, xx2)))
                if overlap > 0:
                    center_distance = abs(y1 - yy1)
            elif x1 == x2 and xx1 == xx2 and x1 != xx1:
                overlap = (min(max(y1, y2), max(yy1, yy2))
                           - max(min(y1, y2), min(yy1, yy2)))
                if overlap > 0:
                    center_distance = abs(x1 - xx1)
            if center_distance is None:
                continue
            sum_widths = wa + wb
            _insist(sum_widths % 2 == 0,
                    "SVG_WIRE_STROKE_HALF_UM_NOT_REPRESENTABLE")
            gap = center_distance - sum_widths // 2
            if gap < 3000:
                failures.append({
                    "first_segment": i,
                    "second_segment": j,
                    "first_net": net_a,
                    "second_net": net_b,
                    "edge_gap_um": gap,
                    "required_gap_um": 3000,
                })
    return failures


def _check_physical_svg(root: ET.Element, manifest: dict,
                        diagnostic: bool) -> dict:
    parts = root.findall(f"./{SVG}g[@data-layer='symbols']")
    refs = [g.get("data-reference") for g in parts]
    _insist(len(parts) == 23 and len(set(refs)) == 23 and "DA1" in refs,
            "SHEET_23_UNIQUE_COMPONENT_GROUPS_REQUIRED")
    da1 = next(g for g in parts if g.get("data-reference") == "DA1")
    _insist(da1.get("data-composed-engine") == "physical-ic-renderer",
            "DA1_FAKE_UGO_SURROGATE")
    _insist(da1.get("data-physical-pin-count") == "16",
            "DA1_16_PHYSICAL_PIN_COUNT_WRONG")
    _insist(root.get("data-native-ic-composition") == "exact-circuit-pinrefs",
            "DA1_SOURCE_PINREF_COMPOSITION_MISSING")
    wires = root.findall(f".//{SVG}line[@data-layer='wires']")
    _insist(len(wires) == 91, "REAL_91_WIRE_SEGMENTS_LOST")
    _insist(all(w.get("data-net") for w in wires),
            "WIRE_TYPED_NET_PROVENANCE_MISSING")
    junctions = root.findall(
        f".//{SVG}circle[@data-kind='authored-junction']"
    )
    _insist(len(junctions) == 37, "REAL_37_AUTHORED_DOTS_LOST")
    leads = da1.findall(f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line")
    ids = [line.get("data-pin-number") for line in leads]
    _insist(len(ids) == 16 and set(ids) == {str(i) for i in range(1, 17)},
            "DA1_PHYSICAL_NUMBERED_LEADS_NOT_1_TO_16")
    _insist(root.find(f".//{SVG}g[@data-layer='typed-nonphysical-continuations']")
            is not None, "SOURCE_TYPED_B_CONTINUATION_LAYER_MISSING")
    indicators = root.findall(
        f".//{SVG}circle[@data-nonphysical-net-continuation]"
    )
    found = {p.get("data-nonphysical-net-continuation") for p in indicators}
    _insist(len(indicators) == 2 and found == {"b-X2", "b-R5"},
            "B_CONTINUATION_WRONG_COUNT_OR_IDS")
    _insist(all(p.get("data-electrical-junction") == "false"
                for p in indicators), "B_CONTINUATION_PHANTOM_ELECTRICAL_JUNCTION")
    for label in root.findall(f".//{SVG}text[@data-source='typed-net-continuation-v2']"):
        _insist((label.text or "").strip() == "b"
                and label.get("data-nonphysical") == "true",
                "B_CONTINUATION_WRONG_TEXT_OR_PHYSICAL")
    # This is a *source-specific* negative: source COMMON/0V is not PE/chassis.
    for e in root.iter():
        if e.get("data-marker-id"):
            _insist(e.get("data-marker-id") not in {
                "net-marker.earth", "net-marker.chassis",
                "net-marker.protective_earth",
            }, "COMMON_FABRICATED_EARTH_OR_CHASSIS")
    _insist(root.get("data-native-ic-composition") == "exact-circuit-pinrefs",
            "SHEET_NOT_SOURCE_NATIVE")
    width_mm, height_mm = _svg_mm(root)
    targets = root.findall(f"./{SVG}g[@data-layer='editor-connection-targets']")
    if diagnostic:
        # The PAINT composition appends authored junctions and typed b
        # after the markers; contract is foreground over ALL WIRE strokes,
        # not 'last child of root' (which would falsely reject real owner).
        children = list(root)
        wire_indices = [i for i, child in enumerate(children)
                        if child.tag == SVG + "line"
                        and child.get("data-layer") == "wires"]
        _insist(len(targets) == 1 and len(wire_indices) == 91
                and children.index(targets[0]) > max(wire_indices),
                "EDITOR_HOTSPOTS_NOT_FOREGROUND")
        _insist(targets[0].get("data-layer-order") == "after-all-copper",
                "EDITOR_FOREGROUND_ORDER_MISSING")
        markers = targets[0].findall(f".//{SVG}rect[@data-pin-number]")
        numbers = [m.get("data-pin-number") for m in markers]
        _insist(len(markers) == 16
                and set(numbers) == {str(i) for i in range(1, 17)},
                "EDITOR_16_REAL_PIN_HOTSPOTS_REQUIRED")
        for mark in markers:
            num = mark.get("data-pin-number")
            at = manifest["paint_authoritative_points"][num]
            if mark.get("data-external-anchor-x-um") is not None:
                _insist([
                    int(mark.get("data-external-anchor-x-um")),
                    int(mark.get("data-external-anchor-y-um")),
                ] == at, "EDITOR_HOTSPOT_MOVED_FROM_REAL_PINREF")
    else:
        _insist(not targets, "EDITOR_HOTSPOTS_LEAKED_INTO_CLEAN")
        _insist(not any(e.get("data-layer") == "geometry-review"
                        for e in root.iter()),
                "CLEAN_HAS_EDITOR_GEOMETRY_OVERLAY")
        _insist(not any(e.get("fill", "").lower() in {"#168f78", "#be6300"}
                        or e.get("stroke", "").lower() in {"#168f78", "#be6300"}
                        for e in root.iter()), "CLEAN_CONTAINS_COLORED_DEBUG_INK")
    return {
        "physical_width_mm": width_mm,
        "physical_height_mm": height_mm,
        "symbols": len(parts),
        "wire_segments": len(wires),
        "junctions": len(junctions),
        "numbered_tl494_pins": len(leads),
        "nonphysical_b_addresses": sorted(found),
        "diagnostic_only_hotspots": 16 if diagnostic else 0,
    }


def _verify_png(png_file: Path, width_mm: float, root: ET.Element, *,
                diagnostic: bool) -> dict:
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise PrintEvidenceError("PIL_REQUIRED_FOR_ACTUAL_PRINT_RASTER") from exc
    _insist(png_file.is_file(), f"PNG_300DPI_MISSING:{png_file.name}")
    with Image.open(png_file) as im:
        measured_px = im.size
        declared_dpi = im.info.get("dpi")
        _insist(abs(im.width - round(width_mm * 300 / 25.4)) <= 1,
                "PNG_RASTER_NOT_PHYSICALLY_300DPI")
        raster = im.convert("RGB")
        if not diagnostic:
            red, green, blue = raster.split()
            _insist(ImageChops.difference(red, green).getbbox() is None
                    and ImageChops.difference(red, blue).getbbox() is None,
                    "PNG_CLEAN_COLORED_EDITOR_INK")
            green_samples = 0
        else:
            real_leads = {
                el.get("data-pin-number"): el
                for el in root.findall(
                    f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
                )
            }
            markers = root.findall(
                f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
            )
            viewport = [float(v) for v in root.get("viewBox", "").split()]
            _insist(len(viewport) == 4 and len(markers) == 16,
                    "PNG_REAL_16_PIN_DEBUG_SOURCE_REQUIRED")
            green_samples = 0
            for marker in markers:
                number = marker.get("data-pin-number")
                _insist(number in real_leads, "PNG_MARKER_FOREIGN_PIN")
                _insist(marker.get("data-pin-ref") == f"DA1.{number}"
                        and marker.get("data-connectable") == "true"
                        and marker.get("data-manufacturer-electrical-type")
                        and marker.get("data-net-id"),
                        "PNG_MARKER_NOT_VERIFIED_REAL_PINREF")
                line = real_leads[number]
                center = (float(marker.get("x", "nan"))
                          + float(marker.get("width", "nan")) / 2,
                          float(marker.get("y", "nan"))
                          + float(marker.get("height", "nan")) / 2)
                _insist(math.isclose(center[0], float(line.get("x2", "nan")),
                                       abs_tol=1e-6)
                        and math.isclose(center[1], float(line.get("y2", "nan")),
                                         abs_tol=1e-6),
                        "PNG_GREEN_MARKER_NOT_ACTUAL_PIN_LEAD_END")
                x = round((center[0] - viewport[0]) * 300 / 25.4)
                y = round((center[1] - viewport[1]) * 300 / 25.4)
                _insist(0 <= x < im.width and 0 <= y < im.height,
                        "PNG_PIN_OUT_OF_PHYSICAL_SHEET")
                red, green, blue = raster.getpixel((x, y))
                _insist(green > red + 35 and green > blue + 20,
                        "PNG_GREEN_ENDPOINT_COVERED_BY_COPPER")
                green_samples += 1
        return {
            "pixels": list(measured_px),
            "dpi_metadata": list(declared_dpi) if declared_dpi else None,
            "physical_width_mm": width_mm,
            "real_green_pin_pixels": green_samples,
            "clean_monochrome": not diagnostic,
        }


def audit(folder: Path, profile_path: Path, *,
          verify_png: bool = False) -> dict:
    manifest_path = folder / "TL494_full_native_23_engine_manifest.json"
    _insist(manifest_path.is_file(), "REAL_NATIVE_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    expected_profiles = _source_profile(profile)
    _owner_facts(manifest, expected_profiles)
    result = {
        "release_verdict": "NO_GO",
        "approval": "DRAFT_NOT_APPROVED",
        "frozen_original_sha": FROZEN_SOURCE,
        "paint_owner_sha": PAINT_HEAD,
        "catalog_owner_sha": YGO_HEAD,
        "checks": {},
        "source_selected_symbols": {
            name: {
                "symbol_id": entry["symbol_id"],
                "rotation": entry["rotation"],
                "standard_figure": entry["standard_figure"],
                "status_source_profile": "PASS_DRAFT",
                "source_1to1": "BLOCKED_UNCALIBRATED",
            } for name, entry in sorted(expected_profiles.items())
        },
    }
    actual = {}
    for suffix, is_diagnostic in (("clean", False), ("diagnostic", True)):
        file = folder / f"{PAINT_BASE}_{suffix}.svg"
        _insist(file.is_file(), f"PAINT_REAL_{suffix.upper()}_SVG_MISSING")
        root = _parse_svg(file)
        details = _check_physical_svg(root, manifest, is_diagnostic)
        direction = _read_function(root)
        _insist(math.isclose(direction[0], 0, abs_tol=1e-8)
                and math.isclose(direction[1], -1, abs_tol=1e-8),
                "PAINT_NEW_PWM_READING_NOT_BOTTOM_TO_TOP")
        details["pwm_baseline"] = list(direction)
        details["correct_editorial_pwm_direction"] = True
        if verify_png:
            png = folder / f"{PAINT_BASE}_{suffix}-300dpi.png"
            details["raster"] = _verify_png(png, details["physical_width_mm"], root,
                                            diagnostic=is_diagnostic)
        actual[suffix] = details
    _insist(actual["clean"]["physical_width_mm"] ==
            actual["diagnostic"]["physical_width_mm"]
            and actual["clean"]["physical_height_mm"] ==
            actual["diagnostic"]["physical_height_mm"],
            "CLEAN_DIAGNOSTIC_PHYSICAL_PAGE_SIZE_MISMATCH")
    result["checks"]["native_owner_clean_and_debug"] = {
        "status": "PASS_DRAFT_REAL_OWNER_SVG",
        "details": actual,
    }
    actual_3mm = _actual_svg_3mm_violations(
        _parse_svg(folder / f"{PAINT_BASE}_clean.svg")
    )
    _insist(len(actual_3mm) == 5
            and sorted(item["edge_gap_um"] for item in actual_3mm) == SOURCE_GAPS_UM,
            "REAL_SVG_3MM_GAPS_DISAGREE_WITH_SOURCE_FIVE")
    owner_3mm = manifest["source_3mm_parallel_wire_details"]
    _insist(actual_3mm == owner_3mm,
            "REAL_SVG_3MM_NET_AND_SEGMENT_PROVENANCE_MISMATCH")
    result["checks"]["print_hard_3mm_parallel_gaps"] = {
        "status": "FAIL_FROZEN_91_WIRES",
        "independent_actual_svg_pairwise_comparisons": 4095,
        "independent_actual_svg_failed_pairs": actual_3mm,
        "real_min_gaps_mm": [g / 1000 for g in SOURCE_GAPS_UM],
        "worst_actual_mm": 0.7,
        "source_five_negative_preserved": True,
    }
    w = actual["clean"]["physical_width_mm"]
    h = actual["clean"]["physical_height_mm"]
    fits_a3 = ((w <= 420 and h <= 297)
               or (w <= 297 and h <= 420))
    result["checks"]["native_full_print_a3"] = {
        "status": "BLOCKED_NOT_FINAL_ROUTED_A3_PRINT",
        "as_rendered_fits_a3": fits_a3,
        "native_size_mm": [w, h],
        "separate_reference_115_compact_bbox_mm": [395.3, 228.351],
        "compact_bbox_is_not_a_complete_routed_print": True,
    }
    result["checks"]["normative_rules_and_user_bitmap"] = {
        "status": "BLOCKED",
        "reason": "13 source UGO still DRAFT; no scanned-original calibrated overlay"
                  "; function-only PWM independent GOST approval absent"
                  "; source C1/C2/C3/C5/C6 node potentials unverified",
        "current_full_new_net_route_count": None,
        "current_final_print_approved": False,
        "300dpi_is_qa_convention_not_mandatory_gost": True,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify-png", action="store_true")
    parser.add_argument("--expect-source-blocked", action="store_true")
    args = parser.parse_args()
    result = audit(args.folder, args.profile, verify_png=args.verify_png)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    if not args.expect_source_blocked:
        raise SystemExit("NO_GO: real PAINT 91-wire source has 5 hard DRC FAIL;"
                         " release gate deliberately refuses PASS")
    assert result["release_verdict"] == "NO_GO"
    assert result["checks"]["print_hard_3mm_parallel_gaps"]["status"].startswith("FAIL")
    print("PASS evidence integrity; NO_GO final ESKD source print acceptance."
          " All five original hard gaps remain visible.")


if __name__ == "__main__":
    main()
