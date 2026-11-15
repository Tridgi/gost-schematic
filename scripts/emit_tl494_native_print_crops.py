"""1:1 A3 and enlarged crops of already native-rendered 23-part Circuit.

This tool makes viewing windows ONLY; it never modifies drawing primitives,
sources a new Net, changes pin numbers, text, UGO or end points. Formal
multisheet E3 with reciprocal destination addresses is NOT synthesized.
"""
import argparse
import copy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.units import format_mm

NS = "{http://www.w3.org/2000/svg}"
A3_MM = (420, 297)
PAGE_WINDOW = (390, 250)

REGIONS_MM = {
    "DA1_PWM": (34, 79, 117, 90),
    "R5_R6_wiring": (-154, 147, 112, 85),
    "VD1_Schottky": (245, 105, 62, 65),
    "VT1_MOS": (147, 110, 63, 61),
    "C1_C2": (195, 10, 65, 77),
    "b_R5_continuation": (-154, 194, 44, 40),
    "b_X2_continuation": (427, 23, 61, 49),
}


def _plot(original: ET.Element, bounds, *, physical: bool):
    x, y, width, height = bounds
    if physical:
        canvas = ET.Element(NS+"svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{A3_MM[0]}mm", "height": f"{A3_MM[1]}mm",
            "viewBox": f"0 0 {A3_MM[0]} {A3_MM[1]}",
            "data-view": "A3_1_TO_1_NATIVE_CIRCUIT_REVIEW_TILE",
            "data-e3-multisheet-certified": "false",
        })
        ET.SubElement(canvas, NS+"rect", {
            "x": "15", "y": "20", "width": str(PAGE_WINDOW[0]),
            "height": str(PAGE_WINDOW[1]),
            "stroke": "#000000", "stroke-width": "0.25",
            "fill": "none",
        })
        viewport = ET.SubElement(canvas, NS+"svg", {
            "x": "15", "y": "20", "width": str(PAGE_WINDOW[0]),
            "height": str(PAGE_WINDOW[1]),
            "viewBox": f"{x} {y} {width} {height}",
            "overflow": "hidden",
        })
        title = ET.SubElement(canvas, NS+"text", {
            "x": "15", "y": "280", "font-size": "3.5",
            "font-family": "OpenGOST type A", "fill": "#000000",
        })
        title.text = "DRAFT 1:1 REVIEW TILE — NOT A SIGNED MULTISHEET E3"
    else:
        canvas = ET.Element(NS+"svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "220mm", "height": "155mm",
            "viewBox": f"{x} {y} {width} {height}",
            "data-view": "LARGE_NATIVE_INK_DETAIL_NOT_PRINT_SCALE",
        })
        viewport = canvas
    for element in original:
        if element.tag in (NS+"title", NS+"desc"):
            continue
        viewport.append(copy.deepcopy(element))
    canvas.set("data-original-geometry", "UNMODIFIED_FULL_NATIVE_23_PART_RENDER")
    return ET.tostring(canvas, encoding="unicode")+"\n"


def generate(folder: Path):
    cases = {
        "BEFORE": "TL494_native_23_BEFORE_old_pwm_top_to_bottom.svg",
        "AFTER_clean": "TL494_native_23_bottom_to_top_clean.svg",
        "AFTER_diagnostic": "TL494_native_23_bottom_to_top_diagnostic.svg",
    }
    manifest = {
        "status": "DRAFT_TRUE_PRINT_NATIVE_23_NO_E3_SPLIT_APPROVAL",
        "paper_mm": list(A3_MM),
        "source_mm_per_paper_mm": 1,
        "files": [],
    }
    for tag, original_name in cases.items():
        original = ET.fromstring((folder/original_name).read_text(encoding="utf-8"))
        assert original.get("data-native-ic-composition") == (
            "exact-circuit-pinrefs"
        )
        assert len(original.findall(
            f"./{NS}g[@data-layer='symbols']"
        )) == 23
        x, y, w, h = (float(value) for value in original.get("viewBox").split())
        if w > 760 or h > PAGE_WINDOW[1]:
            raise ValueError(
                f"NATIVE_A3_TWO_TILES_NOT_FIT: {w}x{h} mm; "
                "do NOT shrink source symbols to hide bad print size"
            )
        top = y - (PAGE_WINDOW[1]-h)/2
        starts = (x, x+370)
        if starts[1]+PAGE_WINDOW[0] < x+w:
            raise AssertionError("NATIVE_A3_TILES_DO_NOT_COVER_SOURCE_INK")
        for index, left in enumerate(starts, 1):
            filename = f"native_{tag}_A3_1to1_tile{index}.svg"
            (folder/filename).write_text(_plot(
                original, (
                    format_mm(round(left*1000)),
                    format_mm(round(top*1000)),
                    PAGE_WINDOW[0], PAGE_WINDOW[1],
                ), physical=True,
            ), encoding="utf-8")
            manifest["files"].append({
                "name": filename, "view": tag, "paper": "A3",
                "physical_mm": list(A3_MM),
                "scale": "1:1 SOURCE MILLIMETRES",
                "not_a_legal_multisheet_e3": True,
            })
        for name, bounds in REGIONS_MM.items():
            filename = f"native_{tag}_detail_{name}.svg"
            (folder/filename).write_text(
                _plot(original, bounds, physical=False),
                encoding="utf-8",
            )
            manifest["files"].append({
                "name": filename, "view": tag,
                "paper_mm": [220,155],
                "source_window_mm": list(bounds),
                "scale": "ENLARGED_DISPLAY_NOT_TRUE_PRINT_1_TO_1",
            })
    manifest["native_input_count"] = len(cases)
    manifest["A3_1_to_1_count"] = sum(
        entry.get("paper") == "A3" for entry in manifest["files"]
    )
    manifest["enlargement_count"] = len(manifest["files"])-manifest["A3_1_to_1_count"]
    assert manifest["A3_1_to_1_count"] == 6
    assert manifest["enlargement_count"] == 21
    (folder/"TL494_native_23_A3_and_details_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print("PASS 6 A3 1:1 native 23-part views + 21 large crops (DRAFT)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
