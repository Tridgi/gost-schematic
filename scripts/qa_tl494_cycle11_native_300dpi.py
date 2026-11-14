"""QA Cycle 11: inspect genuine PAINT 23-part NEW-route A3 SVG and 300 DPI.

DO NOT manually repair route art. Only read the real renderer's clean/debug
SVG, validate electrical/physical/source fidelity and convert original SVG
bytes to a corresponding 300dpi raster. Partial routes remain BLOCKED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
from PIL import Image, ImageChops

SVG = "{http://www.w3.org/2000/svg}"
ORIGINAL = "e695c415fdced164b0e0c39c5249d030795a0aa6"


def demand(condition: bool, error: str) -> None:
    if not condition:
        raise AssertionError(error)


def inspect_native(source_dir: Path, destination: Path) -> dict:
    manifest = json.loads(
        (source_dir / "TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json")
        .read_text(encoding="utf-8")
    )
    require = manifest
    demand(
        (require.get("model_source"),
         require.get("source_components"),
         require.get("source_nets"),
         require.get("source_net_pinrefs"),
         require.get("manufacturer_DA1_physical_pin_count"))
        == (ORIGINAL, 23, 15, 62, 16),
        "QA_C11_NATIVE_REAL_SOURCE_23_15_62_16_MISMATCH",
    )
    source = require.get("source_reference")
    demand(isinstance(source, dict) and
           source.get("components") == 23 and
           len(source.get("BOM", {})) == 23 and
           len(source.get("nets", {})) == 15 and
           sum(len(refs) for refs in source["nets"].values()) == 62,
           "QA_C11_NATIVE_ORIGINAL_BOM_AND_PHYSICAL_NETS_MISSING")
    real_net_by_pin = {}
    for net_name, pins in source["nets"].items():
        for pin in pins:
            demand(pin not in real_net_by_pin,
                   "QA_C11_NATIVE_DUPLICATE_PHYSICAL_PINREF")
            real_net_by_pin[pin] = net_name
    demand({f"DA1.{number}" for number in range(1, 17)} <=
           set(real_net_by_pin),
           "QA_C11_NATIVE_TL494_PIN_NOT_IN_SOURCE_NET")
    route = require.get("router_attempt")
    demand(isinstance(route, dict) and
           len(route.get("net_trees", ())) == 15,
           "QA_C11_NATIVE_MISSING_REAL_15_NET_TREE_EVIDENCE")
    completed = sum(tree.get("complete") is True
                    for tree in route["net_trees"])
    demand(completed == route.get("routed_net_count"),
           "QA_C11_NATIVE_FAKE_ROUTED_NET_COUNTER")
    demand(completed < 15 or bool(route.get("print_pass")) is True,
           "QA_C11_NATIVE_FULL_15_WITHOUT_ROUTE_DRC")
    demand(require.get("source_photo_raster_comparison") ==
           "BLOCKED_NO_AUTHORITATIVE_RASTER",
           "QA_C11_NATIVE_FAKE_SOURCE_PHOTO_PARITY")
    demand(require.get("real_print_release") is False and
           require.get("gost_approved") is False and
           require.get("nonphysical_b_marker_status") ==
           "BLOCKED_OWNER_NO_COMPACT_RELOCATION_VALIDATED",
           "QA_C11_NATIVE_RELEASE_OR_B_CONTINUATION_UNVERIFIED")
    demand(require.get("original_net_memberships_unchanged") is True and
           require.get("source_graph_mutated") is False,
           "QA_C11_NATIVE_INPUT_TOPOLOGY_MODIFIED")
    drc = require.get("native_post_render_route_drc")
    demand(isinstance(drc, dict) and
           drc.get("checked_symbol_geometry") is True and
           drc.get("checked_measured_text") is True,
           "QA_C11_NATIVE_POST_RENDER_DRC_MISSING_INK")
    findings = drc.get("findings")
    demand(isinstance(findings, list) and
           drc.get("error_count") ==
           sum(x.get("severity") == "error" for x in findings),
           "QA_C11_NATIVE_DRC_COUNT_FORGED")
    if completed != 15:
        demand("ROUTER_INCOMPLETE_OR_UNVERIFIED_15_NETS"
               in require.get("blockers", ()),
               "QA_C11_NATIVE_PARTIAL_GRAPH_FAKED_PRINT_PASS")
        demand(require.get("printable_candidate") is False,
               "QA_C11_NATIVE_PARTIAL_PRINT_ACCEPTED")
    actual_segments = require.get("route_segments")
    demand(type(actual_segments) is int and actual_segments >= 0 and
           route.get("graph_segments") == actual_segments,
           "QA_C11_NATIVE_GRAPH_SEGMENT_COUNT_FORGED")
    destination.mkdir(parents=True, exist_ok=True)
    modes = {}
    views = []
    for name in ("clean", "diagnostic"):
        target = source_dir / f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{name}.svg"
        svg = target.read_bytes()
        root = ET.fromstring(svg)
        demand(root.tag == SVG + "svg" and
               root.get("data-release") ==
               "BLOCKED_INCOMPLETE_OR_PRINT_DRC",
               "QA_C11_NATIVE_SVG_NOT_BLOCKED")
        demand(root.get("data-route-graph-sha256") ==
               require.get("graph_sha256") and
               root.get("data-render-route-kind") ==
               "EXTERNAL_VERIFIED_MODEL_GRAPH",
               "QA_C11_NATIVE_NOT_GENUINE_VERIFIED_GRAPH_RENDER")
        demand(root.get("data-source-components") == "23" and
               root.get("data-source-nets") == "15" and
               root.get("data-actual-route-segments") == str(actual_segments),
               "QA_C11_NATIVE_SVG_LOST_SOURCE_ATTESTATION")
        demand(root.get("data-e3-normative-approval") ==
               "DRAFT_NOT_APPROVED",
               "QA_C11_NATIVE_CLAIMED_UNREVIEWED_UGO_CERTIFICATION")
        symbols = root.findall(f"./{SVG}g[@data-layer='symbols']")
        wires = root.findall(f".//{SVG}line[@data-layer='wires']")
        leads = root.findall(
            f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
        )
        targets = root.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        demand(len(symbols) == 23 and len(wires) == actual_segments
               and len(leads) == 16,
               "QA_C11_NATIVE_SVG_LOST_23_16_OR_WIRES")
        demand({lead.get("data-pin-number") for lead in leads} ==
               {str(n) for n in range(1, 17)},
               "QA_C11_NATIVE_WRONG_DA1_PHYSICAL_NUMBER")
        demand(len(targets) == (0 if name == "clean" else 16),
               "QA_C11_NATIVE_EDITOR_LAYER_POLICY")
        tips = {}
        for lead in leads:
            number = lead.get("data-pin-number")
            demand(number not in tips,
                   "QA_C11_NATIVE_DUPLICATE_MANUFACTURER_PIN_NUMBER")
            x, y = lead.get("x2"), lead.get("y2")
            demand(x is not None and y is not None,
                   "QA_C11_NATIVE_UNRESOLVED_PHYSICAL_PIN_POINT")
            tips[number] = (round(float(x) * 1000), round(float(y) * 1000))
        if name == "diagnostic":
            demand({t.get("data-pin-ref") for t in targets} ==
                   {f"DA1.{n}" for n in range(1, 17)},
                   "QA_C11_NATIVE_DIAGNOSTIC_PHYSICAL_PINREFS_CHANGED")
            for marker in targets:
                number = marker.get("data-pin-number")
                demand(number in tips and marker.get("data-pin-ref") ==
                       f"DA1.{number}" and
                       marker.get("data-net-id") ==
                       real_net_by_pin[f"DA1.{number}"] and
                       marker.get("data-connectable") == "true" and
                       marker.get("fill") == "#148645",
                       "QA_C11_NATIVE_FOREIGN_PINREF_NET_OR_GREEN_ROLE")
                ax, ay = tips[number]
                demand((
                    marker.get("data-external-anchor-x-um"),
                    marker.get("data-external-anchor-y-um"),
                ) == (str(ax), str(ay)),
                       "QA_C11_NATIVE_MARKER_NOT_ON_ACTUAL_LEAD_TIP")
                w = round(float(marker.get("width", "0")) * 1000)
                h = round(float(marker.get("height", "0")) * 1000)
                x = round(float(marker.get("x", "0")) * 1000)
                y = round(float(marker.get("y", "0")) * 1000)
                demand(w == h == 700 and
                       2*x + w == 2*ax and 2*y + h == 2*ay,
                       "QA_C11_NATIVE_HOTSPOT_NOT_TRUE_700UM_SQUARE")
        width, height = root.get("width", ""), root.get("height", "")
        demand(width.endswith("mm") and height.endswith("mm"),
               "QA_C11_NATIVE_SVG_HAS_NO_MILLIMETRE_DIMENSIONS")
        mm = (float(width[:-2]), float(height[:-2]))
        demand(all(0 < dimension < 1200 for dimension in mm),
               "QA_C11_NATIVE_INVALID_PHYSICAL_SCALE")
        destination_png = destination / (target.stem + "-300dpi.png")
        # SVG original source remains byte-for-byte unchanged on disk.
        cairosvg.svg2png(
            bytestring=svg, write_to=str(destination_png), dpi=300,
        )
        with Image.open(destination_png) as raster:
            demand(raster.format == "PNG", "QA_C11_NATIVE_NOT_REAL_PNG")
            exact_pixels = tuple(round(dimension * 300 / 25.4)
                                 for dimension in mm)
            demand(all(abs(a - b) <= 2 for a, b in zip(
                raster.size, exact_pixels, strict=True
            )), "QA_C11_NATIVE_FALSE_300DPI_PHYSICAL_RASTER")
            if name == "clean":
                rgb = raster.convert("RGB")
                channels = rgb.split()
                demand(ImageChops.difference(
                    channels[0], channels[1]
                ).getbbox() is None and ImageChops.difference(
                    channels[0], channels[2]
                ).getbbox() is None,
                       "QA_C11_NATIVE_CLEAN_HAS_EDITOR_COLORS")
            raster.save(destination_png, dpi=(300, 300))
        with Image.open(destination_png) as check:
            density = check.info.get("dpi")
            demand(density is not None and
                   all(abs(value - 300) < 1 for value in density),
                   "QA_C11_NATIVE_PNG_DPI_NOT_STAMPED_AND_VERIFIED")
        demand(hashlib.sha256(target.read_bytes()).hexdigest() ==
               hashlib.sha256(svg).hexdigest(),
               "QA_C11_NATIVE_UNEXPECTED_MANUAL_SVG_EDIT")
        views.append(svg)
        modes[name] = {
            "original_svg": target.name,
            "source_svg_sha256": hashlib.sha256(svg).hexdigest(),
            "raster": destination_png.name,
            "real_source_mm": mm,
            "physical_300dpi_png_pixels": exact_pixels,
            "physical_leads": 16,
            "true_editor_squares": len(targets),
            "source_symbols": len(symbols),
            "new_net_segments": len(wires),
            "print_release": "BLOCKED",
        }
    demand(views[0] != views[1],
           "QA_C11_NATIVE_CLEAN_AND_DIAGNOSTIC_SAME_IMAGE")
    return {
        "source_sha": ORIGINAL,
        "real_native_components": 23,
        "physical_net_memberships": 62,
        "manufacturer_DA1_tips": 16,
        "current_new_route_nets_completed": completed,
        "all_15_trees_evaluated": True,
        "new_route_segments": actual_segments,
        "real_native_post_render_drc_errors": drc["error_count"],
        "all_views": modes,
        "original_91_wire_9_error_32_warning_source":
            "UNCHANGED_NEGATIVE_FIXTURE",
        "source_b_continuation": "BLOCKED_PENDING_VALIDATED_NEW_PLACEMENT",
        "photo_parity": "BLOCKED_TRUSTED_ORIGINAL_PHOTO_NOT_AVAILABLE",
        "normative_UGO": "DRAFT_NOT_APPROVED",
        "release": "NO_GO_PARTIAL_ROUTING_OR_ESKD",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    report = inspect_native(args.source_dir, args.output_dir)
    (args.output_dir / "qa92-cycle11-native-new-route-drc-300dpi.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n", encoding="utf-8",
    )
    print("QA92_CYCLE11_NEW_ROUTE_NATIVE_REVIEW " +
          json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
