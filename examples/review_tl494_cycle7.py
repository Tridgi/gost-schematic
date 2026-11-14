"""True TI 16-number annotation gallery; positions are NEW synthetic draft.

Does NOT claim the unchanged 679.3mm connected user sheet is repaired.
Old reference physical anchors remain frozen pending ELEKTRIK #87 revision.
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcFunctionReading,
    IcRenderingPolicy,
    IcResolvedUnit,
    ResolvedIcPin,
    propose_ic_dimensions,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_tl494_profile import (
    TI_TL494_PIN_NAMES,
    apply_tl494_portrait_profile,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"
LEFT = ("2", "4", "3", "5", "6", "7", "1", "16")
RIGHT = ("12", "15", "14", "13", "8", "11", "9", "10")


def specimen(style, measure, pose: Transform = Transform()):
    policy = IcRenderingPolicy()
    preliminary = []
    for side, numbers in ((Side.LEFT, LEFT), (Side.RIGHT, RIGHT)):
        for row, number in enumerate(numbers, 1):
            full, alias = TI_TL494_PIN_NAMES[number]
            preliminary.append(ResolvedIcPin(
                f"DA1.P{number}", number, full,
                side, row, Point(200000+int(number), 300000+int(number)),
                "power" if number in ("7", "12", "14") else "passive",
                display_alias=alias,
            ))
    original = tuple(preliminary)
    content = IcFieldContent(function="PWM", analog=True)
    proposals = tuple(
        propose_ic_dimensions(
            content, original, style, measure, policy,
            function_rotation=angle, shared_function_envelope=True,
        ) for angle in (0, 90, 270)
    )
    if len({p.row_pitch_um for p in proposals}) != 1:
        raise ValueError("IC_TL494_PRINT_FONT_PITCH_REVISION_REQUIRED")
    pitch = proposals[0].row_pitch_um
    width = max(p.width_um for p in proposals)
    height = max(width + pitch, *(p.height_um for p in proposals))
    height = ((height + pitch - 1) // pitch) * pitch
    origin = Point(250000, 180000)
    pins = []
    for p in original:
        local = Point(
            0 if p.side is Side.LEFT else width,
            p.row * pitch + pitch // 2,
        )
        frame = pose.apply(local) + origin
        normal = SIDE_VECTORS[pose.side(p.side)]
        pins.append(replace(p, anchor=Point(
            frame.x + normal.x * proposals[0].lead_length_um,
            frame.y + normal.y * proposals[0].lead_length_um,
        )))
    baseline = IcResolvedUnit(
        "DA1", Box(0, 0, width, height),
        tuple(pins), content, origin, pose,
    )
    return apply_tl494_portrait_profile(baseline), policy


def generate(folder: Path, font_file: Path):
    style = inspect_type_a_font(font_file, h_um=3500).style
    measure = PillowTextMeasurer()
    folder.mkdir(parents=True, exist_ok=True)
    proof = {
        "status": "DRAFT_TI_LABELS_SYNTHETIC_PHYSICAL_PLACEMENT",
        "full_labels": {
            number: full for number, (full, _) in TI_TL494_PIN_NAMES.items()
        },
        "visible_alias": {
            number: alias for number, (_, alias) in TI_TL494_PIN_NAMES.items()
        },
        "type_a_sha256": style.font_sha256,
        "cases": {},
    }
    for angle in (0, 90, 270):
        for rotation, mirror in (
            (0, False), (90, False), (180, False), (270, False),
            (0, True), (90, True), (180, True), (270, True),
        ):
            base, policy = specimen(
                style, measure, Transform(rotation, mirror),
            )
            unit = base.select_function_text_reading({
                0: IcFunctionReading.HORIZONTAL,
                90: IcFunctionReading.TOP_TO_BOTTOM,
                270: IcFunctionReading.BOTTOM_TO_TOP,
            }[angle])
            targets = tuple(IcConnectionTarget(
                pin.pin_id, PinRef("DA1", pin.number), pin.anchor,
                True,
            ) for pin in unit.pins)
            for diagnostic in (False, True):
                result = render_resolved_ic(
                    unit, style, measure, policy=policy,
                    editor_targets=targets, editor_overlay=diagnostic,
                    review_overlay=diagnostic, glyph_detail=True,
                )
                root = ET.fromstring(result.svg)
                fn = root.find(f".//{SVG}text[@data-kind='function']")
                assert fn is not None and fn.text == "PWM"
                assert root.get("data-function-reading-local") == {
                    0: "horizontal", 90: "top_to_bottom",
                    270: "bottom_to_top",
                }[angle]
                assert result.pin_anchors == tuple(
                    (p.pin_id, p.anchor) for p in unit.pins
                )
                assert len(result.glyph_ink) > 16
                name = (
                    f"tl494-16-pwm-{angle}-d4-{rotation}"
                    f"-m{int(mirror)}-"
                    f"{'diagnostic' if diagnostic else 'clean'}"
                )
                (folder / f"{name}.svg").write_text(
                    result.svg, encoding="utf-8",
                )
                labels = root.findall(f".//{SVG}text[@data-kind='pin-label']")
                assert len(labels) == 16
                assert all(len(el.text) <= 6 for el in labels)
                assert {el.get("data-physical-pin-number") for el in labels} == (
                    set(TI_TL494_PIN_NAMES)
                )
                assert all(
                    el.get("data-full-manufacturer-name") ==
                    TI_TL494_PIN_NAMES[el.get("data-physical-pin-number")][0]
                    for el in labels
                )
                if diagnostic:
                    assert len(root.findall(
                        f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
                    )) == 16
                else:
                    assert "editor-connection-targets" not in result.svg
                proof["cases"][name] = {
                    "angle": angle, "D4": [rotation, mirror],
                    "physical_count": len(result.pin_anchors),
                    "body_um": [
                        unit.body.max_x, unit.body.max_y,
                    ],
                    "anchors": {
                        pin.number: [pin.anchor.x, pin.anchor.y]
                        for pin in unit.pins
                    },
                }
    assert len(proof["cases"]) == 48
    for key, case in proof["cases"].items():
        if "-pwm-270-" in key:
            other = key.replace("-pwm-270-", "-pwm-0-")
            assert case["anchors"] == proof["cases"][other]["anchors"]
            assert case["body_um"] == proof["cases"][other]["body_um"]
    (folder / "tl494-pwm-reading-and-16-aliases.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS TL494 synthetic placements / genuine Type A:",
        len(proof["cases"]), "vector diagrams, 16 real TI pin numbers",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output_dir, args.font_file)


if __name__ == "__main__":
    main()
