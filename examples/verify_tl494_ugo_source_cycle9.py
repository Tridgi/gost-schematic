"""Independent SVG/PNG metric raster audit for 13 source selections + 64 D4."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

from gost_schematic.agent_project.catalog import value_digest

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
    figure_path = directory / profile["normative_figure_ledger_file"]
    figures = json.loads(figure_path.read_text(encoding="utf-8"))
    if (profile["normative_figure_count"] != 8
        or len(figures.get("figures", ())) != 8
        or figures["source_reference_sha"] != profile["source_sha"]
        or figures["status"] != "DRAFT"
        or figures["actual_printed_1to1_verified"]
        or figures["nomination_for_ESKD"] != "NONE"
        or any(record["metric_1to1"] !=
               "BLOCKED_SOURCE_CALIBRATION_AND_EVALUATOR"
               for record in figures["figures"])):
        raise ValueError("Uncalibrated normative figure must remain BLOCKED")
    if len(set(profile["files"])) != len(profile["files"]):
        raise ValueError("Duplicate gallery output name")
    # Independent semantic inspection: raster success alone cannot prove
    # pin-lead identity, ink envelopes or immutable source geometry.
    proof_path = directory / profile["footprint_proofs_file"]
    geometry = json.loads(proof_path.read_text(encoding="utf-8"))
    if (geometry["status"] != "DRAFT"
        or geometry["source_reference_sha"] != profile["source_sha"]
        or geometry["release_blocker"] != "NO_INDEPENDENT_CALIBRATED_1TO1"
        or len(geometry["source_pose"]) != 13
        or len(geometry["d4_proofs"]) != 104
        or profile["footprint_count"] != 13
        or profile["d4_footprint_count"] != 104):
        raise ValueError("Physical source footprint proof count / status mismatch")
    all_poses = geometry["source_pose"] + geometry["d4_proofs"]
    for shape in all_poses:
        signature = shape["footprint_sha256"]
        if value_digest({
            key: val for key, val in shape.items()
            if key != "footprint_sha256"
        }) != signature:
            raise ValueError("Tampered immutable UGO footprint SHA256")
        pins = shape["physical_pin_roles"]
        escapes = shape["pin_escape"]
        leads = shape["real_leads"]
        if (len(pins) != len(escapes) or len(leads) != len(pins)
            or len(shape["graphic_ink"]) < len(pins)):
            raise ValueError("Missing physical pin or ink obstacle")
        if len({(x["ref"], x["number"]) for x in pins}) != len(pins):
            raise ValueError("Duplicated physical pin identity")
        for role, escape, lead in zip(pins, escapes, leads, strict=True):
            identity = (role["ref"], role["number"])
            if (identity != (escape["ref"], escape["number"])
                or identity != (lead["ref"], lead["number"])
                or escape["contact_um"] not in lead["segment_um"]
                or escape["rule"] != "EXACT_PIN_OUTWARD_ONLY_NO_SELF_INK_WAIVER"
                or lead["stroke_um"] <= 0
                or lead["obstacle_um"] != shape["graphic_ink"][
                    lead["graphic_index"]
                ]["box_um"]):
                raise ValueError("Fake lead, displaced endpoint or blanket waiver")
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
        "source_footprints": len(geometry["source_pose"]),
        "d4_footprints": len(geometry["d4_proofs"]),
        "figure_ledger_sha256": hashlib.sha256(
            figure_path.read_bytes()
        ).hexdigest(),
        "footprint_proofs_sha256": hashlib.sha256(
            proof_path.read_bytes()
        ).hexdigest(),
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
