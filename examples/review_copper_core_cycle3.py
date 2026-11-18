"""Issue #24: two-material clean/diagnostic comparative SVG.

The geometry comes from the actual catalog renderer; text measurement uses a
fixed illustrative stub, NOT a validated GOST Type-A font. For formal
sign-off use the independent real-font/KOMPAS review workflow. No graphics
or font files are embedded in the repository.
"""

import argparse
import json
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.core.geometry import Box, Point, StyledLine
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

IDENTIFIERS = (
    "inductor.trim_copper",
    "inductor.trim_magnetodielectric",
)
STYLE = TextStyle("illustrative-font-not-verified.ttf", "sans-serif", 3500, 500)


class IllustrativeMetrics:
    """Deterministic preview-only widths; NOT an engineering font calibration."""

    def measure(self, text: str, style: TextStyle) -> MeasuredText:
        width_um = max(1, len(text) * 580)
        return MeasuredText(Box(0, -2000, width_um, 1), width_um)


def _load(name: str):
    source = files("gost_schematic").joinpath(f"catalog/inductors/{name}.json")
    return load_inductor(Path(str(source)))


def _render(circuit: Circuit, symbols: dict[str, object], diagnostic: bool) -> str:
    layout = layout_sheet(circuit, symbols, STYLE, IllustrativeMetrics())
    if not layout.valid:
        raise ValueError("Cannot review colliding labels: " + repr(layout.diagnostics))
    root = ET.fromstring(render_sheet_svg(
        circuit, symbols, layout, review_overlay=diagnostic,
    ))
    root.set("data-review-stage", "DRAFT")
    root.set("data-svg-purpose", "diagnostic" if diagnostic else "clean")
    ET.SubElement(root, "desc").text = (
        "Issue 24 material-stroke comparison. Illustrative text metrics; "
        "not a GOST font or a KOMPAS 1:1 certified specimen."
    )
    return ET.tostring(root, encoding="unicode") + "\n"


def generate(output_dir: Path) -> dict[str, object]:
    """Produce individual and paired clean/diagnostic SVG with a manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = {name: _load(name) for name in IDENTIFIERS}
    result: dict[str, object] = {
        "schema_version": 1,
        "issue": 24,
        "approval": "DRAFT",
        "gost_certified": False,
        "text_metrics": "illustrative_only_not_verified_gost_type_a",
        "primary_source": "ГОСТ 2.723-68 табл.1 поз.2а/2в; табл.2 поз.6/7",
        "unresolved": [
            "position of chemical symbol Cu",
            "shape of tuning arrow end",
            "true GOST font glyph metrics",
            "1:1 visual overlay against controlled KOMPAS reference",
        ],
        "materials": {},
        "files": [],
    }

    for name, definition in catalog.items():
        symbol = definition.symbol
        topology = inspect_conductor_topology(symbol)
        if not topology.valid or symbol.status.value != "draft":
            raise ValueError(f"Unsafe UGO graph or approval status for {name}")
        cores = [item for item in symbol.graphics if isinstance(item, StyledLine)]
        if len(cores) != 1:
            raise ValueError(f"Expected one material core for {name}")
        result["materials"][name] = {
            "core_dash_pattern_um": list(cores[0].dash_pattern_um),
            "pin_groups": [list(group) for group in topology.pin_islands],
            "physical_pins": [p.number for p in definition.part.pins],
            "constant_annotations": dict(symbol.constant_annotations),
        }

    views = [
        ("copper", Circuit((ComponentInstance("L1", IDENTIFIERS[0]),), ())),
        ("magnetodielectric", Circuit(
            (ComponentInstance("L2", IDENTIFIERS[1]),), (),
        )),
        ("side-by-side", Circuit((
            ComponentInstance("L1", IDENTIFIERS[0], Point(0, 0)),
            ComponentInstance("L2", IDENTIFIERS[1], Point(39000, 0)),
        ), ())),
    ]
    symbols = {name: definition.symbol for name, definition in catalog.items()}
    for stem, circuit in views:
        for diagnostic in (False, True):
            suffix = "diagnostic" if diagnostic else "clean"
            path = output_dir / f"{stem}-{suffix}.svg"
            path.write_text(_render(circuit, symbols, diagnostic), encoding="utf-8")
            result["files"].append(path.name)
    (output_dir / "manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/copper-core-cycle3"),
    )
    args = parser.parse_args(argv)
    info = generate(args.output_dir)
    print(f"Generated {len(info['files'])} DRAFT SVG and a manifest in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
