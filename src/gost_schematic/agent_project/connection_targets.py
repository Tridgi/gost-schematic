"""Read-only editor connection targets derived from the authoritative saved E3 model.

No SVG parsing, no electrical mutation, no promise of routability or CAS write.
The word "eligible" applies only to target discovery / a potential dry-run;
commit_permission is ALWAYS False until an independently accepted P1.2 writer.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from gost_schematic.model.circuit import PinRef

from .catalog import CatalogResolver, ProjectError
from .contracts import SchematicProject, stable_id

MAX_TARGETS = 4096

_NO_CONNECT = frozenset({"NC", "NO_CONNECT", "NOT_CONNECTED"})
_UNVERIFIED = frozenset({"UNSPECIFIED", "UNKNOWN"})
_POWER = frozenset({"POWER_INPUT", "POWER_OUTPUT"})
_DRIVERS = frozenset({"OUTPUT", "POWER_OUTPUT"})


@dataclass(frozen=True, slots=True)
class NetIdentity:
    """Stable electrical net identity; its printed name is NOT an alias key."""

    id: str
    name: str

    def to_record(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True, slots=True)
class ConnectionTarget:
    """Real physical PinRef OR an authored ExternalWireGraph segment endpoint."""

    target_id: str
    project_id: str
    project_revision: str
    kind: str
    world_um: tuple[int, int]
    component_id: str | None
    pin_ref: PinRef | None
    physical_number: str | None
    pin_name: str | None
    electrical_role: str
    pin_function: str | None
    polarity: str | None
    net_identity: NetIdentity | None
    wire_segment_id: str | None
    wire_end: str | None

    def to_record(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "project_id": self.project_id,
            "project_revision": self.project_revision,
            "kind": self.kind,
            "world_um": list(self.world_um),
            "component_id": self.component_id,
            "pin_ref": None if self.pin_ref is None else {
                "reference": self.pin_ref.reference, "number": self.pin_ref.number,
            },
            "physical_number": self.physical_number,
            "pin_name": self.pin_name,
            "electrical_role": self.electrical_role,
            "pin_function": self.pin_function,
            "polarity": self.polarity,
            "net_identity": (
                self.net_identity.to_record() if self.net_identity else None
            ),
            "wire_segment_id": self.wire_segment_id,
            "wire_end": self.wire_end,
        }


def _selection_reason(target: ConnectionTarget) -> str | None:
    if target.electrical_role in _NO_CONNECT:
        return "NC_CONTACT_FORBIDDEN"
    if target.electrical_role in _UNVERIFIED:
        return "ELECTRICAL_ROLE_UNVERIFIED"
    return None


def _candidate_reason(
    source: ConnectionTarget | None, target: ConnectionTarget,
) -> tuple[bool, str]:
    reason = _selection_reason(target)
    if reason is not None:
        return False, reason
    if source is None:
        return False, "SOURCE_REQUIRED"
    reason = _selection_reason(source)
    if reason is not None:
        return False, "SOURCE_" + reason
    if source.target_id == target.target_id:
        return False, "SAME_TARGET"
    a = source.net_identity
    b = target.net_identity
    if a is not None and b is not None and a.id != b.id:
        return False, "NET_MERGE_DENIED"
    if source.electrical_role in _DRIVERS and target.electrical_role in _DRIVERS:
        return False, "DRIVER_CONFLICT_REVIEW_REQUIRED"
    if source.electrical_role in _POWER or target.electrical_role in _POWER:
        return False, "POWER_POLICY_REVIEW_REQUIRED"
    if (source.electrical_role == "BIDIRECTIONAL"
            or target.electrical_role == "BIDIRECTIONAL"):
        return False, "BIDIRECTIONAL_POLICY_REVIEW_REQUIRED"
    if a is not None and b is not None and a.id == b.id:
        return True, "ALREADY_SAME_NET_PREVIEW_ONLY"
    return True, "PROVISIONAL_PREVIEW_ONLY"


def build_connection_targets(
    project: SchematicProject, catalog: CatalogResolver, *,
    source_target_id: str | None = None,
) -> dict[str, Any]:
    """Enumerate real, SHA-bound project anchors; never infer topology from SVG.

    A previewable candidate is NOT an approved electrical connection. No
    route is created. If a source is supplied, restrict provisional candidates
    using the current model's exact Net UUID and electrical pin role.
    """
    if source_target_id is not None and (
        type(source_target_id) is not str or len(source_target_id) != 36
    ):
        raise ProjectError("INVALID_TARGET_SELECTOR", "Expected stable target UUID")
    parts, symbols = catalog.verify(list(project.catalog_lock))
    reference_ids = dict(zip(
        (c.reference for c in project.circuit.components),
        project.component_ids, strict=True,
    ))
    nets = {
        net.name: NetIdentity(net_id, net.name)
        for net, net_id in zip(project.circuit.nets, project.net_ids, strict=True)
    }
    pin_nets: dict[PinRef, NetIdentity] = {}
    for net in project.circuit.nets:
        for ref in net.members:
            if ref in pin_nets:
                raise ProjectError("PHYSICAL_PIN_INVALID", "Duplicate physical Net ownership")
            pin_nets[ref] = nets[net.name]

    targets: list[ConnectionTarget] = []
    for component in project.circuit.components:
        part = parts[component.part_id]
        symbol = symbols[part.symbol_id]
        points = component.pin_positions(symbol)
        component_id = reference_ids[component.reference]
        for pin in part.pins:
            point = points[pin.number]
            ref = PinRef(component.reference, pin.number)
            targets.append(ConnectionTarget(
                target_id=stable_id(
                    project.project_id, "physical-pin-target",
                    f"{component_id}:{pin.number}",
                ),
                project_id=project.project_id,
                project_revision=project.revision,
                kind="physical_pin",
                world_um=(point.x, point.y),
                component_id=component_id,
                pin_ref=ref,
                physical_number=pin.number,
                pin_name=pin.name,
                electrical_role=pin.electrical_type.value.upper(),
                pin_function=pin.function.value,
                polarity=pin.polarity.value,
                net_identity=pin_nets.get(ref),
                wire_segment_id=None,
                wire_end=None,
            ))
    for segment, wire_id in zip(
        project.graph.segments, project.wire_ids, strict=True,
    ):
        net = nets[segment.net_name]
        for end, point in (("start", segment.start), ("end", segment.end)):
            targets.append(ConnectionTarget(
                target_id=stable_id(
                    project.project_id, "authored-wire-end-target", f"{wire_id}:{end}",
                ),
                project_id=project.project_id,
                project_revision=project.revision,
                kind="wire_endpoint",
                world_um=(point.x, point.y),
                component_id=None,
                pin_ref=None,
                physical_number=None,
                pin_name=None,
                electrical_role="CONDUCTOR",
                pin_function=None,
                polarity=None,
                net_identity=net,
                wire_segment_id=wire_id,
                wire_end=end,
            ))
    if len(targets) > MAX_TARGETS:
        raise ProjectError("TARGET_LIMIT_EXCEEDED", "Saved E3 target set exceeds read budget")
    by_id = {target.target_id: target for target in targets}
    if len(by_id) != len(targets):
        raise ProjectError("TARGET_ID_COLLISION", "Duplicate physical target identity")
    if source_target_id is not None and source_target_id not in by_id:
        raise ProjectError("SOURCE_TARGET_UNKNOWN", "Source is not part of this saved revision")
    source = by_id.get(source_target_id) if source_target_id else None
    colocated: dict[tuple[int, int], list[str]] = defaultdict(list)
    for target in targets:
        colocated[target.world_um].append(target.target_id)

    entries: list[dict[str, Any]] = []
    for target in targets:
        preview_allowed, reason = _candidate_reason(source, target)
        own_reason = _selection_reason(target)
        coincident = colocated[target.world_um]
        entries.append({
            **target.to_record(),
            "selection_allowed": own_reason is None,
            "preview_candidate_allowed": preview_allowed,
            "connection_allowed": False,
            "reason_code": reason,
            "commit_blocker": "WRITE_TRANSACTION_NOT_IMPLEMENTED",
            "coincident_target_ids": coincident if len(coincident) > 1 else [],
            "requires_disambiguation": len(coincident) > 1,
        })
    return {
        "schema_version": 1,
        "project_kind": "E3",
        "project_id": project.project_id,
        "project_revision": project.revision,
        "source_target_id": source_target_id,
        "read_only": True,
        "source_of_truth": (
            "saved Circuit + PhysicalPin + exact transformed GraphicPin "
            "+ Circuit.Net UUID + authored ExternalWireGraph"
        ),
        "hover_creates_net": False,
        "route_preview_available": False,
        "transaction_available": False,
        "target_count": len(entries),
        "targets": entries,
    }
