"""Re-render ONLY DA1's visible SVG ink in the frozen connected TL494 sheet.

The original reference drawing is SHA-pinned and source-owned. All 23 parts,
all 91 authored wire strokes, their original Net IDs, junctions and a/b
continuation artwork remain exactly unchanged. This is a read-only graphical
migration, NOT an electrical model correction or route revision.
"""
import argparse
import copy
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcRenderingPolicy,
    IcResolvedUnit,
    ResolvedIcPin,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_tl494_profile import (
    TI_TL494_PIN_NAMES,
    apply_tl494_portrait_profile,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def _um(value: str) -> int:
    exact = Decimal(value) * 1000
    integer = int(exact)
    if Decimal(integer) != exact:
        raise ValueError("IC_TL494_SOURCE_NON_INTEGER_MICROMETRE")
    return integer


def _source_wires(root):
    return tuple((
        n.get("data-wire-index"), n.get("data-net"),
        n.get("x1"), n.get("y1"), n.get("x2"), n.get("y2"),
        n.get("stroke-width"),
    ) for n in root.findall(f".//{SVG}line[@data-layer='wires']"))


def _source_junctions(root):
    return tuple((
        n.get("cx"), n.get("cy"), n.get("r"),
        n.get("data-kind"),
    ) for n in root.findall(
        f".//{SVG}g[@data-layer='explicit-junctions']/{SVG}circle"
    ))


def _source_continuations(root):
    return tuple((
        n.get("cx"), n.get("cy"), n.get("r"),
        n.get("data-nonphysical-net-continuation"),
    ) for n in root.findall(
        f".//{SVG}circle[@data-nonphysical-net-continuation]"
    ))


def _resolved_source_ic(root, *, alias_view=False):
    owners = [
        n for n in root if n.tag == SVG+"g"
        and n.get("data-owner") == "DA1"
        and n.get("data-physical-pin-count") == "16"
    ]
    if len(owners) != 1:
        raise ValueError("TL494_SOURCE_DA1_GRAPHIC_OWNER_AMBIGUOUS")
    old = owners[0]
    frame = old.find(f".//{SVG}rect[@data-kind='actual-stroked-outer-frame']")
    if frame is None:
        raise ValueError("TL494_SOURCE_REAL_IC_FRAME_REQUIRED")
    left, top, wide, tall = (
        _um(frame.get("x")), _um(frame.get("y")),
        _um(frame.get("width")), _um(frame.get("height")),
    )
    # Source is already PORTRAIT! A new body/PinRef geometry is not necessary.
    if (wide, tall) != (60000, 67500):
        raise ValueError("TL494_SOURCE_BODY_REVISION_NOT_AUTHORIZED")
    lines = old.findall(
        f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
    )
    if len(lines) != 16:
        raise ValueError("TL494_SOURCE_16_PHYSICAL_LEADS_REQUIRED")
    lines_by_number = {}
    pins = []
    for line in lines:
        number = line.get("data-pin-number")
        if number in lines_by_number or number not in TI_TL494_PIN_NAMES:
            raise ValueError("TL494_SOURCE_DUPLICATE_OR_UNKNOWN_PIN")
        lines_by_number[number] = line
        boundary_x = _um(line.get("x1"))
        port_y = _um(line.get("y1"))
        if boundary_x == left:
            side = Side.LEFT
        elif boundary_x == left + wide:
            side = Side.RIGHT
        else:
            raise ValueError("TL494_SOURCE_PORT_NOT_ON_PHYSICAL_FRAME")
        row, remainder = divmod(port_y - top - 3750, 7500)
        if remainder or row not in range(1, 9):
            raise ValueError("TL494_SOURCE_ROW_PITCH_OR_ANCHOR_MISMATCH")
        physical = Point(_um(line.get("x2")), _um(line.get("y2")))
        full, _ = TI_TL494_PIN_NAMES[number]
        pins.append(ResolvedIcPin(
            line.get("data-pin-id"), number, full,
            side, row, physical, line.get("data-role"),
        ))
    if set(lines_by_number) != set(TI_TL494_PIN_NAMES):
        raise ValueError("TL494_SOURCE_VENDOR_16PIN_COVERAGE_MISMATCH")
    # Verify original printed labels before authorizing a changed visible
    # alias. No inference of manufacturer's role or Net from string.
    source_label_nodes = old.findall(
        f".//{SVG}text[@data-kind='pin-label']"
    )
    source_by_owner = {
        n.get("data-owner"): n.text for n in source_label_nodes
    }
    if len(source_label_nodes) != 16:
        raise ValueError("TL494_SOURCE_PIN_TEXT_INCOMPLETE")
    for pin in pins:
        owner = f"{pin.side.value}.{pin.row}"
        expected_name = (
            TI_TL494_PIN_NAMES[pin.number][1]
            if alias_view else pin.label
        )
        if source_by_owner.get(owner) != expected_name:
            raise ValueError(
                f"TL494_SOURCE_PRINTED_LABEL_MISMATCH: {pin.number}"
            )
    unit = IcResolvedUnit(
        "DA1", Box(0, 0, wide, tall),
        tuple(pins), IcFieldContent("PWM", analog=True),
        Point(left, top),
    )
    return old, apply_tl494_portrait_profile(unit)


def migrate(root, style, measurer, policy, *,
            diagnostic: bool = False):
    drawing = copy.deepcopy(root)
    original_wires = _source_wires(root)
    original_junctions = _source_junctions(root)
    original_continuations = _source_continuations(root)
    assert len(original_wires) == 91
    assert len(original_junctions) == 37
    previous, model = _resolved_source_ic(drawing)
    positions_before = tuple(
        (p.pin_id, p.anchor) for p in model.pins
    )
    targets = tuple(IcConnectionTarget(
        p.pin_id, PinRef("DA1", p.number),
        p.anchor, True,
        net_id=None,  # NEVER GUESS Net from adjacent SVG conductor
    ) for p in model.pins)
    result = render_resolved_ic(
        model, style, measurer, policy=policy,
        editor_targets=targets, editor_overlay=diagnostic,
        review_overlay=diagnostic, glyph_detail=True,
    )
    if result.pin_anchors != positions_before:
        raise AssertionError("TL494_PROFILE_MOVED_ANY_PHYSICAL_PIN")
    former = list(drawing).index(previous)
    drawing.remove(previous)
    new_group = ET.Element(SVG+"g", {
        "data-owner": "DA1",
        "data-physical-pin-count": "16",
        "data-ink-source": "PAINT_93_TL494_V3_BOTTOM_TO_TOP",
        "data-font-sha256": style.font_sha256,
        "data-topology-source": "UNCHANGED_REFERENCE_PHOTO_SVG",
    })
    symbol_root = ET.fromstring(result.svg)
    for element in symbol_root:
        if element.tag == SVG+"title":
            continue
        new_group.append(copy.deepcopy(element))
    drawing.insert(former, new_group)
    drawing.set("data-tl494-pwm-reading", "bottom_to_top")
    drawing.set("data-approval-status", "DRAFT")
    drawing.set("data-alias-policy", "source_ti_16pins_max6")
    if diagnostic:
        drawing.set("data-editor-diagnostic", "true")
    if _source_wires(drawing) != original_wires:
        raise AssertionError("TL494_REPAINT_MUTATED_ANY_WIRE_OR_NET")
    if _source_junctions(drawing) != original_junctions:
        raise AssertionError("TL494_REPAINT_MUTATED_ANY_JUNCTION")
    if _source_continuations(drawing) != original_continuations:
        raise AssertionError("TL494_REPAINT_MUTATED_CONTINUATION_AB")
    reprinted, unit_again = _resolved_source_ic(
        drawing, alias_view=True,
    )
    assert unit_again.pins == model.pins
    assert reprinted.get("data-owner") == "DA1"
    # 16 original numbered physical lead x2/y2 still physically valid.
    new_leads = reprinted.findall(
        f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
    )
    assert len(new_leads) == 16
    for lead in new_leads:
        source = next(
            p for p in model.pins
            if p.number == lead.get("data-pin-number")
        )
        assert (
            _um(lead.get("x2")), _um(lead.get("y2"))
        ) == (source.anchor.x, source.anchor.y)
    if diagnostic:
        markers = reprinted.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        assert len(markers) == 16
    else:
        assert "editor-connection-targets" not in ET.tostring(
            drawing, encoding="unicode",
        )
    return drawing, model, result


def generate(original_file: Path, font_file: Path, output: Path):
    root = ET.fromstring(original_file.read_text(encoding="utf-8"))
    inspection = inspect_type_a_font(font_file, h_um=3500)
    style = inspection.style
    measure = PillowTextMeasurer()
    policy = IcRenderingPolicy()
    output.mkdir(parents=True, exist_ok=True)
    manifests = {}
    for diagnostic in (False, True):
        new, unit, ic = migrate(
            root, style, measure, policy, diagnostic=diagnostic,
        )
        mode = "diagnostic" if diagnostic else "clean"
        fname = f"TL494_named_photo_AFTER_btt_FB_OC_{mode}.svg"
        (output/fname).write_text(
            ET.tostring(new, encoding="unicode")+"\n",
            encoding="utf-8",
        )
        manifests[mode] = {
            "file": fname, "source_wires": 91,
            "physical_PINREF": [p.number for p in unit.pins],
            "real_16_anchor_um": {
                p.number: [p.anchor.x, p.anchor.y] for p in unit.pins
            },
            "source_net_wires_unchanged": True,
            "source_explicit_junctions_unchanged": True,
            "source_ab_continuation_unchanged": True,
            "font_actual_sha256": ic.font_sha256,
            "PWM_direction": "bottom_to_top",
            "original_full_manufacturer_names_preserved": True,
            "electrical_role_of_feedback_source": "UNVERIFIED_REFER_TO_ELEKTRIK_IC",
        }
    assert (manifests["clean"]["real_16_anchor_um"] ==
            manifests["diagnostic"]["real_16_anchor_um"])
    (output/"TL494_connected_before_after_immutable_91_wires.json").write_text(
        json.dumps(manifests, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print("PASS source connected TL494: real 60x67.5mm portrait DA1,"
          " 16 identical world PinRef endpoints, 91 unchanged Net wire records,"
          " PWM reads bottom-to-top, aliases FB/OC, print still 679.3mm")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-svg", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.source_svg, args.font_file, args.output_dir)


if __name__ == "__main__":
    main()
