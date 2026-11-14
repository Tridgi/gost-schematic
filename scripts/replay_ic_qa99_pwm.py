"""Replay QA #99's exact independently authored PWM fixture against live PAINT.

This extracts _port_fixture from a SHA-pinned QA source file in the runner,
without modifying the original QA branch or replacing its failed test.
The real external QA workflow must separately re-pin and rerun for signoff.
"""
import argparse
import ast
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.rendering import ic_rectangular as paint
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def replay(qa_source: Path, font_file: Path, output_dir: Path) -> None:
    text = qa_source.read_text(encoding="utf-8")
    parsed = ast.parse(text, filename=str(qa_source))
    matching = [
        node for node in parsed.body if isinstance(
            node, ast.FunctionDef,
        ) and node.name == "_port_fixture"
    ]
    if len(matching) != 1:
        raise ValueError("IC_QA99_SOURCE_FIXTURE_MISSING_OR_DUPLICATE")
    snippet = ast.Module(body=matching, type_ignores=[])
    names = {
        "paint": paint, "SIDE_VECTORS": SIDE_VECTORS,
        "Box": Box, "Point": Point, "Side": Side,
        "Transform": Transform, "replace": replace,
    }
    # The fixture is fetched by immutable Git SHA from QA #99 in CI, not
    # user input; only the named function is compiled, never the full script.
    exec(compile(snippet, str(qa_source), "exec"), names)  # noqa: S102
    independent = names["_port_fixture"]
    face = inspect_type_a_font(font_file, h_um=2500)
    metrics = PillowTextMeasurer()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": str(qa_source),
        "status": "DRAFT_CROSS_SOURCE_FIXTURE_REPLAY_NOT_QA99_SIGNOFF",
        "font_sha256": face.style.font_sha256,
        "cases": {},
    }
    for count in (8, 14, 40, 64):
        for word in ("PWM_CONTROLLER", "КОНТРОЛЛЕР_ШИМ"):
            for angle in (0, 90, 180, 270):
                for mirror in (False, True):
                    pair = independent(
                        paint, count, face.style, metrics,
                        word, Transform(angle, mirror),
                    )
                    variant = replace(pair, function_rotation=0)
                    out90 = paint.render_resolved_ic(
                        pair, face.style, metrics, glyph_detail=True,
                    )
                    out0 = paint.render_resolved_ic(
                        variant, face.style, metrics, glyph_detail=True,
                    )
                    assert out90.body_world == out0.body_world
                    assert out90.pin_anchors == out0.pin_anchors
                    root90, root0 = (
                        ET.fromstring(out90.svg), ET.fromstring(out0.svg)
                    )
                    for layer in ("ic-outline", "ic-physical-pin-leads"):
                        a, b = (
                            root.findall(
                                f".//{SVG}g[@data-layer='{layer}']",
                            ) for root in (root90, root0)
                        )
                        assert len(a) == len(b) == 1
                        assert ET.tostring(a[0]) == ET.tostring(b[0])
                    fn90, fn0 = (
                        root.find(f".//{SVG}text[@data-kind='function']")
                        for root in (root90, root0)
                    )
                    assert fn90 is not None and fn0 is not None
                    assert fn90.text == fn0.text == word
                    assert fn90.get("transform", "").startswith("matrix(")
                    assert "transform" not in fn0.attrib
                    for result in (out90, out0):
                        assert len(result.pin_anchors) == count
                        assert result.glyph_ink
                        assert not any(color in result.svg for color in (
                            "#148645", "#8b1e27",
                        ))
                    key = f"{count}-{word}-{angle}-m{int(mirror)}"
                    manifest["cases"][key] = {
                        "status": "PASS_BOTH_0_90",
                        "pin_count": count,
                        "original_qa_fixture": True,
                        "body_unchanged": True,
                        "world_pinrefs_unchanged": True,
                    }
    assert len(manifest["cases"]) == 64
    (output_dir / "qa99-pwm-exact-source-fixture-replay.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("PASS exact external QA #99 _port_fixture: 64 pairs, 128 renders")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-file", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    replay(args.qa_file, args.font_file, args.output_dir)


if __name__ == "__main__":
    main()
