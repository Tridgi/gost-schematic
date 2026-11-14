"""Exact 16-lead real PAINT 300-DPI TL494CN photo-grade print/debug gate.

No screenshot OCR. Source model and SVG XML are authoritative, raster RGB is
an independent check. Synthetic paper proof != manufacturer behavior or GOST.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


def verify(folder: Path) -> dict:
    manifest = json.loads(
        (folder / "TL494CN_ic_manifest.json").read_text(encoding="utf-8"),
    )
    if manifest["physical_count"] != 16 or len(manifest["variants"]) != 4:
        raise ValueError("TL494_16_PIN_TWO_ANGLE_TWO_MODE_COVERAGE")
    if (
        manifest["types"]["3"] != "input"
        or manifest["types"]["13"] != "input"
        or manifest["short_labels"]["3"] != "FB"
        or manifest["short_labels"]["13"] != "OC"
    ):
        raise ValueError("TL494_TI_PIN_ALIAS_SEMANTIC_MISMATCH")
    truth = manifest["world_pinref_points_um"]
    if set(truth) != {f"DA1.{n}" for n in range(1, 17)}:
        raise ValueError("TL494_WRONG_PHYSICAL_REF_SET")
    for name in manifest["variants"]:
        if name not in {
            f"TL494CN_PWM_{angle}_{layer}"
            for angle in ("bottom_to_top_270", "horizontal_0")
            for layer in ("diagnostic", "clean")
        }:
            raise ValueError("TL494_UNEXPECTED_EXPORT_NAME")
    markers_checked = 0
    for angle in ("bottom_to_top_90", "horizontal_0"):
        pair = []
        for mode in ("clean", "diagnostic"):
            stem = f"TL494CN_PWM_{angle}_{mode}"
            svg_file = folder / (stem + ".svg")
            png_file = folder / (stem + ".png")
            root = ET.fromstring(svg_file.read_text(encoding="utf-8"))
            width = root.get("width", "")
            height = root.get("height", "")
            if not width.endswith("mm") or not height.endswith("mm"):
                raise ValueError("TL494_NOT_REAL_PRINT_MM")
            viewbox = [float(n) for n in root.attrib["viewBox"].split()]
            if len(viewbox) != 4:
                raise ValueError("TL494_WRONG_SVG_VIEWPORT")
            function = [
                n for n in root.iter() if n.get("data-kind") == "function"
            ]
            if len(function) != 1 or function[0].text != "PWM":
                raise ValueError("TL494_MISSING_WHOLE_PWM_WORD")
            transform = function[0].get("transform", "")
            if angle == "bottom_to_top_90":
                if not transform.startswith("matrix(0 -1 1 0 "):
                    raise ValueError("TL494_WRONG_PWM_DIRECTION")
            elif transform:
                raise ValueError("TL494_HORIZONTAL_HAS_UNWANTED_TRANSFORM")
            fields = [
                n for n in root.iter() if n.get("data-kind") == "pin-label"
            ]
            actual_labels = [n.text for n in fields]
            if len(actual_labels) != 16 or (
                sorted(actual_labels)
                != sorted(manifest["short_labels"].values())
            ):
                raise ValueError("TL494_PIN_LABELS_NOT_16_OR_NOT_ALIASED")
            if any(x in actual_labels for x in ("FEEDBACK", "OUTPUT CTRL")):
                raise ValueError("TL494_MANUFACTURER_TEXT_OVERFLOWED_LABELS")
            numbers = [
                n for n in root.iter() if n.get("data-kind") == "pin-number"
            ]
            if len(numbers) != 16 or {
                n.text for n in numbers
            } != {str(n) for n in range(1, 17)}:
                raise ValueError("TL494_PHYSICAL_PIN_NUMBERS_NOT_PRINTED")
            leads = [
                n for layer in root.iter()
                if layer.get("data-layer") == "ic-physical-pin-leads"
                for n in layer if n.tag.endswith("line")
            ]
            if len(leads) != 16:
                raise ValueError("TL494_16_LEADS_INCOMPLETE")
            for line in leads:
                n = line.attrib["data-pin-number"]
                physical = truth[f"DA1.{n}"]
                if (
                    float(line.attrib["x2"]) * 1000 != physical[0]
                    or float(line.attrib["y2"]) * 1000 != physical[1]
                ):
                    raise ValueError("TL494_1UM_LEAD_SHIFT")
            with Image.open(png_file) as image:
                if image.mode not in ("RGB", "RGBA"):
                    raise ValueError("TL494_RASTER_NOT_RGB")
                dpi = image.info.get("dpi")
                if dpi is None or any(abs(d - 300) > 1 for d in dpi):
                    raise ValueError("TL494_REAL_300DPI_METADATA_MISSING")
                pixels = image.convert("RGB")
            if pixels.width < 500 or pixels.height < 500:
                raise ValueError("TL494_RASTER_TOO_SMALL_TO_READ")
            markers = [
                node for g in root.iter()
                if g.get("data-layer") == "editor-connection-targets"
                for node in g if node.tag.endswith("rect")
            ]
            if mode == "diagnostic":
                if len(markers) != 16:
                    raise ValueError("TL494_DIAGNOSTIC_MARKER_COUNT")
                by_ref = {m.get("data-pin-ref"): m for m in markers}
                if set(by_ref) != set(truth):
                    raise ValueError("TL494_DIAGNOSTIC_FOREIGN_PHYSICAL_REF")
                for ref, position in truth.items():
                    m = by_ref[ref]
                    if m.get("fill") != "#148645" or (
                        m.get("data-connectable") != "true"
                    ):
                        raise ValueError("TL494_POWER_OR_PIN_WRONGLY_DISABLED")
                    x = round(
                        (position[0] / 1000 - viewbox[0])
                        / viewbox[2] * pixels.width,
                    )
                    y = round(
                        (position[1] / 1000 - viewbox[1])
                        / viewbox[3] * pixels.height,
                    )
                    if x < 3 or y < 3 or (
                        x >= pixels.width - 3 or y >= pixels.height - 3
                    ):
                        raise ValueError("TL494_ENDPOINT_OUTSIDE_REAL_PRINT")
                    if pixels.getpixel((x, y)) != (20, 134, 69):
                        raise ValueError("TL494_GREEN_PIXEL_MISSING")
                    markers_checked += 1
            elif markers:
                raise ValueError("TL494_MARKERS_LEAK_INTO_CLEAN")
            pair.append({
                "angle": angle, "mode": mode, "size": pixels.size,
                "viewbox": viewbox, "svg_file": svg_file.name,
            })
        if pair[0]["size"] != pair[1]["size"] or (
            pair[0]["viewbox"] != pair[1]["viewbox"]
        ):
            raise ValueError("TL494_DEBUG_ALTERED_REAL_PRINT_GEOMETRY")
    if markers_checked != 32:
        raise ValueError("TL494_TOTAL_32_DIAGNOSTIC_MARKERS_MISSING")
    return {"result": "PASS", "angles": 2, "files": 8,
            "marker_pixels": markers_checked, "physical_pins": 16}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output_dir), sort_keys=True))


if __name__ == "__main__":
    main()
