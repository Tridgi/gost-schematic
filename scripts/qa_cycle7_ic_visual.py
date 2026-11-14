"""QA #92 actual PAINT #88 E3 IC renderer + measured OpenGost Type A SVG/PNG gate.

All 2/8/14/40/64-pin data here are EXPLICIT SYNTHETIC TEST PIN ARRANGEMENTS
(never manufacturer datasheet/approved component claims). The renderer is the
byte-identical production draft from the pinned owner SHA, not a test double.
Full physical IC semantic identity #87 remains BLOCKED until actual owner code.
"""
import argparse
import json
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cycle7_support import BLOBS, OWNER_SHA, owner_renderer

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def _fixture(mod, n, label, content, transform=None):
    assert n % 2 == 0 and n >= 2
    trans = Transform() if transform is None else transform
    left = n // 2
    pins0 = []
    for number in range(1, n+1):
        is_left = number <= left
        side = Side.LEFT if is_left else Side.RIGHT
        row = number if is_left else number-left
        pins0.append(mod.ResolvedIcPin(
            pin_id=f"p{number}", number=str(number),
            label=f"ВХОД_{number:02d}" if is_left
                else f"OUTPUT_{number:02d}",
            side=side, row=row,
            # Preliminary value is discarded before owner rendering;
            # final physical anchor computed from *specified test* geometry.
            anchor=Point(0, 0),
            role="in" if is_left else "out",
        ))
    policy = mod.IcRenderingPolicy()
    metrics = PillowTextMeasurer()
    style = content[1]
    field = content[0]
    suggestion = mod.propose_ic_dimensions(
        field, tuple(pins0), style, metrics, policy
    )
    width = suggestion.width_um
    height = suggestion.height_um
    assert width % policy.module_um == 0
    assert height % policy.module_um == 0
    body = Box(0, 0, width, height)
    origin = Point(30000, 33000)
    # PR88 1b09e59 contract: anchor is EXTERNAL copper connection end.
    # Border point and lead direction are separately derived only in this
    # TEST fixture. Actual owner render checks exact end points against them.
    resolved = []
    for pin in pins0:
        rim = trans.apply(Point(
            0 if pin.side == Side.LEFT else width,
            pin.row * suggestion.row_pitch_um
            + suggestion.row_pitch_um // 2,
        )) + origin
        outward = trans.side(pin.side)
        from gost_schematic.core.geometry import SIDE_VECTORS

        offset = SIDE_VECTORS[outward]
        resolved.append(replace(
            pin,
            anchor=Point(
                rim.x + offset.x * suggestion.lead_length_um,
                rim.y + offset.y * suggestion.lead_length_um,
            ),
        ))
    return mod.IcResolvedUnit(
        reference=label, body=body, pins=tuple(resolved),
        content=field, origin=origin, transform=trans,
    ), suggestion


def _find_ink_in_real_png(image, box, view):
    # Physical 300 DPI raster from CairoSVG. Require INK inside each text box,
    # not just a renderer-reported bbox with invisible/omitted text.
    from PIL import Image

    with Image.open(image) as opened:
        pic = opened.convert("RGB")
        vx, vy, w, h = view
        scale_x = pic.width / w
        scale_y = pic.height / h
        x0 = max(0, int((box.min_x / 1000 - vx) * scale_x) - 2)
        x1 = min(pic.width, int((box.max_x / 1000 - vx) * scale_x) + 3)
        y0 = max(0, int((box.min_y / 1000 - vy) * scale_y) - 2)
        y1 = min(pic.height, int((box.max_y / 1000 - vy) * scale_y) + 3)
        assert x1 > x0 and y1 > y0, (box, view)
        crop = pic.crop((x0, y0, x1, y1))
        pixels = list(crop.getdata())
        return sum(1 for p in pixels if max(p) < 160)


def run(font_file, output):
    import cairosvg

    output.mkdir(parents=True, exist_ok=True)
    face = inspect_type_a_font(font_file, h_um=2500)
    assert abs(face.cap_height_error_um) <= 5
    mod = owner_renderer()
    face_sha = sha256(Path(font_file).read_bytes()).hexdigest()
    assert face_sha == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    ), "Owner-visible ink must use the exact reviewed OpenGost Type A face"
    style = face.style
    metrics = PillowTextMeasurer()
    filenames = {}
    reports = []
    for n in (2, 8, 14, 40, 64):
        label = "DA1" if n in (2, 8) else f"DD{n}"
        function = (
            "АНАЛОГОВЫЙ КОМПАРАТОР" if n <= 8
            else "MULTICHANNEL DIGITAL INTERFACE"
        )
        field = mod.IcFieldContent(
            function=function, main_rows=("ГОСТ 2.743 / DRAFT",),
            analog=n <= 8,
        )
        unit, size = _fixture(mod, n, label, (field, style))
        drawn = mod.render_resolved_ic(
            unit, style, metrics, page_bounds=Box(0, 0, 420000, 297000),
            review_overlay=True,
        )
        assert drawn.font_sha256 == face_sha
        assert len(drawn.pin_anchors) == n
        assert all(
            rendered == original.anchor
            for (_, rendered), original
            in zip(drawn.pin_anchors, unit.pins, strict=True)
        )
        root = ET.fromstring(drawn.svg)
        assert root.attrib["data-document-kind"] == "E3-physical-IC"
        assert root.attrib["data-approval"] == "DRAFT"
        assert root.attrib["data-font-sha256"] == face_sha
        leads = root.findall(
            f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
        )
        assert len(leads) == n
        ink_nodes = root.findall(
            f".//{SVG}text[@data-layer='ic-text']"
        )
        assert len([a for a in ink_nodes if a.get("data-kind") == "pin-number"]) == n
        assert len([a for a in ink_nodes if a.get("data-kind") == "pin-label"]) == n
        assert any(x.text == function for x in ink_nodes)
        for lead in leads:
            ref = lead.attrib["data-pin-id"]
            owner = next(p for p in unit.pins if p.pin_id == ref)
            assert [
                round(float(lead.attrib["x2"]) * 1000),
                round(float(lead.attrib["y2"]) * 1000),
            ] == [owner.anchor.x, owner.anchor.y]
        # Independent real SVG glyph metadata vs owner measured ink
        txt = [x for x in drawn.ink if x.kind in {
            "function", "pin-label", "pin-number", "refdes", "main-text"
        }]
        assert len(txt) == len(ink_nodes)
        by_ink = {
            (x.kind, x.owner, x.text): x.box for x in txt
        }
        assert len(by_ink) == len(txt), "Overlapping/duplicate title identities"
        for node in ink_nodes:
            key = node.get("data-kind"), node.get("data-owner"), node.text
            expected = by_ink[key]
            assert node.get("data-ink-um") == ",".join(str(v) for v in (
                expected.min_x, expected.min_y, expected.max_x, expected.max_y
            ))
        # Real raster must visibly contain every glyph; not only XML markers.
        svg_name = f"qa-e3-ic-{n:02d}-pins.svg"
        png_name = f"qa-e3-ic-{n:02d}-pins-300dpi.png"
        (output / svg_name).write_text(drawn.svg, encoding="utf-8")
        cairosvg.svg2png(
            bytestring=drawn.svg.encode(),
            write_to=str(output / png_name), dpi=300,
        )
        view = tuple(float(v) for v in root.attrib["viewBox"].split())
        missing = [
            (x.owner, x.kind, x.text) for x in txt
            if _find_ink_in_real_png(output / png_name, x.box, view) == 0
        ]
        assert not missing, f"TEXT_NOT_VISIBLE_IN_REAL_RASTER: {missing}"
        # Confirm physical symbol field lines remain separate.
        assert root.findall(
            f".//{SVG}rect[@data-kind='actual-stroked-outer-frame']"
        )
        for file in (svg_name, png_name):
            raw = (output / file).read_bytes()
            filenames[file] = {
                "sha256": sha256(raw).hexdigest(), "bytes": len(raw)
            }
        reports.append({
            "pins": n, "reference": label,
            "real_svg_pin_leads": len(leads),
            "real_svg_text_nodes": len(ink_nodes),
            "raster_missing_ink": len(missing),
            "proposed_width_um": size.width_um,
            "proposed_height_um": size.height_um,
            "row_pitch_um": size.row_pitch_um,
            "body_width_um": drawn.body_world.max_x-drawn.body_world.min_x,
            "body_height_um": drawn.body_world.max_y-drawn.body_world.min_y,
        })
        # A 1µm displacement must trigger real renderer's fail-closed check.
        bad = replace(
            unit, pins=(replace(unit.pins[0],
                anchor=Point(unit.pins[0].anchor.x + 1,
                             unit.pins[0].anchor.y)), *unit.pins[1:])
        )
        try:
            mod.render_resolved_ic(bad, style, metrics)
        except ValueError as exc:
            assert "IC_PIN_ANCHOR_MISMATCH" in str(exc)
        else:
            raise AssertionError("Owner renderer accepted displaced physical pin")
        try:
            mod.render_resolved_ic(
                unit, style, metrics, page_bounds=Box(0, 0, 50000, 30000)
            )
        except ValueError as exc:
            assert "IC_PAGE_OVERFLOW" in str(exc)
        else:
            raise AssertionError("Owner renderer silently overflowed page")
    report = {
        "issue": 92,
        "status": "PARTIAL_P0_RENDERER_ONLY_NOT_FULL_REAL_IC",
        "owner_source": OWNER_SHA,
        "git_blobs": BLOBS,
        "font_sha256": face_sha,
        "font_requested_cap_um": face.requested_cap_height_um,
        "font_actual_cap_um": face.measured_cap_height_um,
        "rasterization": "real CairoSVG 300 DPI, pixels verified for each text ink",
        "approval": "DRAFT_NOT_GOST_CERTIFIED",
        "semantic_ic_87": "BLOCKED",
        "separate_real_ic_pinout": "BLOCKED_VENDOR_DATASHEET",
        "samples": reports,
        "files": filenames,
    }
    (output / "qa-cycle7-ic-evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(run(args.font_file, args.output_dir))
