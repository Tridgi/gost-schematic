"""Cycle7 #88 physical IC vector/ink gallery; all pin maps are SYNTHETIC DRAFT.

The demonstration is NOT a manufacturer pinout and NEVER creates Circuit.PinRef.
The two-phase fixture creates synthetic resolved anchors explicitly *after* the
size proposal; the production renderer accepts those authoritative Points only.
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent, IcRenderingPolicy, IcResolvedUnit, ResolvedIcPin,
    propose_ic_dimensions, render_resolved_ic,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font


def _fixture(count, kind, style, measurer):
    if count % 2:
        raise ValueError("Synthetic gallery requires even pin count")
    half = count // 2
    sample = []
    for index in range(count):
        side = Side.LEFT if index < half else Side.RIGHT
        row = index % half + 1
        label = (
            "EN" if index == 0 else
            "CLK↑" if index == 1 else
            "NC" if index == 2 else
            "VCC" if index == count - 1 else
            f"ВХ_{index:02d}" if side == Side.LEFT else f"Q{index-half:02d}"
        )
        if count == 64 and index == half - 1:
            label = "РАЗРЕШЕНИЕ_ЗАПИСИ"
        if count == 40 and index == half + 10:
            label = "ДАННЫЕ_КОНТРОЛЯ_10"
        sample.append(ResolvedIcPin(
            f"TEST_IC_{count}.P{index+1}", str(index+1), label,
            side, row, Point(index*100 + 1, index*100 + 2),
            "in" if side == Side.LEFT else "out",
        ))
    extras = (
        ("ТАКТИРОВАНИЕ", "РЕГИСТР_16") if count >= 14
        else ("ИСПЫТАНИЕ",) if count == 8 else ()
    )
    content = IcFieldContent(
        function="AMP" if kind == "analog" else "RAM" if count >= 40 else "AND",
        main_rows=extras,
        left_zone_after=(3, 11) if count >= 40 else (2,) if count >= 8 else (),
        right_zone_after=(5,) if count >= 14 else (),
        analog=kind == "analog",
    )
    plan = propose_ic_dimensions(content, tuple(sample), style, measurer)
    origin = Point(30000, 20000)
    resolved = tuple(replace(
        p,
        anchor=Point(
            origin.x + (0 if p.side == Side.LEFT else plan.width_um),
            origin.y + p.row * plan.row_pitch_um + plan.row_pitch_um // 2,
        ),
    ) for p in sample)
    unit = IcResolvedUnit(
        "DA1" if kind == "analog" else "DD1",
        Box(0, 0, plan.width_um, plan.height_um),
        resolved, content, origin,
    )
    return unit, plan


def _bbox_gap(a, b):
    dx = max(b.min_x - a.max_x, a.min_x - b.max_x, 0)
    dy = max(b.min_y - a.max_y, a.min_y - b.max_y, 0)
    if dx and dy:
        from math import hypot
        return hypot(dx, dy)
    return max(dx, dy)


def generate(folder: Path, font_file: Path):
    inspection = inspect_type_a_font(font_file, h_um=3500)
    style = inspection.style
    measure = PillowTextMeasurer()
    policy = IcRenderingPolicy()
    folder.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "DRAFT_SYNTHETIC_IC_PINOUTS_NOT_REAL_PARTS",
        "issue": 88,
        "font": {
            "family": style.font_family,
            "sha256": style.font_sha256,
            "face": list(inspection.reported_face),
            "requested_cap_height_um": inspection.requested_cap_height_um,
            "measured_cap_height_um": inspection.measured_cap_height_um,
            "em_height_um": style.em_height_um,
        },
        "drawing_profile": {
            "status": "EDITORIAL_UNTIL_ESKD_91_CONCLUSION",
            "module_um": policy.module_um,
            "row_modules": policy.pitch_modules,
            "ink_padding_um": policy.ink_padding_um,
            "line_width_um": policy.line_width_um,
            "lead_length_um": policy.lead_length_um,
        },
        "cases": {},
    }
    for count in (4, 8, 14, 40, 64):
        kind = "analog" if count == 8 else "digital"
        unit, plan = _fixture(count, kind, style, measure)
        render = render_resolved_ic(unit, style, measure, policy=policy)
        diag = render_resolved_ic(unit, style, measure, policy=policy,
                                  review_overlay=True)
        key = f"ic-{count:02d}-{kind}"
        (folder / f"{key}-clean.svg").write_text(render.svg, encoding="utf-8")
        (folder / f"{key}-diagnostic.svg").write_text(diag.svg, encoding="utf-8")
        text_boxes = [x for x in render.ink if x.text]
        protected_strokes = [x for x in render.ink if x.kind in (
            "outer-stroke", "field-divider", "zone-divider", "pin-lead",
        )]
        min_gap = min(
            _bbox_gap(t.box, edge.box)
            for t in text_boxes for edge in protected_strokes
        )
        assert min_gap >= policy.ink_padding_um, (count, min_gap)
        assert tuple((p.pin_id, p.anchor) for p in unit.pins) == render.pin_anchors
        report["cases"][key] = {
            "physical_pin_count": count,
            "has_analog_function": kind == "analog",
            "frame_width_um": plan.width_um,
            "frame_height_um": plan.height_um,
            "pitch_um": plan.row_pitch_um,
            "main_width_um": plan.main_width_um,
            "left_width_um": plan.left_width_um,
            "right_width_um": plan.right_width_um,
            "row_count": plan.row_count,
            "minimum_text_to_stroke_ink_gap_um": round(min_gap, 3),
            "text_box_count": len(text_boxes),
            "pin_source": "DEMONSTRATION_ONLY_NOT_DATASHEET",
            "pin_anchors": {
                pin.pin_id: [pin.anchor.x, pin.anchor.y]
                for pin in unit.pins
            },
            "all_measured_text_regions": [{
                "owner": b.owner, "kind": b.kind,
                "text": b.text,
                "ink_um": [
                    b.box.min_x, b.box.min_y, b.box.max_x, b.box.max_y,
                ],
            } for b in text_boxes],
            "source_pin_numbers": [p.number for p in unit.pins],
            "status": "DRAFT",
        }
    (folder / "ic-metric-audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("output/ic-cycle7"))
    args = parser.parse_args(argv)
    result = generate(args.output_dir, args.font_file)
    print("DRAFT real Type A IC metrics:", {
        name: {
            "count": row["physical_pin_count"],
            "size_mm": [row["frame_width_um"]/1000, row["frame_height_um"]/1000],
            "min_text_stroke_mm": row["minimum_text_to_stroke_ink_gap_um"]/1000,
        } for name, row in result["cases"].items()
    })


if __name__ == "__main__":
    main()
