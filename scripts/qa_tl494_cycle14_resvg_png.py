"""Independent physical Resvg PNG300 QA for genuine PAINT 23-part SVG.

Requires source-signed 2 b strokes, all 24 hostile XML mutations and exact
diagnostic IC targets before raster. No hand-edited artwork, surrogate route,
font bytes committed or whole-sheet release when only some Nets are routed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import resvg_py
from PIL import Image, ImageChops
from qa_tl494_cycle11_native_300dpi import SVG, demand
from qa_tl494_cycle14_b_xml_gate import inspect_source_svg_only

FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
A3_MM = (420.0, 297.0)
DPI = 300


def physical_resvg_raster(
    source_dir: Path, witness_file: Path, font_file: Path, dest: Path,
) -> dict:
    """Render real untouched clean/debug SVG, independently validate PNG."""
    demand(hashlib.sha256(font_file.read_bytes()).hexdigest() == FONT_SHA,
           "QA_C14_RESVG_TYPE_A_FONT_NOT_ORIGINAL_SHA")
    svg_evidence = inspect_source_svg_only(source_dir, witness_file)
    dest.mkdir(parents=True, exist_ok=True)
    views = {}
    for mode in ("clean", "diagnostic"):
        source = source_dir / f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{mode}.svg"
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        root = ET.fromstring(source.read_bytes())
        demand(
            (root.get("width"), root.get("height")) == ("420mm", "297mm")
            and float(root.get("viewBox", "0 0 0 0").split()[2]) > 0,
            "QA_C14_RESVG_NOT_TRUE_A3_MM_PRINT",
        )
        data = resvg_py.svg_to_bytes(
            svg_path=str(source), dpi=float(DPI), background="#ffffff",
            font_files=[str(font_file)], skip_system_fonts=True,
        )
        image_path = dest / f"TL494_REAL_PARTIAL_{mode}-300dpi-resvg.png"
        with Image.open(io.BytesIO(data)) as raster:
            expected = tuple(round(mm * DPI / 25.4) for mm in A3_MM)
            demand(
                raster.format == "PNG" and
                all(abs(real - ideal) <= 2 for real, ideal in
                    zip(raster.size, expected, strict=True)),
                "QA_C14_RESVG_PHYSICAL_PNG_SIZE_OR_FORMAT_INVALID",
            )
            rgb = raster.convert("RGB")
            if mode == "clean":
                channels = rgb.split()
                demand(
                    ImageChops.difference(channels[0], channels[1]).getbbox()
                    is None and
                    ImageChops.difference(channels[0], channels[2]).getbbox()
                    is None,
                    "QA_C14_RESVG_CLEAN_VIEW_HAS_EDITOR_INK",
                )
            else:
                targets = root.findall(
                    f".//{SVG}g[@data-layer='editor-connection-targets']/"
                    f"{SVG}rect"
                )
                demand(len(targets) == 16,
                       "QA_C14_RESVG_DIAGNOSTIC_NOT_16_REAL_CONTACTS")
                seen = set()
                for marker in targets:
                    ident = marker.get("data-pin-ref")
                    demand(ident not in seen,
                           "QA_C14_RESVG_DUPLICATE_VISIBLE_PINREF")
                    seen.add(ident)
                    x = int(marker.get("data-external-anchor-x-um"))
                    y = int(marker.get("data-external-anchor-y-um"))
                    # SVG uses integer µm; convert to physical 300 DPI pixels.
                    px = round(x * DPI / 25400)
                    py = round(y * DPI / 25400)
                    demand(9 <= px < rgb.width - 9 and
                           9 <= py < rgb.height - 9,
                           "QA_C14_RESVG_EDITOR_MARK_OUTSIDE_REAL_PAPER")
                    green_pixels = 0
                    for iy in range(py - 9, py + 10):
                        for ix in range(px - 9, px + 10):
                            rr, gg, bb = rgb.getpixel((ix, iy))
                            if gg > rr * 1.4 and gg > bb * 1.15 and gg > 45:
                                green_pixels += 1
                    demand(green_pixels > 0,
                           "QA_C14_RESVG_REAL_DA1_CONTACT_NOT_VISIBLE")
                demand(seen == {f"DA1.{number}" for number in range(1, 17)},
                       "QA_C14_RESVG_MANUFACTURER_PIN_NUMBER_CHANGED")
            raster.save(image_path, dpi=(DPI, DPI))
        with Image.open(image_path) as verified:
            density = verified.info.get("dpi")
            demand(
                density is not None and
                all(abs(value - DPI) < 1 for value in density),
                "QA_C14_RESVG_PHYSICAL_300DPI_METADATA_NOT_VERIFIED",
            )
            pixels = list(verified.size)
        demand(
            hashlib.sha256(source.read_bytes()).hexdigest() == source_sha,
            "QA_C14_RESVG_ACTUAL_PAINT_SVG_MODIFIED",
        )
        views[mode] = {
            "source_svg_sha256": source_sha,
            "physical_page_mm": list(A3_MM),
            "source_unmodified": True,
            "PNG_SHA256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "png_file": image_path.name,
            "png_pixels": pixels,
            "png_dpi": DPI,
            "real_green_IC_targets": 16 if mode == "diagnostic" else 0,
            "release": "PARTIAL_DIAGNOSTIC_ONLY",
        }
    return {
        "result": "PASS_REAL_RESVG_300DPI_PARTIAL_ONLY",
        "source_svg_gate": svg_evidence["status"],
        "actual_source_24_negative_rejections": len(
            svg_evidence["twenty_four_real_xml_hostile_mutants"]
        ),
        "source_signed_b_strokes_per_view": 2,
        "new_route_completed_nets": svg_evidence["completed_route_trees"],
        "type_a_sha256": FONT_SHA,
        "source_reference_sha": svg_evidence["source"],
        "png": views,
        "global_print_release": "NO_GO_UNTIL_15_NETS_GLOBAL_DRC_AND_ESKD",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--source-b-witness", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = physical_resvg_raster(
        args.source_dir, args.source_b_witness, args.font_file, args.output_dir,
    )
    (args.output_dir / "qa14-independent-real-resvg-300dpi.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("QA14_REAL_300DPI_RASTER", json.dumps({
        "source_b": result["source_svg_gate"],
        "two_views": list(result["png"]),
        "route": result["new_route_completed_nets"],
        "hostile_rejected": result["actual_source_24_negative_rejections"],
        "release": result["global_print_release"],
    }))


if __name__ == "__main__":
    main()
