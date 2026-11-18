"""SVG review of genuine externally-installed Type A font and draft capacitors.

No font binaries are embedded/distributed; viewer must have this exact font
installed, otherwise SVG font fallback is NOT the verified preview.
"""

import argparse
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.standards.type_a_font import inspect_type_a_font


def _load(relative_path: str):
    path = files("gost_schematic").joinpath(f"catalog/symbols/{relative_path}")
    return load_symbol(Path(str(path)))


def generate(output_dir: Path, font_file: Path, family: str, h_um: int) -> int:
    inspected = inspect_type_a_font(font_file, family=family, h_um=h_um)
    print(f"Face: {inspected.reported_face!r}")
    print(f"ГОСТ Type A requested cap height: {inspected.requested_cap_height_um} µm")
    print(f"Calibrated cap height: {inspected.measured_cap_height_um} µm")
    print(f"Calibrated SVG font-size: {inspected.style.em_height_um} µm")
    symbols = {
        "resistor": _load("resistors/fixed.json"),
        "capacitor": _load("capacitors/fixed.json"),
        "polarized": _load("capacitors/polarized.json"),
    }
    circuit = Circuit((
        ComponentInstance(
            "R1", "resistor", Point(0, 0),
            nominal=Quantity.from_unit("2,3", Unit.KOHM),
        ),
        ComponentInstance(
            "C1", "capacitor", Point(30000, 0),
            nominal=Quantity.from_unit("100", Unit.NANOFARAD),
        ),
        ComponentInstance(
            "C2", "polarized", Point(63000, 0),
            nominal=Quantity.from_unit("470", Unit.MICROFARAD),
        ),
        ComponentInstance(
            "C3", "capacitor", Point(30000, 28000), Transform(rotation=90),
            nominal=Quantity.from_unit("47", Unit.PICOFARAD),
        ),
    ), ())
    output_dir.mkdir(parents=True, exist_ok=True)
    for mode in (NominalDisplayMode.ESKD_COMPACT, NominalDisplayMode.FULL_UNITS):
        config = NominalDisplayConfiguration(
            NominalDisplaySettings(mode=mode)
        )
        layout = layout_sheet(
            circuit, symbols, inspected.style, PillowTextMeasurer(),
            configuration=config,
        )
        if not layout.valid:
            for issue in layout.diagnostics:
                print(f"{issue.severity.value}: {issue.code}: {issue.message}")
            return 1
        for review in (False, True):
            suffix = "review" if review else "clean"
            name = f"type-a-capacitors-{mode.value}-{suffix}.svg"
            target = output_dir / name
            target.write_text(
                render_sheet_svg(
                    circuit, symbols, layout, review_overlay=review,
                ),
                encoding="utf-8",
            )
            print(f"Created: {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="OpenGost Type A")
    parser.add_argument("--height-mm", choices=("2.5", "3.5", "5", "7"), default="3.5")
    parser.add_argument("--output-dir", type=Path, default=Path("output/type-a-capacitors"))
    args = parser.parse_args(argv)
    return generate(
        args.output_dir, args.font_file, args.font_family,
        int(float(args.height_mm) * 1000),
    )


if __name__ == "__main__":
    raise SystemExit(main())
