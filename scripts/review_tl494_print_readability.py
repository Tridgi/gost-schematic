"""Source-frozen TL494 photo rendering: true mm printing and stroke-aware DRC.

The source 23-component/15-Net/91-wire SVG is read from a PINNED reference
commit. This produces print preview pages and diagnostics only. It does NOT
re-route, reassign Nets, move source components, or certify two tiles as E3.
"""
import argparse
import copy
import json
from math import hypot
from pathlib import Path
from xml.etree import ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
A3_W, A3_H = 420.0, 297.0
PAPER_INK_X, PAPER_INK_Y = 15.0, 22.0
PAPER_INK_W, PAPER_INK_H = 390.0, 250.0


def _value(el, key, default=0.0):
    return float(el.get(key, str(default)))


def _stroke(el, inherited=0.3):
    return _value(el, "stroke-width", inherited)


def _distance_point_to_segment(p, a, b):
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    t = max(0.0, min(1.0, (
        ((p[0] - ax) * vx + (p[1] - ay) * vy) /
        (vx * vx + vy * vy)
    ))) if vx or vy else 0.0
    return hypot(p[0] - ax - t * vx, p[1] - ay - t * vy)


def _segment_gap(a, b):
    # All actual sheet wire segments are orthogonal; symbol strokes may be
    # diagonals. Exact segment intersections have zero distance.
    (ax, ay), (bx, by), aw = a
    (cx, cy), (dx, dy), bw = b
    ux, uy, vx, vy = bx - ax, by - ay, dx - cx, dy - cy
    wx, wy = ax - cx, ay - cy
    denom = ux * ux * (vx * vx + vy * vy) - (ux * vx + uy * vy) ** 2
    if abs(denom) > 1e-12:
        # Interior/interior closest approach, before clamped endpoints.
        s = ((ux * vx + uy * vy) * (vx * wx + vy * wy)
             - (vx * vx + vy * vy) * (ux * wx + uy * wy)) / denom
        t = ((ux * ux + uy * uy) * (vx * wx + vy * wy)
             - (ux * vx + uy * vy) * (ux * wx + uy * wy)) / denom
        if 0 <= s <= 1 and 0 <= t <= 1:
            d = hypot(wx + ux * s - vx * t, wy + uy * s - vy * t)
            return d - (aw + bw) / 2
    distance = min(
        _distance_point_to_segment((ax, ay), (cx, cy), (dx, dy)),
        _distance_point_to_segment((bx, by), (cx, cy), (dx, dy)),
        _distance_point_to_segment((cx, cy), (ax, ay), (bx, by)),
        _distance_point_to_segment((dx, dy), (ax, ay), (bx, by)),
    )
    return distance - (aw + bw) / 2


def _svg_lines(group, inherited=0.3):
    result = []
    stroke = _stroke(group, inherited)
    for el in group.iter():
        tag = el.tag.removeprefix(SVG)
        thickness = _stroke(el, stroke)
        if tag == "line":
            result.append((
                (_value(el, "x1"), _value(el, "y1")),
                (_value(el, "x2"), _value(el, "y2")),
                thickness,
            ))
        elif tag == "rect":
            x, y = _value(el, "x"), _value(el, "y")
            w, h = _value(el, "width"), _value(el, "height")
            corners = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
            for i in range(4):
                result.append((corners[i], corners[(i+1) % 4], thickness))
    return result


def _svg_circles(group):
    result = []
    stroke = _stroke(group)
    for node in group.iter():
        if node.tag == SVG+"circle":
            result.append((
                (_value(node, "cx"), _value(node, "cy")),
                _value(node, "r"), _stroke(node, stroke),
            ))
    return result


def _segment_circle_gap(segment, circle):
    (start, end, wire_stroke) = segment
    center, radius, circle_stroke = circle
    closest = _distance_point_to_segment(center, start, end)
    farthest = max(hypot(center[0]-p[0], center[1]-p[1])
                   for p in (start, end))
    radial = (
        0 if closest <= radius <= farthest
        else min(abs(closest-radius), abs(farthest-radius))
    )
    return radial - (wire_stroke+circle_stroke)/2


def _circle_circle_gap(a, b):
    center_a, ra, wa = a
    center_b, rb, wb = b
    d = hypot(center_a[0]-center_b[0], center_a[1]-center_b[1])
    if abs(ra-rb) <= d <= ra+rb:
        return -(wa+wb)/2
    return min(abs(d-(ra+rb)), abs(d-abs(ra-rb))) - (wa+wb)/2


def _symbol_gap(axes_a, circles_a, axes_b, circles_b):
    distances = (
        [_segment_gap(a, b) for a in axes_a for b in axes_b]
        + [_segment_circle_gap(a, c) for a in axes_a for c in circles_b]
        + [_segment_circle_gap(b, c) for b in axes_b for c in circles_a]
        + [_circle_circle_gap(a, b) for a in circles_a for b in circles_b]
    )
    return min(distances) if distances else None


def _all_wires(root):
    wires = []
    for node in root.findall(f".//{SVG}line[@data-layer='wires']"):
        wires.append({
            "index": node.get("data-wire-index"),
            "net": node.get("data-net"),
            "geometry": (
                (_value(node, "x1"), _value(node, "y1")),
                (_value(node, "x2"), _value(node, "y2")),
                _stroke(node),
            ),
        })
    return wires


def _parallel(a, b):
    (x1, y1), (x2, y2), _ = a
    (x3, y3), (x4, y4), _ = b
    if y1 == y2 and y3 == y4:
        return max(min(x1, x2), min(x3, x4)) < min(
            max(x1, x2), max(x3, x4),
        ) and abs(y1 - y3) > 1e-8
    if x1 == x2 and x3 == x4:
        return max(min(y1, y2), min(y3, y4)) < min(
            max(y1, y2), max(y3, y4),
        ) and abs(x1 - x3) > 1e-8
    return False


def audit_strokes(root):
    wires = _all_wires(root)
    assert len(wires) == 91, "TL494_SOURCE_WIRE_COUNT_CHANGED"
    symbols = root.findall(f".//{SVG}g[@data-layer='symbols']")
    # 22 native component groups + one physical DA1 painted as its own
    # source-authoritative IC layer, never count its internals twice.
    painted_ic = root.findall(f".//{SVG}g[@data-owner='DA1']")
    assert len(symbols) == 22 and len(painted_ic) == 1, (
        "TL494_SOURCE_BOM_GROUP_COUNT_CHANGED"
    )
    assert painted_ic[0].get("data-physical-pin-count") == "16"
    symbol_types = {
        kind: [
            el for group in symbols if group.get("data-reference", "").startswith(kind)
            for el in group.iter()
            if el.tag in (SVG+"line", SVG+"rect", SVG+"circle", SVG+"path")
        ] for kind in ("VD", "VT", "C")
    }
    assert all(symbol_types.values()), "TL494_REQUIRED_SYMBOL_STROKES_MISSING"
    alerts = []
    min_parallel = None
    for index, a in enumerate(wires):
        for b in wires[index + 1:]:
            if not _parallel(a["geometry"], b["geometry"]):
                continue
            gap = _segment_gap(a["geometry"], b["geometry"])
            min_parallel = gap if min_parallel is None else min(min_parallel, gap)
            if gap < 3.0 - 1e-9:
                alerts.append({
                    "code": "PARALLEL_WIRE_STROKE_GAP_LT_3MM",
                    "wires": [a["index"], b["index"]],
                    "nets": [a["net"], b["net"]],
                    "gap_mm": round(gap, 4),
                })
    symbol_alerts = []
    for group in symbols:
        name = group.get("data-reference")
        if not name.startswith(("VD", "VT", "C")):
            continue
        axes = _svg_lines(group)
        circles = _svg_circles(group)
        if not (axes or circles):
            raise ValueError(f"TL494_SYMBOL_STROKES_UNMEASURABLE: {name}")
        if any(node.tag == SVG+"path" for node in group.iter()):
            raise ValueError(
                f"TL494_COMPLEX_PATH_NEEDS_STROKE_PATH_PARSER: {name}"
            )
        for wire in wires:
            distances = (
                [_segment_gap(wire["geometry"], axis) for axis in axes]
                + [_segment_circle_gap(wire["geometry"], circle)
                   for circle in circles]
            )
            nearest = min(distances)
            if nearest < 1.0:
                symbol_alerts.append({
                    "code": "WIRE_SYMBOL_STROKE_PROXIMITY_REVIEW",
                    "symbol": name,
                    "wire": wire["index"],
                    "net": wire["net"],
                    "minimum_stroke_gap_mm": round(nearest, 4),
                    "pin_net_exemption_verified": False,
                })
    symbol_pair_alerts = []
    measured = [
        (group.get("data-reference"), _svg_lines(group), _svg_circles(group))
        for group in symbols
        if group.get("data-reference", "").startswith(("VD", "VT", "C"))
    ]
    for i, (ref1, axes1, dots1) in enumerate(measured):
        for ref2, axes2, dots2 in measured[i+1:]:
            distance = _symbol_gap(axes1, dots1, axes2, dots2)
            if distance is not None and distance < 2.0:
                symbol_pair_alerts.append({
                    "code": "SYMBOL_OUTER_STROKE_GAP_LT_2MM_REVIEW",
                    "symbols": [ref1, ref2],
                    "actual_stroke_gap_mm": round(distance, 4),
                })
    return {
        "source_segments": len(wires),
        "source_symbol_groups": len(symbols) + len(painted_ic),
        "source_symbols_with_strokes": {
            "diode": len(symbol_types["VD"]),
            "mosfet": len(symbol_types["VT"]),
            "capacitors": len(symbol_types["C"]),
        },
        "minimum_parallel_wire_stroke_gap_mm": round(
            min_parallel, 4,
        ) if min_parallel is not None else None,
        "parallel_wire_under_3mm_count": len(alerts),
        "parallel_wire_examples": alerts[:35],
        "symbol_wire_proximity_candidate_count": len(symbol_alerts),
        "symbol_wire_examples": symbol_alerts[:35],
        "symbol_symbol_under_2mm_count": len(symbol_pair_alerts),
        "symbol_symbol_examples": symbol_pair_alerts[:35],
        "real_circle_stroke_geometry": "MEASURED_EXACT_RADIUS_AND_STROKE",
        "target_vd_vt_cap_paths": "FAIL_CLOSED_IF_COMPLEX_UNMEASURED",
        "inductor_arc_paths": "BLOCKED_SEPARATE_ARC_STROKE_AUDIT",
        "text_glyph_vs_wire": "BLOCKED_FOR_FULL_SHEET_PENDING_TYPE_A_RUN_INK",
        "electrical_net_deductions": "NONE",
        "print_release": "BLOCKED_UNTIL_ISSUE108_ROUTING_AND_91_ESKD",
    }


def _view_page(original, min_x, min_y, width, height, *,
               paper=False, diagnostic=False):
    if paper:
        root = ET.Element(SVG+"svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "420mm", "height": "297mm",
            "viewBox": "0 0 420 297",
            "data-output-kind": "A3_PHYSICAL_1TO1_REVIEW_TILE_NOT_FORMAL_E3",
            "data-source-topology": "unchanged_svg_tree",
            "data-print-ratio": "1:1",
        })
        ET.SubElement(root, SVG+"rect", {
            "x": str(PAPER_INK_X), "y": str(PAPER_INK_Y),
            "width": str(PAPER_INK_W),
            "height": str(PAPER_INK_H), "fill": "none",
            "stroke": "#000000", "stroke-width": "0.25",
        })
        nested = ET.SubElement(root, SVG+"svg", {
            "x": str(PAPER_INK_X), "y": str(PAPER_INK_Y),
            "width": str(PAPER_INK_W), "height": str(PAPER_INK_H),
            "viewBox": f"{min_x} {min_y} {width} {height}",
            "overflow": "hidden",
        })
        note = ET.SubElement(root, SVG+"text", {
            "x": "15", "y": "283", "font-size": "3.5",
            "font-family": "OpenGost Type A TT",
            "fill": "#000000", "stroke": "none",
        })
        note.text = (
            "DRAFT REVIEW TILE — shared wires cross tile edge; "
            "NOT A FORMAL TWO-SHEET SCHEMATIC"
        )
    else:
        root = ET.Element(SVG+"svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": "220mm", "height": "155mm",
            "viewBox": f"{min_x} {min_y} {width} {height}",
            "data-output-kind": "ENLARGED_DIAGNOSTIC_NOT_TRUE_PRINT_SCALE",
        })
        nested = root
    for el in original:
        if el.tag in (SVG+"title", SVG+"desc"):
            continue
        nested.append(copy.deepcopy(el))
    if diagnostic:
        root.set("data-stroke-aware-diagnostics", "true")
        # True source-coordinate stroke-distance markers, not fake electrical
        # junctions. Same Net, physical terminals and source lines stay put.
        problems = audit_strokes(original)
        by_index = {
            x["index"]: x["geometry"] for x in _all_wires(original)
        }
        overlay = ET.SubElement(nested, SVG+"g", {
            "data-layer": "editor-stroke-clearance-diagnostics",
            "data-editor-only": "true",
            "fill": "none", "stroke": "#be6300",
            "stroke-width": "0.35", "stroke-dasharray": "1 0.5",
        })
        for problem in problems["parallel_wire_examples"]:
            aa, bb = (
                by_index[idx] for idx in problem["wires"]
            )
            (ax, ay), (bx, by), _ = aa
            (cx, cy), (dx, dy), _ = bb
            if ay == by and cy == dy:
                cxm = (max(min(ax, bx), min(cx, dx))
                       + min(max(ax, bx), max(cx, dx))) / 2
                cym = (ay + cy) / 2
            else:
                cxm = (ax + cx) / 2
                cym = (max(min(ay, by), min(cy, dy))
                       + min(max(ay, by), max(cy, dy))) / 2
            ET.SubElement(overlay, SVG+"rect", {
                "x": str(cxm-2), "y": str(cym-2),
                "width": "4", "height": "4",
                "data-code": problem["code"],
                "data-wires": ",".join(problem["wires"]),
                "data-stroke-gap-mm": str(problem["gap_mm"]),
                "data-not-an-electrical-contact": "true",
            })
        for end in original.findall(
            f".//{SVG}circle[@data-nonphysical-net-continuation]"
        ):
            xx = _value(end, "cx")
            yy = _value(end, "cy")
            ET.SubElement(overlay, SVG+"rect", {
                "x": str(xx-2.5), "y": str(yy-2.5),
                "width": "5", "height": "5",
                "data-kind": "continuation-reading-zone-not-pad",
                "data-endpoint": end.get("data-nonphysical-net-continuation"),
                "data-not-an-electrical-contact": "true",
            })
    return ET.tostring(root, encoding="unicode") + "\n"


def generate(source: Path, output: Path):
    original = ET.fromstring(source.read_text(encoding="utf-8"))
    x, y, w, h = (float(a) for a in original.get("viewBox").split())
    assert abs(w - 679.3) < 0.1 and abs(h - 220.051) < 0.1
    assert w > 594.0 and h < 297.0
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "source_frozen": source.name,
        "source_viewbox_mm": [x, y, w, h],
        "whole_640px_px_per_mm": 640.0 / w,
        "whole_640px_wire_0_3mm_px": 640.0 / w * .3,
        "whole_640px_continuation_circle_diameter_px": 640.0 / w * 1.3,
        "A3_single_sheet": "FAIL_UNCHANGED_SOURCE_WIDTH",
        "A2_landscape_single_sheet": "FAIL_UNCHANGED_SOURCE_WIDTH",
        "A3_two_review_tiles_1_to_1": "PASS_GEOMETRIC_COVERAGE_NOT_FORMAL_E3_SPLIT",
        "stroke_drc": audit_strokes(original),
        "images": [],
    }
    continuation = original.findall(
        f".//{SVG}circle[@data-nonphysical-net-continuation]"
    )
    evidence["continuation_b_source_count"] = len(continuation)
    evidence["typed_a_explicit_marker_count"] = len([
        node for node in continuation
        if "a" == node.get("data-nonphysical-net-continuation", "").lower()
    ])
    evidence["continuation_markers_not_electrical_pads"] = True
    # Crop source without moving actual SVG primitives or scaling ESKD UGO.
    starts = (x, x + 370.0)
    assert starts[0] <= x and starts[1] + PAPER_INK_W >= x + w
    for number, start in enumerate(starts, 1):
        for diagnostic in (False, True):
            stem = (
                f"tl494-a3-tile-{number}-"
                f"{'diagnostic' if diagnostic else 'clean'}"
            )
            svg = _view_page(
                original, start, y - 15.0,
                PAPER_INK_W, PAPER_INK_H,
                paper=True, diagnostic=diagnostic,
            )
            (output / f"{stem}.svg").write_text(svg, encoding="utf-8")
            evidence["images"].append({
                "file": stem+".svg", "size_mm": [420, 297],
                "scale": "TRUE_PRINT_1_TO_1", "source_crop_x": start,
            })
    zones = {
        "TL494": (32.0, 78.0, 142.0, 98.0),
        "R5-R6": (-155.0, 151.0, 100.0, 80.0),
        "VD1-SCHOTTKY": (252.0, 112.0, 36.0, 44.0),
        "C1-C2": (195.0, 16.0, 54.0, 63.0),
    }
    for index, el in enumerate(continuation, 1):
        zones[f"continuation-{index}"] = (
            _value(el, "cx") - 17.5, _value(el, "cy") - 17.5,
            35.0, 35.0,
        )
    for tag, (left, top, span_x, span_y) in zones.items():
        stem = "tl494-detail-"+tag.lower()
        view = _view_page(original, left, top, span_x, span_y)
        (output / f"{stem}.svg").write_text(view, encoding="utf-8")
        evidence["images"].append({
            "file": stem+".svg", "size_mm": [220, 155],
            "scale": f"ENLARGED_{round(220/span_x,2)}X_NOT_PRINT",
        })
    (output / "tl494-true-print-readability-audit.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "width_mm": w, "source_wires": 91,
        "two_A3_tiles": 2, "detail_crops": len(zones),
        "wire_gap_under_3mm": (
            evidence["stroke_drc"]["parallel_wire_under_3mm_count"]
        ),
        "normative_release": "BLOCKED",
    }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-svg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.source_svg, args.output_dir)


if __name__ == "__main__":
    main()
