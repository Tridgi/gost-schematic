"""Fail-closed adapter from gscad-project v2 into the existing Python E3 engine.

The signed Net/PinRef inventory comes only from ProjectFileV2; artwork and
pixel proximity never create electrical connections. This adapter does not
claim GOST approval, full routing, or a validated manufacturer catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from contract import ContractError, digest, source_inventory_hash, validate
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment


@dataclass(frozen=True, slots=True)
class EngineSheetProjection:
    sheet_id: str
    sheet_index: int
    graph: ExternalWireGraph
    authored_segments: tuple[tuple[str, str], ...]
    source_b_graphic_ids: tuple[str, ...]
    unfinished_net_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineProjectProjection:
    circuit: Circuit
    sheets: tuple[EngineSheetProjection, ...]
    component_id_to_refdes: Mapping[str, str]
    refdes_to_component_id: Mapping[str, str]
    net_id_to_name: Mapping[str, str]
    source_refdes_by_component_id: Mapping[str, str]
    unparsed_values_by_component_id: Mapping[str, str]
    project_sha256: str
    source_topology_hash: str
    geometry_complete: bool
    rendering_catalog_verified: bool = False


def _point(value: list[int]) -> Point:
    return Point(value[0], value[1])


def _positive_overlap(first: tuple[Point, Point], second: tuple[Point, Point]) -> bool:
    """The legacy ExternalWireGraph implicitly joins collinear positive overlap."""
    p, q = first
    r, s = second
    if (
        (q.x - p.x) * (r.y - p.y) != (q.y - p.y) * (r.x - p.x)
        or (q.x - p.x) * (s.y - p.y) != (q.y - p.y) * (s.x - p.x)
    ):
        return False
    if p.x != q.x:
        return max(min(p.x, q.x), min(r.x, s.x)) < min(max(p.x, q.x), max(r.x, s.x))
    return max(min(p.y, q.y), min(r.y, s.y)) < min(max(p.y, q.y), max(r.y, s.y))


def _ensure_legacy_graph_compatible(sheet: dict) -> None:
    """Deny geometry whose projection would accidentally merge graph islands.

    Project v2 Free terminals remain isolated even if they coincide. Legacy
    ExternalWireGraph, by contrast, joins coincident authored wire endpoints
    and overlapping collinear wire segments. Reject these lossy cases.
    """
    endpoints: dict[tuple[int, int], list[tuple[str, str, str]]] = {}
    segments: list[tuple[str, tuple[Point, Point]]] = []
    for wire in sheet["wires"]:
        for vertex in (wire["vertices"][0], wire["vertices"][-1]):
            xy = tuple(vertex["at_um"])
            anchor = vertex["anchor"]
            endpoints.setdefault(xy, []).append((wire["id"], wire["net_id"], anchor["kind"]))
        vertices = {item["id"]: item for item in wire["vertices"]}
        for edge in wire["segments"]:
            a = vertices[edge["from_vertex_id"]]
            b = vertices[edge["to_vertex_id"]]
            segments.append((wire["id"], (_point(a["at_um"]), _point(b["at_um"]))))
    for xy, contacts in endpoints.items():
        if len({item[0] for item in contacts}) <= 1:
            continue
        if any(item[2] == "free" for item in contacts):
            raise ContractError("ENGINE_FREE_ENDPOINT_COLLISION", f'{sheet["id"]}:{xy}')
        if len({item[1] for item in contacts}) > 1:
            raise ContractError("ENGINE_FOREIGN_ENDPOINT_COLLISION", f'{sheet["id"]}:{xy}')
    for index, (first_id, first) in enumerate(segments):
        for second_id, second in segments[index + 1:]:
            if first_id != second_id and _positive_overlap(first, second):
                raise ContractError("ENGINE_SEGMENT_OVERLAP",
                                    f'{sheet["id"]}:{first_id}/{second_id}')


def project_to_engine(document: dict, *, require_placed: bool = True) -> EngineProjectProjection:
    """Project exact source data to existing E3 types without mutating document.

    Component IDs map bijectively to mutable refdes for the legacy Circuit.
    Source refdes are preserved independently. Missing placements are allowed
    only for a netlist-only projection; that result is NEVER render-ready.
    Multi-unit symbols are not representable by old ComponentInstance and
    therefore fail closed instead of selecting an arbitrary placement.
    """
    validate(document)
    project = document["project"]
    components = project["components"]
    ids_to_current = {item["id"]: item["refdes"] for item in components}
    current_to_ids = {value: key for key, value in ids_to_current.items()}
    net_names = {item["id"]: item["name"] for item in project["nets"]}
    placements: dict[str, list[dict]] = {}
    for sheet in project["sheets"]:
        for instance in sheet["instances"]:
            placements.setdefault(instance["component_id"], []).append(instance)
    if require_placed:
        for component in components:
            count = len(placements.get(component["id"], ()))
            if count != 1:
                raise ContractError("ENGINE_PLACEMENT_AMBIGUOUS",
                                    f'{component["source_refdes"]}: {count} placements')

    native_components: list[ComponentInstance] = []
    for component in components:
        items = placements.get(component["id"], ())
        if len(items) > 1:
            raise ContractError("ENGINE_MULTIUNIT_UNSUPPORTED", component["refdes"])
        if items:
            instance = items[0]
            origin = _point(instance["origin_um"])
            transform = Transform(rotation=instance["rotation_deg"],
                                  mirror_x=instance["mirror_x"])
        else:
            # Explicit netlist-only mode, never used for geometry export.
            origin, transform = Point(0, 0), Transform()
        native_components.append(ComponentInstance(
            reference=component["refdes"], part_id=component["part_id"],
            origin=origin, transform=transform,
        ))
    native_nets = tuple(
        Net(name=net["name"], members=tuple(
            PinRef(ids_to_current[pref["component_id"]], pref["physical_pin_number"])
            for pref in net["members"]
        ))
        for net in project["nets"]
    )

    native_sheets = []
    for sheet in project["sheets"]:
        _ensure_legacy_graph_compatible(sheet)
        segments: list[WireSegment] = []
        provenance: list[tuple[str, str]] = []
        for wire in sheet["wires"]:
            vertices = {vertex["id"]: vertex for vertex in wire["vertices"]}
            for segment in wire["segments"]:
                segments.append(WireSegment(
                    start=_point(vertices[segment["from_vertex_id"]]["at_um"]),
                    end=_point(vertices[segment["to_vertex_id"]]["at_um"]),
                    net_name=net_names[wire["net_id"]],
                ))
                provenance.append((wire["id"], segment["id"]))
        # Splice degree=2 is invisible. Only authored Junction produces a dot.
        # Decorative source-b/label/graphics never become conducting wires.
        graph = ExternalWireGraph(
            segments=tuple(segments),
            junctions=tuple(_point(j["at_um"]) for j in sheet["junctions"]),
        )
        native_sheets.append(EngineSheetProjection(
            sheet_id=sheet["id"], sheet_index=sheet["index"],
            graph=graph, authored_segments=tuple(provenance),
            source_b_graphic_ids=tuple(
                graphic["id"] for graphic in sheet["graphics"]
                if graphic["kind"] == "source_b_continuation"
            ),
            unfinished_net_ids=tuple(net["id"] for net in project["nets"]
                                     if net["route_status"] != "verified"),
        ))

    return EngineProjectProjection(
        circuit=Circuit(tuple(native_components), native_nets),
        sheets=tuple(native_sheets),
        component_id_to_refdes=MappingProxyType(ids_to_current),
        refdes_to_component_id=MappingProxyType(current_to_ids),
        net_id_to_name=MappingProxyType(net_names),
        source_refdes_by_component_id=MappingProxyType(
            {item["id"]: item["source_refdes"] for item in components}),
        unparsed_values_by_component_id=MappingProxyType(
            {item["id"]: item["value"] for item in components}),
        project_sha256=digest(document),
        source_topology_hash=source_inventory_hash(project),
        geometry_complete=all(len(placements.get(item["id"], ())) == 1
                              for item in components),
    )
