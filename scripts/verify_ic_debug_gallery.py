"""Independent SVG/300-DPI QA of real IC endpoint marker layers.

The generator must already have authored the four SVG variants from the same
ResolvedIcPin/typed PinRef. This verifier does not infer a single Net by text
label and does not paint post-hoc dots onto PNG. See Issue #100.
"""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

SVG = "{http://www.w3.org/2000/svg}"
DPI = 300
UM_PER_MM = Decimal(1000)
MARKER_HALF_UM = 350


def _pic_geometry(svg, png: Path):
    width = float(svg.get("width").removesuffix("mm"))
    height = float(svg.get("height").removesuffix("mm"))
    view_x, view_y, _, _ = (float(x) for x in svg.get("viewBox").split())
    with Image.open(png) as raster:
        dimensions = (
            round(width * DPI / 25.4), round(height * DPI / 25.4),
        )
        assert all(abs(a - b) <= 1 for a, b in zip(
            raster.size, dimensions, strict=True,
        )), (png, raster.size, dimensions)
        assert all(abs(x - DPI) <= .2 for x in raster.info["dpi"])
    return view_x, view_y


def _markers(svg):
    return svg.findall(
        f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect",
    )


def verify(root: Path):
    sources = sorted(root.glob("*-clean.svg"))
    assert len(sources) >= 18, "IC_DIAGNOSTIC_GALLERY_MISSING"
    proof = {
        "pixel_dpi": DPI,
        "status": "DRAFT_SYNTHETIC_PHYSICAL_ENDPOINTS",
        "cases": {},
    }
    for clean_path in sources:
        stem = clean_path.name.removesuffix("-clean.svg")
        xml = {}
        for variant in ("clean", "diagnostic-ink", "diagnostic-pins", "diagnostic"):
            svg_path = root / f"{stem}-{variant}.svg"
            png_path = root / f"{stem}-{variant}-300dpi.png"
            assert svg_path.is_file() and png_path.is_file(), stem
            xml[variant] = ET.fromstring(svg_path.read_text(encoding="utf-8"))
            _pic_geometry(xml[variant], png_path)
        clean = xml["clean"]
        lead_nodes = clean.findall(f".//{SVG}line[@data-pin-id]")
        leads = {node.get("data-pin-id"): node for node in lead_nodes}
        assert len(leads) == len(lead_nodes) and len(leads) in (4, 8, 14, 40, 64)
        assert not _markers(clean)
        assert not _markers(xml["diagnostic-ink"])
        assert xml["diagnostic-ink"].find(
            f".//{SVG}g[@data-layer='ic-review-ink']",
        ) is not None
        assert xml["diagnostic-pins"].find(
            f".//{SVG}g[@data-layer='ic-review-ink']",
        ) is None
        assert xml["diagnostic"].find(
            f".//{SVG}g[@data-layer='ic-review-ink']",
        ) is not None
        for variant, root_svg in xml.items():
            if variant == "clean":
                assert "editor-connection-targets" not in (
                    ET.tostring(root_svg, encoding="unicode")
                )
            same_leads = {
                node.get("data-pin-id"): ET.tostring(node)
                for node in root_svg.findall(f".//{SVG}line[@data-pin-id]")
            }
            assert same_leads == {
                name: ET.tostring(node) for name, node in leads.items()
            }, (stem, variant, "physical lead moved")
            for kind in ("function", "pin-number", "refdes", "pin-label"):
                a = [ET.tostring(n) for n in clean.findall(
                    f".//{SVG}text[@data-kind='{kind}']",
                )]
                b = [ET.tostring(n) for n in root_svg.findall(
                    f".//{SVG}text[@data-kind='{kind}']",
                )]
                assert a == b, (stem, variant, kind, "text moved")
        all_targets = _markers(xml["diagnostic"])
        only_targets = _markers(xml["diagnostic-pins"])
        assert len(all_targets) == len(only_targets) == len(leads)
        assert [ET.tostring(t) for t in all_targets] == [
            ET.tostring(t) for t in only_targets
        ]
        nc_count = 0
        actual_rgb = {}
        for target in all_targets:
            key = target.get("data-pin-id")
            lead = leads[key]
            number = lead.get("data-pin-number")
            assert target.get("data-pin-number") == number
            ref = target.get("data-pin-ref")
            assert ref and ref.endswith("." + number)
            assert target.get("data-pin-role") == lead.get("data-role")
            assert target.get("data-net-id") is not None
            assert target.get("data-connectable") in ("true", "false")
            assert target.get("data-reason") is not None
            x_um = int(target.get("data-external-anchor-x-um"))
            y_um = int(target.get("data-external-anchor-y-um"))
            cx_um = Decimal(target.get("x")) * UM_PER_MM + MARKER_HALF_UM
            cy_um = Decimal(target.get("y")) * UM_PER_MM + MARKER_HALF_UM
            assert cx_um == x_um and cy_um == y_um, (stem, key)
            assert Decimal(lead.get("x2")) * UM_PER_MM == x_um
            assert Decimal(lead.get("y2")) * UM_PER_MM == y_um
            assert target.get("width") == target.get("height") == "0.7"
            disabled = target.get("data-connectable") == "false"
            if disabled:
                nc_count += 1
                assert target.get("data-pin-role") == "nc"
                assert target.get("data-net-id") == ""
                assert target.get("data-reason"), (stem, key)
            expected_fill = "#8b1e27" if disabled else "#148645"
            assert target.get("fill") == expected_fill
            for variant in ("diagnostic", "diagnostic-pins"):
                canvas = xml[variant]
                x0, y0 = (float(x) for x in canvas.get("viewBox").split()[:2])
                px = round((x_um / 1000 - x0) * DPI / 25.4)
                py = round((y_um / 1000 - y0) * DPI / 25.4)
                with Image.open(root / f"{stem}-{variant}-300dpi.png") as img:
                    red, green, blue = img.convert("RGB").getpixel((px, py))
                if disabled:
                    assert red > green + 35 and red > blue + 35, (
                        stem, key, variant, (red, green, blue),
                    )
                else:
                    assert green > red + 35 and green > blue + 20, (
                        stem, key, variant, (red, green, blue),
                    )
                actual_rgb[f"{key}/{variant}"] = [red, green, blue]
        assert nc_count >= 1, (stem, "real typed NC marker absent")
        with Image.open(root / f"{stem}-clean-300dpi.png") as image:
            rgb = image.convert("RGB")
            channels = rgb.split()
            assert ImageChops.difference(channels[0], channels[1]).getbbox() is None
            assert ImageChops.difference(channels[0], channels[2]).getbbox() is None
        proof["cases"][stem] = {
            "external_physical_leads": len(leads),
            "exact_pin_markers": len(all_targets),
            "disabled_nc": nc_count,
            "source_svg_sha256": hashlib.sha256(
                clean_path.read_bytes()
            ).hexdigest(),
            "pixel_colors": actual_rgb,
        }
    (root / "ic-diagnostic-endpoint-300dpi-proof.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS actual OpenGost 300DPI endpoint overlays:",
        len(sources), "IC views,",
        sum(x["exact_pin_markers"] for x in proof["cases"].values()),
        "source-anchored markers; clean drawings monochrome",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gallery-dir", type=Path, required=True)
    args = parser.parse_args()
    verify(args.gallery_dir)


if __name__ == "__main__":
    main()
