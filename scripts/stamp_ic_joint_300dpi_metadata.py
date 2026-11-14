"""Add explicit physical 300 DPI PNG metadata to already rasterized DRAFT SVGs.

librsvg rsvg-convert respects --dpi-x/--dpi-y while choosing pixel size, but
does not always write PNG pHYs density metadata. This lossless PNG rewrite
does NOT resize an image or alter electrical/SVG coordinates.
"""

import argparse
from pathlib import Path

from PIL import Image


def stamp(directory: Path, expected_count: int = 14) -> int:
    paths = sorted(directory.glob("*.png"))
    if expected_count < 1 or len(paths) != expected_count:
        raise ValueError(
            f"Expected {expected_count} PNGs, got {len(paths)}"
        )
    for png_path in paths:
        with Image.open(png_path) as source:
            pixel_dims = source.size
            data = source.copy()
        data.save(png_path, "PNG", dpi=(300, 300))
        with Image.open(png_path) as stamped:
            if stamped.size != pixel_dims:
                raise AssertionError("DPI metadata operation changed pixels")
            actual_dpi = stamped.info.get("dpi")
            if actual_dpi is None or not all(
                abs(d - 300) < 0.5 for d in actual_dpi
            ):
                raise AssertionError(f"PNG density metadata absent: {png_path}")
    return len(paths)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=14)
    args = parser.parse_args()
    print(
        f"Stamped {stamp(args.output_dir, args.expected_count)}"
        " exact 300DPI review PNG files"
    )


if __name__ == "__main__":
    main()
