"""Independently validate real RECON115 compact partial-route 300DPI artifacts.

No invented print PASS, no edits of source SVG geometry. Tests actual
raster color at every external physical TL494DA1 point.
"""
import argparse
import hashlib
import json
from decimal import Decimal
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
    assert proof["NET114_owner_sha"] == "ef48b2a1a6a77ed8d2e18528aeeeb1f0e0e41d2d"
    assert proof["RECON115_owner_sha"] == "d9286dc2719157109c110db86581951cd58192ab"
    assert proof["IC97_owner_sha"] == "892640cfff9780bb4f13c1a6753dbba5f7754a96"
    assert proof["canonical_ti_part_id_verified"] == "ti.tl494cn.pdip16"
    assert proof["trusted_97_part_rebinding"]
    assert proof["source_signed_16_pin_overlay"] is True
    assert proof["signed_manufacturer_ic_16_verified"] is True
    assert proof["source_b_two_physical_vectors_verified"] is True
    assert len(proof["source_signed_overlay_sha256"]) == 64
    assert proof["legacy_part_id_preserved_only_in_frozen_fixture"]
    source_names = {
        "a_INPUT_PLUS", "SWITCH", "TRANSFER", "OUT_BEFORE_FUSE",
        "b_NEGATIVE_OUTPUT", "GATE_DRIVE", "CONTROL_REFERENCE",
        "SOFT_START", "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK",
        "ADJUSTED_DIVIDER", "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
    }
    assert len(proof["original_named_nets_verified"]) == 15
    assert set(proof["original_named_nets_verified"]) == source_names
    expected_files = {
        "TL494_COMPACT_A3_SOURCE_BOM_DRAFT.json",
        "TL494_COMPACT_A3_SOURCE_NETLIST_DRAFT.json",
    }
    assert set(proof["source_model_exports"]) == expected_files
    source_records = {}
    for name, evidence in proof["source_model_exports"].items():
        raw = (folder/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == evidence["sha256"]
        assert len(raw) == evidence["bytes"]
        item = json.loads(raw)
        assert item["source_sha"] == proof["model_source"]
        assert item["signed_ic_owner_sha"] == proof["IC97_owner_sha"]
        assert item["print_approved"] is False
        source_records[name] = item
    bom = source_records["TL494_COMPACT_A3_SOURCE_BOM_DRAFT.json"]
    netlist = source_records["TL494_COMPACT_A3_SOURCE_NETLIST_DRAFT.json"]
    assert bom["schema"] == "paint.source-bom.v1"
    assert netlist["schema"] == "paint.source-netlist.v1"
    assert len(bom["components"]) == 23
    assert len({item["reference"] for item in bom["components"]}) == 23
    assert next(item for item in bom["components"] if (
        item["reference"] == "DA1"
    ))["part_id"] == "ti.tl494cn.pdip16"
    assert all(
        entry["nominal"] is None or entry["nominal"]["schema_version"] == 1
        for entry in bom["components"]
    )
    assert len(netlist["nets"]) == 15
    assert {item["name"] for item in netlist["nets"]} == source_names
    members = [
        (pin["reference"], pin["number"])
        for net in netlist["nets"] for pin in net["pinrefs"]
    ]
    assert len(members) == len(set(members)) == 62
    assert {(ref, number) for ref, number in members if ref == "DA1"} == {
        ("DA1", str(pin)) for pin in range(1, 17)
    }
    # Independently compare source-backed values AND each physical net against
    # the byte-locked IC97 JSON taken from immutable e695 photo source.
    frozen_file = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/tl494_photo_23_frozen_cycle9.json"
    )
    frozen = json.loads(frozen_file.read_text(encoding="utf-8"))
    assert frozen["source_commit"] == proof["model_source"]
    original_bom = {part["ref"]: part for part in frozen["components"]}
    original_nets = frozen["nets"]
    assert len(original_bom) == 23 and len(original_nets) == 15
    for actual in bom["components"]:
        ref = actual["reference"]
        expected = original_bom[ref]
        expected_part = (
            "ti.tl494cn.pdip16" if ref == "DA1" else expected["part_id"]
        )
        assert actual["part_id"] == expected_part
        source_nominal = expected["nominal_si"]
        record = actual["nominal"]
        assert (source_nominal is None) == (record is None)
        if record is not None:
            assert Decimal(record["si_value"]) == Decimal(source_nominal)
    for net in netlist["nets"]:
        expected = set(original_nets[net["name"]])
        actual = {f'{pin["reference"]}.{pin["number"]}' for pin in net["pinrefs"]}
        assert actual == expected
        assert len(net["pinrefs"]) == len(expected)
    assert "PE" not in source_names and "CHASSIS" not in source_names
    assert proof["A3_true_catalog_bounds"]["A3_capacity_fit"]
    assert proof["status"] == "BLOCKED" and not proof["real_print_release"]
    assert not proof["printable_candidate"]
    assert proof["nonphysical_b_marker_status"] == "VERIFIED_SOURCE_B_REBOUND"
    b = proof["two_source_b_markers"]
    assert set(b) == {"b-X2", "b-R5"}
    assert all(item["net"] == "b_NEGATIVE_OUTPUT" for item in b.values())
    assert all(item["printed_label"] == "b" for item in b.values())
    stubs = proof["source_b_stubs_um"]
    assert set(stubs) == {"b-X2", "b-R5"}
    assert {name: data["source_pin_ref"] for name, data in stubs.items()} == {
        "b-X2": "X2.1", "b-R5": "R5.2",
    }
    assert all(data["nonphysical"] is True for data in stubs.values())
    assert all(data["end"] == [b[key]["x_um"], b[key]["y_um"]]
               for key, data in stubs.items())
    assert "A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED" not in proof["blockers"]
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
        b_circles = root.findall(
            f".//{SVG}g[@data-layer='typed-nonphysical-continuations']/"
            f"{SVG}circle"
        )
        assert len(b_circles) == 2
        assert {x.get("data-nonphysical-net-continuation") for x in b_circles} == {
            "b-X2", "b-R5",
        }
        b_lines = root.findall(
            f".//{SVG}g[@data-layer='typed-nonphysical-continuations']/"
            f"{SVG}line[@data-layer='nonphysical-continuation-stub']"
        )
        assert len(b_lines) == 2
        assert {line.get("data-nonphysical-net-continuation")
                for line in b_lines} == set(stubs)
        for line in b_lines:
            evidence = stubs[line.get("data-nonphysical-net-continuation")]
            assert line.get("data-source-pin-ref") == evidence["source_pin_ref"]
            assert line.get("data-source-stub-id") == evidence["source_stub_id"]
            assert line.get("data-nonphysical") == "true"
            assert line.get("data-electrical-junction") == "false"
            assert line.get("data-connectable") == "false"
            assert [
                round(float(line.get("x1")) * 1000),
                round(float(line.get("y1")) * 1000),
            ] == evidence["start"]
            assert [
                round(float(line.get("x2")) * 1000),
                round(float(line.get("y2")) * 1000),
            ] == evidence["end"]
        assert len(root.findall(f".//{SVG}line[@data-layer='wires']")) == (
            proof["route_segments"]
        )
        for circle in b_circles:
            expected_b = b[circle.get("data-nonphysical-net-continuation")]
            assert abs(float(circle.get("cx")) * 1000 - expected_b["x_um"]) < 0.01
            assert abs(float(circle.get("cy")) * 1000 - expected_b["y_um"]) < 0.01
            assert circle.get("data-electrical-junction") == "false"
        markers = root.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        assert len(markers) == (0 if mode == "clean" else 16)
        if mode == "diagnostic":
            assert {marker.get("data-pin-ref") for marker in markers} == {
                f"DA1.{number}" for number in range(1, 17)
            }
            assert all(marker.get("data-connectable") == "true"
                       for marker in markers)
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
