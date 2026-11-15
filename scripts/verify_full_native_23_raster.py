"""Source-native 23-part actual SVG/PNG 300DPI physical target pixel proof.

The foreground diagnostic green squares must be sampled IN THE RENDERED
RASTER, not merely found in the XML. Clean output must have no colored ink.
Only original 16 real TL494 physical PinRefs are enabled.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

NS = "{http://www.w3.org/2000/svg}"
EXPECTED = frozenset(str(n) for n in range(1, 17))


def _actual_sheet(folder: Path, stem: str):
    root = ET.fromstring((folder/(stem+".svg")).read_text(encoding="utf-8"))
    if len(root.findall(f".//{NS}g[@data-layer='symbols']")) != 23:
        raise ValueError("NATIVE_23_CATALOG_GRAPHICS_LOST")
    leads = root.findall(
        f".//{NS}g[@data-layer='ic-physical-pin-leads']/{NS}line"
    )
    by_number = {l.get("data-pin-number"): l for l in leads}
    if len(leads) != 16 or set(by_number) != EXPECTED:
        raise ValueError("NATIVE_TI_16_REAL_TERMINAL_INVENTORY_WRONG")
    marks = root.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect"
    )
    viewport = [Decimal(p) for p in root.get("viewBox").split()]
    with Image.open(folder/(stem+"-300dpi.png")) as image:
        raster = image.convert("RGB")
        assert abs(image.width - round(
            float(Decimal(root.get("width").removesuffix("mm")))
            * 300 / 25.4,
        )) <= 1
        if stem.endswith("_clean"):
            assert not marks, "NATIVE_CLEAN_PRINT_HAS_GREEN_CONTACT_MARKERS"
            rr, gg, bb = raster.split()
            assert ImageChops.difference(rr, gg).getbbox() is None
            assert ImageChops.difference(rr, bb).getbbox() is None
            return 0
        if len(marks) != 16:
            raise ValueError("NATIVE_16_FOREGROUND_TARGETS_MISSING")
        # Image pixels are rounded nearest; target is 0.7mm wide = 8.3px,
        # so its center must remain truly GREEN, NOT overwritten by wires.
        total = 0
        for marker in marks:
            number = marker.get("data-pin-number")
            line = by_number[number]
            expected_center = (
                Decimal(line.get("x2")), Decimal(line.get("y2")),
            )
            actual_center = (
                Decimal(marker.get("x")) + Decimal("0.35"),
                Decimal(marker.get("y")) + Decimal("0.35"),
            )
            assert expected_center == actual_center
            assert marker.get("data-pin-ref") == "DA1."+number
            assert marker.get("data-connectable") == "true"
            assert marker.get("data-manufacturer-electrical-type")
            assert marker.get("data-net-id")
            x = round(float(actual_center[0]-viewport[0])*300/25.4)
            y = round(float(actual_center[1]-viewport[1])*300/25.4)
            red, green, blue = raster.getpixel((x, y))
            assert green > red + 35 and green > blue + 20, (
                "NATIVE_GREEN_SQUARE_HIDDEN_BY_COPPER",
                stem, number, (red, green, blue),
            )
            total += 1
        layers = root.findall(
            f"./{NS}g[@data-layer='editor-connection-targets']"
        )
        assert len(layers) == 1
        assert layers[0].get("data-layer-order") == "after-all-copper"
        return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    samples = {}
    for mode in ("horizontal", "top_to_bottom", "bottom_to_top"):
        for suffix in ("clean", "diagnostic"):
            name = f"TL494_native_23_{mode}_{suffix}"
            samples[name] = _actual_sheet(args.folder, name)
    assert sum(samples.values()) == 48
    (args.folder/"native_23_GREEN_PIXEL_PRINT_VERIFICATION.json").write_text(
        json.dumps({
            "status": "DRAFT_TRUE_300DPI_PNG_GLYPH_AND_PIN_ENDPOINTS",
            "all_16_TI_numbers_have_real_ink": True,
            "3_modes_48_verified_green_pixels": sum(samples.values()),
            "clean_0_editor_markers_monochrome": True,
            "source_pinrefs": sorted(EXPECTED, key=int),
            "cases": samples,
        }, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print("PASS full native 23 source: 48 foreground true-green pixels"
          " at PinRef ends / 3 clean grayscale true PNG300dpi")


if __name__ == "__main__":
    main()
