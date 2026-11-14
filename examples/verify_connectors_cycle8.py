"""Verify real metric 300DPI connector review images and physical endpoints."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

from examples.review_connectors_cycle8 import IDS, SIZE_MM

SVG = "{http://www.w3.org/2000/svg}"
DPI = Decimal(300)


def verify(directory: Path) -> dict:
    manifest = json.loads(
        (directory / "cycle8-connectors-manifest.json").read_text(encoding="utf-8")
    )
    if (manifest["gallery_count"] != len(IDS)
        or set(manifest["symbols"]) != set(IDS)
        or manifest["approved_count"] != 0
        or not manifest["approval"].startswith("BLOCKED")):
        raise ValueError("Connector manifest improperly approved or incomplete")
    result = []
    for filename in manifest["files"]:
        path = directory / filename
        root = ET.fromstring(path.read_bytes())
        diagnostic = filename.endswith("-diagnostic.svg")
        marks = root.findall(f".//{SVG}rect[@data-editor-target='true']")
        keepouts = root.findall(f".//{SVG}rect[@data-keepout='true']")
        expected = (sum(len(c["physical_pin_roles"]) for c in manifest["symbols"].values())
                    if filename.startswith("cycle8-")
                    else len(manifest["symbols"][root.get("data-symbol-id")][
                        "physical_pin_roles"]))
        if root.get("data-approval") != "DRAFT":
            raise ValueError(f"{filename}: unauthorized approval")
        if diagnostic:
            if len(marks) != expected:
                raise ValueError(f"{filename}: diagnostic squares mismatch")
            if not keepouts:
                raise ValueError(f"{filename}: body keepout missing")
        elif marks or keepouts:
            raise ValueError(f"{filename}: editor-only squares leaked into clean SVG")
        if not root.findall(f".//{SVG}line"):
            raise ValueError(f"{filename}: no true SVG lines")
        if root.findall(f".//{SVG}image"):
            raise ValueError(f"{filename}: fake bitmap used instead of UGO strokes")
        if filename.startswith("cycle8-"):
            groups = root.findall(f".//{SVG}g[@data-symbol-id]")
            if len(groups) != len(IDS):
                raise ValueError("Missing gallery member")
            if [g.get("data-symbol-id") for g in groups] != list(IDS):
                raise ValueError("Physical gallery ordering mismatch")
            dimensions = [Decimal(n) for n in SIZE_MM]
        else:
            dimensions = [
                Decimal(root.attrib[key].removesuffix("mm"))
                for key in ("width", "height")
            ]
            identifier = root.get("data-symbol-id")
            if identifier not in manifest["symbols"]:
                raise ValueError("Unknown closeup symbol")
            card = manifest["symbols"][identifier]
            if (hashlib.sha256(path.read_bytes()).hexdigest()
                != card["closeup_svg_sha256"][
                    "diagnostic" if diagnostic else "clean"
                ]):
                raise ValueError("SVG passport hash mismatch")
            if diagnostic:
                coords = card["graphic_pin_coordinate_um"]
                for marker in marks:
                    pin = marker.attrib["data-pin-number"]
                    center_x = Decimal(marker.attrib["x"]) + Decimal("0.65")
                    center_y = Decimal(marker.attrib["y"]) + Decimal("0.65")
                    if (center_x != Decimal(coords[pin][0]) / 1000
                        or center_y != Decimal(coords[pin][1]) / 1000):
                        raise ValueError(f"{identifier}: marker not physical endpoint")
        with Image.open(path.with_suffix(".png")) as img:
            img.load()
            expected_px = [m * DPI / Decimal("25.4") for m in dimensions]
            if any(abs(Decimal(p) - e) > 2
                   for p, e in zip(img.size, expected_px)):
                raise ValueError(f"{filename}: incorrect 300DPI mm scale")
            if ImageChops.difference(
                img.convert("RGB"), Image.new("RGB", img.size, "white")
            ).getbbox() is None:
                raise ValueError(f"{filename}: blank image")
            size = img.size
        result.append({"file": filename, "dpi": 300, "px": list(size)})
    report = {
        "status": "DRAFT_GRAPHICS_AND_PINS_PASS",
        "normative_approval": False,
        "manufacturer_pinmap_verified": False,
        "total_svg_png_pairs": len(result),
        "results": result,
    }
    (directory / "cycle8-raster-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(verify(args.output_dir))


if __name__ == "__main__":
    main()
