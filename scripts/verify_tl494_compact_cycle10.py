"""Independently validate real RECON115 compact partial-route 300DPI artifacts.

No invented print PASS, no edits of source SVG geometry. Tests actual
raster color at every external physical TL494DA1 point.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

SVG = "{http://www.w3.org/2000/svg}"


def verify(folder: Path) -> dict:
    proof = json.loads(
        (folder/"TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json").read_text()
    )
    assert (proof["source_components"], proof["source_nets"],
            proof["source_net_pinrefs"]) == (23, 15, 62)
    assert proof["model_source"] == "e695c415fdced164b0e0c39c5249d030795a0aa6"
    assert proof["NET114_owner_sha"] == "2c4596e3e2897c5a34618169e4cfa5c3b8c38b43"
    assert proof["RECON115_owner_sha"] == "10f22cea8d5908605b52853113b0c75bf91eec75"
    assert proof["A3_true_catalog_bounds"]["A3_capacity_fit"]
    assert proof["status"] == "BLOCKED" and not proof["real_print_release"]
    assert not proof["printable_candidate"]
    assert "A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED" in proof["blockers"]
    assert proof["native_post_render_route_drc"] is not None
    assert proof["real_GOST_Type_A_h_mm"] == 3.5
    checked_pixels = 0
    for mode in ("clean", "diagnostic"):
        stem = f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{mode}"
        root = ET.fromstring((folder/(stem+".svg")).read_text())
        assert root.get("data-release") == "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
        assert len(root.findall(f".//{SVG}g[@data-layer='symbols']")) == 23
        assert len(root.findall(f".//{SVG}line[@data-layer='wires']")) == (
            proof["route_segments"]
        )
        markers = root.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        assert len(markers) == (0 if mode == "clean" else 16)
        if proof["physical_page_fits_1_to_1"]:
            assert root.get("width") == "420mm"
            assert root.get("height") == "297mm"
            assert root.get("viewBox") == "0 0 420 297"
        with Image.open(folder/(stem+"-300dpi.png")) as image:
            assert image.format == "PNG"
            mm = float(root.get("width").removesuffix("mm"))
            assert abs(image.width-round(mm*300/25.4)) <= 1
            rgb = image.convert("RGB")
            if mode == "clean":
                red, green, blue = rgb.split()
                assert ImageChops.difference(red, green).getbbox() is None
                assert ImageChops.difference(red, blue).getbbox() is None
            else:
                viewport = [float(v) for v in root.get("viewBox").split()]
                for marker in markers:
                    x = round(
                        (float(marker.get("x"))+0.35-viewport[0])*300/25.4
                    )
                    y = round(
                        (float(marker.get("y"))+0.35-viewport[1])*300/25.4
                    )
                    if not (0 <= x < image.width and 0 <= y < image.height):
                        raise ValueError(
                            "COMPACT_PHYSICAL_PIN_MARKER_OUTSIDE_RASTER:"
                            + marker.get("data-pin-ref", "")
                        )
                    r, g, b = rgb.getpixel((x, y))
                    assert g > r+35 and g > b+20, (
                        "COMPACT_GREEN_SQUARE_OCCLUDED_BY_REAL_WIRE",
                        marker.get("data-pin-ref"), (r, g, b),
                    )
                    checked_pixels += 1
            image.save(folder/(stem+"-300dpi.png"), dpi=(300, 300))
    assert checked_pixels == 16
    details = {
        "source_23_15_16_62": True,
        "new_owner_route_genuine": True,
        "confirmed_blocked": True,
        "A3_1to1_actual_fit": proof["physical_page_fits_1_to_1"],
        "real_300dpi_green_pin_centers": checked_pixels,
        "clean_png_monochrome": True,
        "real_gost_or_e3_print_approval": False,
    }
    (folder/"C10_COMPACT_RASTER_VERIFIED_NOT_RELEASED.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2)+"\n"
    )
    print(json.dumps(details))
    return details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output)


if __name__ == "__main__":
    main()
