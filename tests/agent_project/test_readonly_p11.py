"""P1.1 real model -> immutable store -> cold load -> renderer/diagnostics."""
import copy
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from gost_schematic.agent_project import CatalogResolver, ProjectError, ProjectService
from gost_schematic.agent_project.contracts import SchematicProject
from gost_schematic.agent_project.trusted_import import import_six_part
from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import ExternalWireGraph

PID = "11111111-1111-4111-8111-111111111111"
KEY = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def saved(tmp_path: Path):
    workspace = tmp_path / "allowed"
    imported = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    return workspace, imported


def _service(workspace: Path) -> ProjectService:
    return ProjectService.for_workspace(workspace)


def test_real_roundtrip_source_fields_pinrefs_and_catalog(saved):
    workspace, created = saved
    from examples.review_end_to_end_circuit import definitions, renderer_wires, scenarios

    original = next(item for item in scenarios() if item.identifier == "valid")
    snapshot = _service(workspace).open_project(PID)
    project = snapshot.project
    assert (snapshot.head.revision, snapshot.head.generation) == (created.head.revision, 1)
    assert project.circuit == original.circuit
    assert project.graph == original.graph
    assert project.scenario == original.scenario
    assert [lock["part_id"] for lock in project.catalog_lock] == sorted({
        c.part_id for c in original.circuit.components
    })
    assert project.stroke_widths_um == tuple(w.stroke_um for w in renderer_wires(original.graph))
    assert len(project.component_ids) == 6
    assert len(project.net_ids) == 5
    assert len(project.wire_ids) == 16
    assert len(project.junction_ids) == 3
    assert len(set(project.component_ids + project.net_ids +
                   project.wire_ids + project.junction_ids)) == 30
    assert project.to_record() == created.project.to_record()
    parts, symbols = definitions()
    c3 = next(c for c in project.circuit.components if c.reference == "C3")
    assert c3.part_id == "capacitor.electrolytic"
    assert {key: (p.x, p.y) for key, p in c3.pin_positions(
        symbols[parts[c3.part_id].symbol_id]
    ).items()} == {"1": (91000, 80000), "2": (109000, 80000)}
    nets = {n.name: {(p.reference, p.number) for p in n.members}
            for n in project.circuit.nets}
    assert ("C3", "1") in nets["TOP"] and ("C3", "2") in nets["RIGHT"]
    assert [p.name for p in parts[c3.part_id].pins] == ["PLUS", "MINUS"]


def test_cold_process_open_rehydrate_validate_and_render_without_examples(saved, tmp_path):
    workspace, imported = saved
    code = """
import builtins, json, sys
original = builtins.__import__
def forbid(name, *args, **kwargs):
    if name == 'examples' or name.startswith('examples.'):
        raise AssertionError('Cold open must not import authored Python fixture')
    return original(name, *args, **kwargs)
builtins.__import__ = forbid
from gost_schematic.agent_project import ProjectService
service = ProjectService.for_workspace(__import__('pathlib').Path(sys.argv[1]))
snapshot = service.open_project(sys.argv[2], sys.argv[3])
report = service.validate_project(sys.argv[2], sys.argv[3])
overview = service.render_project(sys.argv[2], sys.argv[3])
crop = service.render_project(sys.argv[2], sys.argv[3], reference='C3')
assert len(snapshot.project.circuit.components) == 6
assert len(snapshot.project.graph.segments) == 16
assert len(snapshot.project.graph.junctions) == 3
assert report['project_revision'] == overview.metadata['project_revision']
assert crop.metadata['project_revision'] == sys.argv[3]
assert overview.png[:8] == b'\\x89PNG\\r\\n\\x1a\\n'
print(json.dumps({'revision': sys.argv[3], 'status': report['status'],
  'svg': overview.metadata['view_svg_sha256'],
  'png': overview.metadata['png_sha256'],
  'crop': crop.metadata['png_sha256'], 'num_wires': len(snapshot.project.graph.segments)}))
"""
    result = subprocess.run([sys.executable, "-c", code, str(workspace), PID,
                             imported.head.revision], cwd=tmp_path, check=True,
                            capture_output=True, text=True, timeout=30)
    assert json.loads(result.stdout)["num_wires"] == 16


def test_validation_and_visual_repeat_are_revision_bound(saved):
    workspace, imported = saved
    service = _service(workspace)
    first = service.render_project(PID, imported.head.revision)
    second = service.render_project(PID, imported.head.revision)
    c3 = service.render_project(PID, imported.head.revision, reference="C3")
    assert first.svg == second.svg and first.png == second.png
    assert first.metadata == second.metadata
    assert first.metadata["png_sha256"] != c3.metadata["png_sha256"]
    assert first.metadata["project_revision"] == c3.metadata["project_revision"]
    assert first.metadata["diagnostics_revision"] == imported.head.revision
    assert "data-layer=\"wires\"" in first.svg
    assert first.svg.count('data-kind="authored-junction"') == 3
    assert first.png.startswith(b"\x89PNG\r\n\x1a\n")
    report = service.validate_project(PID, imported.head.revision)
    assert report["status"] == "WARN"
    assert len(report["diagnostics"]) == 6
    assert all(d["code"] == "UNAPPROVED_SYMBOL" for d in report["diagnostics"])
    assert report["labels_check_status"] == "NOT_IMPLEMENTED"


def test_durable_idempotency_replay_and_conflicts(saved):
    workspace, first = saved
    from examples.review_end_to_end_circuit import renderer_wires, scenarios

    case = scenarios()[0]
    service = _service(workspace)
    replay = service.import_circuit(
        case.circuit, case.graph, project_id=PID, idempotency_key=KEY,
        title="Six-part authored E3 specimen", scenario=case.scenario,
        strokes_um=tuple(w.stroke_um for w in renderer_wires(case.graph)),
        source_tag="fixed-six-part-model-v1",
    )
    assert replay.head == first.head
    assert _service(workspace).open_project(PID).head.generation == 1
    with pytest.raises(ProjectError, match="IDEMPOTENCY_CONFLICT"):
        service.import_circuit(
            case.circuit, case.graph, project_id=PID, idempotency_key=KEY,
            title="Different content", scenario=case.scenario,
            strokes_um=tuple(w.stroke_um for w in renderer_wires(case.graph)),
        )
    with pytest.raises(ProjectError, match="PROJECT_ALREADY_EXISTS"):
        service.import_circuit(
            case.circuit, case.graph, project_id=PID,
            idempotency_key=str(uuid.uuid4()),
            title="Six-part authored E3 specimen", scenario=case.scenario,
            strokes_um=tuple(w.stroke_um for w in renderer_wires(case.graph)),
        )


def test_invalid_uuid_and_storage_corruption_fail_closed(saved, tmp_path):
    workspace, snapshot = saved
    service = _service(workspace)
    for bad in ("../../outside", "C:\\temp\\secret", "not-uuid", "AAA"):
        with pytest.raises(ProjectError, match="INVALID_PROJECT_ID"):
            service.open_project(bad)
    directory = workspace / "projects" / PID / "revisions"
    file = directory / (snapshot.head.revision + ".gseproj")
    original = file.read_bytes()
    file.write_bytes(original.replace(b'"E3"', b'"E1"', 1))
    with pytest.raises(ProjectError, match="STORAGE_CORRUPT"):
        service.open_project(PID)
    file.write_bytes(original)
    assert service.open_project(PID).head == snapshot.head
    with pytest.raises(ProjectError, match="REVISION_NOT_FOUND"):
        service.open_project(PID, "0" * 64)


def test_catalog_pin_lock_and_unknown_physical_contact_rejected(saved):
    _, snapshot = saved
    source = snapshot.project.to_record()
    changed = copy.deepcopy(source)
    changed["catalog_lock"][0]["physical_pins"][0]["name"] = "INJECTED"
    with pytest.raises(ProjectError, match="CATALOG_REVISION_MISMATCH"):
        SchematicProject.from_record(changed, CatalogResolver())
    changed = copy.deepcopy(source)
    changed["nets"][0]["members"][0]["pin"] = "999"
    with pytest.raises(ProjectError, match="PHYSICAL_PIN_INVALID"):
        SchematicProject.from_record(changed, CatalogResolver())
    changed = copy.deepcopy(source)
    changed["project_kind"] = "E1"
    with pytest.raises(ProjectError, match="SCHEMA_UNSUPPORTED"):
        SchematicProject.from_record(changed, CatalogResolver())


def test_import_invalid_junction_no_published_head(tmp_path):
    from examples.review_end_to_end_circuit import scenarios

    case = scenarios()[0]
    bad_graph = ExternalWireGraph(
        case.graph.segments, (*case.graph.junctions, Point(40000, 60000))
    )
    service = _service(tmp_path)
    with pytest.raises(ProjectError, match="JUNCTION_OWNER_AMBIGUOUS"):
        service.import_circuit(
            case.circuit, bad_graph, project_id=PID, idempotency_key=KEY,
            title="Invalid junction", strokes_um=(300,) * 16,
        )
    assert not (tmp_path / "projects" / PID).exists()


def test_40_real_physical_pin_records_supported_without_fake_connectivity():
    catalog = CatalogResolver()
    physical = tuple(PhysicalPin(str(i), f"PIN{i}", ElectricalType.INPUT)
                     for i in range(1, 41))
    graphic = tuple(GraphicPin(str(i), Point(0, i * 1000), Side.LEFT)
                    for i in range(1, 41))
    part = PartDefinition("test.40pin", "DD", "test.40pin", physical)
    symbol = SymbolDefinition(
        "test.40pin", 1, (Line(Point(0, 1000), Point(1000, 1000)),),
        graphic, Box(1000, 0, 5000, 43000), 300,
    )
    catalog.parts[part.identifier] = part
    catalog.symbols[symbol.identifier] = symbol
    circuit = Circuit((ComponentInstance("DD1", part.identifier, Point(20000, 20000)),), ())
    project = SchematicProject.from_circuit(
        PID, "A typed 40 pin E3 fixture", circuit, ExternalWireGraph(()),
        catalog, strokes_um=(),
    )
    pins = project.catalog_lock[0]["physical_pins"]
    assert len(pins) == 40
    assert pins[39]["number"] == "40"
    assert pins[39]["name"] == "PIN40"
    restored = SchematicProject.from_record(project.to_record(), catalog)
    assert restored.circuit == circuit
    assert restored.revision == project.revision


def test_missing_stroke_provenance_rejected_without_save(tmp_path):
    from examples.review_end_to_end_circuit import scenarios

    case = scenarios()[0]
    service = _service(tmp_path)
    with pytest.raises(ProjectError, match="STROKE_PROVENANCE_MISSING"):
        service.import_circuit(
            case.circuit, case.graph, project_id=PID, idempotency_key=KEY,
            title="bad", strokes_um=(),
        )
    assert not (tmp_path / "projects" / PID).exists()
