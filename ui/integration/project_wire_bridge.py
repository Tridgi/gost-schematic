"""R1 ProjectFileV2 <-> typed WireEngine adapter. Single sheet, no native GUI writer."""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor" / "src" / "model"))
import contract as model  # noqa: E402

SIDES = {"left": "left", "right": "right", "top": "up", "bottom": "down"}
KEYS = {"schema_version", "project_id", "revision", "source_topology_hash",
        "components", "nets", "wires", "junctions", "splices"}


class BridgeError(ValueError):
    pass


def sheet_for(doc, name=None):
    sheets = doc["project"]["sheets"]
    if len(sheets) != 1:
        raise BridgeError("MULTISHEET_ADAPTER_NOT_READY")
    if name is not None and sheets[0]["id"] != name:
        raise BridgeError("UNKNOWN_SHEET")
    return sheets[0]


def free_id_gate(wires):
    # CHAT7 runtime is stricter than canonical v2: never silently remap identities.
    for w in wires:
        for side, v in (("start", w["vertices"][0]), ("end", w["vertices"][-1])):
            a = v["anchor"]
            if a["kind"] == "free" and a["free_id"] != f"{w['id']}:{side}":
                raise BridgeError("FREE_ID_RUNTIME_INCOMPATIBLE")


def to_snapshot(doc, *, sheet_id=None, revision=0):
    model.validate(doc)
    if type(revision) is not int or revision < 0:
        raise BridgeError("INVALID_REVISION")
    p, sh = doc["project"], sheet_for(doc, sheet_id)
    parts = {part["id"]: part for part in p["part_definitions"]}
    symbols = {sym["id"]: sym for sym in p["symbol_definitions"]}
    components = {comp["id"]: comp for comp in p["components"]}
    placed, seen = [], set()
    for inst in sh["instances"]:
        cid = inst["component_id"]
        if cid in seen:
            raise BridgeError("MULTIUNIT_VIEW_NOT_READY")
        seen.add(cid)
        c = components[cid]
        part, sym = parts[c["part_id"]], symbols[inst["symbol_id"]]
        if sym["part_id"] != part["id"]:
            raise BridgeError("PART_SYMBOL_MISMATCH")
        physical = {x["number"] for x in part["physical_pins"]}
        pins = []
        for pin in sym["pins"]:
            pn = pin["physical_pin_number"]
            if pn not in physical:
                raise BridgeError("INVALID_PINREF")
            pins.append({"component_id": cid, "physical_pin_number": pn,
                         "local_at_um": copy.deepcopy(pin["at_um"]),
                         "outward": SIDES[pin["side"]]})
        placed.append({"id": cid, "origin_um": copy.deepcopy(inst["origin_um"]),
                       "rotation": inst["rotation_deg"],
                       "mirror_x": inst["mirror_x"], "pins": pins})
    exposed = {(c["id"], pin["physical_pin_number"])
               for c in placed for pin in c["pins"]}
    for net in p["nets"]:
        for pin in net["members"]:
            if (pin["component_id"], pin["physical_pin_number"]) not in exposed:
                raise BridgeError("UNPLACED_SOURCE_PIN")
    free_id_gate(sh["wires"])
    return {"schema_version": 2, "project_id": p["id"], "revision": revision,
            "source_topology_hash": model.source_inventory_hash(p),
            "components": placed,
            "nets": [{"id": n["id"], "literal_source_name": n["name"],
                      "members": copy.deepcopy(n["members"])} for n in p["nets"]],
            "wires": copy.deepcopy(sh["wires"]),
            "junctions": copy.deepcopy(sh["junctions"]),
            "splices": copy.deepcopy(sh["splices"])}


def apply_snapshot(doc, candidate, *, expected_sha, sheet_id=None):
    model.validate(doc)
    if expected_sha != model.digest(doc):
        raise BridgeError("STALE_PROJECT_SHA")
    baseline = to_snapshot(doc, sheet_id=sheet_id)
    if type(candidate) is not dict or set(candidate) != KEYS:
        raise BridgeError("INVALID_WIRE_SNAPSHOT")
    for field in ("schema_version", "project_id", "source_topology_hash",
                  "components", "nets"):
        if candidate[field] != baseline[field]:
            raise BridgeError("SOURCE_TOPOLOGY_CHANGED:" + field)
    if type(candidate["revision"]) is not int or candidate["revision"] < 0:
        raise BridgeError("INVALID_REVISION")
    free_id_gate(candidate["wires"])
    result = copy.deepcopy(doc)
    sh = sheet_for(result, sheet_id)
    for field in ("wires", "junctions", "splices"):
        sh[field] = copy.deepcopy(candidate[field])
    for net in result["project"]["nets"]:
        wires = [w for w in sh["wires"] if w["net_id"] == net["id"]]
        if not wires:
            net["route_status"] = "unrouted"
        elif (all(not w.get("needs_routing_review", False) and
                  all(v["anchor"]["kind"] != "free"
                      for v in (w["vertices"][0], w["vertices"][-1]))
                  for w in wires) and model.route_is_complete(result["project"], net)):
            net["route_status"] = "verified"
        else:
            net["route_status"] = "partial"
    model.validate(result)
    if model.source_inventory_hash(result["project"]) != baseline["source_topology_hash"]:
        raise BridgeError("SOURCE_TOPOLOGY_CHANGED")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("snapshot", "digest", "apply"))
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--expected-sha")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    try:
        doc = model.strict_loads(args.project.read_bytes())
        if args.action == "digest":
            print(model.digest(doc))
        elif args.action == "snapshot":
            raw = json.dumps(to_snapshot(doc), sort_keys=True, ensure_ascii=False) + "\n"
            if args.out:
                args.out.write_text(raw, encoding="utf-8")
            else:
                print(raw, end="")
        else:
            if not args.snapshot or not args.expected_sha or not args.out:
                p.error("apply needs --snapshot --expected-sha --out")
            candidate = model.strict_loads(args.snapshot.read_bytes())
            result = apply_snapshot(doc, candidate, expected_sha=args.expected_sha)
            model.atomic_save(args.out, result)
            print(model.digest(result))
        return 0
    except (BridgeError, model.ContractError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
