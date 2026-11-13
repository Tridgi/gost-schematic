"""Check real 300 DPI raster output from genuine metric-size SVG; no OCR."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

DPI = Decimal(300)
MM_PER_INCH = Decimal("25.4")


def verify(folder: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] != "DRAFT" or len(manifest["files"]) != 6:
        raise ValueError("Expected six DRAFT SVG from three physical part families")
    raster = []
    for filename in manifest["files"]:
        svg_path = folder / filename
        svg_bytes = svg_path.read_bytes()
        root = ET.fromstring(svg_bytes)
        symbol_id = root.attrib["data-symbol-id"]
        kind = root.attrib["data-view"]
        if (manifest["symbols"][symbol_id]["svg_sha256"][kind]
            != hashlib.sha256(svg_bytes).hexdigest()):
            raise ValueError(f"{filename}: real SVG hash differs from manifest")
        if root.attrib["data-approval"] != "DRAFT":
            raise ValueError(f"{filename}: unauthorized normative approval")
        dims_mm = []
        for dim in ("width", "height"):
            text = root.attrib[dim]
            if not text.endswith("mm"):
                raise ValueError(f"{filename}: explicit physical millimetres required")
            dims_mm.append(Decimal(text[:-2]))
        png_path = svg_path.with_suffix(".png")
        with Image.open(png_path) as image:
            image.load()
            actual = image.size
            expected = tuple(dim * DPI / MM_PER_INCH for dim in dims_mm)
            if any(abs(Decimal(real) - target) > 2 for real, target in zip(actual, expected)):
                raise ValueError(
                    f"{png_path.name}: not 300-DPI physical SVG raster "
                    f"(got {actual}, expected {expected})"
                )
            if image.mode not in ("RGB", "RGBA"):
                raise ValueError("PNG color format is not supported")
            if ImageChops.difference(
                image.convert("RGB"), Image.new("RGB", actual, "white")
            ).getbbox() is None:
                raise ValueError(f"{png_path.name}: empty/white specimen")
        raster.append({
            "svg": filename, "png": png_path.name,
            "status": "PASS", "claimed_dpi": 300,
            "source_physical_mm": [str(x) for x in dims_mm],
            "actual_px": list(actual),
            "svg_sha256": hashlib.sha256(svg_bytes).hexdigest(),
            "png_sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
        })
    results = {
        "issue": 89,
        "status": "PASS_DRAFT_SPECIMENS_NOT_NORMATIVE_APPROVAL",
        "raster_count": len(raster),
        "target_dpi": 300,
        "samples": raster,
    }
    (folder / "raster-report.json").write_text(
        json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Verified {len(raster)} independent 300-DPI PNG vs metric SVG samples")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output_dir)


if __name__ == "__main__":
    main()
