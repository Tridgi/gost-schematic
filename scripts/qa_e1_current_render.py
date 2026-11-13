"""Independent true PR80 82d400 + PR78 b7fa seven-block SVG/PNG proof.

No hand-painted seven-block fallback. Uses actual typed FunctionalBlocks,
PortRefs, authoritative model resolver, PR78 typed renderer, external OpenGost
Type A at measured 2.5mm cap, and independently inspects SVG path 'd' ink.
"""

import argparse
import json
import re
import sys
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "tests"))
from qa_e1_integration_support import (
    CURRENT_BLOBS,
    CURRENT_SHAS,
    real_current_sources,
)

SVG = "{http://www.w3.org/2000/svg}"
COORDS = re.compile(r"[ML] (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)")
VIA = {"L9": ((380000, 180000), (70000, 180000))}


def _real_path(d):
    out = []
    for sx, sy in COORDS.findall(d):
        x, y = Fraction(sx) * 1000, Fraction(sy) * 1000
        assert x.denominator == y.denominator == 1
        out.append([x.numerator, y.numerator])
    return out


def execute(directory: Path, font: Path):
    from PIL import Image

    try:
        import cairosvg
    except ImportError as err:
        raise RuntimeError("Dedicated CI requires CairoSVG") from err
    assert font.is_file(), "A real external OpenGost Type A font is mandatory"
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {}
    with real_current_sources() as (model, actual, legacy, typed):
        graph = actual.specimen()
        original_json = model.structural_to_json(graph)
        assert model.structural_from_json(original_json) == graph
        assert len(graph.blocks) == 7 and len(graph.ports) == 18
        assert len(graph.links) == 9
        legacy_seed = actual.ygo2_visual_seed()
        legacy_scene = legacy.validate_design(legacy_seed)
        assert len(legacy_scene["blocks"]) == 7
        canonical = legacy.semantic_projection(legacy_seed)
        assert canonical["diagram_type"] == "E1"
        semantic = model.structural_from_json(json.dumps(
            canonical, ensure_ascii=False
        ))
        assert semantic == graph
        anchors = model.resolve_port_positions(graph)
        expected = {
            (ref.block_id, ref.port_id): [p.x, p.y] for ref, p in anchors.items()
        }
        legacy_ports = {
            (b["id"], p["id"]): list(p["point_um"])
            for b in legacy_scene["blocks"] for p in b["ports"].values()
        }
        assert expected == legacy_ports
        for variant in ("clean", "diagnostic"):
            overlay = variant == "diagnostic"
            svg, manifest = typed.render_structural_model(
                graph, font, via_by_link=VIA, diagnostic=overlay
            )
            assert manifest["svg_sha256"] == sha256(svg.encode()).hexdigest()
            assert (manifest["block_count"], manifest["port_count"],
                    manifest["link_count"]) == (7, 18, 9)
            assert manifest["font"]["requested_cap_height_um"] == 2500
            assert abs(manifest["font"]["measured_cap_height_um"] - 2500) <= 5
            assert all(p["model_um"] == p["svg_um"] for p in manifest["ports"])
            assert all(
                tuple(p["svg_um"]) == tuple(expected[
                    (p["ref"]["block_id"], p["ref"]["port_id"])
                ])
                for p in manifest["ports"]
            )
            root = ET.fromstring(svg)
            assert root.get("data-diagram-type") == "E1"
            paths = root.findall(
                f".//{SVG}path[@data-role='functional-link']"
            )
            arrows = root.findall(
                f".//{SVG}path[@data-role='functional-process-arrow']"
            )
            assert len(paths) == len(arrows) == 9
            assert not root.findall(
                f".//{SVG}circle[@data-role='junction']"
            )
            owner_links = {link.id: link for link in graph.links}
            for path in paths:
                name = path.get("data-link-id")
                record = owner_links[name]
                points = _real_path(path.attrib["d"])
                assert points == json.loads(path.attrib["data-points-um"])
                assert points[0] == expected[
                    (record.source.block_id, record.source.port_id)
                ]
                assert points[-1] == expected[
                    (record.target.block_id, record.target.port_id)
                ]
                assert sum(a.get("data-link-id") == name for a in arrows) == 1
            if overlay:
                markers = root.findall(
                    f".//{SVG}circle[@data-role='declared-functional-port']"
                )
                assert len(markers) == 18
                for mark in markers:
                    key = tuple(mark.attrib["data-portref"].split(":"))
                    assert [
                        Fraction(mark.attrib["cx"]) * 1000,
                        Fraction(mark.attrib["cy"]) * 1000,
                    ] == expected[key]
            block_boxes = {
                box["block_id"]: box["bounds"]
                for box in manifest["block_boxes_um"]
            }
            assert len(manifest["text_hitboxes_um"]) >= 7
            for entry in manifest["text_hitboxes_um"]:
                ink, box = entry["bounds"], block_boxes[entry["block_id"]]
                assert box[0] < ink[0] < ink[2] < box[2]
                assert box[1] < ink[1] < ink[3] < box[3]
            stem = f"current-pr78-typed-seven-{variant}"
            svg_path = directory / (stem + ".svg")
            png_path = directory / (stem + ".png")
            svg_path.write_text(svg, encoding="utf-8")
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"), write_to=str(png_path),
                dpi=300,
            )
            with Image.open(png_path) as pic:
                pic.load()
                assert pic.width >= 1000 and pic.height >= 100
            manifest_path = directory / (stem + "-manifest.json")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            for file in (svg_path, png_path, manifest_path):
                raw = file.read_bytes()
                outputs[file.name] = {
                    "sha256": sha256(raw).hexdigest(), "bytes": len(raw)
                }
        seven_visual = legacy.render_svg(legacy_seed, diagnostic=True)
        target = directory / "current-pr78-seven-legacy-diagnostic.svg"
        target.write_text(seven_visual, encoding="utf-8")
        outputs[target.name] = {
            "sha256": sha256(target.read_bytes()).hexdigest(),
            "bytes": len(target.read_bytes()),
        }
        result = {
            "source_shas": CURRENT_SHAS,
            "exact_source_blobs": CURRENT_BLOBS,
            "rendered_with": "real PR78 typed render_structural_model",
            "model_authority": "real PR80 resolve_port_positions",
            "blocks": 7, "ports": 18, "links": 9,
            "actual_svg_path_endpoint_mismatches": 0,
            "actual_svg_marker_mismatches": 0,
            "real_measured_text_overflow_count": 0,
            "model_json_roundtrip": "PASS",
            "no_electrical_junctions": True,
            "legacy_projection_marker": "PASS current PR78 E1 discriminator",
            "font_sha256": manifest["font"]["sha256"],
            "font_measured_cap_height_um": manifest["font"]["measured_cap_height_um"],
            "svg_and_png": outputs,
            "standard_approval": "BLOCKED full GOST document/print approval; DRAFT",
        }
        report_path = directory / "qa-e1-current-seven-report.json"
        report_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--font-file", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(execute(args.output_dir, args.font_file))
