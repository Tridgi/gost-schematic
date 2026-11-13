"""Immutable E3 project v1: exact physical PinRefs and authored ExternalWireGraph.

Persistence holds typed engineering records, never image-derived connectivity.
"""
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.potentials import NetPotential, PotentialScenario
from gost_schematic.model.quantities import Quantity
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

from .catalog import CatalogResolver, ProjectError, canonical_bytes, digest, normalized

FORMAT_ID = "gse-project"
VERSION = 1
DOMAIN = b"GSE_PROJECT_V1\x00"


def project_uuid(value: str) -> str:
    try:
        resolved = str(uuid.UUID(value))
    except (TypeError, AttributeError, ValueError) as exc:
        raise ProjectError("INVALID_PROJECT_ID", "Expected canonical UUID") from exc
    if value != resolved:
        raise ProjectError("INVALID_PROJECT_ID", "Project UUID must be canonical lowercase")
    return value


def stable_id(project_id: str, kind: str, identifier: str) -> str:
    return str(uuid.uuid5(uuid.UUID(project_id), f"{kind}:{identifier}"))


def _keys(value: Any, names: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != names:
        raise ProjectError("SCHEMA_UNSUPPORTED", f"Expected exact fields {sorted(names)}")
    return value


def _list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise ProjectError("SCHEMA_UNSUPPORTED", "Expected ordered array")
    return value


def _text(value: Any) -> str:
    if type(value) is not str or not value or len(value) > 256:
        raise ProjectError("SCHEMA_UNSUPPORTED", "Expected bounded nonempty string")
    return value


def _integer(value: Any) -> int:
    if type(value) is not int or abs(value) > 1_000_000_000:
        raise ProjectError("SCHEMA_UNSUPPORTED", "Expected bounded integer micrometres")
    return value


def _point(value: Any) -> Point:
    numbers = _list(value)
    if len(numbers) != 2:
        raise ProjectError("SCHEMA_UNSUPPORTED", "Point must have x and y")
    return Point(*(_integer(v) for v in numbers))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


def _on_wire(segment: WireSegment, point: Point) -> bool:
    a, b = segment.start, segment.end
    return ((b.x - a.x) * (point.y - a.y) == (b.y - a.y) * (point.x - a.x)
            and min(a.x, b.x) <= point.x <= max(a.x, b.x)
            and min(a.y, b.y) <= point.y <= max(a.y, b.y))


@dataclass(frozen=True, slots=True)
class SchematicProject:
    project_id: str
    title: str
    circuit: Circuit
    graph: ExternalWireGraph
    catalog_lock: tuple[dict[str, Any], ...]
    component_ids: tuple[str, ...]
    net_ids: tuple[str, ...]
    wire_ids: tuple[str, ...]
    junction_ids: tuple[str, ...]
    junction_owners: tuple[str, ...]
    stroke_widths_um: tuple[int, ...]
    labels: tuple[dict[str, Any], ...]
    scenario: PotentialScenario | None
    source_tag: str

    def __post_init__(self) -> None:
        # Dataclass frozen is insufficient when nested catalog dictionaries are mutable.
        object.__setattr__(
            self, "catalog_lock", tuple(_freeze(v) for v in self.catalog_lock),
        )
        object.__setattr__(self, "labels", tuple(_freeze(v) for v in self.labels))

    @classmethod
    def from_circuit(
        cls, project_id: str, title: str, circuit: Circuit, graph: ExternalWireGraph,
        catalog: CatalogResolver, *, strokes_um: tuple[int, ...],
        scenario: PotentialScenario | None = None, source_tag: str = "trusted-inprocess-e3",
    ) -> "SchematicProject":
        project_uuid(project_id)
        _text(title)
        _text(source_tag)
        if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
            raise ProjectError("MODEL_INVALID", "Real Circuit and ExternalWireGraph required")
        if len(graph.segments) != len(strokes_um) or any(
            type(s) is not int or not 50 <= s <= 5000 for s in strokes_um
        ):
            raise ProjectError("STROKE_PROVENANCE_MISSING", "Explicit proven stroke per wire required")
        references = [c.reference for c in circuit.components]
        names = [n.name for n in circuit.nets]
        if len(set(references)) != len(references) or len(set(names)) != len(names):
            raise ProjectError("MODEL_INVALID", "Duplicate component refdes or net name")
        part_ids = sorted({c.part_id for c in circuit.components})
        locks = tuple(catalog.lock(part_id) for part_id in part_ids)
        parts, symbols = catalog.verify(list(locks))
        for component in circuit.components:
            part = parts[component.part_id]
            symbol = symbols[part.symbol_id]
            if component.nominal is not None and component.nominal.kind != part.nominal_kind:
                raise ProjectError("NOMINAL_MISMATCH", component.reference)
            if set(component.pin_positions(symbol)) != {pin.number for pin in part.pins}:
                raise ProjectError("PHYSICAL_PIN_INVALID", component.reference)
        owners: dict[PinRef, str] = {}
        for net in circuit.nets:
            for pin in net.members:
                component = next((c for c in circuit.components if c.reference == pin.reference),
                                 None)
                if component is None or pin.number not in {
                    p.number for p in parts[component.part_id].pins
                } or pin in owners:
                    raise ProjectError("PHYSICAL_PIN_INVALID", f"Invalid/duplicate {pin}")
                owners[pin] = net.name
        if any(w.net_name not in names for w in graph.segments):
            raise ProjectError("WIRE_NET_INVALID", "Conductor is assigned to unknown Net")
        junction_owners: list[str] = []
        for point in graph.junctions:
            containing = {w.net_name for w in graph.segments if _on_wire(w, point)}
            if len(containing) != 1:
                raise ProjectError("JUNCTION_OWNER_AMBIGUOUS", str(point))
            junction_owners.append(next(iter(containing)))
        if scenario is not None and any(p.net_name not in names for p in scenario.potentials):
            raise ProjectError("SCENARIO_NET_INVALID", "Potential references missing net")
        component_ids = tuple(stable_id(project_id, "component", c.reference)
                              for c in circuit.components)
        net_ids = tuple(stable_id(project_id, "net", n.name) for n in circuit.nets)
        wire_ids = tuple(stable_id(project_id, "wire", str(i))
                         for i in range(len(graph.segments)))
        junction_ids = tuple(stable_id(project_id, "junction", str(i))
                             for i in range(len(graph.junctions)))
        labels = tuple({
            "id": stable_id(project_id, "label", c.reference),
            "component_id": component_ids[i],
            "text": c.reference,
            "at_um": [c.origin.x, c.transform.box(
                symbols[parts[c.part_id].symbol_id].body_keepout
            ).translated(c.origin).min_y - 2500],
            "font_family": "sans-serif",
            "font_size_um": 3500,
        } for i, c in enumerate(circuit.components))
        return cls(project_id, title, circuit, graph, locks, component_ids, net_ids,
                   wire_ids, junction_ids, tuple(junction_owners), strokes_um,
                   labels, scenario, source_tag)

    def to_record(self) -> dict[str, Any]:
        component_by_ref = dict(zip(
            (c.reference for c in self.circuit.components), self.component_ids, strict=True
        ))
        net_by_name = dict(zip(
            (n.name for n in self.circuit.nets), self.net_ids, strict=True
        ))
        return {
            "format_id": FORMAT_ID, "schema_version": VERSION,
            "project_id": self.project_id, "project_kind": "E3",
            "title": self.title, "source_tag": self.source_tag,
            "catalog_lock": [normalized(v) for v in self.catalog_lock],
            "components": [{
                "id": key, "reference": c.reference, "part_id": c.part_id,
                "origin_um": [c.origin.x, c.origin.y],
                "rotation": c.transform.rotation, "mirror_x": c.transform.mirror_x,
                "nominal": c.nominal.to_record() if c.nominal else None,
            } for c, key in zip(self.circuit.components, self.component_ids, strict=True)],
            "nets": [{
                "id": key, "name": n.name,
                "members": [{"component_id": component_by_ref[p.reference], "pin": p.number}
                            for p in n.members],
            } for n, key in zip(self.circuit.nets, self.net_ids, strict=True)],
            "wires": [{
                "id": key, "ordinal": i, "net_id": net_by_name[w.net_name],
                "start_um": [w.start.x, w.start.y], "end_um": [w.end.x, w.end.y],
                "stroke_um": self.stroke_widths_um[i],
            } for i, (w, key) in enumerate(zip(
                self.graph.segments, self.wire_ids, strict=True
            ))],
            "junctions": [{
                "id": key, "net_id": net_by_name[owner], "point_um": [p.x, p.y],
            } for p, owner, key in zip(
                self.graph.junctions, self.junction_owners, self.junction_ids, strict=True
            )],
            "labels": [normalized(v) for v in self.labels],
            "scenario": None if self.scenario is None else {
                "name": self.scenario.name,
                "potentials": [{"net_name": p.net_name, "volts": str(p.volts),
                                "reference_id": p.reference_id}
                               for p in self.scenario.potentials],
            },
        }

    @property
    def canonical(self) -> bytes:
        return canonical_bytes(self.to_record())

    @property
    def revision(self) -> str:
        return digest(DOMAIN + self.canonical)

    @classmethod
    def from_record(cls, record: dict[str, Any], catalog: CatalogResolver) -> "SchematicProject":
        _keys(record, {"format_id", "schema_version", "project_id", "project_kind",
                       "title", "source_tag", "catalog_lock", "components", "nets",
                       "wires", "junctions", "labels", "scenario"})
        if record["format_id"] != FORMAT_ID or type(record["schema_version"]) is not int or (
            record["schema_version"] != VERSION or record["project_kind"] != "E3"
        ):
            raise ProjectError("SCHEMA_UNSUPPORTED", "Only E3 project schema 1 is supported")
        project_id = project_uuid(record["project_id"])
        locks = _list(record["catalog_lock"])
        parts, _symbols = catalog.verify(locks)
        components = []
        component_ids = []
        for row in _list(record["components"]):
            _keys(row, {"id", "reference", "part_id", "origin_um",
                        "rotation", "mirror_x", "nominal"})
            component_id = project_uuid(row["id"])
            part_id = _text(row["part_id"])
            if part_id not in parts:
                raise ProjectError("CATALOG_REVISION_MISMATCH", part_id)
            if type(row["mirror_x"]) is not bool:
                raise ProjectError("SCHEMA_UNSUPPORTED", "Mirror flag must be boolean")
            components.append(ComponentInstance(
                _text(row["reference"]), part_id, _point(row["origin_um"]),
                Transform(_integer(row["rotation"]), row["mirror_x"]),
                None if row["nominal"] is None else Quantity.from_record(row["nominal"]),
            ))
            component_ids.append(component_id)
        references = dict(zip(component_ids, (c.reference for c in components), strict=True))
        nets = []
        net_ids = []
        for row in _list(record["nets"]):
            _keys(row, {"id", "name", "members"})
            net_ids.append(project_uuid(row["id"]))
            pins = []
            for item in _list(row["members"]):
                _keys(item, {"component_id", "pin"})
                if item["component_id"] not in references:
                    raise ProjectError("PHYSICAL_PIN_INVALID", "Unknown member component ID")
                pins.append(PinRef(references[item["component_id"]], _text(item["pin"])))
            nets.append(Net(_text(row["name"]), tuple(pins)))
        names = dict(zip(net_ids, (n.name for n in nets), strict=True))
        wires, wire_ids, strokes = [], [], []
        for index, row in enumerate(_list(record["wires"])):
            _keys(row, {"id", "ordinal", "net_id", "start_um", "end_um", "stroke_um"})
            if _integer(row["ordinal"]) != index or row["net_id"] not in names:
                raise ProjectError("SCHEMA_UNSUPPORTED", "Invalid wire ordinal/net ID")
            wire_ids.append(project_uuid(row["id"]))
            wires.append(WireSegment(_point(row["start_um"]), _point(row["end_um"]),
                                     names[row["net_id"]]))
            strokes.append(_integer(row["stroke_um"]))
        junctions, junction_ids, junction_owners = [], [], []
        for row in _list(record["junctions"]):
            _keys(row, {"id", "net_id", "point_um"})
            if row["net_id"] not in names:
                raise ProjectError("JUNCTION_OWNER_AMBIGUOUS", "Unrecognized net ID")
            junction_ids.append(project_uuid(row["id"]))
            junction_owners.append(names[row["net_id"]])
            junctions.append(_point(row["point_um"]))
        labels = []
        for row in _list(record["labels"]):
            _keys(row, {"id", "component_id", "text", "at_um",
                        "font_family", "font_size_um"})
            project_uuid(row["id"])
            if row["component_id"] not in references:
                raise ProjectError("SCHEMA_UNSUPPORTED", "Label with unknown component ID")
            _point(row["at_um"])
            _text(row["text"])
            _text(row["font_family"])
            _integer(row["font_size_um"])
            labels.append(row)
        case = record["scenario"]
        scenario = None
        if case is not None:
            _keys(case, {"name", "potentials"})
            values = []
            for item in _list(case["potentials"]):
                _keys(item, {"net_name", "volts", "reference_id"})
                if type(item["volts"]) is not str:
                    raise ProjectError("SCHEMA_UNSUPPORTED", "Exact voltages must be strings")
                values.append(NetPotential.from_volts(
                    _text(item["net_name"]), item["volts"],
                    reference_id=_text(item["reference_id"])))
            scenario = PotentialScenario(_text(case["name"]), tuple(values))
        candidate = cls.from_circuit(
            project_id, _text(record["title"]), Circuit(tuple(components), tuple(nets)),
            ExternalWireGraph(tuple(wires), tuple(junctions)), catalog,
            strokes_um=tuple(strokes), scenario=scenario,
            source_tag=_text(record["source_tag"]),
        )
        # IDs are assigned at import, then persisted independently of refdes.
        # Future authorized rename/reposition must never regenerate UUIDs.
        assigned = (*component_ids, *net_ids, *wire_ids, *junction_ids,
                    *(row["id"] for row in labels))
        if len(assigned) != len(set(assigned)):
            raise ProjectError("PROJECT_CANONICAL_MISMATCH", "Duplicate persisted identity UUID")
        if (tuple(junction_owners) != candidate.junction_owners
                or tuple(locks) != tuple(normalized(v) for v in candidate.catalog_lock)):
            raise ProjectError("PROJECT_CANONICAL_MISMATCH", "Pinned catalog/junction owner differs")
        return cls(
            project_id, candidate.title, candidate.circuit, candidate.graph,
            candidate.catalog_lock, tuple(component_ids), tuple(net_ids),
            tuple(wire_ids), tuple(junction_ids), tuple(junction_owners),
            candidate.stroke_widths_um, tuple(labels), candidate.scenario,
            candidate.source_tag,
        )
