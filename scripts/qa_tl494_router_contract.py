"""Independent TL494 full-router CONTRACT, not a substitute for routed artwork.

Tests the immutable native 23/15 source and rejects semantic mutations.
A future router must export exact physical refs, nets, lead coordinates,
segments and junctions; absence of that export is explicitly BLOCKED.
No xfail, source drawing substitution, or 2-terminal router release PASS.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
RENAMES = {
    "a_INPUT_PLUS": "INPUT_POS",
    "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
    "TRANSFER": "ENERGY_TRANSFER",
}
PIN_NUMBERS = {str(i) for i in range(1, 17)}


class ContractError(AssertionError):
    """A genuine release-blocking physical or geometrical discrepancy."""


def demand(condition, code):
    if not condition:
        raise ContractError(code)


def source_model():
    """Use the ORIGINAL executable 23-part model, never handwritten fixtures."""
    from examples.tl494_full_native_model import SPEC, TRACED_NETS

    demand(len(SPEC) == 23 and len(TRACED_NETS) == 15,
           "SOURCE_23_15_COUNTS_CHANGED")
    components = [
        {"reference": ref, "part_id": item[0]}
        for ref, item in SPEC.items()
    ]
    nets = [
        {"name": RENAMES.get(name, name),
         "members": [f"{ref}.{pin}" for ref, pin in members]}
        for name, members in TRACED_NETS.items()
    ]
    physical = [p for n in nets for p in n["members"]
                if p.startswith("DA1.")]
    demand(len(physical) == 16 and
           {p.split(".", 1)[1] for p in physical} == PIN_NUMBERS,
           "SOURCE_TL494_NOT_ALL_16_CONNECTED")
    return {"components": components, "nets": nets}


def _records(model):
    demand(isinstance(model, dict), "CANDIDATE_NOT_OBJECT")
    comps = model.get("components")
    nets = model.get("nets")
    demand(isinstance(comps, list) and isinstance(nets, list),
           "CANDIDATE_NO_TYPED_COMPONENTS_OR_NETS")
    comp_map = {}
    for comp in comps:
        demand(isinstance(comp, dict), "CANDIDATE_BAD_COMPONENT")
        name, kind = comp.get("reference"), comp.get("part_id")
        demand(isinstance(name, str) and isinstance(kind, str) and name and kind,
               "CANDIDATE_UNTYPED_COMPONENT")
        demand(name not in comp_map, "CANDIDATE_DUPLICATE_COMPONENT")
        comp_map[name] = kind
    net_map, pin_owners = {}, {}
    for net in nets:
        demand(isinstance(net, dict), "CANDIDATE_BAD_NET")
        name, members = net.get("name"), net.get("members")
        demand(isinstance(name, str) and name and isinstance(members, list),
               "CANDIDATE_UNTYPED_NET")
        demand(name not in net_map and members, "CANDIDATE_DUPLICATE_OR_EMPTY_NET")
        demand(all(isinstance(p, str) and "." in p for p in members),
               "CANDIDATE_MALFORMED_PINREF")
        demand(len(set(members)) == len(members), "CANDIDATE_DUPLICATE_NET_PIN")
        net_map[name] = frozenset(members)
        for pin in members:
            demand(pin not in pin_owners, "CANDIDATE_PIN_IN_MULTIPLE_NETS")
            demand(pin.split(".", 1)[0] in comp_map,
                   "CANDIDATE_UNKNOWN_COMPONENT_PINREF")
            pin_owners[pin] = name
    return comp_map, net_map, pin_owners


def validate_semantics(source, candidate):
    expected_parts, expected_nets, expected_pins = _records(source)
    parts, nets, pins = _records(candidate)
    demand(parts == expected_parts, "CANDIDATE_BOM_OR_PART_SELECTION_CHANGED")
    demand(len(parts) == 23 and len(nets) == 15, "CANDIDATE_23_15_LOST")
    demand(nets == expected_nets, "CANDIDATE_PHYSICAL_NET_DELTA")
    demand(pins == expected_pins, "CANDIDATE_PINREF_OWNERSHIP_CHANGED")
    da1 = {p.partition(".")[2] for p in pins if p.startswith("DA1.")}
    demand(da1 == PIN_NUMBERS, "CANDIDATE_DA1_16_PIN_LOSS")
    roles = candidate.get("tl494_pin_roles", {})
    aliases = candidate.get("tl494_pin_aliases", {})
    demand(isinstance(roles, dict) and isinstance(aliases, dict),
           "CANDIDATE_IC_ROLE_ALIAS_NOT_TYPED")
    demand(set(roles) == PIN_NUMBERS and set(aliases) == PIN_NUMBERS,
           "CANDIDATE_IC_PIN_METADATA_NOT_16")
    demand(roles["3"] == "input" and roles["13"] == "input",
           "CANDIDATE_TI_PIN3_OR_PIN13_DIRECTION")
    demand(aliases["3"] == "FB" and aliases["13"] == "OC",
           "CANDIDATE_SHORT_FB_OC_MISSING")
    demand(all(isinstance(s, str) and 0 < len(s) <= 6 for s in aliases.values()),
           "CANDIDATE_PIN_ALIAS_OVERFLOW")
    demand(len(set(aliases.values())) == 16, "CANDIDATE_ALIAS_COLLISION")
    demand(not set(candidate.get("nc_pins", ())) & set(pins),
           "CANDIDATE_WIRED_PIN_FALSE_NC")
    return {"components": 23, "nets": 15, "DA1_physical_pins": 16,
            "net_memberships": sum(map(len, nets.values())),
            "physical_net_delta": 0, "pin3_role": "input",
            "pin3_alias": "FB", "pin13_alias": "OC"}


def _point(value):
    demand(isinstance(value, list) and len(value) == 2 and
           all(type(n) is int for n in value),
           "CANDIDATE_COORDINATE_NOT_INTEGER_UM")
    return tuple(value)


def _on(a, b, p):
    return ((b[0] - a[0]) * (p[1] - a[1]) ==
            (b[1] - a[1]) * (p[0] - a[0]) and
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def _overlap(a, b):
    x, y = a[:2], a[2:]
    u, v = b[:2], b[2:]
    if not _on(x, y, u) or not _on(x, y, v):
        return False
    axis = 0 if x[0] != y[0] else 1
    return max(min(x[axis], y[axis]), min(u[axis], v[axis])) < min(
        max(x[axis], y[axis]), max(u[axis], v[axis]))


def parallel_gap_um(first, second):
    """Stroke edge gap only for parallel runs with positive overlap."""
    a, b, wa = first
    c, d, wb = second
    if a[1] == b[1] and c[1] == d[1]:
        overlap = min(max(a[0], b[0]), max(c[0], d[0])) - max(
            min(a[0], b[0]), min(c[0], d[0]))
        if overlap > 0:
            return abs(a[1] - c[1]) * 2 - wa - wb
    if a[0] == b[0] and c[0] == d[0]:
        overlap = min(max(a[1], b[1]), max(c[1], d[1])) - max(
            min(a[1], b[1]), min(c[1], d[1]))
        if overlap > 0:
            return abs(a[0] - c[0]) * 2 - wa - wb
    return None  # half-micrometre exact arithmetic (value = 2*gap)


def validate_router_geometry(candidate, pin_owners):
    """Fail closed on real 15-net geometry. Crossing X != an electrical join."""
    endpoints = candidate.get("pin_positions_um")
    raw = candidate.get("wires")
    points = candidate.get("junctions_um")
    demand(isinstance(endpoints, dict) and isinstance(raw, list) and
           isinstance(points, list), "CANDIDATE_MISSING_ROUTER_EXPORT")
    junctions = [_point(p) for p in points]
    demand(len(set(junctions)) == len(junctions),
           "CANDIDATE_DUPLICATE_JUNCTION")
    wires = []
    net_names = set(pin_owners.values())
    per_net = defaultdict(list)
    for i, item in enumerate(raw):
        demand(isinstance(item, dict), "CANDIDATE_BAD_WIRE")
        net = item.get("net_name")
        start = _point(item.get("start_um"))
        end = _point(item.get("end_um"))
        stroke = item.get("stroke_um")
        demand(net in net_names, "CANDIDATE_WIRE_UNKNOWN_NET")
        demand(type(stroke) is int and 200 <= stroke <= 400,
               "CANDIDATE_INVALID_PRINT_STROKE")
        demand(start != end and (start[0] == end[0] or start[1] == end[1]),
               "CANDIDATE_NON_ORTHOGONAL_OR_ZERO_WIRE")
        wires.append((start, end, stroke, net))
        per_net[net].append(i)
    demand(set(per_net) == net_names, "CANDIDATE_NOT_ALL_15_NETS_ROUTED")
    for pin in pin_owners:
        demand(pin in endpoints, "CANDIDATE_MISSING_PHYSICAL_PIN_POSITION")
        p = _point(endpoints[pin])
        demand(any(_on(wires[i][0], wires[i][1], p)
                   for i in per_net[pin_owners[pin]]),
               "CANDIDATE_PIN_NOT_ON_ITS_DECLARED_NET")
        demand(not any(_on(a, b, p) and net != pin_owners[pin]
                       for a, b, _, net in wires),
               "CANDIDATE_WRONG_NET_TOUCHES_PHYSICAL_PIN")
    for j in junctions:
        touched = {net for a, b, _, net in wires if _on(a, b, j)}
        demand(len(touched) == 1 and
               sum(_on(a, b, j) for a, b, _, _ in wires) >= 2,
               "CANDIDATE_JUNCTION_SHORT_OR_ORPHAN")
    parallel = []
    crossings = 0
    for i, (a, b, aw, an) in enumerate(wires):
        for k in range(i + 1, len(wires)):
            c, d, bw, bn = wires[k]
            if an == bn:
                continue
            gap2 = parallel_gap_um((a, b, aw), (c, d, bw))
            if gap2 is not None and gap2 < 6000:
                parallel.append((i, k, gap2))
            if ((a[1] == b[1] and c[0] == d[0]) or
                    (a[0] == b[0] and c[1] == d[1])):
                h1, h2, v1, v2 = (a, b, c, d) if a[1] == b[1] else (c, d, a, b)
                p = (v1[0], h1[1])
                if _on(h1, h2, p) and _on(v1, v2, p):
                    crossings += 1
                    demand(p not in junctions,
                           "CANDIDATE_DIFFERENT_NET_CROSS_WITH_DOT")
            if _overlap((a, b, aw), (c, d, bw)):
                raise ContractError("CANDIDATE_COLLINEAR_WRONG_NET_SHORT")
    demand(not parallel, "CANDIDATE_PARALLEL_3MM_STROKE_DRC")
    # Same-net physical terminals must reach a SINGLE connected wire cluster.
    for net, ids in per_net.items():
        parent = {i: i for i in ids}

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for pos, i in enumerate(ids):
            a, b, _, _ = wires[i]
            for k in ids[pos + 1:]:
                c, d, _, _ = wires[k]
                joining = (_overlap((a, b, 0), (c, d, 0)) or
                           (a in (c, d) or b in (c, d)) or
                           any(_on(a, b, p) and _on(c, d, p)
                               for p in junctions))
                if joining:
                    parent[root(i)] = root(k)
        pin_roots = set()
        for pin, name in pin_owners.items():
            if name == net:
                p = _point(endpoints[pin])
                touched = [i for i in ids if _on(wires[i][0], wires[i][1], p)]
                demand(bool(touched), "CANDIDATE_UNROUTED_PIN")
                pin_roots.update(root(i) for i in touched)
        demand(len(pin_roots) == 1, "CANDIDATE_DISCONNECTED_MULTITERMINAL_NET")
    return {"wires": len(wires), "all_15_nets_routed": True,
            "parallel_3mm_violations": 0, "different_net_crossings_review": crossings,
            "pinrefs_physically_on_declared_net": True,
            "multi_terminal_nets_connected": True,
            "symbol_text_ink_drc": "BLOCKED_EXTERNAL_GEOMETRY_REQUIRED",
            "raster_300dpi": "BLOCKED_EXTERNAL_RENDER_REQUIRED"}


def negative_fixture_gate(source):
    """Mutation tests reuse the ACTUAL 23/15 model, not a fake good E3."""
    raw = deepcopy(source)
    raw["tl494_pin_roles"] = {str(n): "unspecified" for n in range(1, 17)}
    raw["tl494_pin_roles"].update({"3": "input", "13": "input"})
    raw["tl494_pin_aliases"] = {
        str(n): (("FB" if n == 3 else "OC") if n in (3, 13)
                 else f"P{n}") for n in range(1, 17)
    }
    validate_semantics(source, raw)
    negative = {}
    changes = {
        "component_missing": lambda x: x["components"].pop(),
        "net_deleted": lambda x: x["nets"].pop(),
        "wrong_net_pin": lambda x: x["nets"][0]["members"].pop(),
        "pin_in_two_nets": lambda x: x["nets"][1]["members"].append(
            x["nets"][0]["members"][0]),
        "duplicate_net_member": lambda x: x["nets"][0]["members"].append(
            x["nets"][0]["members"][0]),
        "false_nc": lambda x: x.update(nc_pins=["DA1.3"]),
        "pin3_output": lambda x: x["tl494_pin_roles"].update({"3": "output"}),
        "missing_alias": lambda x: x["tl494_pin_aliases"].pop("3"),
        "duplicate_alias": lambda x: x["tl494_pin_aliases"].update({"13": "FB"}),
        "overlong_alias": lambda x: x["tl494_pin_aliases"].update(
            {"3": "LONGNAME"}),
    }
    for label, mutate in changes.items():
        altered = deepcopy(raw)
        mutate(altered)
        try:
            validate_semantics(source, altered)
        except ContractError:
            negative[label] = "REJECTED"
        else:
            raise ContractError(f"NEGATIVE_FIXTURE_ACCEPTED:{label}")
    a = ((0, 0), (10000, 0), 300)
    below = ((0, 3299), (10000, 3299), 300)
    exact = ((0, 3300), (10000, 3300), 300)
    demand(parallel_gap_um(a, below) == 5998,
           "NEGATIVE_2_999_MM_PRECISION")
    demand(parallel_gap_um(a, exact) == 6000,
           "NEGATIVE_3_000_MM_PRECISION")
    negative["edge_2999um"] = "REJECTED"
    negative["edge_3000um"] = "ACCEPTED"
    return negative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--candidate-json", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    sha = subprocess.check_output(
        ["git", "-C", str(args.reference_root), "rev-parse", "HEAD"],
        text=True).strip()
    demand(sha == SOURCE_SHA, "NOT_EXACT_FROZEN_REAL_REFERENCE")
    source = source_model()
    report = {
        "baseline": SOURCE_SHA,
        "baseline_status": "KNOWN_BAD_PRINT_NO_GO",
        "real_source_counts": {"components": 23, "nets": 15, "DA1_pins": 16},
        "negative_fixture_results": negative_fixture_gate(source),
        "candidate_status": "BLOCKED_NO_NATIVE_ROUTER_EXPORT",
        "candidate_release": "NO_GO",
    }
    if args.candidate_json:
        candidate = json.loads(args.candidate_json.read_text(encoding="utf-8"))
        report["candidate_semantics"] = validate_semantics(source, candidate)
        _, _, owners = _records(candidate)
        report["candidate_route"] = validate_router_geometry(candidate, owners)
        report["candidate_status"] = "SEMANTIC_AND_WIRE_ONLY_PASS"
        report["candidate_release"] = "BLOCKED_RENDER_D4_INK_NORMATIVE"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False,
                                     indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("QA92_ROUTER_CONTRACT " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
