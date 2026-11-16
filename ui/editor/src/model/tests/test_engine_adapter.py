"""Regression tests against the REAL Python gost_schematic engine (no stub).

Run: PYTHONPATH=ui/editor/src/model pytest -q ui/editor/src/model/tests
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

from contract import ContractError, digest, source_inventory_hash, strict_loads
from engine_adapter import project_to_engine

from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.validation.external_wire_checks import ExternalWireGraph

FIX = ROOT / "ui" / "fixtures"


def fixture(name: str = "toy-v2.gscad.json") -> dict:
    return strict_loads((FIX / name).read_bytes())


def add_unconnected(doc: dict) -> tuple[dict, dict]:
    component = copy.deepcopy(doc["project"]["components"][0])
    component.update(id="unwired-c5", refdes="RT99", source_refdes="RT99")
    doc["project"]["components"].append(component)
    doc["project"]["provenance"]["expected_counts"]["components"] += 1
    instance = copy.deepcopy(doc["project"]["sheets"][0]["instances"][0])
    instance.update(id="unwired-instance", component_id=component["id"],
                    origin_um=[70000, 70000])
    doc["project"]["sheets"][0]["instances"].append(instance)
    return component, instance


def test_toy_exports_actual_native_types_without_changing_nets():
    document = fixture()
    old = copy.deepcopy(document)
    p = project_to_engine(document)
    assert document == old
    assert isinstance(p.circuit, Circuit)
    assert isinstance(p.sheets[0].graph, ExternalWireGraph)
    assert len(p.circuit.components) == 4
    assert len(p.circuit.nets) == 2
    assert len(p.sheets[0].graph.segments) == sum(
        len(w["segments"]) for w in document["project"]["sheets"][0]["wires"])
    assert not p.sheets[0].graph.junctions  # X crossing does not connect
    assert p.project_sha256 == digest(document)
    assert p.source_topology_hash == source_inventory_hash(document["project"])
    for source, native in zip(document["project"]["nets"], p.circuit.nets, strict=True):
        assert native.name == source["name"]
        assert all(isinstance(member, PinRef) for member in native.members)
        assert {(p.refdes_to_component_id[m.reference], m.number)
                for m in native.members} == {
                    (m["component_id"], m["physical_pin_number"]) for m in source["members"]}


def test_frozen_e695_has_original_23_15_62_16_and_two_nonconductive_b():
    doc = fixture("tl494-source-e695-v2.gscad.json")
    p = project_to_engine(doc)
    assert len(p.circuit.components) == 23
    assert len(p.circuit.nets) == 15
    assert sum(len(net.members) for net in p.circuit.nets) == 62
    assert sum(pin.reference == "DA1" for net in p.circuit.nets
               for pin in net.members) == 16
    assert sum(len(sh.source_b_graphic_ids) for sh in p.sheets) == 2
    assert sum(len(sh.graph.segments) for sh in p.sheets) == 0
    assert len(p.sheets[0].unfinished_net_ids) == 15
    assert not p.rendering_catalog_verified


def test_mutable_reference_rename_preserves_original_physical_net_ids():
    doc = fixture()
    first = project_to_engine(doc)
    component = doc["project"]["components"][0]
    old_name = component["refdes"]
    component["refdes"] = "RRENAME"
    updated = project_to_engine(doc)
    assert updated.component_id_to_refdes[component["id"]] == "RRENAME"
    assert updated.source_refdes_by_component_id[component["id"]] == old_name
    assert updated.source_topology_hash == first.source_topology_hash
    assert updated.project_sha256 != first.project_sha256
    assert sum(len(n.members) for n in updated.circuit.nets) == sum(
        len(n.members) for n in first.circuit.nets)


def test_exact_plus_one_um_and_rotation_of_unwired_symbol():
    doc = fixture()
    _, inst = add_unconnected(doc)
    inst["origin_um"][0] += 1
    inst["rotation_deg"] = 270
    p = project_to_engine(doc)
    native = next(item for item in p.circuit.components if item.reference == "RT99")
    assert native.origin.x == 70001
    assert native.transform.rotation == 270
    assert p.geometry_complete


def test_fake_physical_pin_is_rejected_before_projection():
    doc = fixture()
    doc["project"]["nets"][0]["members"][0]["physical_pin_number"] = "999"
    with pytest.raises(ContractError, match="INVALID_PINREF"):
        project_to_engine(doc)


def test_one_um_detached_wire_anchor_rejected_before_projection():
    doc = fixture()
    doc["project"]["sheets"][0]["wires"][0]["vertices"][0]["at_um"][0] += 1
    with pytest.raises(ContractError, match="PIN_ANCHOR_MISMATCH"):
        project_to_engine(doc)


def test_false_cross_dot_rejected_instead_of_joining_foreign_net():
    doc = fixture()
    doc["project"]["sheets"][0]["junctions"].append({
        "id": "fake-dot", "net_id": doc["project"]["nets"][0]["id"],
        "layer_id": "layer-electric", "at_um": [50000, 30000],
    })
    with pytest.raises(ContractError, match="JUNCTION_CROSSES_FOREIGN_NET"):
        project_to_engine(doc)


def test_coincident_free_terminal_is_not_silently_joined_by_legacy_graph():
    doc = fixture()
    sheet = doc["project"]["sheets"][0]
    first = sheet["wires"][0]
    a = copy.deepcopy(first["vertices"][0])
    b = copy.deepcopy(first["vertices"][-1])
    at = [40000, 30000]
    first["vertices"] = [a, {"id": "free-a", "at_um": at,
                              "anchor": {"kind": "free", "free_id": "free-a-id"}}]
    first["segments"] = [{"id": "seg-a", "from_vertex_id": a["id"],
                          "to_vertex_id": "free-a"}]
    other = copy.deepcopy(first)
    other["id"] = "second-half"
    other["vertices"] = [{"id": "free-b", "at_um": at,
                          "anchor": {"kind": "free", "free_id": "free-b-id"}}, b]
    other["segments"] = [{"id": "seg-b", "from_vertex_id": "free-b",
                          "to_vertex_id": b["id"]}]
    sheet["wires"].insert(1, other)
    doc["project"]["nets"][0]["route_status"] = "partial"
    with pytest.raises(ContractError, match="ENGINE_FREE_ENDPOINT_COLLISION"):
        project_to_engine(doc)


def test_parallel_collinear_overlapped_wires_denied():
    doc = fixture()
    sheet = doc["project"]["sheets"][0]
    extra = copy.deepcopy(sheet["wires"][0])
    extra["id"] = "parallel-overlap"
    for vertex in extra["vertices"]:
        vertex["id"] = "overlap-" + vertex["id"]
    for segment in extra["segments"]:
        segment["id"] = "overlap-" + segment["id"]
        segment["from_vertex_id"] = "overlap-" + segment["from_vertex_id"]
        segment["to_vertex_id"] = "overlap-" + segment["to_vertex_id"]
    sheet["wires"].append(extra)
    with pytest.raises(ContractError, match="ENGINE_SEGMENT_OVERLAP"):
        project_to_engine(doc)


def test_graphical_line_not_exported_as_conducting_wire():
    doc = fixture()
    sheet = doc["project"]["sheets"][0]
    sheet["graphics"].append({
        "id": "illustrative-line", "kind": "line", "layer_id": "layer-electric",
        "points_um": [[0, 0], [10000, 0]], "stroke_um": 300,
    })
    p = project_to_engine(doc)
    assert len(p.sheets[0].graph.segments) == sum(
        len(w["segments"]) for w in sheet["wires"])


def test_second_sheet_does_not_merge_same_coordinates():
    doc = fixture()
    second = copy.deepcopy(doc["project"]["sheets"][0])
    second.update(id="sheet-2", index=2, name="Sheet 2",
                  instances=[], wires=[], junctions=[], splices=[],
                  graphics=[], labels=[], texts=[])
    for layer in second["layers"]:
        layer["id"] = "s2-" + layer["id"]
    doc["project"]["sheets"].append(second)
    p = project_to_engine(doc)
    assert len(p.sheets) == 2
    assert len(p.sheets[1].graph.segments) == 0
    assert p.sheets[0].sheet_id != p.sheets[1].sheet_id


def test_netlist_only_missing_placement_not_export_ready():
    doc = fixture()
    component, instance = add_unconnected(doc)
    doc["project"]["sheets"][0]["instances"].remove(instance)
    with pytest.raises(ContractError, match="ENGINE_PLACEMENT_AMBIGUOUS"):
        project_to_engine(doc)
    obj = project_to_engine(doc, require_placed=False)
    assert obj.source_refdes_by_component_id[component["id"]] == "RT99"
    assert not obj.geometry_complete
    assert not obj.rendering_catalog_verified

def test_unconnected_symbol_pin_under_wire_cannot_become_implicit_contact():
    """Existing Python graph infers pin contact from ink; v2 does not."""
    doc = fixture()
    _, inst = add_unconnected(doc)
    # Extra R shares two physical pin points with an unrelated existing wire
    # but has NO source Net membership. This must not silently connect.
    inst["origin_um"] = [50000, 30000]
    with pytest.raises(ContractError, match="ENGINE_UNAUTHORED_PIN_CONTACT"):
        project_to_engine(doc)


def test_free_terminal_exactly_at_physical_pin_cannot_bind_implicitly():
    """Free is isolated even when precisely over the real circuit pin."""
    doc = fixture()
    wire = doc["project"]["sheets"][0]["wires"][0]
    last = wire["vertices"][-1]
    assert last["anchor"]["kind"] == "pin"
    last["anchor"] = {"kind": "free", "free_id": "unbound-on-real-pin"}
    doc["project"]["nets"][0]["route_status"] = "partial"
    with pytest.raises(ContractError, match="ENGINE_UNAUTHORED_PIN_CONTACT"):
        project_to_engine(doc)
