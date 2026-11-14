"""Cycle7 #88 physical IC vector/ink gallery; all pin maps are SYNTHETIC DRAFT.

The demonstration is NOT a manufacturer pinout and NEVER creates Circuit.PinRef.
The two-phase fixture creates synthetic resolved anchors explicitly *after* the
size proposal; the production renderer accepts those authoritative Points only.
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path

from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Side
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcOrientation,
    IcRenderingPolicy,
    IcResolvedUnit,
    ResolvedIcPin,
    propose_ic_dimensions,
    render_resolved_ic,
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
        function=">" if kind == "analog" else "RAM" if count >= 40 else "RG" if count == 14 else "&",
        main_rows=extras,
        left_zone_after=(3, 11) if count >= 40 else (2,) if count >= 8 else (),
        right_zone_after=(5,) if count >= 14 else (),
        analog=kind == "analog",
    )
    plan = propose_ic_dimensions(content, tuple(sample), style, measurer)
    origin = Point(30000, 20000)
    resolved = []
    for p in sample:
        frame = Point(
            origin.x + (0 if p.side == Side.LEFT else plan.width_um),
            origin.y + p.row * plan.row_pitch_um + plan.row_pitch_um // 2,
        )
        outward = SIDE_VECTORS[p.side]
        resolved.append(replace(
            p, anchor=Point(
                frame.x + outward.x * plan.lead_length_um,
                frame.y + outward.y * plan.lead_length_um,
            ),
        ))
    resolved = tuple(resolved)
    unit = IcResolvedUnit(
        "DA1" if kind == "analog" else "DD1",
        Box(0, 0, plan.width_um, plan.height_um),
        resolved, content, origin,
    )
    return unit, plan


def _vertical_fixture(count, kind, style, measurer):
    """True source TOP/BOTTOM ports from independent typed side annotations."""
    canonical, _ = _fixture(count, kind, style, measurer)
    pre = tuple(replace(
        pin, side=Side.TOP if pin.side is Side.LEFT else Side.BOTTOM,
    ) for pin in canonical.pins)
    plan = propose_ic_dimensions(
        canonical.content, pre, style, measurer,
        orientation=IcOrientation.TOP_BOTTOM,
    )
    max_row = max(p.row for p in pre)
    origin = Point(35000, 25000)
    resolved = []
    for pin in pre:
        virtual_row = max_row + 1 - pin.row
        x = plan.width_um - (
            virtual_row * plan.row_pitch_um + plan.row_pitch_um // 2
        )
        y = 0 if pin.side is Side.TOP else plan.height_um
        outward = SIDE_VECTORS[pin.side]
        resolved.append(replace(
            pin, anchor=Point(
                origin.x + x + outward.x * plan.lead_length_um,
                origin.y + y + outward.y * plan.lead_length_um,
            ),
        ))
    return IcResolvedUnit(
        canonical.reference,
        Box(0, 0, plan.width_um, plan.height_um),
        tuple(resolved), canonical.content, origin,
        orientation=IcOrientation.TOP_BOTTOM,
        function_rotation=90, field_text_rotation=90,
    ), plan



def _portrait_function_pair(count, kind, style, measurer):
    """Two genuinely identical physical ICs, changing only PWM/ADC angle.

    This is a SYNTHETIC, profile-v2 DRAFT. All resolved port endpoints are
    built once from an explicit body revision and never re-proposed on toggle.
    """
    from gost_schematic.rendering.ic_rectangular import IcTypographyProfile

    source, _ = _fixture(count, kind, style, measurer)
    content = replace(source.content, function="ADC" if kind == "analog" else "PWM")
    policy = IcRenderingPolicy()
    rotated = propose_ic_dimensions(
        content, source.pins, style, measurer, policy, function_rotation=90,
    )
    flat = propose_ic_dimensions(
        content, source.pins, style, measurer, policy, function_rotation=0,
    )
    if rotated.row_pitch_um != flat.row_pitch_um:
        raise ValueError(
            "IC_PROFILE_PITCH_REVISION_REQUIRED: request ELEKTRIK geometry"
        )
    pitch = rotated.row_pitch_um
    width = max(flat.width_um, rotated.width_um)
    height = max(
        flat.height_um, rotated.height_um,
        (width // pitch + 1) * pitch,
    )
    origin = Point(30000, 20000)
    resolved = []
    for pin in source.pins:
        frame = Point(
            origin.x + (0 if pin.side is Side.LEFT else width),
            origin.y + pin.row * pitch + pitch // 2,
        )
        vector = SIDE_VECTORS[pin.side]
        resolved.append(replace(pin, anchor=Point(
            frame.x + vector.x * rotated.lead_length_um,
            frame.y + vector.y * rotated.lead_length_um,
        )))
    baseline = IcResolvedUnit(
        source.reference, Box(0, 0, width, height),
        tuple(resolved), content, origin,
    )
    portrait = baseline.select_typography_profile(
        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )
    return portrait, replace(portrait, function_rotation=0)

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
        "portrait_cases": {},
    }
    for count in (4, 8, 14, 40, 64):
        kind = "analog" if count == 8 else "digital"
        for orientation in ("horizontal", "vertical"):
            if orientation == "horizontal":
                unit, plan = _fixture(count, kind, style, measure)
                key = f"ic-{count:02d}-{kind}"
            else:
                unit, plan = _vertical_fixture(count, kind, style, measure)
                key = f"ic-{count:02d}-vertical"
            render = render_resolved_ic(
                unit, style, measure, policy=policy, glyph_detail=True,
            )
            diag = render_resolved_ic(
                unit, style, measure, policy=policy,
                review_overlay=True, glyph_detail=True,
            )
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
            "orientation": unit.orientation.value,
            "function_rotation": unit.function_rotation,
            "field_text_rotation": unit.field_text_rotation,
                "frame_width_um": plan.width_um,
                "frame_height_um": plan.height_um,
                "pitch_um": plan.row_pitch_um,
                "main_width_um": plan.main_width_um,
                "left_width_um": plan.left_width_um,
                "right_width_um": plan.right_width_um,
                "row_count": plan.row_count,
                "minimum_text_to_stroke_ink_gap_um": round(min_gap, 3),
                "text_box_count": len(text_boxes),
                "visible_glyph_count": len(render.glyph_ink),
                "glyph_ink_boxes": [{
                    "owner": item.owner,
                    "codepoint_index": item.index,
                    "char": item.char,
                    "ink_um": [
                        item.ink.min_x, item.ink.min_y,
                        item.ink.max_x, item.ink.max_y,
                    ],
                } for item in render.glyph_ink],
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

    # New independent-function portrait pair, kept separate from the ten
    # historical source-orientation SVGs and their byte-level conventions.
    for count in (8, 14, 40, 64):
        kind = "analog" if count == 8 else "digital"
        p90, p0 = _portrait_function_pair(count, kind, style, measure)
        pair = {}
        for angle, unit in ((90, p90), (0, p0)):
            result = render_resolved_ic(
                unit, style, measure, policy=policy, glyph_detail=True,
            )
            key = f"portrait-{count:02d}-function-{angle:02d}"
            (folder / f"{key}-clean.svg").write_text(
                result.svg, encoding="utf-8",
            )
            (folder / f"{key}-diagnostic.svg").write_text(
                render_resolved_ic(
                    unit, style, measure, policy=policy,
                    glyph_detail=True, review_overlay=True,
                ).svg, encoding="utf-8",
            )
            txt = tuple(x for x in result.ink if x.text)
            strokes = tuple(x for x in result.ink if x.kind in (
                "outer-stroke", "field-divider", "zone-divider", "pin-lead",
            ))
            distance = min(
                _bbox_gap(t.box, edge.box)
                for t in txt for edge in strokes
            )
            assert distance >= policy.ink_padding_um
            assert result.pin_anchors == tuple(
                (p.pin_id, p.anchor) for p in unit.pins
            )
            pair[str(angle)] = {
                "svg": f"{key}-clean.svg",
                "physical_pin_count": count,
                "body_width_um": unit.body.max_x - unit.body.min_x,
                "body_height_um": unit.body.max_y - unit.body.min_y,
                "angle_deg": angle,
                "minimum_ink_clearance_um": distance,
                "function_ink_um": [
                    x.box.min_x for x in txt if x.kind == "function"
                ] + [
                    value for x in txt if x.kind == "function"
                    for value in (x.box.min_y, x.box.max_x, x.box.max_y)
                ],
                "source_anchors": {
                    pin.pin_id: [pin.anchor.x, pin.anchor.y]
                    for pin in unit.pins
                },
                "glyph_ink_boxes": [
                    [g.owner, g.index, g.ink.min_x, g.ink.min_y,
                     g.ink.max_x, g.ink.max_y]
                    for g in result.glyph_ink
                ],
            }
        assert pair["90"]["source_anchors"] == pair["0"]["source_anchors"]
        assert (
            pair["90"]["body_width_um"] == pair["0"]["body_width_um"]
            and pair["90"]["body_height_um"] == pair["0"]["body_height_um"]
        )
        report["portrait_cases"][str(count)] = pair

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
