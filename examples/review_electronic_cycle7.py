"""Deterministic Cycle 7 first-batch review: genuine SVG, exact pin map, DRAFT.

SVG files are source specimens; the dedicated GitHub workflow rasterizes them
at 300 DPI (with size-based pixel verification). No package-specific pinout,
normatively approved font, or APPROVED status is implied.
"""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.units import format_mm
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

IDS = ("resistor.variable", "resistor.trimmer", "fuse.general")


def _source(identifier: str, layer: str) -> Path:
    family, variant = identifier.split(".", 1)
    folder = {"resistor": "resistors", "fuse": "fuses"}[family]
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    return root / layer / folder / (variant + ".json")


def generate(directory: Path) -> dict:
    """Write 3×(clean+diagnostic) vector files with auditable pin coordinates."""
    directory.mkdir(parents=True, exist_ok=True)
    records = {}
    names = []
    for identifier in IDS:
        source = _source(identifier, "symbols")
        part_source = _source(identifier, "parts")
        symbol = load_symbol(source)
        part = load_part(part_source)
        checks = validate_symbol(symbol)
        if any(item.severity.value == "error" for item in checks):
            raise ValueError(f"{identifier}: invalid symbol geometry")
        trace = inspect_conductor_topology(symbol)
        if not trace.valid:
            raise ValueError(f"{identifier}: invalid conducting stroke graph")
        if symbol.status != SymbolStatus.DRAFT or part.symbol_id != identifier:
            raise ValueError(f"{identifier}: unexpected status or physical part")
        if {pin.number for pin in part.pins} != {pin.number for pin in symbol.pins}:
            raise ValueError(f"{identifier}: graphical/physical pin mapping drift")
        content_shas = {}
        for kind in ("clean", "diagnostic"):
            svg = ET.fromstring(render_symbol_svg(
                symbol, review_overlay=(kind == "diagnostic"),
            ))
            svg.set("data-issue", "89")
            svg.set("data-symbol-id", identifier)
            svg.set("data-approval", "DRAFT")
            svg.set("data-view", kind)
            content = ET.tostring(svg, encoding="unicode") + "\n"
            filename = f"{identifier}-{kind}.svg"
            (directory / filename).write_text(content, encoding="utf-8")
            content_shas[kind] = hashlib.sha256(content.encode("utf-8")).hexdigest()
            names.append(filename)
        records[identifier] = {
            "status": "DRAFT",
            "symbol_json_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "part_json_sha256": hashlib.sha256(part_source.read_bytes()).hexdigest(),
            "svg_sha256": content_shas,
            "pin_roles": {pin.number: pin.name for pin in part.pins},
            "actual_drawing_ports_um": {
                pin.number: [pin.at.x, pin.at.y] for pin in symbol.pins
            },
            "pin_islands": [list(group) for group in trace.pin_islands],
            "stroked_bounds_mm": [
                format_mm(value) for value in (
                    symbol.stroked_bounds.min_x, symbol.stroked_bounds.min_y,
                    symbol.stroked_bounds.max_x, symbol.stroked_bounds.max_y,
                )
            ],
            "source_references": list(symbol.standard_refs),
            "abstract_numbering_only": True,
            "manufacturer_datasheet_pinout_verified": False,
        }
    result = {
        "schema_version": 1,
        "issue": 89,
        "epic": 86,
        "status": "DRAFT",
        "graphic_certification": False,
        "nominal_ugo_to_kompas_overlay_signed": False,
        "physical_contact_numbers": "ABSTRACT_ONLY_NO_MANUFACTURER_MAPPING",
        "dpi_output_target": 300,
        "files": names,
        "symbols": records,
    }
    (directory / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Cycle 7 DRAFT: {len(records)} symbols, {len(names)} vector SVG; "
          "3 physical part mappings, 0 approved UGO")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/cycle7-first-batch"))
    args = parser.parse_args()
    generate(args.output_dir)


if __name__ == "__main__":
    main()
