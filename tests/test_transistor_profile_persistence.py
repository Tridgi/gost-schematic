"""S4.6a: exact profile resolution, immutable locks and cold project reopen."""
import copy

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.contracts import SchematicProject
from gost_schematic.agent_project.service import ProjectService
from gost_schematic.catalog.transistor_profiles import transistor_profiles
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

PID = "77777777-7777-4777-8777-777777777777"
KEY = "88888888-8888-4888-8888-888888888888"
BJT = "transistor.bjt_npn.layout_hh.bare"
MOS = "transistor.mosfet_n_enh.body_diode.layout_vv.bare"
BODY = "transistor.mosfet_p_dep.body4.layout_hh.case"


def test_registry_resolves_all_profiles_without_polluting_installed_inventory():
    catalog = CatalogResolver()
    ids = catalog.transistor_layout_ids()
    assert len(ids) == len(set(ids)) == 112
    assert not set(ids).intersection(catalog.parts)
    assert not set(ids).intersection(catalog.symbols)
    installed = tuple(catalog.parts)
    for identifier in ids:
        part, symbol = catalog.resolve(identifier)
        assert (part, symbol) == transistor_profiles()[identifier]
        assert part.identifier == symbol.identifier == identifier
        assert symbol.status.value == "draft"
        assert catalog.lock(identifier) == CatalogResolver().lock(identifier)
    assert tuple(catalog.parts) == installed
    with pytest.raises(TypeError):
        transistor_profiles()[BJT] = transistor_profiles()[MOS]


@pytest.mark.parametrize("identifier", (
    "transistor.bjt_npn.layout_xx.bare",
    "transistor.mosfet_n_dep.body_diode.layout_vv.bare",
    "transistor.igbt_p.layout_vv.case",
    "transistor../catalog/transistors",
))
def test_unknown_or_unsupported_profile_fails_closed(identifier):
    with pytest.raises(ProjectError, match="CATALOG_PART_MISSING"):
        CatalogResolver().resolve(identifier)


def test_all_profiles_roundtrip_exact_locks_and_transformed_pins():
    catalog = CatalogResolver()
    components = tuple(
        ComponentInstance(f"VT{i}", identifier, Point(i * 50000, 0), Transform(90, True))
        for i, identifier in enumerate(catalog.transistor_layout_ids(), start=1)
    )
    project = SchematicProject.from_circuit(
        PID, "All transistor layouts", Circuit(components, ()),
        ExternalWireGraph((), ()), catalog, strokes_um=(),
    )
    restored = SchematicProject.from_record(project.to_record(), CatalogResolver())
    assert restored.canonical == project.canonical
    assert restored.revision == project.revision
    for component in restored.circuit.components:
        _, symbol = catalog.resolve(component.part_id)
        _, reopened = CatalogResolver().resolve(component.part_id)
        assert component.pin_positions(symbol) == component.pin_positions(reopened)


def test_tampered_geometry_hash_or_layout_identity_is_rejected():
    catalog = CatalogResolver()
    locks = [catalog.lock(BODY)]
    for key, value in (
        ("symbol_sha256", "0" * 64),
        ("part_id", BJT),
        ("symbol_revision", 999),
    ):
        changed = copy.deepcopy(locks)
        changed[0][key] = value
        with pytest.raises(ProjectError, match="CATALOG_REVISION_MISMATCH"):
            catalog.verify(changed)


def test_legacy_and_parametric_definitions_do_not_alias():
    catalog = CatalogResolver()
    old_part, old_symbol = catalog.resolve("transistor.bjt_npn")
    new_part, new_symbol = catalog.resolve(BJT)
    assert old_part.pins == new_part.pins
    assert old_symbol.identifier != new_symbol.identifier
    assert catalog.lock(old_part.identifier) != catalog.lock(new_part.identifier)
    assert catalog.symbols[old_symbol.identifier] == old_symbol


def test_cold_store_reopen_and_real_render_with_connected_transistors(tmp_path):
    service = ProjectService.for_workspace(tmp_path)
    _, bjt = service.catalog.resolve(BJT)
    _, mos = service.catalog.resolve(MOS)
    first = ComponentInstance("VT1", BJT, Point(30000, 30000))
    second = ComponentInstance("VT2", MOS, Point(80000, 23000))
    # BJT collector y=-4 mm, MOS gate y=+3 mm: align the endpoints.
    a = first.pin_positions(bjt)["2"]
    b = second.pin_positions(mos)["1"]
    assert a.y == b.y and a.x < b.x
    circuit = Circuit((first, second), (
        Net("CONTROL", (PinRef("VT1", "2"), PinRef("VT2", "1"))),
    ))
    graph = ExternalWireGraph((WireSegment(a, b, "CONTROL"),), ())
    saved = service.import_circuit(
        circuit, graph, project_id=PID, idempotency_key=KEY,
        title="Parametric transistor connection", strokes_um=(300,),
    )
    cold = ProjectService.for_workspace(tmp_path)
    restored = cold.open_project(PID)
    assert restored.project.canonical == saved.project.canonical
    assert restored.project.revision == saved.project.revision
    assert restored.project.graph.segments == (WireSegment(a, b, "CONTROL"),)
    assert not any(d["severity"] == "error" for d in cold.validate_project(PID)["diagnostics"])
    for mode in ("clean", "diagnostic"):
        image = cold.render_project(PID, restored.project.revision, mode=mode)
        assert image.png.startswith(b"\x89PNG\r\n\x1a\n")
        assert image.metadata["project_revision"] == saved.project.revision
        assert "VT1" in image.svg and "VT2" in image.svg
