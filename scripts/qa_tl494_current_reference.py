"""Independent exact-source TL494 23-part E3 QA. No replacement artwork.

Loads genuine reference Python code, Circuit, Net, ExternalWireGraph, actual
catalog symbols and PAINT-built SVG. It measures mm/um, not screenshot pixels.
Mandatory real failures are NOT xfailed, suppressed or relabeled as GOST PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import traceback
from collections import Counter
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
from PIL import Image

from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import PinRef

NS = "{http://www.w3.org/2000/svg}"
SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
OWNER_PAINT_SHA = "8623d2c9ea11963ed0d795575e4e95666ab69f7a"
OWNER_ELEKTRIK_SHA = "8451a87bfa17344670017a6a07b460b8b4cf4835"
SOURCE_BLOBS = {
    "examples/tl494_named_photo_sheet.py":
        "990a1aca651f34dcae991575dddfa28b2acae813",
    "examples/tl494_full_native_model.py":
        "049c32ff6e3bf2c839641d0102e3a63fcb86caaf",
    "examples/tl494_named_truth_output/TL494_named_photo_clean.svg":
        "69fa5d18f0844b080d8f1574c686e5c1156ae1f9",
    "examples/tl494_named_truth_output/TL494_named_photo_manifest.json":
        "b2375feb43ad18b8a8e5a515bfc007d169b26908",
}
TI_PIN_NAMES = {
    "1": "1IN+", "2": "1IN−", "3": "FEEDBACK", "4": "DTC",
    "5": "CT", "6": "RT", "7": "GND", "8": "C1", "9": "E1",
    "10": "E2", "11": "C2", "12": "VCC", "13": "OUTPUT CTRL",
    "14": "REF", "15": "2IN−", "16": "2IN+",
}
DISPLAY_ALIASES = {**TI_PIN_NAMES, "3": "FB", "13": "OC"}
EXPECTED_SYMBOLS = {
    **{f"C{i}": "capacitor.polarized" for i in (1, 2, 3, 5, 6)},
    "C4": "capacitor.fixed", "C7": "capacitor.fixed",
    "L1": "inductor.ferromagnetic", "L2": "inductor.ferromagnetic",
    "R5": "resistor.variable", "FU1": "fuse.general",
    "VT1": "transistor.mosfet_n_enh", "VD1": "diode.schottky",
}
CAPS = {"C1", "C2", "C3", "C5", "C6"}
PHOTO_NOT_EMBEDDED = "BLOCKED_ORIGINAL_USER_PHOTO_NOT_IN_SOURCE_REPOSITORY"


def check(condition, code):
    if not condition:
        raise AssertionError(code)


def git_head(path):
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def git_blob(path):
    content = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(content)).encode() + b"\0" + content
    ).hexdigest()


def svg_attrs(root):
    def size(s):
        if not s.endswith("mm"):
            raise AssertionError("SVG_HAS_NO_PRINT_MM_SIZE")
        return float(s[:-2])
    vb = tuple(float(s) for s in root.attrib["viewBox"].split())
    width, height = size(root.attrib["width"]), size(root.attrib["height"])
    check(len(vb) == 4, "BAD_VIEWBOX")
    check(abs(width - vb[2]) < 0.001 and abs(height - vb[3]) < 0.001,
          "SVG_MM_SCALE_NOT_1_TO_1")
    return width, height, vb


def svg_lines(svg):
    result = []
    for el in svg.findall(f".//{NS}line[@data-layer='wires']"):
        a = el.attrib
        result.append({
            "index": int(a["data-wire-index"]),
            "net": a["data-net"],
            "x1": round(float(a["x1"]) * 1000),
            "y1": round(float(a["y1"]) * 1000),
            "x2": round(float(a["x2"]) * 1000),
            "y2": round(float(a["y2"]) * 1000),
            "stroke_um": round(float(a["stroke-width"]) * 1000),
        })
    return result


def parallel_clearance_um(a, b):
    """Exact stroke-edge clearance; None unless positive projection overlap."""
    ax, ay, bx, by = a["x1"], a["y1"], a["x2"], a["y2"]
    cx, cy, dx, dy = b["x1"], b["y1"], b["x2"], b["y2"]
    ah, av = ay == by, ax == bx
    bh, bv = cy == dy, cx == dx
    if ah and bh:
        overlap = min(max(ax, bx), max(cx, dx)) - max(min(ax, bx), min(cx, dx))
        if overlap > 0:
            return abs(ay - cy) - (a["stroke_um"] + b["stroke_um"]) / 2
    if av and bv:
        overlap = min(max(ay, by), max(cy, dy)) - max(min(ay, by), min(cy, dy))
        if overlap > 0:
            return abs(ax - cx) - (a["stroke_um"] + b["stroke_um"]) / 2
    return None


def parallel_endpoint_clearance_um(a, b):
    """Stroke-to-stroke Euclidean clearance for parallel non-overlapping spans.

    Separate from the GOST 3mm *adjacent parallel* long-run rule.
    Catches R5/R6 1mm near-end gaps without misquoting §5.3.4.
    """
    ah, bh = a["y1"] == a["y2"], b["y1"] == b["y2"]
    av, bv = a["x1"] == a["x2"], b["x1"] == b["x2"]
    if ah and bh:
        first = sorted((a["x1"], a["x2"]))
        second = sorted((b["x1"], b["x2"]))
        projected_overlap = min(first[1], second[1]) - max(
            first[0], second[0]
        )
        if projected_overlap > 0:
            return None
        dx = max(0, max(first[0], second[0]) - min(first[1], second[1]))
        center_dist = math.hypot(dx, a["y1"] - b["y1"])
    elif av and bv:
        first = sorted((a["y1"], a["y2"]))
        second = sorted((b["y1"], b["y2"]))
        projected_overlap = min(first[1], second[1]) - max(
            first[0], second[0]
        )
        if projected_overlap > 0:
            return None
        dy = max(0, max(first[0], second[0]) - min(first[1], second[1]))
        center_dist = math.hypot(dy, a["x1"] - b["x1"])
    else:
        return None
    return center_dist - (a["stroke_um"] + b["stroke_um"]) / 2


def orthogonal_crossing(a, b):
    """World coordinate in µm of crossing; topology does not change."""
    ah = a["y1"] == a["y2"]
    av = a["x1"] == a["x2"]
    bh = b["y1"] == b["y2"]
    bv = b["x1"] == b["x2"]
    if not ((ah and bv) or (av and bh)):
        return None
    horizontal, vertical = (a, b) if ah else (b, a)
    px, py = vertical["x1"], horizontal["y1"]
    if (
        min(horizontal["x1"], horizontal["x2"]) <= px
        <= max(horizontal["x1"], horizontal["x2"])
        and min(vertical["y1"], vertical["y2"]) <= py
        <= max(vertical["y1"], vertical["y2"])
    ):
        return [px, py]
    return None


def run_negative_spacing():
    a = {"x1": 0, "y1": 0, "x2": 10000, "y2": 0, "stroke_um": 300}
    b = {**a, "y1": 3299, "y2": 3299}
    check(parallel_clearance_um(a, b) == 2999, "NEG_2_999_MM_NOT_EXACT")
    check(parallel_clearance_um(a, b) < 3000, "NEG_2_999_NOT_REJECTED")
    b = {**b, "y1": 3300, "y2": 3300}
    check(parallel_clearance_um(a, b) == 3000, "NEG_3_000_MM_NOT_EXACT")
    check(not (parallel_clearance_um(a, b) < 3000),
          "NEG_3_000_MM_FALSE_REJECT")
    b = {**b, "y1": 3299, "y2": 3299}
    check(parallel_clearance_um(a, b) != 3000, "NEG_1UM_LOST")
    check(orthogonal_crossing(
        a, {**b, "x1": 5000, "x2": 5000, "y1": -5000, "y2": 5000}
    ) == [5000, 0], "NEG_X_CROSS_MISCLASSIFIED")
    return {"at_2_999_mm": "REJECT", "at_3_000_mm": "PASS",
            "one_um_precision": "PASS",
            "orthogonal_x_does_not_create_net": "PASS"}


def provenance(args):
    check(git_head(args.reference_root) == SOURCE_SHA, "WRONG_REFERENCE_COMMIT")
    check(git_head(args.owner_paint) == OWNER_PAINT_SHA, "WRONG_CURRENT_PAINT_SHA")
    check(git_head(args.owner_ic) == OWNER_ELEKTRIK_SHA, "WRONG_CURRENT_ELEKTRIK_SHA")
    for path, sha in SOURCE_BLOBS.items():
        check(git_blob(args.reference_root / path) == sha,
              "SOURCE_BLOB_MISMATCH: " + path)
    paint = args.owner_paint / "src/gost_schematic/rendering/ic_rectangular.py"
    elec = args.owner_ic / "src/gost_schematic/electrical/ic.py"
    return {"source_commit": SOURCE_SHA, "owner_paint_commit": OWNER_PAINT_SHA,
            "owner_ic_commit": OWNER_ELEKTRIK_SHA,
            "current_paint_blob": git_blob(paint),
            "current_ic_blob": git_blob(elec),
            "reference_files": SOURCE_BLOBS}


def truth_circuit(font):
    from examples.tl494_full_native_model import (
        MANUFACTURER_PIN_MAP,
        SPEC,
        TRACED_NETS,
        build,
    )
    from examples.tl494_named_photo_sheet import compose_circuit, photo_nets

    native, _native_parts, _native_symbols, seen = build()
    (circuit, graph, parts, symbols, poses, unit, targets, style, measure,
     policy, inspection, continuation) = compose_circuit(font)
    check(len(native.components) == len(circuit.components) == len(SPEC) == 23,
          "TL494_NOT_23_PHYSICAL_COMPONENTS")
    check(len(native.nets) == len(circuit.nets) == len(TRACED_NETS) == 15,
          "TL494_NOT_15_NETS")
    check(len(graph.segments) == 91, "TL494_NOT_91_SOURCE_WIRES")
    check(len({c.reference for c in circuit.components}) == 23,
          "TL494_DUPLICATE_COMPONENT")
    check(len({str(n) for n in circuit.nets}) == 15,
          "TL494_DUPLICATE_NET")
    check(tuple((n.name, n.members) for n in circuit.nets) ==
          tuple((n.name, n.members) for n in photo_nets()),
          "TL494_NET_TRUTH_CHANGED")
    check({(c.reference, c.part_id) for c in native.components} ==
          {(c.reference, c.part_id) for c in circuit.components},
          "TL494_COMPONENT_SELECTION_CHANGED")
    all_pins = [
        pin.number for net in circuit.nets for pin in net.members
        if pin.reference == "DA1"
    ]
    check(len(all_pins) == 16 and set(all_pins) == set(TI_PIN_NAMES),
          "TL494_PHYSICAL_PIN_LOSS_OR_DUPLICATION")
    check(len(seen) == len({p for n in native.nets for p in n.members}),
          "TL494_NETLIST_PIN_DUPLICATION")
    return {
        "components": 23, "nets": 15, "wires": 91,
        "DA1_physical_pin_numbers": sorted(all_pins, key=int),
        "full_net_identity": {
            n.name: [f"{p.reference}.{p.number}" for p in n.members]
            for n in circuit.nets
        },
        "original_layout_boolean_is_not_a_DRC": True,
        "b_continuation": "SOURCE_TYPED_NOT_PHANTOM_WIRE",
    }, (circuit, graph, parts, symbols, poses, unit, targets, style,
        measure, policy, inspection, continuation, MANUFACTURER_PIN_MAP)


def part_gate(ctx):
    circuit, _graph, parts, symbols, poses, *_ = ctx
    mapping = {c.reference: c for c in circuit.components}
    actual = {}
    for ref, expected in EXPECTED_SYMBOLS.items():
        comp = mapping[ref]
        check(comp.part_id == expected,
              f"TL494_{ref}_WRONG_UGO_{comp.part_id}")
        part = parts[comp.part_id]
        symbol = symbols[part.symbol_id]
        physical = {p.number for p in part.pins}
        graphic = {p.number for p in symbol.pins}
        check(physical == graphic, f"TL494_{ref}_LOST_REAL_PIN")
        check(len(poses[ref]) == len(physical), f"TL494_{ref}_PIN_POSE_LOST")
        if ref == "VD1":
            check({p.label for p in symbol.pins} == {"A", "K"},
                  "TL494_VD1_NOT_SCHOTTKY_AK")
            check(len(physical) == 2, "TL494_VD1_NOT_TWO_PHYSICAL_CONTACTS")
            positions = {p.label: poses[ref][p.number] for p in symbol.pins}
            check(positions["A"].y < positions["K"].y,
                  "TL494_VD1_SOURCE_VERTICAL_A_NOT_ABOVE_K")
        if ref == "VT1":
            check({p.label for p in symbol.pins} == {"G", "D", "S"},
                  "TL494_VT1_NOT_GDS")
            check(len(physical) == 3, "TL494_MOSFET_NOT_THREE_CONTACTS")
        if ref in CAPS:
            check(len(physical) == 2, "TL494_POLARIZED_CAP_NOT_TWO_CONTACTS")
        if ref in ("L1", "L2"):
            check(len(physical) == 2, "TL494_CORE_CHOKE_PINS_NOT_TWO")
        if ref == "R5":
            check(len(physical) == 3, "TL494_R5_WIPER_MISSING")
        if ref == "FU1":
            check(len(physical) == 2, "TL494_FUSE_CONTACTS_MISSING")
        actual[ref] = {
            "symbol": symbol.identifier, "status": str(symbol.status.value),
            "pin_labels": {p.number: p.label for p in symbol.pins},
            "pin_positions_um": {
                num: [pos.x, pos.y] for num, pos in poses[ref].items()
            },
        }
    d4 = []
    for ref in ("VD1", "VT1", "R5", "C1", "L1", "FU1"):
        comp = mapping[ref]
        sym = symbols[parts[comp.part_id].symbol_id]
        source = {p.number: p.at for p in sym.pins}
        for mirror in (False, True):
            for rotation in (0, 90, 180, 270):
                tr = Transform(rotation=rotation, mirror_x=mirror)
                test = replace(comp, origin=Point(0, 0), transform=tr)
                points = test.pin_positions(sym)
                check(set(points) == set(source), "TL494_D4_LOST_PIN_NUMBER")
                check(len(set(points.values())) == len(points),
                      "TL494_D4_COLLAPSED_PHYSICAL_CONTACTS")
                check(all(points[num] == tr.apply(value)
                          for num, value in source.items()),
                      "TL494_D4_DISPLACED_PIN_REF")
                d4.append({"part": ref, "rotation": rotation,
                           "mirror": mirror, "pins": len(points)})
    return {"actual_ugo": actual, "d4_transform_cases": len(d4),
            "d4": d4, "normative_1to1": "BLOCKED_GOST_GRAPHICS_OVERLAY_AND_DRAFT",
            "mosfet_dot": "BLOCKED_TINY_SOURCE_ADDON_NOT_NORMATIVE_APPROVAL",
            "capacitor_potential": "BLOCKED_NO_MEASURED_TERMINAL_POTENTIALS"}


def ic_gate(ctx, root):
    from examples.tl494_ic_paint_reference import PINS

    *_, manufacturer = ctx
    check(set(manufacturer) == set(PINS) == set(TI_PIN_NAMES),
          "TL494_PIN_NUMBERS_NOT_TI")
    pins = {}
    for num, manufacturer_name in TI_PIN_NAMES.items():
        model_name, model_role = manufacturer[num]
        paint_name, paint_role = PINS[num]
        check(model_name.replace("-", "−") == manufacturer_name,
              f"TL494_PIN_NAME_DIFFERENT_{num}")
        check(paint_name == manufacturer_name, f"TL494_PAINT_NAME_DIFFERENT_{num}")
        pins[num] = {
            "full_manufacturer_label": manufacturer_name,
            "native_type": model_role.value,
            "paint_type": paint_role.value,
            "proposed_display_alias": DISPLAY_ALIASES[num],
        }
    check(len(set(DISPLAY_ALIASES.values())) == 16,
          "TL494_ALIAS_COLLISION_PROPOSAL")
    check(all(len(v) <= 6 for v in DISPLAY_ALIASES.values()),
          "TL494_ALIAS_LONGER_THAN_SIX_PROPOSAL")
    feedback = pins["3"]["native_type"]
    feedback_paint = pins["3"]["paint_type"]
    texts = root.findall(f".//{NS}text[@data-kind='pin-label']")
    live_text = [x.text or "" for x in texts]
    oversized = sorted({x for x in live_text if len(x) > 6})
    check(len(texts) == 16, "TL494_NOT_16_RENDERED_PIN_LABELS")
    function = root.findall(f".//{NS}text[@data-kind='function']")
    check(len(function) == 1 and (function[0].text or "") == "PWM",
          "TL494_PWM_MAIN_FUNCTION_ABSENT")
    matrix = function[0].attrib.get("transform", "")
    m = re.search(r"matrix\(\s*([\d.-]+)\s+([\d.-]+)", matrix)
    axis_y = float(m.group(2)) if m else None
    checks = {
        "FEEDBACK_input": "PASS" if feedback == feedback_paint == "input" else "FAIL",
        "visible_labels_max6": "PASS" if not oversized else "FAIL",
        "PWM_bottom_to_top": "PASS" if axis_y is not None and axis_y < 0 else "FAIL",
    }
    return {
        "pin_map": pins,
        "pin3_actual": [feedback, feedback_paint],
        "pin3_expected_TI": "input",
        "oversized_actual_labels": oversized,
        "visible_label_texts": live_text,
        "actual_pwm_svg_transform": matrix,
        "text_baseline_page_dy": axis_y,
        "requested_direction": "baseline moves negative page-Y (bottom-to-top)",
        "normative_text_angle": "DRAFT_EDITORIAL",
        "checks": checks,
    }


def geometry_gate(ctx, svg):
    circuit, graph, _parts, _symbols, _poses, _unit, *_ = ctx
    lines = svg_lines(svg)
    check(len(lines) == len(graph.segments) == 91, "TL494_SVG_WIRE_INVENTORY")
    for i, (line, original) in enumerate(zip(lines, graph.segments, strict=True)):
        check(line["index"] == i and line["net"] == original.net_name,
              "TL494_SVG_WIRE_INDEX_OR_NET_CHANGED")
        check((line["x1"], line["y1"], line["x2"], line["y2"]) ==
              (original.start.x, original.start.y, original.end.x,
               original.end.y), "TL494_SVG_NOT_ORIGINAL_WIRE_GEOMETRY")
    check(all(x["stroke_um"] == 300 for x in lines),
          "TL494_WIRES_LINE_WIDTH_NOT_0_3MM")
    pairs = []
    endpoint_near_misses = []
    crossings = []
    for i, a in enumerate(lines):
        check(a["x1"] == a["x2"] or a["y1"] == a["y2"],
              "TL494_DIAGONAL_WIRE")
        for b in lines[i + 1:]:
            if a["net"] == b["net"]:
                continue
            d = parallel_clearance_um(a, b)
            if d is not None and d < 3000:
                pairs.append({
                    "line_a": a["index"], "line_b": b["index"],
                    "net_a": a["net"], "net_b": b["net"],
                    "centerline_gap_um": d + (
                        a["stroke_um"] + b["stroke_um"]
                    ) / 2, "edge_clearance_um": d,
                    "edge_clearance_mm": d / 1000,
                    "a_um": [a["x1"], a["y1"], a["x2"], a["y2"]],
                    "b_um": [b["x1"], b["y1"], b["x2"], b["y2"]],
                })
            endpoint_gap = parallel_endpoint_clearance_um(a, b)
            if endpoint_gap is not None and endpoint_gap < 3000:
                endpoint_near_misses.append({
                    "line_a": a["index"], "line_b": b["index"],
                    "net_a": a["net"], "net_b": b["net"],
                    "edge_gap_mm": round(endpoint_gap / 1000, 6),
                    "kind": "NEAR_PARALLEL_ENDPOINTS_NOT_LONG_RUN_GOST_3MM",
                    "a_um": [a["x1"], a["y1"], a["x2"], a["y2"]],
                    "b_um": [b["x1"], b["y1"], b["x2"], b["y2"]],
                })
            xy = orthogonal_crossing(a, b)
            if xy is not None:
                crossings.append({
                    "line_a": a["index"], "line_b": b["index"],
                    "net_a": a["net"], "net_b": b["net"],
                    "coordinate_um": xy,
                })
    pairs.sort(key=lambda x: x["edge_clearance_um"])
    endpoint_near_misses.sort(key=lambda x: x["edge_gap_mm"])
    check(not any(c["coordinate_um"] in [
        [x.x, x.y] for x in graph.junctions
    ] for c in crossings), "TL494_DIFFERENT_NET_JUNCTION_DOT_SHOWN")
    widths = [x["stroke_um"] / 1000 for x in lines]
    width, height, vb = svg_attrs(svg)
    # A2 landscape width 594 mm; source is substantially wider.
    status = {
        "parallel_3mm": "PASS" if not pairs else "FAIL",
        "dangerous_parallel_endpoint_below_1mm": (
            "FAIL" if any(x["edge_gap_mm"] < 1.0
                          for x in endpoint_near_misses) else "PASS"
        ),
        "unmarked_crossing_print": "PASS" if not crossings else "FAIL",
        "line_weight": "PASS" if all(.2 <= w <= 1 for w in widths) else "FAIL",
        "a3_fit": "PASS" if width <= 420 and height <= 297 else "FAIL",
        "a2_fit": "PASS" if width <= 594 and height <= 420 else "FAIL",
    }
    source_tags = {
        "a": svg.findall(f".//{NS}text[@data-source='typed-net-continuation-v2']"),
        "b": svg.findall(f".//{NS}circle[@data-nonphysical-net-continuation]"),
    }
    has_visible_a = any((t.text or "").strip() == "a"
                        for t in svg.iter(f"{NS}text"))
    status["visible_a"] = "PASS" if has_visible_a else "FAIL"
    status["b_legibility_whole_640px"] = "FAIL" if width > 500 else "BLOCKED"
    pinrefs = {p for net in circuit.nets for p in net.members}
    for k in (PinRef("DA1", "3"), PinRef("DA1", "7"),
              PinRef("R5", "2"), PinRef("X2", "1")):
        check(k in pinrefs, "TL494_MISSING_PHYSICAL_NETMEMBER")
    return {
        "wire_count": len(lines), "distinct_net_names": sorted({
            l["net"] for l in lines
        }), "parallel_wire_violations": pairs,
        "parallel_violations_count": len(pairs),
        "distinct_net_near_endpoint_gaps": endpoint_near_misses,
        "near_endpoint_below_1mm": [
            x for x in endpoint_near_misses if x["edge_gap_mm"] < 1
        ],
        "min_parallel_edge_clearance_mm":
            min([x["edge_clearance_mm"] for x in pairs], default=None),
        "different_net_orthogonal_crossings": crossings,
        "crossing_count": len(crossings),
        "explicit_conductive_junctions": len(graph.junctions),
        "wire_stroke_mm": dict(Counter(widths)),
        "source_sheet_mm": [width, height], "source_viewbox_mm": vb,
        "scale_when_fit_640px": 640 / width, "actual_0_3mm_stroke_at_640px":
            .3 * 640 / width,
        "a_text_present": has_visible_a,
        "b_markers": len(source_tags["b"]),
        "b_diameter_640px": 1.3 * 640 / width,
        "status": status,
        "R5_R6_DA1_obstacle_clearance": "BLOCKED_PROTECT_REAL_TEXT_INK_AND_UGO_PRIMITIVES",
        "source_photo_ground_not_a_PE_claim": True,
        "source_graph_net_immutable": True,
        "new_router_not_implemented": True,
    }


def _as_um(value):
    return round(float(value) * 1000)


def _point_segment_um(px, py, first, last):
    dx, dy = last[0] - first[0], last[1] - first[1]
    t = ((px - first[0]) * dx + (py - first[1]) * dy) / (
        dx * dx + dy * dy
    )
    t = max(0.0, min(1.0, t))
    return math.hypot(px - first[0] - t * dx, py - first[1] - t * dy)


def _cross2(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (
        b[1] - a[1]
    ) * (p[0] - a[0])


def _segments_intersect(a, b, c, d):
    c1, c2, c3, c4 = (
        _cross2(a, b, c), _cross2(a, b, d),
        _cross2(c, d, a), _cross2(c, d, b),
    )
    if c1 * c2 > 0 or c3 * c4 > 0:
        return False
    return (
        max(min(a[0], b[0]), min(c[0], d[0]))
        <= min(max(a[0], b[0]), max(c[0], d[0]))
        and max(min(a[1], b[1]), min(c[1], d[1]))
        <= min(max(a[1], b[1]), max(c[1], d[1]))
    )


def _strokes_gap_um(wire, glyph, glyph_stroke_um):
    a = (wire["x1"], wire["y1"])
    b = (wire["x2"], wire["y2"])
    c, d = glyph
    if _segments_intersect(a, b, c, d):
        distance = 0.0
    else:
        distance = min(
            _point_segment_um(*a, c, d),
            _point_segment_um(*b, c, d),
            _point_segment_um(*c, a, b),
            _point_segment_um(*d, a, b),
        )
    return distance - (wire["stroke_um"] + glyph_stroke_um) / 2


def _segment_through_open_box(w, bounds):
    """Return true only for positive wire length inside the *open* box."""
    xlo, ylo, xhi, yhi = bounds
    if w["y1"] == w["y2"]:
        return (
            ylo < w["y1"] < yhi
            and min(w["x2"], xhi) > max(w["x1"], xlo)
            if w["x1"] < w["x2"] else
            ylo < w["y1"] < yhi
            and min(w["x1"], xhi) > max(w["x2"], xlo)
        )
    if w["x1"] == w["x2"]:
        return (
            xlo < w["x1"] < xhi
            and min(max(w["y1"], w["y2"]), yhi)
            > max(min(w["y1"], w["y2"]), ylo)
        )
    return False


def symbol_and_ic_obstacle_gate(ctx, svg):
    """Independent measured PAINT/body and real UGO strokes vs authored wires.

    Supports exact SVG line primitives and PAINT's real measured text ink.
    Curved/arc geometry is explicitly unapproved, not assumed clear.
    """
    circuit, _graph, _parts, _symbols, poses, unit, *_ = ctx
    wires = svg_lines(svg)
    members = {
        (p.reference, p.number): net.name
        for net in circuit.nets for p in net.members
    }
    byref = {c.reference: c for c in circuit.components}
    line_clashes, legal_pin_contacts, unsupported = [], [], []
    for group in svg.iter(NS + "g"):
        ref = group.get("data-reference")
        if not ref or ref not in byref:
            continue
        expected = {
            (point.x, point.y): (ref, num, members.get((ref, num)))
            for num, point in poses[ref].items()
        }
        for idx, glyph in enumerate(group):
            if glyph.tag != NS + "line":
                if glyph.tag in (NS + "path", NS + "circle"):
                    unsupported.append({
                        "ref": ref, "tag": glyph.tag.split("}")[-1]
                    })
                continue
            a = glyph.attrib
            glyph_stroke = _as_um(a.get(
                "stroke-width", group.get("stroke-width", "0.3")
            ))
            segment = (
                (_as_um(a["x1"]), _as_um(a["y1"])),
                (_as_um(a["x2"]), _as_um(a["y2"])),
            )
            for w in wires:
                gap = _strokes_gap_um(w, segment, glyph_stroke)
                if gap >= 1000:
                    continue
                # A genuine contact to its OWN physical source terminal
                # is legal only if both the actual wire and glyph touch
                # that same endpoint with exact integer-µm identity.
                own = [
                    (num, pt) for pt, (device, num, net) in expected.items()
                    if device == ref and net == w["net"]
                    and pt in segment
                    and pt in ((w["x1"], w["y1"]),
                               (w["x2"], w["y2"]))
                ]
                case = {
                    "ref": ref, "glyph_line": idx, "wire": w["index"],
                    "net": w["net"], "stroke_edge_gap_mm":
                        round(gap / 1000, 6),
                    "symbol_line_um": [list(segment[0]), list(segment[1])],
                    "wire_um": [w["x1"], w["y1"], w["x2"], w["y2"]],
                }
                if own and gap >= -(
                    w["stroke_um"] + glyph_stroke
                ) / 2:
                    legal_pin_contacts.append(case)
                else:
                    line_clashes.append(case)
    # The central 16-pin PAINT housing is NOT represented by the 22
    # standard catalog <g data-reference> groups above.
    body = (
        unit.origin.x + unit.body.min_x,
        unit.origin.y + unit.body.min_y,
        unit.origin.x + unit.body.max_x,
        unit.origin.y + unit.body.max_y,
    )
    through_body = [
        {"wire": w["index"], "net": w["net"],
         "geometry_um": [w["x1"], w["y1"], w["x2"], w["y2"]]}
        for w in wires if _segment_through_open_box(w, body)
    ]
    text_ink_hits = []
    text_nodes = list(svg.findall(f".//{NS}text[@data-ink-um]"))
    for t in text_nodes:
        box = tuple(int(x) for x in t.attrib["data-ink-um"].split(","))
        if len(box) != 4:
            raise AssertionError("IC_PAINT_TEXT_INK_BOX_INVALID")
        text_ink_hits.extend({
            "wire": w["index"], "net": w["net"],
            "text": t.text, "region": t.get("data-owner"),
            "measured_ink_um": list(box),
        } for w in wires if _segment_through_open_box(w, box))
    line_clashes.sort(key=lambda x: x["stroke_edge_gap_mm"])
    return {
        "source_body_um": list(body),
        "line_ugo_obstacle_hits_below_1mm": line_clashes[:250],
        "line_ugo_obstacle_count": len(line_clashes),
        "legal_original_pin_join_count": len(legal_pin_contacts),
        "DA1_frame_internal_wire_count": len(through_body),
        "DA1_frame_internal_wires": through_body[:50],
        "true_opengost_measured_text_ink_boxes": len(text_nodes),
        "measured_text_ink_wire_intrusions": text_ink_hits[:60],
        "ink_wire_intrusion_count": len(text_ink_hits),
        "curves_not_approvable_from_line_only_DRC": len(unsupported),
        "curves_by_reference": dict(Counter(x["ref"] for x in unsupported)),
        "status": {
            "unlicensed_ugo_stroke_intrusions": (
                "FAIL" if any(x["stroke_edge_gap_mm"] < 0
                              for x in line_clashes) else "BLOCKED"
            ),
            "DA1_physical_body_unlicensed_wires": (
                "FAIL" if through_body else "PASS"
            ),
            "measured_text_ink_intrusions": (
                "FAIL" if text_ink_hits else "PASS"
            ),
            "full_ugo_ink_normative_1to1": (
                "BLOCKED_CURVES_AND_NON_IC_ANNOTATION_METRICS"
            ),
        },
    }


def pixel_box(bounds_mm, vb, png_wh):
    x0, y0, x1, y1 = bounds_mm
    factorx = png_wh[0] / vb[2]
    factory = png_wh[1] / vb[3]
    return (
        max(0, math.floor((x0 - vb[0]) * factorx)),
        max(0, math.floor((y0 - vb[1]) * factory)),
        min(png_wh[0], math.ceil((x1 - vb[0]) * factorx)),
        min(png_wh[1], math.ceil((y1 - vb[1]) * factory)),
    )


def visual_gate(ctx, clean_svg, debug_svg, args):
    """Rasterize actual assembled source code output and source-specific ROIs."""
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    clean = ET.parse(clean_svg).getroot()
    diag = ET.parse(debug_svg).getroot()
    w, h, vb = svg_attrs(clean)
    _, _, vb_debug = svg_attrs(diag)
    check(vb == vb_debug, "TL494_CLEAN_DIAGNOSTIC_VIEWBOX_CHANGED")
    check(len(svg_lines(clean)) == len(svg_lines(diag)) == 91,
          "TL494_DEBUG_CHANGED_PHYSICAL_WIRING")
    check(not clean.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']"
    ), "TL494_CLEAN_HAS_EDITOR_GREEN")
    rects = diag.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect"
    )
    check(len(rects) == 16, "TL494_DEBUG_NOT_16_PHYSICAL_PIN_SQUARES")
    for rect in rects:
        a = rect.attrib
        check(a["data-pin-ref"].startswith("DA1."),
              "TL494_DEBUG_WRONG_COMPONENT_PINREF")
        px = round((float(a["x"]) + float(a["width"]) / 2) * 1000)
        py = round((float(a["y"]) + float(a["height"]) / 2) * 1000)
        check(px == int(a["data-external-anchor-x-um"]) and
              py == int(a["data-external-anchor-y-um"]),
              "TL494_DEBUG_PIN_SQUARE_OFFSET")
    png_info = {}
    for label, svg in (("clean", clean_svg), ("diagnostic", debug_svg)):
        output = out / f"TL494_23_real_{label}_300dpi.png"
        cairosvg.svg2png(url=str(svg), write_to=str(output),
                         dpi=300, background_color="#ffffff")
        with Image.open(output) as im:
            size = im.size
            check(abs(size[0] - w * 300 / 25.4) <= 2 and
                  abs(size[1] - h * 300 / 25.4) <= 2,
                  "TL494_NOT_ACTUAL_300DPI_1TO1")
            converted = im.convert("RGB")
            converted.save(output, dpi=(300, 300))
            import numpy as np
            rgb = np.asarray(converted)
            green = ((rgb[:, :, 0] < 80) & (rgb[:, :, 1] > 100)
                     & (rgb[:, :, 1] > rgb[:, :, 0])
                     & (rgb[:, :, 1] > rgb[:, :, 2]))
            n_green = int(np.count_nonzero(green))
            if label == "clean":
                check(n_green == 0, "TL494_PRINT_HAS_EDITOR_GREEN_PIXELS")
            else:
                check(n_green > 100, "TL494_DEBUG_GREEN_NOT_VISIBLE_300DPI")
            png_info[label] = {
                "size_px": list(size), "dpi": 300,
                "green_pixels": n_green,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
    circuit, _graph, _parts, _symbols, _pose, unit, *_ = ctx
    byref = {c.reference: c for c in circuit.components}
    crops = {
        "DA1_TL494": [
            (unit.origin.x + unit.body.min_x) / 1000 - 15,
            (unit.origin.y + unit.body.min_y) / 1000 - 16,
            (unit.origin.x + unit.body.max_x) / 1000 + 25,
            (unit.origin.y + unit.body.max_y) / 1000 + 24,
        ],
        "R5_R6": [-153, 165, -67, 227],
    }
    for ref in ("VD1", "VT1"):
        center = byref[ref].origin
        cx, cy = center.x / 1000, center.y / 1000
        crops[ref] = [cx - 27, cy - 27, cx + 27, cy + 27]
    for label, bounds in crops.items():
        png = out / "TL494_23_real_diagnostic_300dpi.png"
        with Image.open(png) as im:
            xy = pixel_box(bounds, vb, im.size)
            check(xy[2] > xy[0] and xy[3] > xy[1], "BAD_REAL_CROP_" + label)
            image = im.crop(xy)
            image.save(out / ("detail_" + label + "_300dpi.png"),
                       dpi=(300, 300))
    real_src = args.original_photo
    has_photo = real_src is not None and real_src.is_file()
    clean_data = "TL494_23_real_clean_300dpi.png"
    if has_photo:
        from PIL import ImageOps
        with Image.open(real_src) as photo, Image.open(out / clean_data) as drawing:
            a = ImageOps.contain(photo.convert("RGB"), (1280, 840))
            b = ImageOps.contain(drawing.convert("RGB"), (1280, 840))
            canvas = Image.new("RGB", (2560, 840), "white")
            canvas.paste(a, (0, 0))
            canvas.paste(b, (1280, 0))
            canvas.save(out / "photo_vs_actual_23_part_svg.png")
        photo_status = "PASS_REAL_ORIGINAL_USER_IMAGE_COMPARED"
    else:
        photo_status = PHOTO_NOT_EMBEDDED
    side_by_side = f"""<!doctype html><html lang="ru"><meta charset="utf-8">
<title>TL494 real source vs printed SVG (QA, NOT ESKD APPROVED)</title>
<style>body{{font:16px sans-serif}}main{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
img{{max-width:100%;height:auto}}section{{overflow:auto;border:1px solid #555;padding:8px}}</style>
<h2>TL494: фото пользователя / реальный текущий SVG, 23 детали, 15 Net</h2>
<main><section><h3>Исходная фотография</h3>
{('<p>Фото подтверждено и получено без переработки</p>'
  if has_photo else '<p>BLOCKED: исходная фотография отсутствует в зафиксированном GitHub репозитории. Подстановка старой 13-компонентной схемы запрещена.</p>')}
</section><section><h3>Настоящий 23-компонентный SVG → PNG 300 DPI</h3>
<img src="{clean_data}" alt="Именно текущий физический источник TL494"></section></main></html>"""
    (out / "TL494_source_photo_comparison.html").write_text(
        side_by_side, encoding="utf-8"
    )
    return {"raster": png_info, "real_300dpi_crops": list(crops),
            "clean_service_color": "PASS_ZERO_GREEN",
            "debug_pin_squares": 16,
            "photo_comparison_status": photo_status,
            "full_size_sheet_mm": [w, h],
            "print_full_scale": "PASS_MM_TO_DPI_WITHOUT_FIT_OR_DOWNSCALE"}


def write_report(args, results):
    summary = {
        "issue": 92, "epic": 107,
        "reference": SOURCE_SHA, "status": "NO_GO_DRAFT",
        "gates": results, "no_xfail_or_padded_PASSES": True,
        "main_and_owner_production_unchanged": True,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dest = args.output_dir / "qa92-tl494-real-23-part-matrix.json"
    dest.write_text(json.dumps(
        summary, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n", encoding="utf-8")
    print("QA92_TL494_MATRIX " + json.dumps({
        k: (v["status"] if isinstance(v, dict) else "N/A")
        for k, v in results.items()
    }, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--owner-paint", type=Path, required=True)
    parser.add_argument("--owner-ic", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--original-photo", type=Path)
    args = parser.parse_args()
    args.reference_root = args.reference_root.resolve()
    args.owner_paint = args.owner_paint.resolve()
    args.owner_ic = args.owner_ic.resolve()
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    mandatory_fail = []

    def gate(name, func):
        try:
            evidence = func()
            status = "PASS"
            if name == "P2_TI_PIN_ALIASES_AND_PWM":
                status = ("FAIL" if "FAIL" in evidence["checks"].values()
                          else "PASS")
            if name == "P3_SYMBOL_AND_DA1_OBSTACLES":
                status = ("FAIL" if "FAIL" in evidence["status"].values()
                          else "BLOCKED")
            if name == "P3_STROKE_AWARE_DRC":
                status = ("FAIL" if "FAIL" in evidence["status"].values()
                          else "PASS")
            if name == "P4_REAL_IMAGES" and evidence[
                "photo_comparison_status"
            ] != "PASS_REAL_ORIGINAL_USER_IMAGE_COMPARED":
                status = "BLOCKED"
            result[name] = {"status": status, "evidence": evidence}
            if status == "FAIL":
                mandatory_fail.append(name)
        except (AssertionError, ValueError, TypeError, KeyError, OSError,
                RuntimeError, ImportError, AttributeError) as exc:
            traceback.print_exc()
            result[name] = {"status": "FAIL", "error": repr(exc)}
            mandatory_fail.append(name)
        write_report(args, result)
        print("QA92_TL494_GATE " + name + " " + result[name]["status"],
              flush=True)

    gate("P0_EXACT_SOURCE_SHA", lambda: provenance(args))
    gate("P0_REAL_23_15_16_91", lambda: truth_circuit(args.font_file)[0])
    try:
        typed = truth_circuit(args.font_file)[1]
        from examples.tl494_named_photo_sheet import generate
        regenerated = args.output_dir / "regenerated-original-23-part-svg"
        generate(regenerated, args.font_file, strict=False)
        clean = regenerated / "TL494_named_photo_clean.svg"
        diag = regenerated / "TL494_named_photo_diagnostic.svg"
        svg = ET.parse(clean).getroot()
        gate("P1_REAL_CATALOG_AND_48_D4", lambda: part_gate(typed))
        gate("P2_TI_PIN_ALIASES_AND_PWM", lambda: ic_gate(typed, svg))
        gate("P3_STROKE_AWARE_DRC", lambda: geometry_gate(typed, svg))
        gate("P3_SYMBOL_AND_DA1_OBSTACLES", lambda: symbol_and_ic_obstacle_gate(
            typed, svg
        ))
        gate("P3_NEGATIVE_EXACT_UM", run_negative_spacing)
        gate("P4_REAL_IMAGES", lambda: visual_gate(
            typed, clean, diag, args
        ))
    except (AssertionError, ValueError, TypeError, KeyError, OSError,
                RuntimeError, ImportError, AttributeError) as exc:
        traceback.print_exc()
        result["SOURCE_REAL_REGENERATION"] = {
            "status": "FAIL", "error": repr(exc)
        }
        mandatory_fail.append("SOURCE_REAL_REGENERATION")
        write_report(args, result)
    if mandatory_fail:
        raise SystemExit("QA92 TL494 NO-GO mandatory failures: " +
                         ",".join(mandatory_fail))
    if any(v["status"] == "BLOCKED" for v in result.values()):
        raise SystemExit("QA92 TL494 BLOCKED source-photo or normative review")


if __name__ == "__main__":
    main()
