"""Isolated native PAINT #93 rotation extension for verified bottom-to-top PWM.

Patches Python renderer sources only; never post-processes an output SVG.
Refuses unknown upstream source through exact token/occurrence checks.
This is a DRAFT owner proposal for #110, NOT an approved shared renderer.
"""
from __future__ import annotations

import sys
from pathlib import Path


REPLACEMENTS = (
    ("or self.function_rotation not in (0, 90)", "or self.function_rotation not in (0, 90, 270)", 1),
    ("IC_TEXT_ROTATION_UNVERIFIED: only 0/90", "IC_TEXT_ROTATION_UNVERIFIED: only 0/90/270", 1),
    ("if function_rotation not in (0, 90):", "if function_rotation not in (0, 90, 270):", 1),
    ("if function_rotation == 90 or shared_function_envelope", "if function_rotation in (90, 270) or shared_function_envelope", 2),
    ("_height(function_ink) if function_rotation == 90 else", "_height(function_ink) if function_rotation in (90, 270) else", 1),
    ("measurer: TextMeasurer, policy: IcRenderingPolicy,\n) -> tuple[IcInkBox, Point]:\n    \"\"\"Rotate the WHOLE", "measurer: TextMeasurer, policy: IcRenderingPolicy,\n    rotation: int,\n) -> tuple[IcInkBox, Point]:\n    \"\"\"Rotate the WHOLE", 1),
    ("rotated = Transform(90).box(_measure(text, style, measurer))",
     "rotated = Transform(rotation).box(_measure(text, style, measurer))", 1),
    ('if (kind == "function" and unit.function_rotation == 90', 'if (kind == "function" and unit.function_rotation in (90, 270)', 1),
    ("owner, text, cell, style, measurer, policy,\n            )\n            rotated_function_baselines",
     "owner, text, cell, style, measurer, policy, unit.function_rotation,\n            )\n            rotated_function_baselines", 1),
    ("compose_transforms(unit.transform, Transform(90))",
     "compose_transforms(unit.transform, Transform(unit.function_rotation))", 1),
    ("unit.function_rotation == 90 or", "unit.function_rotation in (90, 270) or", 1),
    ("rotated_local = Transform(90).box(glyph.ink)",
     "rotated_local = Transform(unit.function_rotation).box(glyph.ink)", 1),
    ('if (unit.function_rotation == 90 and not _vertical_internal):',
     'if (unit.function_rotation in (90, 270) and not _vertical_internal):', 1),
    ('svg.set("data-function-rotation-deg", "90")',
     'svg.set("data-function-rotation-deg", str(unit.function_rotation))', 1),
)


def patch(path: Path) -> None:
    data=path.read_text(encoding="utf-8")
    for source,target,count in REPLACEMENTS:
        actual=data.count(source)
        if actual!=count:
            raise ValueError(
                f"P3 PATCH_UPSTREAM_DRIFT: {source!r} expected {count} got {actual}"
            )
        data=data.replace(source,target)
    # DO NOT change other text or other graphics. 270 is the opposite of 90.
    path.write_text(data,encoding="utf-8")
    print(f"Patched genuine PAINT function rotation (0/90/270): {path}")


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python -m examples.tl494_v4.paint_rotation_patch <file>")
    patch(Path(sys.argv[1]))
