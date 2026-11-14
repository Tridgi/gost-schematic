"""Strict DRAFT v1 continuation overlay serialization.

The actual Circuit is an external authoritative object supplied on import.
Serialization never rebuilds/fabricates any physical PartDefinition or Net.
"""

import json

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import (
    ContinuationAddressBinding,
    ContinuationAddressKind,
    ContinuationDirection,
    ContinuationPair,
    ContinuationScope,
    ContinuationSheet,
    ContinuationStub,
    NetContinuationEndpoint,
    NetContinuationProject,
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, PinRef


def _p(p: Point) -> list[int]:
    return [p.x, p.y]


def _decode_point(p: object) -> Point:
    if type(p) is not list or len(p) != 2 or any(type(x) is not int for x in p):
        raise ValueError("Point requires two integer micrometres")
    return Point(*p)


def _obj(value: object, keys: set[str]) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"Expected exact JSON keys: {sorted(keys)}")
    return value


def _arr(value: object) -> list:
    if type(value) is not list:
        raise ValueError("Expected JSON array")
    return value


def _pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in items:
        if k in result:
            raise ValueError(f"Duplicate JSON key: {k}")
        result[k] = v
    return result


def _constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number {value} prohibited")


def _pin(p: PinRef) -> dict:
    return {"reference": p.reference, "number": p.number}


def _decode_pin(p: object) -> PinRef:
    p = _obj(p, {"reference", "number"})
    return PinRef(p["reference"], p["number"])


def netrefs_to_json(
    project: NetContinuationProject,
    *, verified_address_owners: dict[
        tuple[ContinuationAddressKind, str], frozenset[PinRef]
    ] | None = None,
) -> str:
    if not isinstance(project, NetContinuationProject):
        raise TypeError("Expected NetContinuationProject")
    issues = validate_net_continuations(
        project, verified_address_owners=verified_address_owners,
    )
    if issues:
        raise ValueError("; ".join(issue.code for issue in issues))
    value = {
        "schema_version": project.schema_version, "record_type": "DRAFT_E3_NET_CONTINUATIONS",
        "nets": [{
            "id": n.id, "net_name": n.net_name,
            "members": [_pin(p) for p in n.members],
        } for n in project.nets],
        "sheets": [{"id": s.id, "number": s.number} for s in project.sheets],
        "endpoints": [{
            "id": e.id, "net_id": e.net_id,
            "sheet_id": e.sheet_id, "sheet_number": e.sheet_number,
            "address": e.address, "target_address": e.target_address,
            "anchor_um": _p(e.anchor), "label": e.label,
            "direction": e.direction.value,
        } for e in project.endpoints],
        "pairs": [{
            "id": p.id, "source_id": p.source_id, "target_id": p.target_id,
            "scope": p.scope.value,
        } for p in project.pairs],
        "stubs": [{
            "id": s.id, "endpoint_id": s.endpoint_id,
            "pin": _pin(s.pin), "start_um": _p(s.start), "end_um": _p(s.end),
        } for s in project.stubs],
    }
    if project.schema_version == 2:
        value["address_bindings"] = [{
            "endpoint_id": record.endpoint_id,
            "kind": record.kind.value, "owner_ref": record.owner_ref,
            "physical_pin": _pin(record.physical_pin) if record.physical_pin else None,
        } for record in project.address_bindings]
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def netrefs_from_json(
    text: str, circuit: Circuit, *,
    verified_address_owners: dict[
        tuple[ContinuationAddressKind, str], frozenset[PinRef]
    ] | None = None,
    expected_schema_version: int | None = None,
) -> NetContinuationProject:
    if type(text) is not str or not isinstance(circuit, Circuit):
        raise TypeError("Decoder requires text and REAL existing Circuit")
    raw = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    if type(raw) is not dict:
        raise ValueError("Expected JSON object")
    version = raw.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported continuation schema version")
    if expected_schema_version is not None:
        if type(expected_schema_version) is not int or expected_schema_version not in (1, 2):
            raise ValueError("Expected schema version must be 1 or 2")
        if version != expected_schema_version:
            raise ValueError("E3_CONT_SCHEMA_VERSION_MISMATCH: explicit migration required")
    keys = {"schema_version", "record_type", "nets", "sheets",
            "endpoints", "pairs", "stubs"}
    if version == 2:
        keys.add("address_bindings")
    raw = _obj(raw, keys)
    if raw["record_type"] != "DRAFT_E3_NET_CONTINUATIONS":
        raise ValueError("Not an E3 continuation overlay")
    bindings = []
    for n in _arr(raw["nets"]):
        n = _obj(n, {"id", "net_name", "members"})
        bindings.append(NetIdentity(
            n["id"], n["net_name"],
            tuple(_decode_pin(p) for p in _arr(n["members"])),
        ))
    sheets = []
    for s in _arr(raw["sheets"]):
        s = _obj(s, {"id", "number"})
        sheets.append(ContinuationSheet(s["id"], s["number"]))
    ends = []
    for e in _arr(raw["endpoints"]):
        e = _obj(e, {
            "id", "net_id", "sheet_id", "sheet_number",
            "address", "target_address", "anchor_um", "label", "direction",
        })
        ends.append(NetContinuationEndpoint(
            e["id"], e["net_id"], e["sheet_id"], e["sheet_number"],
            e["address"], e["target_address"], _decode_point(e["anchor_um"]),
            e["label"], ContinuationDirection(e["direction"]),
        ))
    pairs = []
    for p in _arr(raw["pairs"]):
        p = _obj(p, {"id", "source_id", "target_id", "scope"})
        pairs.append(ContinuationPair(
            p["id"], p["source_id"], p["target_id"], ContinuationScope(p["scope"]),
        ))
    stubs = []
    for s in _arr(raw["stubs"]):
        s = _obj(s, {"id", "endpoint_id", "pin", "start_um", "end_um"})
        stubs.append(ContinuationStub(
            s["id"], s["endpoint_id"], _decode_pin(s["pin"]),
            _decode_point(s["start_um"]), _decode_point(s["end_um"]),
        ))
    address_bindings = []
    if version == 2:
        for record in _arr(raw["address_bindings"]):
            record = _obj(record, {
                "endpoint_id", "kind", "owner_ref", "physical_pin",
            })
            address_bindings.append(ContinuationAddressBinding(
                record["endpoint_id"], ContinuationAddressKind(record["kind"]),
                record["owner_ref"],
                _decode_pin(record["physical_pin"])
                if record["physical_pin"] is not None else None,
            ))
    project = NetContinuationProject(
        circuit, tuple(bindings), tuple(sheets), tuple(ends),
        tuple(pairs), tuple(stubs), schema_version=version,
        address_bindings=tuple(address_bindings),
    )
    issues = validate_net_continuations(
        project, verified_address_owners=verified_address_owners,
    )
    if issues:
        raise ValueError("; ".join(issue.code for issue in issues))
    return project
