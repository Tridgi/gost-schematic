"""Regenerate Issue #65 authentic SVG/PNG proof images from the live specimen.

Only writes to the dedicated in-repo docs/assets/ai-mcp directory.
Run: python -m examples.review_ai_mcp_vision
"""

import json
from pathlib import Path

from gost_schematic.agent_api.vision import (
    diagnostics,
    inspect_component,
    inspect_region,
    render_overview,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "ai-mcp"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    views = {
        "six-part-overview": render_overview("six-part", mode="clean"),
        "c3-at-80mm": inspect_component("six-part", "C3", target_dpi=500),
        "unmarked-wire-crossing": inspect_region(
            "six-part", {"bbox_mm": [65, 35, 75, 45]}, padding_mm=4,
            target_dpi=500, mode="diagnostic",
        ),
    }
    for name, view in views.items():
        (OUTPUT / f"{name}.png").write_bytes(view.png)
        (OUTPUT / f"{name}.svg").write_text(view.svg, encoding="utf-8")
        (OUTPUT / f"{name}.json").write_text(
            json.dumps(view.metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{name}: {view.metadata['pixels']} {len(view.png)} bytes")
    (OUTPUT / "diagnostics.json").write_text(
        json.dumps(diagnostics("six-part"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
