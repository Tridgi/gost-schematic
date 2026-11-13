"""Generate E1 integration-gate VISUAL EVIDENCE from real SHA-verified PR sources.

The 7-block drawing is an EXPLICIT QA diagnostic of PR80's genuine geometry,
NOT a PR78-rendered 7-block or a ГОСТ-certified SVG. The six-block and X-case
graphics are generated only by real PR78 render_svg(). Never claim a 7-block
integration where the source contract refuses it.
"""

import argparse
import json
import subprocess
import sys
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from qa_e1_integration_support import (  # noqa: E402
    PINNED_BLOBS,
    SOURCE_COMMITS,
    graphic_source,
    real_sources,
)
from qa_e1_integration_test import _crossing_view, _graphic_block, _two_port_diagram  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"


def mm(value):
    return str(Decimal(value) / 1000)


def _draw_seven_model_only(model, specimen):
    graph = specimen.specimen()
    anchors = model.resolve_port_positions(graph)
    minx = min(b.bounds.min_x for b in graph.blocks) - 6000
    maxx = max(b.bounds.max_x for b in graph.blocks) + 6000
    miny = min(b.bounds.min_y for b in graph.blocks) - 10000
    maxy = max(b.bounds.max_y for b in graph.blocks) + 10000
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{mm(maxx-minx)}mm",
        "height": f"{mm(maxy-miny)}mm",
        "viewBox": f"{mm(minx)} {mm(miny)} {mm(maxx-minx)} {mm(maxy-miny)}",
        "data-diagram-type": "E1",
        "data-renderer": "QA-ONLY-NOT-PR78",
        "data-approval": "DIAGNOSTIC-NO-GOST-CERTIFICATION",
    })
    ET.SubElement(root, "title").text = (
        "QA only: PR80 real seven-block semantic geometry; NOT PR78 graphics"
    )
    for b in graph.blocks:
        ET.SubElement(root, "rect", {
            "x": mm(b.origin.x), "y": mm(b.origin.y),
            "width": mm(b.width_um), "height": mm(b.height_um),
            "fill": "none", "stroke": "#1e293b", "stroke-width": "0.3",
            "data-block-id": b.id,
        })
        ET.SubElement(root, "text", {
            "x": mm(b.origin.x + b.width_um // 2),
            "y": mm(b.origin.y + b.height_um // 2),
            "text-anchor": "middle", "font-size": "2.6",
            "fill": "#111827", "data-role": "qa-block-id",
        }).text = b.id
    for edge in graph.links:
        a, b = anchors[edge.source], anchors[edge.target]
        ET.SubElement(root, "path", {
            "d": f"M {mm(a.x)} {mm(a.y)} L {mm(b.x)} {mm(b.y)}",
            "stroke": "#64748b", "stroke-width": "0.25",
            "fill": "none", "stroke-dasharray": "1,0.6",
            "data-role": "qa-inspection-chord", "data-link-id": edge.id,
        })
    for ref, point in anchors.items():
        ET.SubElement(root, "circle", {
            "cx": mm(point.x), "cy": mm(point.y), "r": "0.45",
            "fill": "#b91c1c",
            "data-block-id": ref.block_id,
            "data-port-id": ref.port_id,
            "data-role": "qa-semantic-anchor",
        })
    return ET.tostring(root, encoding="unicode") + "\n"


def _font_evidence(scene):
    try:
        from PIL import ImageFont
        file = subprocess.run(
            ["fc-match", "-f", "%{file}", "OpenGost Type A"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        font = ImageFont.truetype(file, 512)
    except (ImportError, OSError, subprocess.CalledProcessError):
        return {
            "status": "BLOCKED_FONT_UNAVAILABLE",
            "note": "No measured FreeType comparison possible",
        }
    source = Path(file)
    lines = []
    for b in scene["blocks"]:
        width = b["box_um"][2] - b["box_um"][0]
        available = width - 2 * 3000
        for line in b["title_lines"]:
            ink_width = round(font.getlength(line) * 3500 / 512)
            lines.append({
                "block": b["id"],
                "title_line": line,
                "measured_advance_um": ink_width,
                "available_um": available,
                "fits": ink_width <= available,
            })
    return {
        "status": "QA_EXTERNAL_FREETYPE_NOT_APPROVED_OPENGOST",
        "resolved_font": source.name,
        "font_sha256": sha256(source.read_bytes()).hexdigest(),
        "title_lines": lines,
        "all_widths_fit": all(line["fits"] for line in lines),
        "block_contour_proof": "SVG uses unembedded external font; vertical baseline not certified",
    }


def run(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {}
    with real_sources() as (model, specimen, visual):
        data = graphic_source()
        native_view = visual.validate_design(data)
        imgs = {
            "pr78-six-clean.svg": visual.render_svg(data),
            "pr78-six-diagnostic.svg": visual.render_svg(data, diagnostic=True),
            "pr78-four-crossing.svg": visual.render_svg(
                _crossing_view(), diagnostic=True
            ),
            "pr80-seven-model-only-diagnostic.svg": _draw_seven_model_only(
                model, specimen
            ),
            "pr80-seven-model.json": model.structural_to_json(
                specimen.specimen()
            ),
        }
        for filename, raw in imgs.items():
            target = directory / filename
            target.write_text(raw, encoding="utf-8")
            outputs[filename] = {
                "bytes": len(raw.encode()),
                "sha256": sha256(raw.encode()).hexdigest(),
            }
        try:
            import cairosvg
        except ImportError:
            png_status = "BLOCKED_CAiroSVG_NOT_INSTALLED"
        else:
            for filename in (
                "pr78-six-clean.svg", "pr78-six-diagnostic.svg",
                "pr78-four-crossing.svg",
                "pr80-seven-model-only-diagnostic.svg",
            ):
                dest = filename.replace(".svg", ".png")
                cairosvg.svg2png(
                    bytestring=imgs[filename].encode("utf-8"),
                    write_to=str(directory / dest), dpi=300,
                )
                raw = (directory / dest).read_bytes()
                outputs[dest] = {
                    "bytes": len(raw), "sha256": sha256(raw).hexdigest()
                }
            png_status = "300DPI_CAIROSVG_RASTER_NOT_PHYSICAL_PRINTER_PROOF"
        visual20 = _graphic_block(visual, height=20000)
        model20 = _two_port_diagram(model, 20000)
        issues20 = [
            {"code": issue.code, "message": issue.message}
            for issue in model.validate_structural_diagram(model20)
        ]
        projection = visual.semantic_projection(data)
        try:
            model.structural_from_json(json.dumps(projection))
        except (ValueError, TypeError) as exc:
            projection_problem = str(exc)
        else:
            projection_problem = "NONE"
        report = {
            "issue": 83,
            "source_commits": SOURCE_COMMITS,
            "sha_verified_real_source_blobs": PINNED_BLOBS,
            "branch_isolation": "PR80/PR78 exact source copied to temp package; never committed to src",
            "native_pr78": {
                "block_count": len(native_view["blocks"]),
                "link_count": len(native_view["links"]),
                "port_count": sum(len(b["ports"]) for b in native_view["blocks"]),
                "svg_units": "mm and physical 1:1 SVG viewBox",
                "no_electrical_nets": native_view["electrical_nets"] is None,
                "font": _font_evidence(native_view),
            },
            "native_pr80": {
                "seven_block_count": len(specimen.specimen().blocks),
                "port_count": len(specimen.specimen().ports),
                "link_count": len(specimen.specimen().links),
                "svg_status": "NOT_RENDERED_BY_PR78; QA-ONLY chords attached to actual anchors",
            },
            "cross_branch_failures": {
                "twenty_mm_two_port_view_anchors_um": [
                    list(visual20["ports"][key]["point_um"])
                    for key in ("out1", "out2")
                ],
                "twenty_mm_two_port_model_diagnostics": issues20,
                "raw_graphic_projection_missing_diagram_type":
                    "diagram_type" not in projection,
                "raw_projection_real_model_error": projection_problem,
                "seven_block_native_PR78_render": "BLOCKED_IF_NO_MODEL_NATIVE_VIEW_ADAPTER",
            },
            "png_status": png_status,
            "files": outputs,
            "warning": "Visual PR78 OpenGost Type A is only a CSS request, font unembedded; 300dpi PNG is not paper approval",
        }
        raw = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        (directory / "qa-e1-evidence.json").write_text(raw, encoding="utf-8")
        print(raw)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output_dir))
