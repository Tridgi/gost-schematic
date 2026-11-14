"""Issue #90 — nonphysical circuit continuation, bound to existing Circuit.Net.

Graphical labels, matching coordinates or coincident drawing ink NEVER
connect distinct electrical networks or add an E3 physical component.
ESKD source status is DRAFT until independent normative signoff.
"""
from dataclasses import dataclass
from enum import Enum
from re import fullmatch

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, PinRef


def _id(value: str, label: str) -> str:
    if type(value) is not str or not value.strip() or value.strip() != value:
        raise ValueError(f"{label} must be a canonical nonblank string")
    return value


def _unique(values: list[str]) -> bool:
    return len(values) == len(set(values))


class ContinuationScope(str, Enum):
    SHEET_LOCAL = "sheet_local"
    GLOBAL = "global"


class ContinuationDirection(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True, slots=True)
class NetIdentity:
    """Stable project ID and exact physical members for ONE existing Circuit.Net."""
    id: str
    net_name: str
    members: tuple[PinRef, ...]

    def __post_init__(self) -> None:
        _id(self.id, "net ID")
        _id(self.net_name, "Circuit.Net name")
        if not isinstance(self.members, tuple) or not self.members:
            raise ValueError("Physical net identity requires exact member inventory")
        if not all(isinstance(item, PinRef) for item in self.members):
            raise TypeError("Net member must be physical PinRef")
        if len(self.members) != len(set(self.members)):
            raise ValueError("Repeated physical PinRef in net binding")


@dataclass(frozen=True, slots=True)
class ContinuationSheet:
    id: str
    number: int

    def __post_init__(self) -> None:
        _id(self.id, "sheet ID")
        if type(self.number) is not int or self.number < 1:
            raise ValueError("Sheet number must be positive integer")


@dataclass(frozen=True, slots=True)
class NetContinuationEndpoint:
    """Nonphysical arrow/marker, with *separate* local and remote addresses."""
    id: str
    net_id: str
    sheet_id: str
    sheet_number: int
    address: str
    target_address: str
    anchor: Point
    label: str
    direction: ContinuationDirection

    def __post_init__(self) -> None:
        for item, name in (
            (self.id, "marker ID"), (self.net_id, "marker net ID"),
            (self.sheet_id, "marker sheet ID"), (self.address, "address"),
            (self.target_address, "target address"), (self.label, "printed label"),
        ):
            _id(item, name)
        if type(self.sheet_number) is not int or self.sheet_number < 1:
            raise ValueError("Marker sheet number must be positive")
        if not isinstance(self.anchor, Point):
            raise TypeError("Marker anchor must be exact Point")
        if not isinstance(self.direction, ContinuationDirection):
            raise TypeError("Marker direction must be typed")


@dataclass(frozen=True, slots=True)
class ContinuationPair:
    id: str
    source_id: str
    target_id: str
    scope: ContinuationScope

    def __post_init__(self) -> None:
        _id(self.id, "pair ID")
        _id(self.source_id, "source marker ID")
        _id(self.target_id, "target marker ID")
        if self.source_id == self.target_id:
            raise ValueError("A continuation pair needs two different endpoints")
        if not isinstance(self.scope, ContinuationScope):
            raise TypeError("Continuation scope must be typed")


@dataclass(frozen=True, slots=True)
class ContinuationStub:
    """A visibly drawn SINGLE local H/V wire, not a cross-page conductor."""
    id: str
    endpoint_id: str
    pin: PinRef
    start: Point
    end: Point

    def __post_init__(self) -> None:
        _id(self.id, "stub ID")
        _id(self.endpoint_id, "stub marker ID")
        if not isinstance(self.pin, PinRef):
            raise TypeError("Stub pin must be actual E3 PinRef")
        if not isinstance(self.start, Point) or not isinstance(self.end, Point):
            raise TypeError("Stub endpoints must be exact Points")
        if self.start == self.end or (
            self.start.x != self.end.x and self.start.y != self.end.y
        ):
            raise ValueError("Stub is a nonzero orthogonal local conductor")


@dataclass(frozen=True, slots=True)
class NetContinuationProject:
    """A view overlay over an immutable existing Circuit; no new physical parts."""
    circuit: Circuit
    nets: tuple[NetIdentity, ...]
    sheets: tuple[ContinuationSheet, ...]
    endpoints: tuple[NetContinuationEndpoint, ...]
    pairs: tuple[ContinuationPair, ...]
    stubs: tuple[ContinuationStub, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.circuit, Circuit):
            raise TypeError("Continuations require an existing Circuit")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported DRAFT continuation schema")
        for values, item_type, label in (
            (self.nets, NetIdentity, "NetIdentity"),
            (self.sheets, ContinuationSheet, "ContinuationSheet"),
            (self.endpoints, NetContinuationEndpoint, "NetContinuationEndpoint"),
            (self.pairs, ContinuationPair, "ContinuationPair"),
            (self.stubs, ContinuationStub, "ContinuationStub"),
        ):
            if not isinstance(values, tuple) or not all(
                isinstance(item, item_type) for item in values
            ):
                raise TypeError(f"Continuation project requires tuple[{label}]")


def _err(code: str, subject: str, detail: str) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, detail, subject)


def validate_net_continuations(
    project: NetContinuationProject,
    *,
    physical_pin_anchors: dict[PinRef, Point] | None = None,
) -> tuple[Diagnostic, ...]:
    """Independent fail-closed semantic and geometrical gate.

    Additional exact physical PinRef→Point anchors can be supplied from the
    authoritative ComponentInstance/SymbolDefinition view; no inference by ink.
    """
    if not isinstance(project, NetContinuationProject):
        raise TypeError("Expected NetContinuationProject")
    errors: list[Diagnostic] = []
    for group, keys in (
        ("NET_ID", [x.id for x in project.nets]),
        ("SHEET_ID", [x.id for x in project.sheets]),
        ("SHEET_NUMBER", [str(x.number) for x in project.sheets]),
        ("ENDPOINT_ID", [x.id for x in project.endpoints]),
        ("PAIR_ID", [x.id for x in project.pairs]),
        ("STUB_ID", [x.id for x in project.stubs]),
    ):
        if not _unique(keys):
            errors.append(_err("E3_CONT_DUPLICATE_" + group, group, "Duplicate identity"))

    # Real circuit must not assign the same physical pin to two distinct nets.
    owners: dict[PinRef, str] = {}
    real_net_names: dict[str, list] = {}
    component_refs = [c.reference for c in project.circuit.components]
    if not _unique(component_refs):
        errors.append(_err("E3_CONT_DUPLICATE_PART", "circuit", "Duplicate reference"))
    for net in project.circuit.nets:
        real_net_names.setdefault(net.name, []).append(net)
        for member in net.members:
            if member.reference not in component_refs:
                errors.append(_err(
                    "E3_CONT_PHYSICAL_PIN_UNKNOWN", net.name,
                    "Net member references a component absent from Circuit",
                ))
            if member in owners and owners[member] != net.name:
                errors.append(_err(
                    "E3_CONT_PHYSICAL_NET_CONFLICT", net.name,
                    "One real PinRef belongs to two different Nets",
                ))
            owners[member] = net.name

    bindings = {x.id: x for x in project.nets}
    bound_nets: set[str] = set()
    for item in project.nets:
        candidates = real_net_names.get(item.net_name, ())
        if len(candidates) != 1:
            errors.append(_err(
                "E3_CONT_NET_UNKNOWN", item.id,
                "Net name is unknown or ambiguous in real Circuit",
            ))
            continue
        if set(item.members) != set(candidates[0].members) or (
            len(item.members) != len(candidates[0].members)
        ):
            errors.append(_err(
                "E3_CONT_NET_MEMBERS_MISMATCH", item.id,
                "Net ID is not the declared exact existing physical PinRef inventory",
            ))
        if item.net_name in bound_nets:
            errors.append(_err(
                "E3_CONT_NET_DUPLICATE_BINDING", item.id,
                "Two stable net IDs claim the same Circuit.Net",
            ))
        bound_nets.add(item.net_name)

    sheets = {x.id: x for x in project.sheets}
    endpoints = {x.id: x for x in project.endpoints}
    by_address: dict[tuple[str, str], str] = {}
    for e in project.endpoints:
        if e.net_id not in bindings:
            errors.append(_err("E3_CONT_NET_ID_UNKNOWN", e.id, "Unknown net_id"))
        sheet = sheets.get(e.sheet_id)
        if sheet is None or e.sheet_number != sheet.number:
            errors.append(_err(
                "E3_CONT_SHEET_UNKNOWN", e.id, "Unknown/mismatched sheet ID/number",
            ))
        key = (e.sheet_id, e.address)
        if key in by_address:
            errors.append(_err(
                "E3_CONT_ADDRESS_DUPLICATE", e.id, "Sheet-local address repeated",
            ))
        by_address[key] = e.id
        if fullmatch(r"(?i)(XP|XS)\d+[A-Za-z0-9._-]*", e.label):
            errors.append(_err(
                "E3_CONT_PHYSICAL_CONNECTOR_IMPERSONATION", e.id,
                "XP/XS is reserved for a real physical PartDefinition/PinRef",
            ))

    paired_ids: set[str] = set()
    global_labels: dict[str, str] = {}
    local_labels: dict[tuple[str, str], str] = {}
    for pair in project.pairs:
        a = endpoints.get(pair.source_id)
        b = endpoints.get(pair.target_id)
        if a is None or b is None:
            errors.append(_err(
                "E3_CONT_ENDPOINT_UNKNOWN", pair.id, "Pair target/source missing",
            ))
            continue
        for e in (a, b):
            if e.id in paired_ids:
                errors.append(_err(
                    "E3_CONT_ENDPOINT_REUSED", e.id, "One marker used by multiple pairs",
                ))
            paired_ids.add(e.id)
        if a.net_id != b.net_id:
            errors.append(_err(
                "E3_CONT_CROSS_NET", pair.id,
                "Visible pair cannot merge different real Net identities",
            ))
        if a.target_address != b.address or b.target_address != a.address:
            errors.append(_err(
                "E3_CONT_ADDRESS_MISMATCH", pair.id,
                "Continuation addresses must be explicit and reciprocal",
            ))
        if a.direction not in (
            ContinuationDirection.SOURCE, ContinuationDirection.BIDIRECTIONAL,
        ) or b.direction not in (
            ContinuationDirection.TARGET, ContinuationDirection.BIDIRECTIONAL,
        ):
            errors.append(_err(
                "E3_CONT_DIRECTION", pair.id, "Arrow orientation mismatches source→target",
            ))
        if pair.scope is ContinuationScope.SHEET_LOCAL and a.sheet_id != b.sheet_id:
            errors.append(_err(
                "E3_CONT_SCOPE", pair.id, "Sheet-local pair crossed sheet boundary",
            ))
        if pair.scope is ContinuationScope.GLOBAL and a.sheet_id == b.sheet_id:
            errors.append(_err(
                "E3_CONT_SCOPE", pair.id, "Global pair must cross sheets",
            ))
        if a.label != b.label:
            errors.append(_err(
                "E3_CONT_LABEL_MISMATCH", pair.id,
                "Same net continuation must show consistent visible label",
            ))
        for e in (a, b):
            if pair.scope is ContinuationScope.GLOBAL:
                old = global_labels.setdefault(e.label, e.net_id)
                if old != e.net_id:
                    errors.append(_err(
                        "E3_CONT_LABEL_AMBIGUOUS", e.id,
                        "Same globally visible label belongs to different net IDs",
                    ))
            key = (e.sheet_id, e.label)
            old = local_labels.setdefault(key, e.net_id)
            if old != e.net_id:
                errors.append(_err(
                    "E3_CONT_LABEL_AMBIGUOUS", e.id,
                    "Same sheet label belongs to different physical net IDs",
                ))
    if paired_ids != set(endpoints):
        errors.append(_err(
            "E3_CONT_UNPAIRED_MARKER", "project",
            "Each continuation marker must belong to one explicit pair",
        ))

    seen_stubs: set[str] = set()
    for stub in project.stubs:
        endpoint = endpoints.get(stub.endpoint_id)
        if endpoint is None:
            errors.append(_err(
                "E3_CONT_STUB_MARKER_UNKNOWN", stub.id, "Missing marker",
            ))
            continue
        if stub.endpoint_id in seen_stubs:
            errors.append(_err(
                "E3_CONT_STUB_DUPLICATE", stub.id, "Repeated visible wire stub",
            ))
        seen_stubs.add(stub.endpoint_id)
        if stub.end != endpoint.anchor:
            errors.append(_err(
                "E3_CONT_STUB_OFF_ANCHOR", stub.id,
                "Wire stub must terminate exactly at declared continuation Point",
            ))
        binding = bindings.get(endpoint.net_id)
        if binding is None or stub.pin not in binding.members:
            errors.append(_err(
                "E3_CONT_STUB_WRONG_NET", stub.id,
                "Physical PinRef must be member of this exact real net",
            ))
        if physical_pin_anchors is not None and (
            physical_pin_anchors.get(stub.pin) != stub.start
        ):
            errors.append(_err(
                "E3_CONT_STUB_PHYSICAL_MISMATCH", stub.id,
                "Wire must begin at exactly the real physical pin anchor",
            ))
    if seen_stubs != set(endpoints):
        errors.append(_err(
            "E3_CONT_STUB_MISSING", "project", "Every marker needs one explicit local stub",
        ))
    return tuple(sorted(
        errors, key=lambda e: (e.code, e.subject or "", e.message),
    ))


def transform_continuations(
    project: NetContinuationProject, transform: Transform,
) -> NetContinuationProject:
    """D4 changes only visible geometry, never electrical IDs or membership."""
    if not isinstance(transform, Transform):
        raise TypeError("Expected Transform")
    from dataclasses import replace

    return replace(
        project,
        endpoints=tuple(
            replace(e, anchor=transform.apply(e.anchor)) for e in project.endpoints
        ),
        stubs=tuple(
            replace(s, start=transform.apply(s.start), end=transform.apply(s.end))
            for s in project.stubs
        ),
    )
