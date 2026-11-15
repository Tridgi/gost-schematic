"""One-command source-locked TL494 native SVG + PNG300 delivery (BLOCKED_PARTIAL).

Requires exact IC/NET/RECON/YGO source snapshots staged by C10 workflow.
Never changes the electrical graph or manually edits the generated SVG.
The output is DRAFT and non-printable until a verified 15/15 graph and
independent ESKD + QA release pipeline exist.
"""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import resvg_py
from PIL import Image

from examples.render_tl494_compact_new_router_cycle10 import generate_compact_attempt
from scripts.verify_tl494_compact_cycle10 import verify

PINNED_FONT_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
SVG_NS = "{http://www.w3.org/2000/svg}"
MODES = ("clean", "diagnostic")
STEM = "TL494_COMPACT_A3_NEW_ROUTE_BLOCKED"


def deliver(output: Path, font_file: Path, *, node_cap: int = 25000) -> dict:
    if node_cap < 1:
        raise ValueError("CYCLE15_POSITIVE_ROUTE_BUDGET_REQUIRED")
    if hashlib.sha256(font_file.read_bytes()).hexdigest() != PINNED_FONT_SHA256:
        raise ValueError("CYCLE15_REAL_TYPE_A_PINNED_SHA_MISMATCH")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("CYCLE15_OUTPUT_MUST_BE_EMPTY_TO_PREVENT_STALE_EVIDENCE")
    output.mkdir(parents=True, exist_ok=True)
    proof = generate_compact_attempt(output, font_file, node_cap=node_cap)
    route = proof["router_attempt"]
    if (
        proof["model_source"] != SOURCE_SHA
        or (proof["source_components"], proof["source_nets"],
            proof["source_net_pinrefs"]) != (23, 15, 62)
        or proof["manufacturer_DA1_physical_pin_count"] != 16
        or not proof["signed_manufacturer_ic_16_verified"]
        or not proof["source_b_two_physical_vectors_verified"]
        or route["source_net_count"] != 15
        or route["source_pin_count"] != 62
    ):
        raise ValueError("CYCLE15_SIGNED_SOURCE_AND_ROUTER_PROVENANCE_INVALID")
    # A partial preview is NEVER promoted by this driver to a print sheet.
    # Full routing still requires independent global ink/text/wire/ESKD QA.
    if (
        route["complete"] or route["print_pass"]
        or proof["printable_candidate"] or proof["real_print_release"]
    ):
        raise ValueError("CYCLE15_CANNOT_SELF_APPROVE_FINAL_PRINT_RELEASE")
    output_files = []
    source_b = proof["source_b_stubs_um"]
    for mode in MODES:
        base = f"{STEM}_{mode}"
        svg_path = output / f"{base}.svg"
        xml = ET.fromstring(svg_path.read_bytes())
        if (
            xml.get("data-release") != "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
            or xml.get("width") != "420mm"
            or xml.get("height") != "297mm"
        ):
            raise ValueError("CYCLE15_EXPECTED_BLOCKED_A3_NATIVE_SHEET")
        strokes = xml.findall(
            f".//{SVG_NS}g[@data-layer='typed-nonphysical-continuations']/"
            f"{SVG_NS}line[@data-layer='nonphysical-continuation-stub']"
        )
        if len(strokes) != 2:
            raise ValueError("CYCLE15_TWO_REAL_SOURCE_B_STROKES_REQUIRED")
        for stroke in strokes:
            label = stroke.get("data-nonphysical-net-continuation")
            if label not in source_b:
                raise ValueError("CYCLE15_FORGED_NONPHYSICAL_B_MARKER")
            expected = source_b[label]
            actual = [
                round(float(stroke.get(a)) * 1000)
                for a in ("x1", "y1", "x2", "y2")
            ]
            if (
                actual != [*expected["start"], *expected["end"]]
                or stroke.get("data-source-pin-ref") != expected["source_pin_ref"]
                or stroke.get("data-nonphysical") != "true"
                or stroke.get("data-connectable") != "false"
                or stroke.get("data-electrical-junction") != "false"
                or stroke.get("stroke-width") != "0.3"
            ):
                raise ValueError("CYCLE15_SOURCE_B_STROKE_OR_ELECTRICAL_DRIFT")
        png_path = output / f"{base}-300dpi.png"
        png_path.write_bytes(resvg_py.svg_to_bytes(
            svg_path=str(svg_path),
            dpi=300.0,
            background="#ffffff",
            skip_system_fonts=True,
            font_files=[str(font_file)],
        ))
        with Image.open(png_path) as png:
            if (
                png.format != "PNG"
                or abs(png.width - round(420 * 300 / 25.4)) > 1
                or abs(png.height - round(297 * 300 / 25.4)) > 1
            ):
                raise ValueError("CYCLE15_REAL_A3_300DPI_RASTER_DIMENSIONS_INVALID")
        output_files.extend((svg_path, png_path))
    raster = verify(output)  # also independently verifies actual 16 green pixel tips
    if raster["real_gost_or_e3_print_approval"] is not False:
        raise ValueError("CYCLE15_NOT_A_PRINT_APPROVAL")
    output_files.extend((
        output / "TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json",
        output / "TL494_COMPACT_A3_SOURCE_BOM_DRAFT.json",
        output / "TL494_COMPACT_A3_SOURCE_NETLIST_DRAFT.json",
        output / "C10_COMPACT_RASTER_VERIFIED_NOT_RELEASED.json",
    ))
    evidence = {
        "schema": "paint.tl494.native.delivery.v1",
        "status": "BLOCKED_PARTIAL",
        "print_approved": False,
        "source_sha": SOURCE_SHA,
        "font_sha256": PINNED_FONT_SHA256,
        "owner_shas": {
            "IC97": proof["IC97_owner_sha"],
            "NET114": proof["NET114_owner_sha"],
            "RECON115": proof["RECON115_owner_sha"],
        },
        "physical_counts": {"components": 23, "nets": 15, "pinrefs": 62, "da1": 16},
        "routed_nets": route["routed_net_count"],
        "routed_segments": route["graph_segments"],
        "node_cap": node_cap,
        "physical_page_mm": [420, 297],
        "nonphysical_b_stubs_um": source_b,
        "rasters_verified": raster,
        "blockers": proof["blockers"],
        "files": {
            item.name: {
                "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
                "bytes": item.stat().st_size,
            }
            for item in sorted(output_files)
        },
    }
    name = output / "CYCLE15_TL494_DELIVERY_BLOCKED_PARTIAL.json"
    name.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": evidence["status"],
        "source": SOURCE_SHA,
        "routed_nets": evidence["routed_nets"],
        "net_count": 15,
        "output": str(output),
        "manifest_sha256": hashlib.sha256(name.read_bytes()).hexdigest(),
    }, sort_keys=True))
    return evidence


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--font-file", type=Path, required=True)
    p.add_argument("--node-cap", type=int, default=25000)
    args = p.parse_args()
    deliver(args.output, args.font_file, node_cap=args.node_cap)


if __name__ == "__main__":
    main()
