"""Issue #32 — deterministic clean/diagnostic previews of two DRAFT diodes.

Single-symbol SVGs use the exact library renderer. Paired SVGs are produced
by the actual sheet renderer with *illustrative* font metrics for automated
structural review. These are NOT GOST-certified measured Type-A glyphs.
"""

import argparse
import json
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.diode_review import verify_draft_diode
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

TYPES = ("diode.general", "diode.zener")
STYLE = TextStyle("illustrative-metrics-only.ttf", "sans-serif", 3500, 500)


class _PreviewText:
    def measure(self, text: str, style: TextStyle) -> MeasuredText:
        width = max(1, len(text) * 580)
        return MeasuredText(Box(0, -2000, width, 1), width)


def _entry(identifier: str):
    kind = identifier.split(".", 1)[1]
    source = files("gost_schematic").joinpath("catalog")
    symbol = load_symbol(Path(str(source.joinpath(
        f"symbols/diodes/{kind}.json",
    ))))
    part = load_part(Path(str(source.joinpath(
        f"parts/diodes/{kind}.json",
    ))))
    verify_draft_diode(symbol, part)
    return symbol, part


def _tag_svg(svg: str, *, identifier: str, view: str) -> str:
    root = ET.fromstring(svg)
    root.set("data-approval-status", "DRAFT")
    root.set("data-ugo", identifier)
    root.set("data-view", view)
    ET.SubElement(root, "desc").text = (
        "ГОСТ 2.730-73 табл.5 пп.1/4а: independent DRAFT representation. "
        "Dimensions are project-defined; 1:1 KOMPAS review not performed."
    )
    return ET.tostring(root, encoding="unicode") + "\n"


def generate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = dict((identifier, _entry(identifier)) for identifier in TYPES)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "issue": 32,
        "approval": "DRAFT",
        "normative_certified": False,
        "reference_standard": "ГОСТ 2.730-73, п.6, табл.5 поз.1 и 4а",
        "source_pdf": "https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=3",
        "dimensional_basis": "editorial_mm_not_required_gost; reference_module_grid",
        "font_metrics": "illustrative_not_measured_gost_type_a",
        "physical_pin_numbering": "abstract_only_not_manufacturer_datasheet",
        "symbols": {},
        "files": [],
    }
    for identifier, (symbol, part) in entries.items():
        track = inspect_conductor_topology(symbol)
        if not track.valid:
            raise ValueError("Diode preview must not have incorrect conductor islands")
        manifest["symbols"][identifier] = {
            "revision": symbol.revision,
            "reference_prefix": part.reference_prefix,
            "pin_roles": {
                pin.number: pin.name for pin in part.pins
            },
            "pin_polarity": {
                pin.number: pin.polarity.value for pin in part.pins
            },
            "conductor_groups": [list(group) for group in track.pin_islands],
            "graphic_strokes": len(symbol.graphics),
        }
        for diagnostic in (False, True):
            view = "diagnostic" if diagnostic else "clean"
            target = output_dir / f"{identifier}-{view}.svg"
            target.write_text(
                _tag_svg(
                    render_symbol_svg(symbol, review_overlay=diagnostic),
                    identifier=identifier, view=view,
                ),
                encoding="utf-8",
            )
            manifest["files"].append(target.name)

    circuit = Circuit((
        ComponentInstance("VD1", TYPES[0], Point(0, 0)),
        ComponentInstance("VD2", TYPES[1], Point(38000, 0)),
    ), ())
    by_part = {identifier: entry[0] for identifier, entry in entries.items()}
    layout = layout_sheet(circuit, by_part, STYLE, _PreviewText())
    if not layout.valid:
        raise ValueError("Paired diode sample annotations collide: "
                         + repr(layout.diagnostics))
    for diagnostic in (False, True):
        view = "diagnostic" if diagnostic else "clean"
        target = output_dir / f"diode-comparison-{view}.svg"
        target.write_text(
            _tag_svg(
                render_sheet_svg(
                    circuit, by_part, layout, review_overlay=diagnostic,
                ),
                identifier="diode.general+diode.zener", view=view,
            ),
            encoding="utf-8",
        )
        manifest["files"].append(target.name)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/diodes-cycle4"),
    )
    args = parser.parse_args(argv)
    data = generate(args.output_dir)
    print(f"Created {len(data['files'])} DRAFT diode SVG previews in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
