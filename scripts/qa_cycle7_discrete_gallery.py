"""Real owner-branch 3 DRAFT UGO gallery (not a substitute GOST drawing).

Loads exact owner YGO2 symbol & physical JSON via REAL production parsers,
renders actual SVG with production render_symbol_svg(), inspects XML and
rasterizes exact SVG with CairoSVG at 300 DPI. Pin maps are abstract labels:
no manufacturer datasheet or physical package number has been established.
"""
import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cycle7_support import BLOBS, IDS, OWNER_SHA, owner_symbol_part

from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"


def run(output):
    import cairosvg
    from PIL import Image

    output.mkdir(parents=True, exist_ok=True)
    photos = {}
    summaries = {}
    for key, identifier in IDS.items():
        symbol, part = owner_symbol_part(key)
        topology = inspect_conductor_topology(symbol)
        assert topology.valid
        assert len(topology.pin_islands) == len(part.pins)
        for review in (False, True):
            kind = "diagnostic" if review else "clean"
            filename = f"qa-cycle7-{key}-{kind}"
            svg_text = render_symbol_svg(symbol, review_overlay=review)
            svg = ET.fromstring(svg_text)
            assert svg.tag == SVG + "svg"
            assert not svg.findall(f".//{SVG}image")
            assert all(x.get("status") != "approved" for x in svg)
            if review:
                circles = svg.findall(f".//{SVG}circle")
                assert len(circles) == len(part.pins)
                points = {
                    (round(float(c.get("cx")) * 1000),
                     round(float(c.get("cy")) * 1000))
                    for c in circles
                }
                assert points == {
                    (x.at.x, x.at.y) for x in symbol.pins
                }
            assert svg.findall(f".//{SVG}line")
            svg_path = output / (filename + ".svg")
            png_path = output / (filename + "-300dpi.png")
            svg_path.write_text(svg_text, encoding="utf-8")
            cairosvg.svg2png(
                bytestring=svg_text.encode("utf-8"),
                write_to=str(png_path), dpi=300,
            )
            with Image.open(png_path) as image:
                pixels = image.convert("RGB")
                count = sum(
                    1 for rgb in pixels.getdata() if max(rgb) < 96
                )
                assert count > 5, f"Rendered {identifier} blank at 300DPI"
                raster = (pixels.width, pixels.height, count)
            for file in (svg_path, png_path):
                raw = file.read_bytes()
                photos[file.name] = {
                    "sha256": sha256(raw).hexdigest(), "bytes": len(raw)
                }
            summaries[filename] = {
                "symbol_id": identifier,
                "DRAFT_not_approved": True,
                "physical_pin_numbers": [x.number for x in part.pins],
                "pin_islands": topology.pin_islands,
                "actual_dark_pixels": raster[-1],
                "png_pixels_wh": list(raster[:2]),
            }
    report = {
        "issue": 92,
        "owner_sha": OWNER_SHA,
        "blob_shas": BLOBS,
        "status": "PASS_THREE_PIN_ABSTRACT_DISCRETE_ONLY",
        "missing": [
            "BJT NPN/PNP", "MOSFET N/P", "Schottky", "LED",
            "photodiode", "varicap", "physical connector",
            "named network continuation", "real DA/DD IC",
        ],
        "files": photos,
        "specimens": summaries,
        "note": (
            "These are actual code-rendered DRAFT examples, not a complete "
            "E3 board or ESKD normative approval"
        ),
    }
    (output / "qa-cycle7-discrete-gallery.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output_dir))
