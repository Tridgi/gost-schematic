"""Deterministic C-EL-P / C-GEN SVG comparison without font dependencies.

All outputs are DRAFT and deliberately omit automatic GOST approval.
With --output-dir the directory is created on demand, no proprietary font
or KOMPAS assets are bundled. Inspect the images alongside the source PDF.
"""

import argparse
import json
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.rendering.svg import render_symbol_svg


def generate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "approval": "DRAFT",
        "normative_certified": False,
        "references": [
            "ГОСТ 2.728-74, п. 5, табл. 4, поз. 1 (C-GEN)",
            "ГОСТ 2.728-74, п. 5, табл. 4, поз. 2а (C-EL-P)",
            "ГОСТ 2.728-74, п. 7, табл. 6, поз. 10 (C-DIM-EL)",
        ],
        "editorial_assumptions_mm": {
            "electrode_length": 8,
            "inter_electrode_gap": 1.5,
            "lead_end_coordinates": [-9, 9],
            "plus_mark_and_keepout": "project-specific; not GOST-certified",
        },
        "specimens": [],
    }
    for item in ("polarized", "electrolytic"):
        source = files("gost_schematic").joinpath(
            f"catalog/symbols/capacitors/{item}.json"
        )
        symbol = load_symbol(Path(str(source)))
        graph = inspect_conductor_topology(symbol)
        if not graph.valid:
            raise ValueError(f"{symbol.identifier} has invalid conducting strokes")
        for overlay in (False, True):
            mode = "diagnostic" if overlay else "clean"
            target = output_dir / f"capacitor-{item}-{mode}.svg"
            target.write_text(
                render_symbol_svg(symbol, review_overlay=overlay),
                encoding="utf-8",
            )
            manifest["specimens"].append({
                "path": target.name,
                "symbol_id": symbol.identifier,
                "view": mode,
                "approval": symbol.status.value,
                "pin_islands": [list(group) for group in graph.pin_islands],
            })
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/electrolytic-issue-10"),
    )
    args = parser.parse_args(argv)
    manifest = generate(args.output_dir)
    print(f"Created {len(manifest['specimens'])} DRAFT SVG specimens in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
