"""Independently verify 300DPI PAINT/ELEKTRIK DRAFT SVG/PNG review artifacts.

Every SVG terminal is checked against the typed physical Circuit PinRef
coordinate recorded by the example generator, with ZERO micrometre tolerance.
Every PNG must have physical 300 DPI dimensions and metadata. This script does
NOT certify any manufacturer IC or ESKD drawing.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

SVG_NS = "{http://www.w3.org/2000/svg}"
EXPECTED_CASES = {
    "TEST_IC_ANALOG_8": (8, 1),
    "TEST_IC_DIGITAL_14": (14, 2),
    "TEST_IC_DIGITAL_40": (40, 2),
    "TEST_IC_DIGITAL_64": (64, 2),
}


def _um_from_mm_string(value: str) -> int:
    exact = Decimal(value) * 1000
    if exact != int(exact):
        raise ValueError("IC_VISUAL_FRACTIONAL_MICROMETRE")
    return int(exact)


def _read_svg(svg: Path, case: dict, unit: dict, *, diagnostic: bool) -> tuple[float, float]:
    source = svg.read_bytes()
    expected_hash = unit[
        "diagnostic_svg_sha256" if diagnostic else "svg_sha256"
    ]
    assert hashlib.sha256(source).hexdigest() == expected_hash, svg
    root = ET.fromstring(source)
    assert root.tag == SVG_NS + "svg"
    assert root.get("data-approval") == "DRAFT"
    assert root.get("data-pin-anchor-authority") == "external-resolved-only"
    overlays = root.findall(f".//{SVG_NS}g[@data-layer='ic-review-ink']")
    assert bool(overlays) is diagnostic
    links = root.findall(
        f".//{SVG_NS}g[@data-layer='ic-physical-pin-leads']/{SVG_NS}line"
    )
    expected = set(unit["physical_numbers"])
    assert len(links) == len(expected)
    assert len(links) == len(unit["physical_numbers"])
    seen = set()
    reference = unit["refdes"].split(".")[0]
    for line in links:
        number = line.get("data-pin-number")
        assert number in expected and number not in seen
        seen.add(number)
        coords = case["pinrefs"][f"{reference}:{number}"]
        assert _um_from_mm_string(line.get("x2")) == coords[0]
        assert _um_from_mm_string(line.get("y2")) == coords[1]
        assert line.get("data-real-anchor") == "true"
    assert seen == expected
    width = root.get("width", "")
    height = root.get("height", "")
    assert width.endswith("mm") and height.endswith("mm")
    return float(width[:-2]), float(height[:-2])


def verify(directory: Path) -> int:
    manifest = json.loads((directory / "joint-ic-qa-manifest.json").read_text("utf-8"))
    assert manifest["approval"] == "DRAFT"
    assert manifest["pinout_source"] == (
        "SYNTHETIC_TEST_ONLY_NOT_A_MANUFACTURER_PART"
    )
    assert set(manifest["cases"]) == set(EXPECTED_CASES)
    verified_pairs = set()
    for key, (pin_count, unit_count) in EXPECTED_CASES.items():
        case = manifest["cases"][key]
        assert case["component_instance_count"] == 1
        assert case["physical_pin_count"] == pin_count
        assert case["logical_unit_count"] == unit_count
        assert len(case["pinrefs"]) == pin_count
        assert len(case["units"]) == unit_count
        all_numbers = set()
        for unit in case["units"]:
            numbers = set(unit["physical_numbers"])
            assert not (all_numbers & numbers)
            all_numbers.update(numbers)
            for diagnostic in (False, True):
                svg_name = unit[
                    "diagnostic_filename" if diagnostic else "filename"
                ]
                assert svg_name not in verified_pairs
                verified_pairs.add(svg_name)
                svg_path = directory / svg_name
                w_mm, h_mm = _read_svg(
                    svg_path, case, unit, diagnostic=diagnostic,
                )
                png_path = svg_path.with_suffix(".png")
                assert png_path.is_file()
                with Image.open(png_path) as png:
                    dpi = png.info.get("dpi")
                    assert dpi and all(abs(v - 300) < 0.5 for v in dpi), (
                        png_path, dpi,
                    )
                    expected_px = (w_mm * 300 / 25.4, h_mm * 300 / 25.4)
                    assert all(
                        abs(actual - expected) <= 2
                        for actual, expected in zip(
                            png.size, expected_px, strict=True,
                        )
                    ), (png_path, png.size, expected_px)
        assert len(all_numbers) == pin_count
    assert len(verified_pairs) == 14
    assert {p.name for p in directory.glob("*.svg")} == verified_pairs
    assert {p.with_suffix(".svg").name for p in directory.glob("*.png")} == (
        verified_pairs
    )
    return len(verified_pairs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    total = verify(args.output_dir)
    print(f"DRAFT joint IC physical-300DPI evidence: {total} SVG/PNG pairs PASS")


if __name__ == "__main__":
    main()
