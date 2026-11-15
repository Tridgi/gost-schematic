"""Independent 300DPI raster verification of TL494 V3 source-typed ink.

No emulated text boxes, no fake connection marks added to pixels.
Read 48 real renderer SVGs plus matching librsvg PNGs.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

SVG = "{http://www.w3.org/2000/svg}"
DPI = 300


def verify(folder: Path):
    clean = sorted(folder.glob("tl494-16-*-clean.svg"))
    assert len(clean) == 24, "TL494_16_D4_CLEAN_SET_MISSING"
    report = {"status": "DRAFT_TRUE_OPENGOST_REAL_RASTER", "cases": {}}
    for source in clean:
        stem = source.name.removesuffix("-clean.svg")
        a = ET.fromstring(source.read_text(encoding="utf-8"))
        b = ET.fromstring(
            (folder / f"{stem}-diagnostic.svg").read_text(encoding="utf-8")
        )
        assert a.get("data-font-sha256") == b.get("data-font-sha256")
        assert a.get("data-function-reading-local") in (
            "bottom_to_top", "top_to_bottom", "horizontal",
        )
        assert a.get("data-typography-profile") == "tl494_portrait_v3_draft"
        assert "editor-connection-targets" not in ET.tostring(
            a, encoding="unicode",
        )
        leads = {
            node.get("data-pin-id"): node for node in a.findall(
                f".//{SVG}line[@data-pin-id]",
            )
        }
        assert len(leads) == 16
        targets = b.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect",
        )
        assert len(targets) == 16
        x0, y0, _, _ = (
            float(x) for x in b.get("viewBox").split()
        )
        labels = a.findall(f".//{SVG}text[@data-kind='pin-label']")
        assert len(labels) == 16
        assert all(len(el.text) <= 6 for el in labels)
        by_no = {el.get("data-physical-pin-number"): el for el in labels}
        assert by_no["3"].text == "FB"
        assert by_no["3"].get("data-full-manufacturer-name") == "FEEDBACK"
        assert by_no["13"].text == "OC"
        assert by_no["13"].get("data-full-manufacturer-name") == "OUTPUT CTRL"
        with Image.open(folder / f"{stem}-clean-300dpi.png") as img:
            raster = img.convert("RGB")
            dims = (
                round(float(a.get("width").removesuffix("mm")) * DPI / 25.4),
                round(float(a.get("height").removesuffix("mm")) * DPI / 25.4),
            )
            assert all(abs(u - v) <= 1 for u, v in zip(
                raster.size, dims, strict=True,
            ))
            rr, gg, bb = raster.split()
            assert ImageChops.difference(rr, gg).getbbox() is None
            assert ImageChops.difference(rr, bb).getbbox() is None
        glyphs = b.findall(
            f".//{SVG}g[@data-layer='measured-individual-glyph-ink']/{SVG}rect",
        )
        assert glyphs, f"TL494_REAL_FREETYPE_GLYPHS_NOT_RECORDED: {stem}"
        x_origin, y_origin, _, _ = (
            float(x) for x in a.get("viewBox").split()
        )
        dark_count = 0
        for box in glyphs[::max(1, len(glyphs)//75)]:
            xx = float(box.get("x"))
            yy = float(box.get("y"))
            ww = float(box.get("width"))
            hh = float(box.get("height"))
            scale = DPI/25.4
            crop = (
                max(0, int((xx-x_origin)*scale)-3),
                max(0, int((yy-y_origin)*scale)-3),
                min(raster.width, int((xx+ww-x_origin)*scale)+4),
                min(raster.height, int((yy+hh-y_origin)*scale)+4),
            )
            assert crop[0] < crop[2] and crop[1] < crop[3]
            assert raster.crop(crop).convert("L").getextrema()[0] < 150
            dark_count += 1
        actual_rgb = []
        with Image.open(folder / f"{stem}-diagnostic-300dpi.png") as im:
            colored = im.convert("RGB")
            for mark in targets:
                ident = mark.get("data-pin-id")
                lead = leads[ident]
                center = (
                    Decimal(mark.get("x")) + Decimal("0.35"),
                    Decimal(mark.get("y")) + Decimal("0.35"),
                )
                assert center == (
                    Decimal(lead.get("x2")), Decimal(lead.get("y2")),
                )
                assert mark.get("data-pin-number") == lead.get("data-pin-number")
                assert mark.get("data-pin-ref") == (
                    "DA1." + lead.get("data-pin-number")
                )
                px = round((float(center[0]) - x0) * DPI / 25.4)
                py = round((float(center[1]) - y0) * DPI / 25.4)
                red, green, blue = colored.getpixel((px, py))
                assert green > red + 35 and green > blue + 20
                actual_rgb.append((red, green, blue))
        report["cases"][stem] = {
            "physical_pin_count": 16,
            "green_vector_point_pixel_checks": len(actual_rgb),
            "measured_glyph_raster_checks": dark_count,
            "all_printed_aliases_max6": True,
            "source_full_names_retained": True,
            "angle": a.get("data-function-reading-local"),
        }
    assert len(report["cases"]) == 24
    (folder / "tl494-16pin-raster-300dpi-proof.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(
        "PASS genuine TL494 OpenGost 300DPI:",
        len(clean), "clean/diagnostic pairs,",
        sum(r["green_vector_point_pixel_checks"] for r in report["cases"].values()),
        "real pin marker pixels",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output_dir)


if __name__ == "__main__":
    main()
