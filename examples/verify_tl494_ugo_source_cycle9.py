"""Independent SVG/PNG metric raster audit for 13 source selections + 64 D4."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

SVG = "{http://www.w3.org/2000/svg}"
DPI = Decimal(300)


def verify(directory: Path) -> dict:
    profile = json.loads(
        (directory / "TL494-UGO-cycle9-manifest.json").read_text(encoding="utf-8")
    )
    if (profile["status"] != "DRAFT_NO_ESKD_1TO1"
        or profile["normative_approved"] != 0
        or profile["gallery_count"] != 13
        or len(profile["d4"]) != 64
        or len(profile["files"]) != 92
        or not profile["source_1to1_status"].startswith("BLOCKED")):
        raise ValueError("Unapproved source-gallery status or content")
    if len(set(profile["files"])) != len(profile["files"]):
        raise ValueError("Duplicate gallery output name")
    metrics = []
    for file in profile["files"]:
        svg_path = directory / file
        root = ET.fromstring(svg_path.read_bytes())
        if root.findall(f".//{SVG}image"):
            raise ValueError(f"{file}: bitmap masquerades as original vector UGO")
        if not any(root.findall(f".//{SVG}{kind}") for kind
                   in ("line", "rect", "path", "circle")):
            raise ValueError(f"{file}: blank source UGO SVG")
        if (not root.attrib.get("width", "").endswith("mm")
            or not root.attrib.get("height", "").endswith("mm")):
            raise ValueError(f"{file}: SVG not in physical millimeters")
        expected = [
            Decimal(root.attrib[key].removesuffix("mm")) * DPI / Decimal("25.4")
            for key in ("width", "height")
        ]
        marked = root.findall(f".//{SVG}rect[@data-editor-target='true']")
        is_diag = file.endswith("-diagnostic.svg")
        if is_diag and not marked:
            raise ValueError(f"{file}: diagnostic green true pin endpoints missing")
        if not is_diag and marked:
            raise ValueError(f"{file}: green editor squares leaked into clean ink")
        if is_diag and root.attrib.get("data-reference"):
            declared = root.attrib["data-real-pin-coordinates-um"]
            expected_pins = {
                row.split(":")[0]: tuple(map(int, row.split(":")[1].split(",")))
                for row in declared.split(";")
            }
            if len(marked) != len(expected_pins):
                raise ValueError(f"{file}: fake or missing PhysicalPin square")
            for mark in marked:
                number = mark.attrib["data-physical-pin"]
                center = (
                    (Decimal(mark.attrib["x"]) + Decimal("0.6")) * 1000,
                    (Decimal(mark.attrib["y"]) + Decimal("0.6")) * 1000,
                )
                if center != expected_pins[number]:
                    raise ValueError(f"{file}: disconnected green PhysicalPin #{number}")
        with Image.open(svg_path.with_suffix(".png")) as png:
            png.load()
            size = png.size
            if any(abs(Decimal(px) - required) > 2
                   for px, required in zip(size, expected, strict=True)):
                raise ValueError(f"{file}: wrong physical 300 DPI raster scale")
            if ImageChops.difference(
                png.convert("RGB"), Image.new("RGB", size, "white")
            ).getbbox() is None:
                raise ValueError(f"{file}: blank actual PNG")
        metrics.append({
            "svg": file, "png": svg_path.with_suffix(".png").name,
            "size_px": list(size),
            "svg_sha256": hashlib.sha256(svg_path.read_bytes()).hexdigest(),
            "png_sha256": hashlib.sha256(
                svg_path.with_suffix(".png").read_bytes()
            ).hexdigest(),
        })
    report = {
        "metric_dpi": 300,
        "status": "PASS_ACTUAL_VECTOR_AND_RASTER_NOT_NORMATIVE_1TO1",
        "physical_source_approval": "BLOCKED_INDEPENDENT_ESKD_OVERLAY",
        "total_pairs": len(metrics),
        "original_photo_pixels_provided": False,
        "files": metrics,
    }
    (directory / "TL494-UGO-cycle9-300dpi-audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.output_dir)
    print(f"Verified {report['total_pairs']} native SVG and PNG 300 DPI pairs")


if __name__ == "__main__":
    main()
