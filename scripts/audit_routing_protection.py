"""Catalog-wide conservative protection audit; a report, not a GOST approval.

Boxes may overestimate the visible ink of a curved or diagonal primitive.
An uncovered ink bounding box is a review candidate, not proof of an
unsafe route: the sheet router also reserves individual primitive bounds.
"""
import argparse
import json
from itertools import pairwise
from pathlib import Path

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import (
    SIDE_VECTORS,
    Box,
    Line,
    Point,
    StyledLine,
    primitive_stroked_bounds,
)
from gost_schematic.model.symbol import SymbolDefinition


def covered(target: Box, boxes: tuple[Box, ...]) -> bool:
    """Exact coverage of an AABB by a union of closed rectangles."""
    xs = sorted({target.min_x, target.max_x, *(
        x for b in boxes for x in (b.min_x, b.max_x)
        if target.min_x < x < target.max_x
    )})
    for left, right in pairwise(xs):
        intervals = sorted(
            (b.min_y, b.max_y) for b in boxes
            if b.min_x <= left and right <= b.max_x
        )
        top = target.min_y
        for lo, hi in intervals:
            if hi < top:
                continue
            if lo > top:
                break
            top = max(top, hi)
            if top >= target.max_y:
                break
        if top < target.max_y:
            return False
    return True


def segment_hits_box(a: Point, b: Point, box: Box) -> bool:
    """Closed intersection for the cardinal escape segment."""
    return (
        min(a.x, b.x) <= box.max_x and max(a.x, b.x) >= box.min_x
        and min(a.y, b.y) <= box.max_y and max(a.y, b.y) >= box.min_y
    )


def audit_symbol(symbol: SymbolDefinition, margin: int = 550,
                 escape: int = 1800) -> dict:
    zones = symbol.routing_boxes
    expanded = tuple(b.expanded(margin) for b in zones)
    pins = {p.at for p in symbol.pins}
    selected = set(symbol.conductor_topology.conductor_indices
                   if symbol.conductor_topology else ())
    uncovered = []
    terminal_stubs = []
    for index, primitive in enumerate(symbol.graphics):
        ink = primitive_stroked_bounds(primitive, symbol.line_width_um)
        if index in selected and isinstance(primitive, (Line, StyledLine)) and (
            primitive.start in pins or primitive.end in pins
        ):
            terminal_stubs.append(index)
            continue
        if not covered(ink, zones):
            uncovered.append({
                "index": index, "kind": type(primitive).__name__,
                "conductive": index in selected,
                "bounds_um": [ink.min_x, ink.min_y, ink.max_x, ink.max_y],
            })
    blocked = []
    for pin in symbol.pins:
        vector = SIDE_VECTORS[pin.side]
        end = Point(pin.at.x + escape * vector.x, pin.at.y + escape * vector.y)
        blockers = [i for i, zone in enumerate(expanded)
                    if segment_hits_box(pin.at, end, zone)]
        if blockers:
            blocked.append({"pin": pin.number, "zone_indices": blockers})
    return {
        "id": symbol.identifier,
        "revision": symbol.revision,
        "body_and_blue_zone_count": len(zones),
        "has_blue_zone": bool(symbol.routing_keepouts),
        "excluded_terminal_strokes": terminal_stubs,
        "uncovered_functional_bounds": uncovered,
        "blocked_cardinal_escapes": blocked,
        "constant_notes_need_measured_obstacles": [
            key for key, _ in symbol.constant_annotations
        ],
    }


def generate() -> dict:
    catalog = CatalogResolver()
    entries = [audit_symbol(s) for _, s in sorted(catalog.symbols.items())]
    return {
        "schema_version": 1,
        "scope": "conservative AABB review; not full routing or normative approval",
        "clearance_plus_half_wire_um": 550,
        "escape_length_um": 1800,
        "total": len(entries),
        "with_blue_zone": sum(row["has_blue_zone"] for row in entries),
        "with_uncovered_bounds": sum(bool(row["uncovered_functional_bounds"])
                                     for row in entries),
        "with_blocked_escapes": sum(bool(row["blocked_cardinal_escapes"])
                                    for row in entries),
        "with_constant_notes": sum(bool(row["constant_notes_need_measured_obstacles"])
                                   for row in entries),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("output/catalog-categorized/protection-audit.json"))
    args = parser.parse_args()
    report = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("Protection audit: "
          + ", ".join(f"{key}={report[key]}" for key in (
              "total", "with_blue_zone", "with_uncovered_bounds",
              "with_blocked_escapes", "with_constant_notes",
          )))
    # Emit actionable identifiers in the workflow log as well as the JSON.
    for row in report["entries"]:
        if row["uncovered_functional_bounds"] or row["blocked_cardinal_escapes"]:
            indices = [item["index"] for item in row["uncovered_functional_bounds"]]
            pins = [item["pin"] for item in row["blocked_cardinal_escapes"]]
            print(f"PROTECTION_REVIEW {row['id']} uncovered={indices} blocked={pins}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
