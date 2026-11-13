"""DRAFT E1 SVG/port atlas over the *real* ELEKTRIK StructuralDiagram (#80).

Importing this standalone example requires the experimental structural package.
It never creates an electrical PartDefinition, PinRef, Circuit, or net.
Source/target SVG geometry is derived ONLY from resolve_port_positions().
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from itertools import combinations, pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.standards.type_a_font import inspect_type_a_font

_e1 = import_module("gost_schematic.structural")
StructuralDiagram = _e1.StructuralDiagram
resolve_port_positions = _e1.resolve_port_positions
structural_from_json = _e1.structural_from_json
structural_to_json = _e1.structural_to_json
validate_structural_diagram = _e1.validate_structural_diagram

TEXT_HEIGHT_UM = 2500  # Reviewed face height, NOT certification of full glyphs.
TEXT_LINE_STEP_UM = 4000  # EDITORIAL for multiline E1 boxes.
TEXT_INSET_UM = 1200  # EDITORIAL internal text-to-frame clearance.
TEXT_CLEARANCE_UM = 250  # EDITORIAL ink collision reserve.
PORT_CORNER_UM = 2000  # EDITORIAL single-port corner distance.
PORT_PITCH_UM = 3350  # EDITORIAL: 3mm clear between 0.35mm parallel lines.
STROKE_UM = 350  # 0.35 mm, within the ГОСТ 2.701-2008 line-width range.
ARROW_LENGTH_UM = 2200  # EDITORIAL, not a specified ГОСТ arrow size.
ARROW_HALF_WIDTH_UM = 950  # EDITORIAL, not a specified ГОСТ arrow size.
SIDE_NORMALS = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
SVG = "http://www.w3.org/2000/svg"


class E1GraphicError(ValueError):
    """Fail-closed visual placement; no electrical/ERC interpretation."""


@dataclass(frozen=True, slots=True)
class BlockView:
    # Consecutive fragments concatenate to EXACTLY the semantic name.
    title_lines: tuple[str, ...]
    code: str | None = None
    rotation: int = 0
    mirror_x: bool = False
    scale: Fraction = Fraction(1)
    outline: str = "functional"

    def __post_init__(self):
        if not self.title_lines or any(
            not isinstance(line, str) or not line.strip() for line in self.title_lines
        ):
            raise E1GraphicError("Empty or invalid multiline functional name")
        if self.code is not None and (not isinstance(self.code, str) or not self.code.strip()):
            raise E1GraphicError("Invalid optional block code")
        if type(self.rotation) is not int or self.rotation not in (0, 90, 180, 270):
            raise E1GraphicError("Only orthogonal view rotations are supported")
        if type(self.mirror_x) is not bool:
            raise E1GraphicError("mirror_x must be a boolean")
        if not isinstance(self.scale, Fraction) or self.scale <= 0 or self.scale > 8:
            raise E1GraphicError("View scale must be an exact positive Fraction <= 8")
        if self.outline not in {"functional", "device_with_schematic",
                               "group_without_schematic"}:
            raise E1GraphicError("Unknown structural outline kind")


def example_views(diagram: StructuralDiagram) -> dict[str, BlockView]:
    """Human-authored break positions, while semantic strings stay unchanged."""
    splits = {
        "ENTRY": ("Ввод ", "команд"),
        "CTRL": ("Контрол", "лер"),
        "ADAPT": ("Согласо", "вание"),
        "ACT": ("Исполни", "тель"),
        "DISPLAY": ("Индика", "ция"),
    }
    return {
        block.id: BlockView(splits.get(block.id, (block.name,)))
        for block in diagram.blocks
    }


def _exact(value: Fraction, what: str) -> int:
    if value.denominator != 1:
        raise E1GraphicError(f"{what}: off the 1-micrometre grid; do not round")
    return value.numerator


def _half_up(value: Fraction) -> int:
    # Presentation-only baseline rounding, never a functional port coordinate.
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _transform_xy(
    x: Fraction, y: Fraction, *, rotation: int, mirror: bool,
    scale: Fraction,
) -> tuple[Fraction, Fraction]:
    if mirror:
        x = -x
    x, y = x * scale, y * scale
    if rotation == 90:
        return -y, x
    if rotation == 180:
        return -x, -y
    if rotation == 270:
        return y, -x
    return x, y


def _map_point(point, block, view: BlockView) -> tuple[int, int]:
    cx = Fraction(2 * block.origin.x + block.width_um, 2)
    cy = Fraction(2 * block.origin.y + block.height_um, 2)
    x, y = _transform_xy(
        Fraction(point.x) - cx, Fraction(point.y) - cy,
        rotation=view.rotation, mirror=view.mirror_x, scale=view.scale,
    )
    return (_exact(cx + x, f"{block.id}.view.x"),
            _exact(cy + y, f"{block.id}.view.y"))


def _block_bounds(block, view: BlockView) -> tuple[int, int, int, int]:
    corners = (
        (block.origin.x, block.origin.y),
        (block.origin.x + block.width_um, block.origin.y),
        (block.origin.x, block.origin.y + block.height_um),
        (block.origin.x + block.width_um, block.origin.y + block.height_um),
    )
    mapped = [_map_point(type(block.origin)(x, y), block, view) for x, y in corners]
    return (min(x for x, _ in mapped), min(y for _, y in mapped),
            max(x for x, _ in mapped), max(y for _, y in mapped))


def _normal(side, view: BlockView) -> tuple[int, int]:
    x, y = SIDE_NORMALS[side.value]
    x, y = _transform_xy(
        Fraction(x), Fraction(y), rotation=view.rotation,
        mirror=view.mirror_x, scale=Fraction(1),
    )
    return (int(x), int(y))


def _inside_segment(a, b, rect) -> bool:
    """Open interior intersection with exact rational segment parameters."""
    lo, hi = Fraction(0), Fraction(1)
    for start, delta, low, high in (
        (a[0], b[0] - a[0], rect[0], rect[2]),
        (a[1], b[1] - a[1], rect[1], rect[3]),
    ):
        if delta == 0:
            if not low < start < high:
                return False
            continue
        p, q = Fraction(low - start, delta), Fraction(high - start, delta)
        lo, hi = max(lo, min(p, q)), min(hi, max(p, q))
    return lo < hi


def _mm(x: int) -> str:
    number = Fraction(x, 1000)
    if number.denominator == 1:
        return str(number.numerator)
    sign = "-" if x < 0 else ""
    whole = abs(x) // 1000
    tail = str(abs(x) % 1000).zfill(3).rstrip("0")
    return f"{sign}{whole}.{tail}"


def _arrowhead(parent, a, b, *, link_id: str):
    """Arrow head is graphics-only; the tip is exactly the model target."""
    from decimal import ROUND_HALF_UP, Decimal

    dx = Decimal(b[0] - a[0])
    dy = Decimal(b[1] - a[1])
    norm = (dx * dx + dy * dy).sqrt()
    if not norm:
        raise E1GraphicError(f"{link_id}: zero-length arrow")
    ux, uy = dx / norm, dy / norm
    px, py = -uy, ux
    cx = Decimal(b[0]) - ARROW_LENGTH_UM * ux
    cy = Decimal(b[1]) - ARROW_LENGTH_UM * uy
    def rnd(z):
        return int(z.to_integral_value(rounding=ROUND_HALF_UP))
    l = (rnd(cx + ARROW_HALF_WIDTH_UM * px),
         rnd(cy + ARROW_HALF_WIDTH_UM * py))
    rr = (rnd(cx - ARROW_HALF_WIDTH_UM * px),
          rnd(cy - ARROW_HALF_WIDTH_UM * py))
    path = f"M {_mm(l[0])} {_mm(l[1])} L {_mm(b[0])} {_mm(b[1])} L {_mm(rr[0])} {_mm(rr[1])}"
    ET.SubElement(parent, "path", {
        "d": path, "data-role": "functional-process-arrow", "data-link-id": link_id,
        "fill": "none", "stroke": "black", "stroke-width": _mm(STROKE_UM),
    })


def _font_lines(block, view, bounds, style, measurer):
    """Measure actual OpenGOST glyph ink before claiming text fits a rectangle."""
    if "".join(view.title_lines) != block.name:
        raise E1GraphicError(f"{block.id}: title fragments differ from model name")
    if view.code is not None and len(view.title_lines) > 1 and bounds[3] - bounds[1] < 19000:
        raise E1GraphicError(f"{block.id}: code and multiline text need a taller block")
    cx = Fraction(bounds[0] + bounds[2], 2)
    cy = Fraction(bounds[1] + bounds[3], 2)
    labels = []
    for index, line in enumerate(view.title_lines):
        measured = measurer.measure(line, style)
        ypos = cy + Fraction(2 * index - len(view.title_lines) + 1, 2) * TEXT_LINE_STEP_UM
        baseline_x = _half_up(cx - Fraction(
            measured.ink_box.min_x + measured.ink_box.max_x, 2,
        ))
        baseline_y = _half_up(ypos - Fraction(
            measured.ink_box.min_y + measured.ink_box.max_y, 2,
        ))
        box = (
            baseline_x + measured.ink_box.min_x - TEXT_CLEARANCE_UM,
            baseline_y + measured.ink_box.min_y - TEXT_CLEARANCE_UM,
            baseline_x + measured.ink_box.max_x + TEXT_CLEARANCE_UM,
            baseline_y + measured.ink_box.max_y + TEXT_CLEARANCE_UM,
        )
        labels.append((line, baseline_x, baseline_y, box, "block-title"))
    if view.code:
        measured = measurer.measure(view.code, style)
        x = bounds[0] + TEXT_INSET_UM - measured.ink_box.min_x
        y = bounds[1] + TEXT_INSET_UM - measured.ink_box.min_y
        box = (
            x + measured.ink_box.min_x - TEXT_CLEARANCE_UM,
            y + measured.ink_box.min_y - TEXT_CLEARANCE_UM,
            x + measured.ink_box.max_x + TEXT_CLEARANCE_UM,
            y + measured.ink_box.max_y + TEXT_CLEARANCE_UM,
        )
        labels.append((view.code, x, y, box, "block-code"))
    for _, _, _, box, _ in labels:
        if (box[0] < bounds[0] + TEXT_INSET_UM or
            box[2] > bounds[2] - TEXT_INSET_UM or
            box[1] < bounds[1] + TEXT_INSET_UM or
            box[3] > bounds[3] - TEXT_INSET_UM):
            raise E1GraphicError(f"{block.id}: text ink/hitbox does not fit block")
    for a, b in combinations(labels, 2):
        aa, bb = a[3], b[3]
        if aa[0] < bb[2] and bb[0] < aa[2] and aa[1] < bb[3] and bb[1] < aa[3]:
            raise E1GraphicError(f"{block.id}: text hitbox overlap")
    return labels


def render_structural_model(
    diagram: StructuralDiagram,
    font_file: str | Path,
    *,
    views: dict[str, BlockView] | None = None,
    via_by_link: dict[str, tuple[tuple[int, int], ...]] | None = None,
    diagnostic: bool = False,
):
    """Return true-vector SVG and verifiable manifest from REAL typed E1 ports.

    The semantic diagram is never mutated. All link endpoints come directly
    from ELEKTRIK's resolve_port_positions, including auto and explicit Fraction.
    """
    diagnostics = validate_structural_diagram(diagram)
    if diagnostics:
        raise E1GraphicError(
            "Invalid semantic E1 graph: " + "; ".join(x.code for x in diagnostics)
        )
    authoritative = resolve_port_positions(diagram)
    selected = dict(views or example_views(diagram))
    blocks = {b.id: b for b in diagram.blocks}
    if set(selected) != set(blocks):
        raise E1GraphicError("Views must cover every functional block exactly")
    if not all(isinstance(v, BlockView) for v in selected.values()):
        raise E1GraphicError("Views require BlockView objects")

    transformed = {
        ref: _map_point(point, blocks[ref.block_id], selected[ref.block_id])
        for ref, point in authoritative.items()
    }
    boxes = {bid: _block_bounds(block, selected[bid]) for bid, block in blocks.items()}
    for a, b in combinations(sorted(blocks), 2):
        first, second = boxes[a], boxes[b]
        # ГОСТ minimum between distinct UGO: >= 2 mm; visual gate editorial.
        gapx = max(first[0] - second[2], second[0] - first[2], 0)
        gapy = max(first[1] - second[3], second[1] - first[3], 0)
        if gapx < 2000 and gapy < 2000:
            raise E1GraphicError(f"Block spacing too small: {a}/{b}")

    side_groups: dict[tuple[str, str], list[int]] = {}
    for port in diagram.ports:
        if port.ref not in transformed:
            raise E1GraphicError(f"Unresolved PortRef {port.ref}")
        original = authoritative[port.ref]
        length = (blocks[port.block_id].height_um if port.side.value in ("left", "right")
                  else blocks[port.block_id].width_um)
        offset = (original.y - blocks[port.block_id].origin.y
                  if port.side.value in ("left", "right")
                  else original.x - blocks[port.block_id].origin.x)
        if offset < PORT_CORNER_UM or length - offset < PORT_CORNER_UM:
            raise E1GraphicError(f"{port.ref}: port corner keepout")
        scaled_offset = Fraction(offset) * selected[port.block_id].scale
        side_groups.setdefault((port.block_id, port.side.value), []).append(
            _exact(scaled_offset, f"{port.ref}.scaled_port_offset")
        )
    for key, offsets in side_groups.items():
        offsets.sort()
        if any(b - a < PORT_PITCH_UM for a, b in pairwise(offsets)):
            raise E1GraphicError(f"{key}: multiport pitch too small")

    style_inspection = inspect_type_a_font(
        font_file, family="OpenGost Type A", h_um=TEXT_HEIGHT_UM,
        clearance_um=TEXT_CLEARANCE_UM,
    )
    style = style_inspection.style
    measurer = PillowTextMeasurer()
    rendered_labels = {
        block.id: _font_lines(
            block, selected[block.id], boxes[block.id], style, measurer,
        )
        for block in diagram.blocks
    }
    routes = dict(via_by_link or {})
    if set(routes) - {link.id for link in diagram.links}:
        raise E1GraphicError("Unknown link route override")
    final_routes = []
    for link in diagram.links:
        source, target = transformed[link.source], transformed[link.target]
        waypoint = routes.get(link.id, ())
        if not isinstance(waypoint, (tuple, list)):
            raise E1GraphicError("Routes must be sequences of exact integer positions")
        via = []
        for item in waypoint:
            if (not isinstance(item, (tuple, list)) or len(item) != 2 or
                any(type(x) is not int for x in item)):
                raise E1GraphicError(f"{link.id}: route waypoint must be integer micrometres")
            via.append(tuple(item))
        points = [source, *via, target]
        if any(a == b for a, b in pairwise(points)):
            raise E1GraphicError(f"{link.id}: zero-length graphic segment")
        s_port = next(p for p in diagram.ports if p.ref == link.source)
        t_port = next(p for p in diagram.ports if p.ref == link.target)
        start_vector = (points[1][0] - points[0][0], points[1][1] - points[0][1])
        end_vector = (points[-1][0] - points[-2][0], points[-1][1] - points[-2][1])
        nsrc = _normal(s_port.side, selected[link.source.block_id])
        ntgt = _normal(t_port.side, selected[link.target.block_id])
        if start_vector[0] * nsrc[0] + start_vector[1] * nsrc[1] <= 0:
            raise E1GraphicError(f"{link.id}: does not exit source port normally")
        if end_vector[0] * ntgt[0] + end_vector[1] * ntgt[1] >= 0:
            raise E1GraphicError(f"{link.id}: does not enter target port normally")
        for a, b in pairwise(points):
            if any(_inside_segment(a, b, rect) for rect in boxes.values()):
                raise E1GraphicError(f"{link.id}: graphic link intersects block interior")
        final_routes.append((link, points))

    lowx = min(rect[0] for rect in boxes.values()) - 7500
    lowy = min(rect[1] for rect in boxes.values()) - 7500
    highx = max(rect[2] for rect in boxes.values()) + 7500
    highy = max(rect[3] for rect in boxes.values()) + 7500
    root = ET.Element("svg", {
        "xmlns": SVG,
        "viewBox": f"{_mm(lowx)} {_mm(lowy)} {_mm(highx-lowx)} {_mm(highy-lowy)}",
        "width": _mm(highx-lowx) + "mm", "height": _mm(highy-lowy) + "mm",
        "data-diagram-type": "E1", "data-status": "DRAFT",
        "data-source": "ELEKTRIK StructuralDiagram and resolve_port_positions",
        "data-font-sha256": style.font_sha256,
    })
    ET.SubElement(root, "title").text = "Electrical functional structural scheme E1 — DRAFT"
    ET.SubElement(root, "desc").text = (
        "All endpoints are exact typed PortRef anchors; no physical PinRef,"
        " PartDefinition, conductive nets, or inferred crossing junctions."
    )
    layer = ET.SubElement(root, "g", {"data-layer": "functional-links"})
    for link, points in final_routes:
        d = " ".join(
            ("M" if index == 0 else "L") + f" {_mm(p[0])} {_mm(p[1])}"
            for index, p in enumerate(points)
        )
        ET.SubElement(layer, "path", {
            "d": d, "fill": "none", "stroke": "black",
            "stroke-width": _mm(STROKE_UM), "data-role": "functional-link",
            "data-link-id": link.id,
            "data-source-ref": f"{link.source.block_id}:{link.source.port_id}",
            "data-target-ref": f"{link.target.block_id}:{link.target.port_id}",
            "data-points-um": json.dumps(points, separators=(",", ":")),
        })
        _arrowhead(layer, points[-2], points[-1], link_id=link.id)

    block_group = ET.SubElement(root, "g", {"data-layer": "functional-blocks"})
    for block in diagram.blocks:
        x1, y1, x2, y2 = boxes[block.id]
        attrs = {
            "x": _mm(x1), "y": _mm(y1), "width": _mm(x2-x1), "height": _mm(y2-y1),
            "stroke": "black", "stroke-width": _mm(STROKE_UM),
            "fill": "white", "data-role": "functional-block", "data-block-id": block.id,
        }
        if selected[block.id].outline == "group_without_schematic":
            attrs["stroke-dasharray"] = "4,1,0.5,1"
        ET.SubElement(block_group, "rect", attrs)

    text_group = ET.SubElement(root, "g", {"data-layer": "block-titles"})
    for block in diagram.blocks:
        for text, x, y, _bounds, role in rendered_labels[block.id]:
            ET.SubElement(text_group, "text", {
                "x": _mm(x), "y": _mm(y),
                "font-family": style.font_family, "font-size": _mm(style.em_height_um),
                "text-anchor": "start", "data-role": role, "data-block-id": block.id,
                "fill": "black",
            }).text = text.strip() if text.endswith(" ") else text

    if diagnostic:
        overlay = ET.SubElement(root, "g", {"data-layer": "diagnostic-overlays"})
        for ref, point in sorted(
            transformed.items(), key=lambda item: (item[0].block_id, item[0].port_id)
        ):
            ET.SubElement(overlay, "circle", {
                "cx": _mm(point[0]), "cy": _mm(point[1]), "r": "0.65",
                "fill": "#0066aa", "data-role": "declared-functional-port",
                "data-portref": f"{ref.block_id}:{ref.port_id}",
            })
        for block in diagram.blocks:
            for _text, _x, _y, rect, role in rendered_labels[block.id]:
                ET.SubElement(overlay, "rect", {
                    "x": _mm(rect[0]), "y": _mm(rect[1]),
                    "width": _mm(rect[2]-rect[0]), "height": _mm(rect[3]-rect[1]),
                    "fill": "none", "stroke": "#cc6633", "stroke-width": "0.1",
                    "stroke-dasharray": "0.7,0.5", "data-role": "measured-text-hitbox",
                    "data-block-id": block.id, "data-text-role": role,
                })

    svg = ET.tostring(root, encoding="unicode") + "\n"
    manifest = {
        "schema_version": 1,
        "diagram_type": "E1",
        "status": "DRAFT",
        "model_anchor_policy": "Exact Fraction; ELEKTRIK rounds final absolute Point once half-away-from-zero; SVG never rounds",
        "font": {
            "family": style.font_family, "sha256": style.font_sha256,
            "measured_cap_height_um": style_inspection.measured_cap_height_um,
            "requested_cap_height_um": TEXT_HEIGHT_UM,
            "external_font_not_committed": True,
        },
        "block_count": len(diagram.blocks),
        "port_count": len(diagram.ports),
        "link_count": len(diagram.links),
        "ports": [
            {"ref": {"block_id": ref.block_id, "port_id": ref.port_id},
             "model_um": [p.x, p.y], "svg_um": list(transformed[ref])}
            for ref, p in sorted(authoritative.items(),
                                 key=lambda item: (item[0].block_id, item[0].port_id))
        ],
        "links": [
            {"id": link.id, "source": {"block_id": link.source.block_id,
                                      "port_id": link.source.port_id},
             "target": {"block_id": link.target.block_id,
                        "port_id": link.target.port_id},
             "points_um": [list(p) for p in path],
             "process_direction": "source_to_target"}
            for link, path in final_routes
        ],
        "text_hitboxes_um": [
            {"block_id": block.id, "role": role, "text": line, "bounds": list(bounds)}
            for block in diagram.blocks
            for line, _x, _y, bounds, role in rendered_labels[block.id]
        ],
        "block_boxes_um": [
            {"block_id": bid, "bounds": list(box)}
            for bid, box in sorted(boxes.items())
        ],
        "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
        "normative_limits": "DRAFT; block sizes, corner/pitch, arrows are editorial",
    }
    return svg, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-json", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/e1-model-visual"))
    parser.add_argument("--model-sha", default="unverified")
    args = parser.parse_args(argv)
    raw = args.model_json.read_text(encoding="utf-8")
    diagram = structural_from_json(raw)
    if structural_to_json(diagram) != raw:
        raise E1GraphicError("Model JSON is not canonical; roundtrip drift")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    via = {"L09": ((110000, 36000), (110000, 22000), (130000, 22000))}
    clean, manifest = render_structural_model(diagram, args.font_file, via_by_link=via)
    diagnostic, diag_manifest = render_structural_model(
        diagram, args.font_file, via_by_link=via, diagnostic=True,
    )
    if manifest["ports"] != diag_manifest["ports"] or (
        manifest["links"] != diag_manifest["links"]
    ):
        raise E1GraphicError("Clean and diagnostic port/link positions differ")
    for name, text in (
        ("e1-seven-clean.svg", clean),
        ("e1-seven-diagnostic.svg", diagnostic),
        ("structural-e1.json", raw),
        ("manifest.json", json.dumps(
            {**manifest, "model_pr80_sha": args.model_sha,
             "diagnostic_svg_sha256": hashlib.sha256(
                 diagnostic.encode("utf-8")
             ).hexdigest()},
            ensure_ascii=False, sort_keys=True, indent=2,
        ) + "\n"),
    ):
        (args.output_dir / name).write_text(text, encoding="utf-8")
    print(f"E1 DRAFT: {manifest['block_count']} blocks, {manifest['port_count']} ports, "
          f"{manifest['link_count']} real typed functional links; "
          f"font SHA256 {manifest['font']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
