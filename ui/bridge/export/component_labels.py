"""Bounded derived component labels for canonical ProjectV2 export.

Mirror the browser component-labels.ts placement contract. Geometry is
integer micrometres, not measured GOST glyph extents. No Net mutations.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, floor

from ui.editor.src.model.contract import pin_world

Box = tuple[int, int, int, int]
H = 2500
STEP = 3500
PAD = 500
BUDGET = 12_000_000


def _box(a, b, pad=0) -> Box:
    return (floor(min(a[0], b[0])-pad), floor(min(a[1], b[1])-pad),
            ceil(max(a[0], b[0])+pad), ceil(max(a[1], b[1])+pad))


def _union(a: Box, b: Box) -> Box:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _hits(a: Box, b: Box) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _round(x) -> int:
    return floor(x + 0.5)


def _note_box(text, at, h, horizontal="left", vertical="bottom") -> Box:
    x, y = at
    y += h if vertical == "top" else _round(h/3) if vertical == "center" else 0
    w = (len(text)+1)*h
    left = x-h if horizontal == "left" else x-w if horizontal == "right" else x-ceil(w/2)
    right = x+w if horizontal == "left" else x+h if horizontal == "right" else x+ceil(w/2)
    return left, y-2*h, right, y+h


def _symbol_box(inst, symbol) -> Box:
    result = _box(inst["origin_um"], inst["origin_um"])
    for pin in symbol["pins"]:
        p = pin_world(inst, pin["at_um"])
        result = _union(result, _box(p, p))
    for g in symbol["graphics"]:
        points = [pin_world(inst, p) for p in g["points_um"]]
        if g["kind"] == "circle":
            (x, y), (u, v) = points
            r = abs(u-x)+abs(v-y)
            points = [(x-r, y-r), (x+r, y+r)]
        # Cardinal semicircle bounds are exactly the start, apex, end.
        pad = g["stroke_um"]/2
        for p in points:
            result = _union(result, _box(p, p, pad))
    for n in symbol.get("constant_annotations", []):
        result = _union(result, _note_box(n["text"], pin_world(inst, n["at_um"]),
                                         n["height_um"], n["horizontal"], n["vertical"]))
    return result


@dataclass(frozen=True)
class Label:
    instance_id: str
    component_id: str
    refdes: str
    value: str
    x: int
    y: int
    bounds: Box


@dataclass
class Entry:
    instance_id: str
    refdes: str
    near: list[Label]
    extra: Callable[[], list[Label]]


def plan_component_labels(document: dict, sheet: dict) -> tuple[list[Label], list[dict]]:
    """Caller validates the ProjectV2 before invoking this read-only planner."""
    project = document["project"]
    components = {c["id"]: c for c in project["components"]}
    defs = {s["id"]: s for s in project["symbol_definitions"]}
    visible = {l["id"] for l in sheet["layers"]
               if l["visible"] and l["printable"] and l["kind"] != "diagnostics"}
    instances = [i for i in sheet["instances"] if i["layer_id"] in visible]
    if (len(instances) > 128 or sum(len(w["segments"]) for w in sheet["wires"]) > 512
            or sum(len(g["points_um"])-1 for g in sheet["graphics"]) > 512
            or len(sheet["junctions"])+len(sheet["splices"]) > 512
            or len(sheet["texts"])+len(sheet["labels"]) > 128):
        return [], [{"instanceId": i["id"], "refdes": components[i["component_id"]]["refdes"],
                     "reason": "LABEL_SIZE_LIMIT"} for i in instances]
    bounds = {i["id"]: _symbol_box(i, defs[i["symbol_id"]]) for i in sheet["instances"]}
    obstacles = list(bounds.values())
    for w in sheet["wires"]:
        for a, b in zip(w["vertices"], w["vertices"][1:]):
            obstacles.append(_box(a["at_um"], b["at_um"], 150))
    for g in sheet["graphics"]:
        for a, b in zip(g["points_um"], g["points_um"][1:]):
            obstacles.append(_box(a, b, g["stroke_um"]/2))
    obstacles.extend(_box(n["at_um"], n["at_um"], 550) for n in sheet["junctions"])
    obstacles.extend(_box(n["at_um"], n["at_um"]) for n in sheet["splices"])
    for n in sheet["texts"] + sheet["labels"]:
        if n["text"]:
            obstacles.append(_note_box(n["text"], n["at_um"], n.get("height_um", 3500)))
    m = sheet["frame"]["margin_um"]
    w, h = sheet["frame"]["size_um"]
    comparisons = 0
    entries: list[Entry] = []
    unplaced: list[dict] = []

    def entry(inst, c) -> Entry:
        nonlocal comparisons
        texts = [v for v in (c["refdes"], c["value"]) if v]
        width = (max(map(len, texts))+1)*H
        height = 3*H+(len(texts)-1)*STEP
        x0, y0, x1, y1 = bounds[inst["id"]]
        cx, cy = _round((x0+x1)/2), _round((y0+y1)/2)
        seen = set()

        def collect(positions) -> list[Label]:
            nonlocal comparisons
            result = []
            for x, y in positions:
                x, y = _round(x), _round(y)
                if (x, y) in seen:
                    continue
                seen.add((x, y))
                left, top = floor(x-width/2), floor(y-height/2)
                b = (left-PAD, top-PAD, left+width+PAD, top+height+PAD)
                if b[0] < m or b[1] < m or b[2] > w-m or b[3] > h-m:
                    continue
                for obstacle in obstacles:
                    comparisons += 1
                    if comparisons > BUDGET or _hits(obstacle, b):
                        break
                else:
                    result.append(Label(inst["id"], c["id"], c["refdes"],
                                        c["value"], x, top+2*H, b))
            return result

        near = []
        for gap in (1000, 2500, 5000, 8000):
            near.extend(collect([
                (cx, y0-gap-height/2), (cx, y1+gap+height/2),
                (x1+gap+width/2, cy), (x0-gap-width/2, cy),
                (x0+width/2, y0-gap-height/2), (x1-width/2, y0-gap-height/2),
                (x0+width/2, y1+gap+height/2), (x1-width/2, y1+gap+height/2),
            ]))

        def extra() -> list[Label]:
            positions = []
            for gap in (1000, 2500, 5000, 8000, 12000, 16000, 20000):
                for d in (0, -2500, 2500, -5000, 5000, -7500, 7500,
                          -10000, 10000, -12500, 12500):
                    x, y = cx+d, cy+d
                    if x0-width/2 <= x <= x1+width/2:
                        positions.extend([(x, y0-gap-height/2), (x, y1+gap+height/2)])
                    if y0-height/2 <= y <= y1+height/2:
                        positions.extend([(x1+gap+width/2, y), (x0-gap-width/2, y)])
            return collect(positions)

        return Entry(inst["id"], c["refdes"], near, extra)

    for i in instances:
        c = components[i["component_id"]]
        if not c["refdes"] or any(len(v) > 64 or any(ord(ch) < 32 or ord(ch) == 127
                for ch in v) for v in (c["refdes"], c["value"])):
            unplaced.append({"instanceId": i["id"], "refdes": c["refdes"],
                             "reason": "LABEL_TEXT_UNSUPPORTED"})
        else:
            entries.append(entry(i, c))

    def choose(order, candidates, seed=()) -> list[Label]:
        result = list(seed)
        for e in order:
            if any(l.instance_id == e.instance_id for l in result):
                continue
            for label in candidates[e.instance_id]:
                if all(not _hits(k.bounds, label.bounds) for k in result):
                    result.append(label)
                    break
        return result

    nearby = {e.instance_id: e.near for e in entries}
    best = choose(entries, nearby)
    if len(best) < len(entries):
        retry = choose(sorted(entries, key=lambda e: (len(e.near), e.instance_id)), nearby)
        if len(retry) > len(best):
            best = retry
    if len(best) < len(entries):
        expanded = dict(nearby)
        missing = [e for e in entries if not any(l.instance_id == e.instance_id for l in best)]
        missing_ids = {e.instance_id for e in missing}
        for e in missing:
            expanded[e.instance_id] = e.near+e.extra()
        best = choose(missing, expanded, best)
        if len(best) < len(entries):
            for e in entries:
                if e.instance_id not in missing_ids:
                    expanded[e.instance_id] = e.near+e.extra()
            order = sorted(entries, key=lambda e: (len(expanded[e.instance_id]), e.instance_id))
            retry = choose(order, expanded)
            if len(retry) > len(best):
                best = retry
    placed = {l.instance_id: l for l in best}
    labels = []
    for e in entries:
        if e.instance_id in placed:
            labels.append(placed[e.instance_id])
        else:
            unplaced.append({"instanceId": e.instance_id, "refdes": e.refdes,
                             "reason": "LABEL_SEARCH_LIMIT" if comparisons > BUDGET
                             else "LABEL_NO_SAFE_POSITION"})
    return labels, unplaced
