"""Cycle 8: real physical XP/XS SymbolDefinition gallery (never a GOST approval).

Clean SVG contains no diagnostic squares. Green square overlays are explicitly
editor-only and sourced from typed real PhysicalPin + transformed GraphicPin.
"""

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.engines.connection_targets import connection_targets
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.rendering.primitives import draw_primitive
from gost_schematic.rendering.svg import render_symbol_svg

IDS = (
    "connector.plug_contact",
    "connector.socket_contact",
    "connector.plug_4",
    "connector.socket_4",
)
SVG = "http://www.w3.org/2000/svg"
ROOT = Path(str(files("gost_schematic").joinpath("catalog")))
SIZE_MM = (220, 175)


def pair(identifier: str):
    suffix = identifier.split(".", 1)[1]
    sub = Path("connectors", suffix + ".json")
    return (load_symbol(ROOT / "symbols" / sub),
            load_part(ROOT / "parts" / sub))


def _source_targets(identifier: str):
    symbol, part = pair(identifier)
    inst = ComponentInstance("XP4" if part.reference_prefix == "XP" else "XS4",
                             part.identifier, Point(0, 0))
    targets = connection_targets(inst, part, symbol)
    return symbol, part, targets


def _mark_targets(parent: ET.Element, targets):
    for target in targets:
        ET.SubElement(parent, f"{{{SVG}}}rect", {
            "x": str(target.point.x / 1000 - 0.65),
            "y": str(target.point.y / 1000 - 0.65),
            "width": "1.3", "height": "1.3",
            "stroke": "#08734c", "stroke-width": "0.15",
            "fill": "#14a56d", "data-editor-target": "true",
            "data-pin-number": target.pin_ref.number,
        })


def _write_svg(path: Path, element: ET.Element):
    content = ET.tostring(element, encoding="unicode") + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "status": "DRAFT", "issue": 89, "phase": "XP_XS_CYCLE8",
        "approval": "BLOCKED_ESKD_INDEPENDENT_1TO1",
        "manufacturer_pinouts": "UNVERIFIED_ABSTRACT_CONTACT_IDS",
        "gallery_count": len(IDS), "approved_count": 0,
        "size_mm": list(SIZE_MM), "symbols": {}, "files": [],
    }
    records = {identifier: _source_targets(identifier) for identifier in IDS}
    for identifier, (symbol, part, targets) in records.items():
        card = {
            "status": "DRAFT", "prefix": part.reference_prefix,
            "physical_pin_roles": {p.number: p.name for p in part.pins},
            "graphic_pin_coordinate_um": {
                p.number: [p.at.x, p.at.y] for p in symbol.pins
            },
            "pin_ref_numbers": [target.pin_ref.number for target in targets],
            "closeup_svg_sha256": {},
        }
        for diagnostic in (False, True):
            kind = "diagnostic" if diagnostic else "clean"
            # Embed actual existing engine renderer. For debug, add square targets
            # instead of the renderer's older circular markers.
            root = ET.fromstring(render_symbol_svg(symbol))
            root.set("data-symbol-id", identifier)
            root.set("data-approval", "DRAFT")
            root.set("data-kind", kind)
            root.set("data-physical-numbers", ",".join(card["pin_ref_numbers"]))
            if diagnostic:
                body = symbol.body_keepout
                ET.SubElement(root, f"{{{SVG}}}rect", {
                    "x": str(body.min_x / 1000), "y": str(body.min_y / 1000),
                    "width": str((body.max_x - body.min_x) / 1000),
                    "height": str((body.max_y - body.min_y) / 1000),
                    "stroke": "#b77e27", "fill": "none",
                    "stroke-dasharray": "1,0.7", "data-keepout": "true",
                })
                _mark_targets(root, targets)
            path = directory / f"{identifier}-{kind}.svg"
            card["closeup_svg_sha256"][kind] = _write_svg(path, root)
            manifest["files"].append(path.name)
        manifest["symbols"][identifier] = card

    for diagnostic in (False, True):
        kind = "diagnostic" if diagnostic else "clean"
        root = ET.Element("svg", {
            "xmlns": SVG,
            "width": f"{SIZE_MM[0]}mm", "height": f"{SIZE_MM[1]}mm",
            "viewBox": f"0 0 {SIZE_MM[0]} {SIZE_MM[1]}",
            "data-approval": "DRAFT", "data-kind": kind,
            "data-gallery-count": str(len(IDS)),
        })
        ET.SubElement(root, "title").text = "DRAFT physical XP/XS contacts"
        for idx, identifier in enumerate(IDS):
            symbol, part, targets = records[identifier]
            cx = (60, 160)[idx % 2]
            cy = (40, 120)[idx // 2]
            label = ET.SubElement(root, "text", {
                "x": str(cx - 30), "y": str(cy - 25),
                "font-family": "OpenGost Type A", "font-size": "3.5",
                "fill": "#000000", "stroke": "none",
            })
            label.text = f"{identifier} / {part.reference_prefix} / DRAFT"
            group = ET.SubElement(root, "g", {
                "transform": f"translate({cx} {cy})",
                "stroke": "#000000", "stroke-width": "0.3",
                "fill": "none", "data-symbol-id": identifier,
                "data-physical-numbers": ",".join(p.number for p in part.pins),
            })
            for primitive in symbol.graphics:
                draw_primitive(group, primitive)
            if diagnostic:
                body = symbol.body_keepout
                ET.SubElement(group, f"{{{SVG}}}rect", {
                    "x": str(body.min_x / 1000), "y": str(body.min_y / 1000),
                    "width": str((body.max_x - body.min_x) / 1000),
                    "height": str((body.max_y - body.min_y) / 1000),
                    "stroke": "#b77e27", "fill": "none",
                    "stroke-dasharray": "1,0.7", "data-keepout": "true",
                })
                _mark_targets(group, targets)
        path = directory / f"cycle8-connectors-{kind}.svg"
        manifest["files"].append(path.name)
        manifest[f"gallery_{kind}_sha256"] = _write_svg(path, root)

    (directory / "cycle8-connectors-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = generate(args.output_dir)
    print(f"{output['gallery_count']} true DRAFT physical connector UGO: "
          f"{len(output['files'])} SVG; 300DPI rasterized by workflow")


if __name__ == "__main__":
    main()
