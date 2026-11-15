"""DRAFT lossless physical IC archive boundary for future MCP ProjectService.

P1.1 ProjectService #96 currently accepts only legacy PartDefinition with
single graphical symbol; do not downcast NC/multi-unit IC into that shape.
This snapshot is read-only, versioned, authenticated and independent of
ProjectService storage. Not an enabled MCP endpoint or project importer.
"""
import hashlib
import json
from dataclasses import dataclass

from gost_schematic.electrical.ic import IcPinType, validate_ic_circuit
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_from_json, ic_to_json
from gost_schematic.model.circuit import Circuit, PinRef

_FORMAT = "DRAFT_E3_IC_AGENT_SNAPSHOT"
_VERSION = 1


def _pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("IC_AGENT_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise ValueError(f"IC_AGENT_NONINTEGER_JSON: {value}")


def _connected_members(circuit: Circuit, component_ref: str) -> tuple:
    return tuple(sorted((
        (net.name, tuple(sorted(
            p.number for p in net.members if p.reference == component_ref
        )))
        for net in circuit.nets
        if any(p.reference == component_ref for p in net.members)
    ), key=lambda x: x[0]))


@dataclass(frozen=True, slots=True)
class IcAgentSnapshot:
    """Validated read-only record, not a generic PartDefinition conversion."""

    record: IcLibraryRecord
    component_ref: str
    connected_nets: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.record, IcLibraryRecord):
            raise TypeError("IC_AGENT_TYPED_RECORD_REQUIRED")
        if not isinstance(self.component_ref, str) or self.component_ref != (
            self.record.placements[0].component_ref
        ):
            raise ValueError("IC_AGENT_PHYSICAL_COMPONENT_REF_MISMATCH")
        if self.connected_nets != tuple(sorted(self.connected_nets)):
            raise ValueError("IC_AGENT_NET_ORDER_INVALID")
        all_pins = {p.number for p in self.record.device.pins}
        seen: set[str] = set()
        for name, numbers in self.connected_nets:
            if not name or not numbers or tuple(sorted(numbers)) != numbers:
                raise ValueError("IC_AGENT_NET_INVALID")
            for num in numbers:
                if (
                    num not in all_pins or num in seen
                    or self.record.device.pin_map[num].electrical_type is IcPinType.NC
                ):
                    raise ValueError("IC_AGENT_NET_PINREF_INVALID")
                seen.add(num)

    def to_json(self) -> str:
        """Preserve unabridged IC v1/v2 source record and real Net membership."""
        payload = ic_to_json(self.record)
        doc = {
            "format": _FORMAT,
            "version": _VERSION,
            "component_ref": self.component_ref,
            "ic_record_json": payload,
            "ic_record_sha256": hashlib.sha256(
                payload.encode("utf-8"),
            ).hexdigest(),
            "connected_nets": [
                {"name": name, "numbers": list(numbers)}
                for name, numbers in self.connected_nets
            ],
        }
        return json.dumps(
            doc, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ) + "\n"


def snapshot_ic_for_agent(record: IcLibraryRecord, circuit: Circuit) -> IcAgentSnapshot:
    if not isinstance(record, IcLibraryRecord) or not isinstance(circuit, Circuit):
        raise TypeError("IC_AGENT_REQUIRES_REAL_CIRCUIT_AND_IC")
    component_ref = record.placements[0].component_ref
    validate_ic_circuit(record.device, circuit, component_ref)
    return IcAgentSnapshot(
        record, component_ref, _connected_members(circuit, component_ref),
    )


def verify_agent_ic_snapshot(
    blob: str, circuit: Circuit,
) -> IcAgentSnapshot:
    """Fail closed on data loss, tampering and stale real Circuit memberships.

    A future P1.2 MCP project schema must explicitly include this versioned
    record; no existing ProjectService v1 path currently consumes it.
    """
    if not isinstance(blob, str) or not isinstance(circuit, Circuit):
        raise TypeError("IC_AGENT_REQUIRES_TYPED_PAYLOAD")
    raw = json.loads(
        blob, object_pairs_hook=_pairs,
        parse_float=_reject_float, parse_constant=_reject_float,
    )
    if type(raw) is not dict or set(raw) != {
        "format", "version", "component_ref", "ic_record_json",
        "ic_record_sha256", "connected_nets",
    } or raw["format"] != _FORMAT or type(raw["version"]) is not int or (
        raw["version"] != _VERSION
    ):
        raise ValueError("IC_AGENT_SCHEMA_UNSUPPORTED")
    if type(raw["ic_record_json"]) is not str or (
        type(raw["ic_record_sha256"]) is not str
    ) or hashlib.sha256(raw["ic_record_json"].encode("utf-8")).hexdigest() != (
        raw["ic_record_sha256"]
    ):
        raise ValueError("IC_AGENT_RECORD_HASH_MISMATCH")
    record = ic_from_json(raw["ic_record_json"])
    if ic_to_json(record) != raw["ic_record_json"]:
        raise ValueError("IC_AGENT_NONCANONICAL_IC_RECORD")
    nets = raw["connected_nets"]
    if type(nets) is not list:
        raise ValueError("IC_AGENT_NET_SCHEMA_INVALID")
    parsed = []
    for net in nets:
        if type(net) is not dict or set(net) != {"name", "numbers"}:
            raise ValueError("IC_AGENT_NET_SCHEMA_INVALID")
        if type(net["name"]) is not str or type(net["numbers"]) is not list:
            raise ValueError("IC_AGENT_NET_SCHEMA_INVALID")
        if any(type(n) is not str for n in net["numbers"]):
            raise ValueError("IC_AGENT_NET_SCHEMA_INVALID")
        parsed.append((net["name"], tuple(net["numbers"])))
    snapshot = IcAgentSnapshot(record, raw["component_ref"], tuple(parsed))
    validate_ic_circuit(snapshot.record.device, circuit, snapshot.component_ref)
    if snapshot.connected_nets != _connected_members(circuit, snapshot.component_ref):
        raise ValueError("IC_AGENT_REAL_NET_MEMBERSHIP_CHANGED")
    if snapshot.to_json() != blob:
        raise ValueError("IC_AGENT_NONCANONICAL_SNAPSHOT")
    # PinRef cannot be synthesized from a decorative SVG or a package name.
    original_refs = {
        PinRef(snapshot.component_ref, p.number)
        for p in snapshot.record.device.pins
    }
    if len(original_refs) != snapshot.record.device.package.pin_count:
        raise ValueError("IC_AGENT_PHYSICAL_PIN_IDENTITY_LOST")
    return snapshot
