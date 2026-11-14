"""Independent 300-DPI real PNG pixel and source PinRef provenance gate."""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


def verify(directory: Path) -> int:
    rows = json.loads(
        (directory / "physical-pinref-editor-manifest.json").read_text(
            encoding="utf-8",
        ),
    )["units"]
    if len(rows) != 14:
        raise ValueError("IC_EDITOR_EXPECTED_14_UNIT_ANGLE_VIEWS")
    total = 0
    for row in rows:
        diagnostic = directory / row["diagnostic_svg"]
        clean = directory / row["clean_svg"]
        diag_root = ET.fromstring(diagnostic.read_text(encoding="utf-8"))
        clean_root = ET.fromstring(clean.read_text(encoding="utf-8"))
        layers = [
            node for node in diag_root.iter()
            if node.get("data-layer") == "editor-connection-targets"
        ]
        if len(layers) != 1:
            raise ValueError("IC_EDITOR_DIAGNOSTIC_LAYER_MISSING")
        if any(node.get("data-layer") == "editor-connection-targets"
               for node in clean_root.iter()):
            raise ValueError("IC_EDITOR_LAYER_LEAK_IN_CLEAN_PRINT")
        layer = layers[0]
        if layer.get("data-physical-print") != "false":
            raise ValueError("IC_EDITOR_MARKERS_NOT_EXCLUDED_FROM_PRINT")
        markers = {e.get("data-pin-ref"): e for e in layer}
        if len(markers) != len(row["pinrefs"]):
            raise ValueError("IC_EDITOR_INCOMPLETE_OR_DUPLICATE_MARKERS")
        svg_box = [float(s) for s in diag_root.attrib["viewBox"].split()]
        clean_box = [float(s) for s in clean_root.attrib["viewBox"].split()]
        if len(svg_box) != 4 or len(clean_box) != 4:
            raise ValueError("IC_EDITOR_BAD_VIEWPORT")
        with Image.open(diagnostic.with_suffix(".png")) as original:
            diag = original.convert("RGB")
        with Image.open(clean.with_suffix(".png")) as original:
            plain = original.convert("RGB")
        if (diag.width, diag.height) != (plain.width, plain.height):
            raise ValueError("IC_EDITOR_PREVIEW_RASTER_MISMATCH")
        if svg_box != clean_box:
            raise ValueError("IC_EDITOR_VIEWPORT_CHANGED_ON_TOGGLE")
        for source in row["pinrefs"]:
            ref = ".".join(source["pin_ref"])
            marker = markers.get(ref)
            if marker is None:
                raise ValueError("IC_EDITOR_MISSING_PHYSICAL_PINREF")
            point = source["world_um"]
            expected = (
                "#148645" if source["connectable"] else "#8b1e27"
            )
            if marker.get("fill") != expected:
                raise ValueError("IC_EDITOR_WRONG_CONNECTABLE_COLOR")
            x, y = (coordinate / 1000 for coordinate in point)
            dx = round((x - svg_box[0]) / svg_box[2] * diag.width)
            dy = round((y - svg_box[1]) / svg_box[3] * diag.height)
            if not (2 <= dx < diag.width - 2 and
                    2 <= dy < diag.height - 2):
                raise ValueError("IC_EDITOR_MARKER_OUTSIDE_PAGE")
            ink = diag.getpixel((dx, dy))
            paper = plain.getpixel((dx, dy))
            if ink != tuple(
                int(expected[index:index + 2], 16) for index in (1, 3, 5)
            ):
                raise ValueError(
                    f"IC_EDITOR_WRONG_REAL_300DPI_PIXEL {ref} {ink} {expected}"
                )
            if max(paper) - min(paper) > 2:
                raise ValueError("IC_EDITOR_COLORED_MARKER_LEAKED_IN_CLEAN")
            total += 1
    if total != 2 * (8 + 14 + 40 + 64):
        raise ValueError("IC_EDITOR_PHYSICAL_PINREF_COUNT_CHANGED")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    n = verify(args.output_dir)
    print(f"PASS: {n} real physical PinRef marker pixels at 300 DPI")


if __name__ == "__main__":
    main()
