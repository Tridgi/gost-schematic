"""Independent image/physical-role audit of the combined 15-symbol 300DPI sheet."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

from examples.review_electronic_cycle7_extended import IDS

SVG = "{http://www.w3.org/2000/svg}"
METRIC_SIZE = (Decimal(275), Decimal(180))
EXPECTED_DPI = Decimal(300)


def verify(directory: Path) -> dict:
    manifest = json.loads(
        (directory / "cycle7-gallery-manifest.json").read_text(encoding="utf-8")
    )
    if (manifest["physical_ugo_count"] != len(IDS)
        or manifest["status"] != "DRAFT"
        or set(manifest["symbols"]) != set(IDS)
        or manifest["approved_count"]):
        raise ValueError("Gallery manifest is not the 15 actual DRAFT pairs")
    results = []
    for kind in ("clean", "diagnostic"):
        svg_path = directory / f"cycle7-all-15-{kind}.svg"
        png_path = svg_path.with_suffix(".png")
        root = ET.fromstring(svg_path.read_bytes())
        if (root.get("data-approval") != "DRAFT"
            or root.get("data-kind") != kind
            or tuple(Decimal(root.get(key).removesuffix("mm"))
                     for key in ("width", "height")) != METRIC_SIZE):
            raise ValueError("Physical SVG size/status mismatch")
        groups = root.findall(f".//{SVG}g[@data-symbol-id]")
        if len(groups) != len(IDS):
            raise ValueError("Missing visualized physical symbols")
        for index, item in enumerate(groups):
            sid = item.attrib["data-symbol-id"]
            if sid != IDS[index]:
                raise ValueError(f"Gallery order/identity mismatch at {index}")
            source = manifest["symbols"][sid]
            roles = source["physical_pin_role"]
            if (item.attrib["data-pin-numbers"].split(",") != list(roles)
                or item.attrib["data-physical-roles"].split(",") != list(
                    roles.values()
                )):
                raise ValueError(f"{sid}: graphic/physical PinRef disagreement")
            if not item.findall(f".//{SVG}line"):
                raise ValueError(f"{sid}: no genuine SVG geometry strokes")
        if root.findall(f".//{SVG}image"):
            raise ValueError("Embedded raster substitution detected")
        with Image.open(png_path) as img:
            img.load()
            actual = img.size
            if any(
                abs(Decimal(px) - length_mm * EXPECTED_DPI / Decimal("25.4")) > 2
                for px, length_mm in zip(actual, METRIC_SIZE)
            ):
                raise ValueError(f"{png_path.name}: not a real 300DPI mm render")
            if ImageChops.difference(
                img.convert("RGB"), Image.new("RGB", actual, "white")
            ).getbbox() is None:
                raise ValueError("Blank raster gallery")
        results.append({
            "kind": kind, "status": "PASS", "symbol_count": len(groups),
            "width_px": actual[0], "height_px": actual[1], "dpi": 300,
            "svg_sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
            "png_sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
        })
    report = {
        "issue": 89,
        "status": "DRAFT_VECTOR_GRAPHIC_AND_PHYSICAL_INTEROP_PASS",
        "normative_approval": False,
        "manufacturer_pinout_verified": False,
        "gallery_count": len(IDS),
        "results": results,
    }
    (directory / "cycle7-gallery-raster-report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Checked {len(IDS)} physical-role vectors in both 300 DPI galleries")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output_dir)


if __name__ == "__main__":
    main()
