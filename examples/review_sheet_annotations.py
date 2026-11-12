"""Three deterministic multi-component preview modes for manual review.

Run after installing the library with pip install -e '.[dev]'. This creates
only SVG illustrations; no production ГОСТ sheet or automatic wiring.
"""

import argparse
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.sheet_svg import render_sheet_svg


def run(output_dir: Path, font_path: Path, family: str) -> int:
    symbol_file = files("gost_schematic").joinpath(
        "catalog/symbols/resistors/fixed.json"
    )
    symbol = load_symbol(Path(str(symbol_file)))
    instances = (
        ComponentInstance("R1", "resistor", Point(0, 0),
                          nominal=Quantity.from_unit("2,3", Unit.KOHM)),
        ComponentInstance("R2", "resistor", Point(31000, 0),
                          nominal=Quantity.from_unit("470", Unit.KOHM)),
        ComponentInstance("R3", "resistor", Point(62000, 0),
                          nominal=Quantity.from_unit("1", Unit.MOHM)),
        ComponentInstance("R4", "resistor", Point(31000, 28000),
                          Transform(rotation=90),
                          nominal=Quantity.from_unit("100", Unit.OHM)),
    )
    circuit = Circuit(instances, ())
    style = TextStyle(str(font_path), family, em_height_um=3500, clearance_um=500)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = {"resistor": symbol}
    measurer = PillowTextMeasurer()

    for mode, hide in (
        (NominalDisplayMode.ESKD_COMPACT, False),
        (NominalDisplayMode.FULL_UNITS, False),
        (NominalDisplayMode.ESKD_COMPACT, True),
    ):
        options = NominalDisplayConfiguration(NominalDisplaySettings(
            mode=mode, show_nominal=not hide,
        ))
        result = layout_sheet(circuit, symbols, style, measurer, configuration=options)
        for issue in result.diagnostics:
            print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        if not result.valid:
            return 1
        name = "hidden" if hide else mode.value
        for overlay in (False, True):
            tag = "-review" if overlay else "-clean"
            output = output_dir / f"sheet-{name}{tag}.svg"
            output.write_text(
                render_sheet_svg(
                    circuit, symbols, result, review_overlay=overlay,
                ),
                encoding="utf-8",
            )
            print(f"Created: {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Four-resistor annotation positioning review"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output/sheet-review"))
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="DejaVu Sans")
    args = parser.parse_args(argv)
    return run(args.output_dir, args.font_file, args.font_family)


if __name__ == "__main__":
    raise SystemExit(main())
