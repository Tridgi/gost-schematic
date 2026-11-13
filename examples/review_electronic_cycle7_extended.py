"""Single Cycle 7 review gallery for ALL delivered E3 physical symbol pairs.

Only exact SVG primitives from package SymbolDefinitions are used, not stock
images, guessed physical package footprints, or compositor-generated copper.
Pure standard library. SVG font-family requests a locally installed OpenGost
Type A for gallery labels; CI asserts Fontconfig selects it for 300DPI PNG.
"""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_electronic_cycle7 import IDS as FIRST_IDS
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

TRANSISTORS = tuple(
    "transistor." + kind + suffix
    for kind in ("bjt_pnp", "bjt_npn", "mosfet_n_enh", "mosfet_p_enh")
    for suffix in ("", ".with_case")
)
DIODES = tuple("diode." + item for item in (
    "schottky", "led", "photodiode", "varicap"
))
IDS = FIRST_IDS + TRANSISTORS + DIODES
SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")
FOLDERS = {"resistor": "resistors", "fuse": "fuses",
           "transistor": "transistors", "diode": "diodes"}


def _source(identifier: str, layer: str) -> Path:
    family, name = identifier.split(".", 1)
    return Path(str(files("gost_schematic").joinpath("catalog"))) / (
        layer + "/" + FOLDERS[family] + "/" + name.replace(".with_case", "_with_case") + ".json"
    )


def generate(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    all_records = {}
    scene_data = {}
    for identifier in IDS:
        spath = _source(identifier, "symbols")
        ppath = _source(identifier, "parts")
        symbol, part = load_symbol(spath), load_part(ppath)
        if (symbol.identifier != identifier or part.symbol_id != identifier
            or symbol.status != SymbolStatus.DRAFT):
            raise ValueError("Incorrect ID or status: " + identifier)
        if {p.number for p in symbol.pins} != {p.number for p in part.pins}:
            raise ValueError("Missing actual physical terminal: " + identifier)
        errs = [d.code for d in validate_symbol(symbol) if d.severity.value == "error"]
        trace = inspect_conductor_topology(symbol)
        if errs or not trace.valid or len(trace.pin_islands) != len(symbol.pins):
            raise ValueError(f"Unsafe UGO {identifier}: {errs} {trace.diagnostics}")
        scene_data[identifier] = symbol
        all_records[identifier] = {
            "id": identifier, "status": "DRAFT", "source_sha256": hashlib.sha256(
                spath.read_bytes()).hexdigest(), "physical_sha256": hashlib.sha256(
                ppath.read_bytes()).hexdigest(),
            "physical_pin_role": {p.number: p.name for p in part.pins},
            "graphic_pin_coordinate_um": {p.number: [p.at.x, p.at.y]
                                          for p in symbol.pins},
            "ink_conductor_islands": [list(group) for group in trace.pin_islands],
            "body_stroked_bounds_um": [
                symbol.stroked_bounds.min_x, symbol.stroked_bounds.min_y,
                symbol.stroked_bounds.max_x, symbol.stroked_bounds.max_y,
            ],
            "standard_refs": list(symbol.standard_refs),
            "status_nonnormative": "NEEDS_1_TO_1_ESKD_OVERLAY",
        }
    files_written = []
    # Keep gallery cells roomy: each is 55×60mm, five columns × three rows.
    for diagnostic in (False, True):
        root = ET.Element(SVG + "svg", {
            "width": "275mm", "height": "180mm", "viewBox": "0 0 275 180",
            "data-approval": "DRAFT", "data-issue": "89",
            "data-kind": "diagnostic" if diagnostic else "clean",
            "data-source": "actual-15-SymbolDefinition-and-15-PartDefinition",
        })
        ET.SubElement(root, SVG + "title").text = (
            "Cycle 7: real 15 DRAFT E3 symbols, diagnostic" if diagnostic
            else "Cycle 7: real 15 DRAFT E3 symbols, clean"
        )
        for idx, identifier in enumerate(IDS):
            symbol = scene_data[identifier]
            col, row = idx % 5, idx // 5
            cx, cy = col * 55 + 27.5, row * 60 + 26
            source = ET.fromstring(render_symbol_svg(
                symbol, review_overlay=diagnostic,
            ))
            bbox = symbol.stroked_bounds
            if (bbox.max_x - bbox.min_x > 44000
                or bbox.max_y - bbox.min_y > 39000):
                raise ValueError(f"{identifier}: cannot fit ink safely in 55×60mm review cell")
            midx = (bbox.min_x + bbox.max_x) / 2000
            midy = (bbox.min_y + bbox.max_y) / 2000
            item = ET.SubElement(root, SVG + "g", {
                "data-symbol-id": identifier,
                "data-pin-numbers": ",".join(p.number for p in symbol.pins),
                "data-physical-roles": ",".join(all_records[identifier][
                    "physical_pin_role"][p.number] for p in symbol.pins),
                "transform": f"translate({cx - midx:g},{cy - midy:g})",
            })
            for child in source:
                if child.tag == SVG + "g":
                    item.append(child)
            ET.SubElement(root, SVG + "text", {
                "x": f"{col * 55 + 27.5:g}", "y": f"{row * 60 + 51:g}",
                "text-anchor": "middle", "font-family": "OpenGost Type A",
                "font-size": "2.9", "fill": "black",
            }).text = identifier
            if diagnostic:
                ET.SubElement(root, SVG + "text", {
                    "x": f"{col * 55 + 27.5:g}", "y": f"{row * 60 + 55:g}",
                    "text-anchor": "middle", "font-family": "OpenGost Type A",
                    "font-size": "2.3", "fill": "#436d71",
                }).text = ",".join(
                    f"{p.number}:{all_records[identifier]['physical_pin_role'][p.number]}"
                    for p in symbol.pins
                )
        name = "cycle7-all-15-diagnostic.svg" if diagnostic else "cycle7-all-15-clean.svg"
        (directory / name).write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8",
        )
        files_written.append(name)
    result = {
        "issue": 89, "epic": 86, "status": "DRAFT", "approved_count": 0,
        "physical_ugo_count": len(IDS), "starting_baseline_new_count": len(FIRST_IDS),
        "physical_pinout_manufacturer_verified": False,
        "source_figure_1_to_1_manually_approved": False,
        "gallery_size_mm": [275, 180],
        "true_png_raster_dpi": 300,
        "files": files_written, "symbols": all_records,
    }
    (directory / "cycle7-gallery-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Cycle 7 single complete gallery: {len(IDS)} real symbol+part DRAFT pairs")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("output/cycle7-all-catalogue"))
    args = parser.parse_args()
    generate(args.output_dir)


if __name__ == "__main__":
    main()
