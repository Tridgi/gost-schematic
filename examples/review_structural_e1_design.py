"""Standalone DRAFT E1 functional-block design specimen — NOT an electrical renderer.

Reference preview for Issue #71. This intentionally does not import any project
Circuit, PartDefinition, PinRef, or existing rendering/model modules.
Real measured font metrics and a production router belong to later reviews.
"""

from __future__ import annotations

import argparse
import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

SIDES = ("LEFT", "RIGHT", "TOP", "BOTTOM")
DIRECTIONS = ("input", "output", "bidirectional")
OUTLINES = ("functional", "device_with_schematic", "group_without_schematic")
ARROWS = ("target", "none")  # Reverse/bidirectional arrow graphics need a separate RFC.
FORBIDDEN = frozenset(("PartDefinition", "PinRef", "Circuit", "nets", "part_id",
                       "physical_pins", "conducting_indices", "net_id"))
MIN_CORNER_UM = 5000  # EDITORIAL, not a ГОСТ dimension.
MIN_PORT_PITCH_UM = 6000  # EDITORIAL, not a ГОСТ dimension.
MIN_TEXT_INSET_UM = 3000  # EDITORIAL, not a ГОСТ dimension.
MIN_PARALLEL_GAP_UM = 3000  # ГОСТ 2.701-2008 §5.3.4.
MIN_BLOCK_GAP_UM = 2000  # ГОСТ 2.701-2008 §5.3.4.
TITLE_EM_UM = 3500  # EDITORIAL preview; font metrics NOT measured.
CODE_EM_UM = 2500
TITLE_LEADING_UM = 5000
STROKE_UM = 350  # Within ГОСТ 2.701-2008 §5.5.1 0.2–1.0 mm.
SVG_NS = "http://www.w3.org/2000/svg"


class E1DesignError(ValueError):
    """A rejectable draft visual contract, never an electrical/ERC error."""


def _integer(value: object, context: str) -> int:
    if type(value) is not int:
        raise E1DesignError(f"{context}: expected an exact integer micrometre value")
    return value


def _decimal(value: object, context: str) -> Decimal:
    if not isinstance(value, str):
        raise E1DesignError(f"{context}: use a decimal string, never binary float")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise E1DesignError(f"{context}: invalid decimal string") from exc
    if not result.is_finite():
        raise E1DesignError(f"{context}: non-finite value")
    return result


def _round_um(number: Decimal) -> int:
    # Deterministic sub-micrometre tie rule, independent of binary floats.
    return int(number.to_integral_value(rounding=ROUND_HALF_UP))


def _transform(x: Decimal, y: Decimal, rotation: int, mirror_x: bool) -> tuple[Decimal, Decimal]:
    if mirror_x:
        x = -x
    if rotation == 90:
        return -y, x
    if rotation == 180:
        return -x, -y
    if rotation == 270:
        return y, -x
    return x, y


def _local_port(side: str, t: Decimal, width: Decimal, height: Decimal):
    if side == "LEFT":
        return -width / 2, height * (t - Decimal("0.5"))
    if side == "RIGHT":
        return width / 2, height * (t - Decimal("0.5"))
    if side == "TOP":
        return width * (t - Decimal("0.5")), -height / 2
    return width * (t - Decimal("0.5")), height / 2


def _normal(side: str, rotation: int, mirror: bool) -> tuple[int, int]:
    vectors = {"LEFT": (-1, 0), "RIGHT": (1, 0), "TOP": (0, -1), "BOTTOM": (0, 1)}
    x, y = vectors[side]
    a, b = _transform(Decimal(x), Decimal(y), rotation, mirror)
    return int(a), int(b)


def _exact_pair(value: object, context: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise E1DesignError(f"{context}: expected a pair of integer micrometres")
    return _integer(value[0], context), _integer(value[1], context)


def _text_width_estimate(text: str, em_um: int) -> int:
    # EDITORIAL rough SVG-preview estimate, NOT FreeType/GOST ink bounds.
    return _round_um(Decimal(len(text)) * Decimal(em_um) * Decimal("0.62"))


def _block(entry: dict) -> dict:
    if not isinstance(entry, dict) or not entry.get("id") or not isinstance(entry["id"], str):
        raise E1DesignError("block: missing stable string id")
    if FORBIDDEN.intersection(entry):
        raise E1DesignError("structural block cannot include electrical/physical fields")
    identifier = entry["id"]
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise E1DesignError(f"{identifier}: semantic nonempty name required")
    title = entry.get("title_lines")
    if not isinstance(title, list) or not title or any(
        not isinstance(line, str) or not line.strip() or "\n" in line for line in title
    ):
        raise E1DesignError(f"{identifier}: nonempty explicit title_lines required")
    if " ".join(name.split()) != " ".join(" ".join(title).split()):
        raise E1DesignError(f"{identifier}: title_lines must spell the semantic name")
    code = entry.get("code")
    if code is not None and (not isinstance(code, str) or not code.strip()):
        raise E1DesignError(f"{identifier}: optional code must be nonempty string or null")
    cx, cy = _exact_pair(entry.get("center_um"), identifier + ".center_um")
    w, h = _exact_pair(entry.get("size_um"), identifier + ".size_um")
    if w <= 0 or h <= 0:
        raise E1DesignError(f"{identifier}: rectangle dimensions must be positive")
    rotation = entry.get("rotation", 0)
    mirror = entry.get("mirror_x", False)
    if type(rotation) is not int or rotation not in (0, 90, 180, 270) or type(mirror) is not bool:
        raise E1DesignError(f"{identifier}: invalid orthogonal transformation")
    scale = _decimal(entry.get("scale", "1"), identifier + ".scale")
    if scale <= 0 or scale > 10:
        raise E1DesignError(f"{identifier}: positive editorial scale <= 10 required")
    outline = entry.get("outline", "functional")
    if outline not in OUTLINES:
        raise E1DesignError(f"{identifier}: invalid structural outline category")
    width, height = Decimal(w) * scale, Decimal(h) * scale
    corners = [
        _transform(x, y, rotation, mirror)
        for x in (-width / 2, width / 2)
        for y in (-height / 2, height / 2)
    ]
    box = (
        _round_um(Decimal(cx) + min(point[0] for point in corners)),
        _round_um(Decimal(cy) + min(point[1] for point in corners)),
        _round_um(Decimal(cx) + max(point[0] for point in corners)),
        _round_um(Decimal(cy) + max(point[1] for point in corners)),
    )
    available_w, available_h = box[2] - box[0], box[3] - box[1]
    max_title = max(_text_width_estimate(line, TITLE_EM_UM) for line in title)
    title_stack_h = TITLE_EM_UM + (len(title) - 1) * TITLE_LEADING_UM
    if max_title + 2 * MIN_TEXT_INSET_UM > available_w or (
        title_stack_h + 2 * MIN_TEXT_INSET_UM > available_h
    ):
        raise E1DesignError(f"{identifier}: multiline title does not fit content keepout")
    if code is not None:
        if _text_width_estimate(code, CODE_EM_UM) + 2 * MIN_TEXT_INSET_UM > available_w:
            raise E1DesignError(f"{identifier}: code does not fit content keepout")
        code_bottom = box[1] + MIN_TEXT_INSET_UM + CODE_EM_UM
        title_top = cy - title_stack_h / 2
        if code_bottom + 1500 > title_top:
            raise E1DesignError(f"{identifier}: code/title protective zones overlap")
    ports = entry.get("ports", [])
    if not isinstance(ports, list) or not ports:
        raise E1DesignError(f"{identifier}: at least one declared structural port required")
    indexed: dict[str, dict] = {}
    groups: dict[str, list[tuple[Decimal, dict]]] = {side: [] for side in SIDES}
    for item in ports:
        if not isinstance(item, dict):
            raise E1DesignError(f"{identifier}: port must be object")
        port_id = item.get("id")
        side = item.get("side")
        direction = item.get("direction")
        if not isinstance(port_id, str) or not port_id or port_id in indexed:
            raise E1DesignError(f"{identifier}: duplicate or blank port id")
        if side not in SIDES or direction not in DIRECTIONS:
            raise E1DesignError(f"{identifier}.{port_id}: invalid side or direction")
        if FORBIDDEN.intersection(item):
            raise E1DesignError(f"{identifier}.{port_id}: electrical fields prohibited")
        t = _decimal(item.get("relative_position"), identifier + "." + port_id)
        if t <= 0 or t >= 1:
            raise E1DesignError(f"{identifier}.{port_id}: port cannot touch corner")
        lx, ly = _local_port(side, t, width, height)
        x, y = _transform(lx, ly, rotation, mirror)
        point = (_round_um(Decimal(cx) + x), _round_um(Decimal(cy) + y))
        p = {"id": port_id, "side": side, "direction": direction,
             "relative_position": str(t), "point_um": point,
             "normal": _normal(side, rotation, mirror)}
        groups[side].append((t, p))
        indexed[port_id] = p
    for side, group in groups.items():
        if not group:
            continue
        side_length = height if side in ("LEFT", "RIGHT") else width
        ordered = sorted(group, key=lambda item: item[0])
        offsets = [_round_um(side_length * t) for t, _ in ordered]
        if offsets[0] < MIN_CORNER_UM or _round_um(side_length) - offsets[-1] < MIN_CORNER_UM:
            raise E1DesignError(f"{identifier}.{side}: port too close to rectangle corner")
        if any(b - a < MIN_PORT_PITCH_UM for a, b in pairwise(offsets)):
            raise E1DesignError(f"{identifier}.{side}: adjacent ports closer than editorial pitch")
        if len(group) > 1:
            for i, (t, _) in enumerate(ordered):
                expected = Decimal(i + 1) / Decimal(len(ordered) + 1)
                if abs((expected - t) * side_length) > Decimal("0.5"):
                    raise E1DesignError(f"{identifier}.{side}: multiple ports not evenly distributed")
    return {"id": identifier, "name": name, "title_lines": title, "code": code,
            "box_um": box, "center_um": (cx, cy), "outline": outline,
            "ports": indexed, "rotation": rotation, "mirror_x": mirror,
            "scale": str(scale)}


def _crosses_interior(start, end, box) -> bool:
    x1, y1 = start
    x2, y2 = end
    left, top, right, bottom = box
    if x1 == x2:
        return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
    if y1 == y2:
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
    return True


def _segments_too_close(first, second) -> bool:
    (a, b), (c, d) = first, second
    if a[1] == b[1] and c[1] == d[1]:
        overlap = min(max(a[0], b[0]), max(c[0], d[0])) - max(
            min(a[0], b[0]), min(c[0], d[0])
        )
        return overlap > 0 and abs(a[1] - c[1]) < MIN_PARALLEL_GAP_UM
    if a[0] == b[0] and c[0] == d[0]:
        overlap = min(max(a[1], b[1]), max(c[1], d[1])) - max(
            min(a[1], b[1]), min(c[1], d[1])
        )
        return overlap > 0 and abs(a[0] - c[0]) < MIN_PARALLEL_GAP_UM
    return False


def validate_design(data: dict) -> dict:
    """Strict standalone proposal check. No electrical connectivity inference."""
    if not isinstance(data, dict) or data.get("schema_version") != 1 or (
        data.get("diagram_type") != "E1" or data.get("status") != "DRAFT"
    ):
        raise E1DesignError("expected DRAFT structural E1 schema_version=1")
    if FORBIDDEN.intersection(data):
        raise E1DesignError("electrical catalog and nets forbidden in structural E1")
    entries = data.get("blocks")
    links = data.get("links")
    if not isinstance(entries, list) or not entries or not isinstance(links, list):
        raise E1DesignError("E1 diagram requires blocks and an explicit links list")
    blocks: dict[str, dict] = {}
    for entry in entries:
        block = _block(entry)
        if block["id"] in blocks:
            raise E1DesignError("duplicate structural block id")
        blocks[block["id"]] = block
    block_list = list(blocks.values())
    for index, a in enumerate(block_list):
        for b in block_list[index + 1:]:
            ax1, ay1, ax2, ay2 = a["box_um"]
            bx1, by1, bx2, by2 = b["box_um"]
            dx = max(ax1 - bx2, bx1 - ax2, 0)
            dy = max(ay1 - by2, by1 - ay2, 0)
            if dx < MIN_BLOCK_GAP_UM and dy < MIN_BLOCK_GAP_UM:
                raise E1DesignError(f"blocks {a['id']} and {b['id']} too close")
    resolved = []
    seen_ids = set()
    all_segments = []
    for item in links:
        if not isinstance(item, dict) or FORBIDDEN.intersection(item):
            raise E1DesignError("invalid structural link / electrical fields")
        link_id = item.get("id")
        if not isinstance(link_id, str) or not link_id or link_id in seen_ids:
            raise E1DesignError("duplicate or blank functional link id")
        seen_ids.add(link_id)
        source = item.get("source")
        target = item.get("target")
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise E1DesignError(f"{link_id}: declared source and target required")
        try:
            s_block = blocks[source["block_id"]]
            t_block = blocks[target["block_id"]]
            s_port = s_block["ports"][source["port_id"]]
            t_port = t_block["ports"][target["port_id"]]
        except (KeyError, TypeError) as exc:
            raise E1DesignError(f"{link_id}: dangling block or port id") from exc
        if s_block["id"] == t_block["id"]:
            raise E1DesignError(f"{link_id}: self-loop requires future policy")
        arrow = item.get("arrow_at", "target")
        if arrow not in ARROWS:
            raise E1DesignError(f"{link_id}: unknown process-arrow direction")
        if arrow == "target" and (
            s_port["direction"] == "input" or t_port["direction"] == "output"
        ):
            raise E1DesignError(f"{link_id}: target arrow violates port flow")
        via = item.get("via_um", [])
        if not isinstance(via, list):
            raise E1DesignError(f"{link_id}: via must be ordered points")
        path = [s_port["point_um"]]
        path.extend(_exact_pair(p, link_id + ".via") for p in via)
        path.append(t_port["point_um"])
        segments = list(pairwise(path))
        if any(a == b or (a[0] != b[0] and a[1] != b[1]) for a, b in segments):
            raise E1DesignError(f"{link_id}: zero-length or diagonal link segment")
        sx, sy = segments[0][1][0] - segments[0][0][0], (
            segments[0][1][1] - segments[0][0][1]
        )
        tx, ty = segments[-1][1][0] - segments[-1][0][0], (
            segments[-1][1][1] - segments[-1][0][1]
        )
        if sx * s_port["normal"][0] + sy * s_port["normal"][1] <= 0:
            raise E1DesignError(f"{link_id}: first segment does not exit source side")
        if tx * t_port["normal"][0] + ty * t_port["normal"][1] >= 0:
            raise E1DesignError(f"{link_id}: last segment does not enter target side")
        for block_id, block in blocks.items():
            if block_id not in (s_block["id"], t_block["id"]) and any(
                _crosses_interior(a, b, block["box_um"]) for a, b in segments
            ):
                raise E1DesignError(f"{link_id}: route intersects unrelated block {block_id}")
        for segment in segments:
            if any(_segments_too_close(segment, prior) for prior in all_segments):
                raise E1DesignError(f"{link_id}: parallel functional links too close")
        all_segments.extend(segments)
        resolved.append({"id": link_id, "path_um": path, "arrow_at": arrow,
                         "source": source, "target": target})
    return {"diagram_type": "E1", "status": "DRAFT",
            "blocks": list(blocks.values()), "links": resolved,
            "electrical_nets": None}


def _mm(value: int | Decimal) -> str:
    result = Decimal(value) / 1000
    return format(result.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".") or "0"


def _arrow(parent: ET.Element, tip, preceding) -> None:
    dx = Decimal(tip[0] - preceding[0])
    dy = Decimal(tip[1] - preceding[1])
    length = (dx * dx + dy * dy).sqrt()
    if length == 0:
        raise E1DesignError("empty process arrow")
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tail_x, tail_y = Decimal(tip[0]) - 3500 * ux, Decimal(tip[1]) - 3500 * uy
    left = (_round_um(tail_x + 1500 * px), _round_um(tail_y + 1500 * py))
    right = (_round_um(tail_x - 1500 * px), _round_um(tail_y - 1500 * py))
    shape = f"M {_mm(left[0])} {_mm(left[1])} L {_mm(tip[0])} {_mm(tip[1])} L {_mm(right[0])} {_mm(right[1])}"
    ET.SubElement(parent, "path", {"d": shape, "data-role": "functional-arrow",
                                   "stroke": "black", "stroke-width": _mm(STROKE_UM),
                                   "fill": "none"})


def render_svg(data: dict, *, diagnostic: bool = False) -> str:
    """Reference-only deterministic vector specimen, never a circuit netlist."""
    scene = validate_design(data)
    bounds = [block["box_um"] for block in scene["blocks"]]
    minx = min(b[0] for b in bounds) - 12000
    miny = min(b[1] for b in bounds) - 12000
    maxx = max(b[2] for b in bounds) + 12000
    maxy = max(b[3] for b in bounds) + 12000
    root = ET.Element("svg", {
        "xmlns": SVG_NS, "width": _mm(maxx - minx) + "mm",
        "height": _mm(maxy - miny) + "mm",
        "viewBox": " ".join(map(_mm, (minx, miny, maxx - minx, maxy - miny))),
        "data-diagram-type": "E1", "data-approval-status": "DRAFT",
        "data-review": "diagnostic" if diagnostic else "clean",
    })
    ET.SubElement(root, "title").text = "Draft E1 functional structural blocks — non-electrical"
    ET.SubElement(root, "desc").text = (
        "Standalone project design: no physical PartDefinition, PinRef, electrical net, "
        "or claim of certified GOST letter dimensions. Font is external and unmeasured."
    )
    for block in scene["blocks"]:
        x1, y1, x2, y2 = block["box_um"]
        attrs = {"x": _mm(x1), "y": _mm(y1), "width": _mm(x2 - x1),
                 "height": _mm(y2 - y1), "stroke": "black",
                 "stroke-width": _mm(STROKE_UM), "fill": "white",
                 "data-block-id": block["id"], "data-role": "functional-block"}
        if block["outline"] == "group_without_schematic":
            attrs["stroke-dasharray"] = "3,1,0.5,1"
        ET.SubElement(root, "rect", attrs)
        cy = block["center_um"][1]
        n = len(block["title_lines"])
        for i, line in enumerate(block["title_lines"]):
            baseline = cy + _round_um(
                (Decimal(i) - Decimal(n - 1) / 2) * TITLE_LEADING_UM
            )
            ET.SubElement(root, "text", {
                "x": _mm(block["center_um"][0]), "y": _mm(baseline),
                "font-family": "OpenGost Type A, sans-serif",
                "font-size": _mm(TITLE_EM_UM), "text-anchor": "middle",
                "dominant-baseline": "middle", "data-role": "block-title",
                "data-block-id": block["id"],
            }).text = line
        if block["code"] is not None:
            ET.SubElement(root, "text", {
                "x": _mm(x1 + MIN_TEXT_INSET_UM),
                "y": _mm(y1 + MIN_TEXT_INSET_UM + CODE_EM_UM // 2),
                "font-family": "OpenGost Type A, sans-serif",
                "font-size": _mm(CODE_EM_UM), "text-anchor": "start",
                "dominant-baseline": "middle", "data-role": "block-code",
            }).text = block["code"]
        for port in block["ports"].values():
            x, y = port["point_um"]
            if diagnostic:
                ET.SubElement(root, "circle", {
                    "cx": _mm(x), "cy": _mm(y), "r": "0.9",
                    "fill": "none", "stroke": "#007b74",
                    "data-role": "functional-port", "data-port-id": port["id"],
                    "data-block-id": block["id"],
                })
        if diagnostic:
            ET.SubElement(root, "rect", {
                "x": _mm(x1 + MIN_TEXT_INSET_UM),
                "y": _mm(y1 + MIN_TEXT_INSET_UM),
                "width": _mm(x2 - x1 - 2 * MIN_TEXT_INSET_UM),
                "height": _mm(y2 - y1 - 2 * MIN_TEXT_INSET_UM),
                "stroke": "#cc6633", "stroke-width": "0.15",
                "stroke-dasharray": "1,1", "fill": "none",
                "data-role": "editorial-text-keepout",
            })
    for link in scene["links"]:
        path = " ".join(
            ("M" if i == 0 else "L") + " " + _mm(x) + " " + _mm(y)
            for i, (x, y) in enumerate(link["path_um"])
        )
        ET.SubElement(root, "path", {
            "d": path, "stroke": "black", "stroke-width": _mm(STROKE_UM),
            "fill": "none", "data-role": "functional-link", "data-link-id": link["id"],
        })
        if link["arrow_at"] == "target":
            _arrow(root, link["path_um"][-1], link["path_um"][-2])
    return ET.tostring(root, encoding="unicode") + "\n"


def semantic_projection(data: dict) -> dict:
    """An explicit mapping to Issue #70's PROPOSED typed graph JSON seam.

    This is serialization data only; it does NOT instantiate its structural
    model and never returns any PartDefinition/PinRef/Circuit.
    """
    validate_design(data)
    blocks = []
    ports = []
    for block in data["blocks"]:
        if block.get("rotation", 0) != 0 or block.get("mirror_x", False) or (
            _decimal(block.get("scale", "1"), block["id"] + ".scale") != 1
        ):
            raise E1DesignError(
                f"{block['id']}: model projection cannot silently apply view transformations"
            )
        cx, cy = block["center_um"]
        width, height = block["size_um"]
        if width % 2 or height % 2:
            raise E1DesignError(
                f"{block['id']}: cannot map half-micrometre origin to exact Point"
            )
        blocks.append({
            "id": block["id"], "name": block["name"],
            "origin_um": [cx - width // 2, cy - height // 2],
            "width_um": width, "height_um": height,
        })
        for port in block["ports"]:
            fraction = Fraction(_decimal(
                port["relative_position"], block["id"] + "." + port["id"]
            ))
            ports.append({
                "block_id": block["id"], "id": port["id"],
                "side": port["side"].lower(), "direction": port["direction"],
                "position": [fraction.numerator, fraction.denominator],
            })
    links = [{
        "id": link["id"],
        "source": dict(link["source"]), "target": dict(link["target"]),
    } for link in data["links"]]
    return {"schema_version": 1, "blocks": blocks,
            "ports": ports, "links": links}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path(
        "examples/fixtures/structural_e1/blocks.json"
    ))
    parser.add_argument("--output-dir", type=Path, default=Path("output/structural-e1"))
    args = parser.parse_args(argv)
    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    scene = validate_design(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for diagnostic in (False, True):
        name = "e1-diagnostic.svg" if diagnostic else "e1-clean.svg"
        (args.output_dir / name).write_text(
            render_svg(data, diagnostic=diagnostic), encoding="utf-8",
        )
    manifest = {
        "approval": "DRAFT", "diagram_type": "E1", "schema_version": 1,
        "electrical_semantics": False,
        "block_count": len(scene["blocks"]), "link_count": len(scene["links"]),
        "blocks": [{"id": b["id"], "bounds_um": b["box_um"],
                    "title_lines": b["title_lines"],
                    "ports": [{"id": p["id"], "side": p["side"],
                               "point_um": p["point_um"], "direction": p["direction"]}
                              for p in b["ports"].values()]}
                   for b in scene["blocks"]],
        "source": "ГОСТ 2.701-2008 / ГОСТ 2.702-2011",
        "limitations": "EDITORIAL spacing and approximate font metrics; NOT normative approval",
    }
    (args.output_dir / "semantic-projection.json").write_text(
        json.dumps(semantic_projection(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"DRAFT E1 review: {len(scene['blocks'])} blocks, {len(scene['links'])} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
