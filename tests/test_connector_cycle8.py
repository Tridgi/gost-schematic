"""Cycle 8 XP/XS contacts: actual isolated physical pins, D4 targets and SVG.

GOST 2.755-87 tab.5/1(1), tab.6/2–4. Geometry is DRAFT.
Abstract contact IDs 1..4 are NOT a manufacturer's package pinout.
"""

import itertools
import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_connectors_cycle8 import IDS, generate, pair
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Line, Point, Rectangle
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.connection_targets import connection_targets
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_symbol_catalog import audit_catalog

ROOT = Path(str(files("gost_schematic").joinpath("catalog")))
SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("identifier", IDS)
def test_source_gost_exact_scope_and_physical_gender(identifier):
    symbol, part = pair(identifier)
    assert part.identifier == part.symbol_id == symbol.identifier == identifier
    assert symbol.status == SymbolStatus.DRAFT
    assert part.reference_prefix == ("XP" if "plug" in identifier else "XS")
    assert any("ГОСТ 2.755-87" in source for source in symbol.standard_refs)
    assert any("EDITORIAL_ASSUMPTION" in source for source in symbol.standard_refs)
    assert any("NOT a manufacturer" in source for source in symbol.standard_refs)
    count = 4 if identifier.endswith("_4") else 1
    assert len(part.pins) == len(symbol.pins) == count
    assert tuple(pin.number for pin in part.pins) == tuple(str(i) for i in range(1, count + 1))
    assert all(pin.name == f"CONTACT_{pin.number}" for pin in part.pins)
    assert all(pin.label == pin.number for pin in symbol.pins)
    assert all(pin.electrical_type.value == "passive" for pin in part.pins)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == tuple((str(i),) for i in range(1, count + 1))
    assert trace.explicit_junctions == 0
    assert not symbol.constant_annotations


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_D4_physical_pinref_targets_are_identical_to_true_pin_endpoints(
    identifier, angle, mirror
):
    symbol, part = pair(identifier)
    inst = ComponentInstance(
        "XP19" if part.reference_prefix == "XP" else "XS19",
        part.identifier, Point(100000, 82000), Transform(rotation=angle, mirror_x=mirror)
    )
    targets = connection_targets(inst, part, symbol)
    positions = inst.pin_positions(symbol)
    assert len(targets) == len(part.pins)
    assert {item.pin_ref for item in targets} == {
        PinRef(inst.reference, p.number) for p in part.pins
    }
    assert {item.point for item in targets} == set(positions.values())
    for marker in targets:
        graphic = next(p for p in symbol.pins if p.number == marker.pin_ref.number)
        real = next(p for p in part.pins if p.number == marker.pin_ref.number)
        assert marker.point == positions[marker.pin_ref.number]
        assert marker.side == inst.transform.side(graphic.side)
        assert marker.physical_name == real.name
        assert marker.symbol_id == symbol.identifier


@pytest.mark.parametrize("identifier", IDS)
def test_connectors_own_real_circuit_nets_but_do_not_short_neighbor_contacts(identifier):
    symbol, part = pair(identifier)
    instance = ComponentInstance("XP8" if part.reference_prefix == "XP" else "XS8",
                                 part.identifier)
    circuit = Circuit((instance,), tuple(
        Net(f"ISOLATED_{pin.number}", (PinRef(instance.reference, pin.number),))
        for pin in part.pins
    ))
    errors = [d for d in validate_circuit(
        circuit, {part.identifier: part}, {symbol.identifier: symbol}
    ) if d.severity.value == "error"]
    assert not errors
    assert len(circuit.nets) == len(part.pins)
    # A visual connector row is NOT a semantic net between other rows.
    assert all(len(net.members) == 1 for net in circuit.nets)


@pytest.mark.parametrize("identifier", ("connector.plug_4", "connector.socket_4"))
def test_bad_bridge_between_two_connector_contacts_is_a_hard_error(identifier):
    symbol, _ = pair(identifier)
    bad = Line(symbol.pins[0].at, symbol.pins[1].at)
    corrupt = replace(
        symbol, graphics=(*symbol.graphics, bad),
        conductor_topology=replace(
            symbol.conductor_topology, conductor_indices=(
                *symbol.conductor_topology.conductor_indices, len(symbol.graphics)
            )
        )
    )
    errors = {d.code for d in inspect_conductor_topology(corrupt).diagnostics}
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in errors


def test_actual_mating_requires_explicit_net_and_wrong_pin_is_not_fabricated():
    xp_s, xp_p = pair("connector.plug_4")
    xs_s, xs_p = pair("connector.socket_4")
    xp, xs = ComponentInstance("XP1", xp_p.identifier), ComponentInstance("XS1",
                                                                          xs_p.identifier)
    open_connector = Circuit((xp, xs), ())
    connected = Circuit((xp, xs), tuple(
        Net(f"MATED_CONTACT_{i}", (PinRef("XP1", str(i)), PinRef("XS1", str(i))))
        for i in range(1, 5)
    ))
    for circuit in (open_connector, connected):
        assert not [d for d in validate_circuit(
            circuit, {xp_p.identifier: xp_p, xs_p.identifier: xs_p},
            {xp_s.identifier: xp_s, xs_s.identifier: xs_s},
        ) if d.severity.value == "error"]
    assert len(open_connector.nets) == 0
    assert len(connected.nets) == 4
    wrong = Circuit((xp, xs), (Net("PHANTOM", (PinRef("XP1", "5"),)),))
    diagnostics = validate_circuit(
        wrong, {xp_p.identifier: xp_p, xs_p.identifier: xs_p},
        {xp_s.identifier: xp_s, xs_s.identifier: xs_s}
    )
    assert "UNKNOWN_PIN" in {d.code for d in diagnostics}
    duplicate = Circuit((xp,), (Net("A", (PinRef("XP1", "1"),)),
                                  Net("B", (PinRef("XP1", "1"),))))
    assert "MULTIPLE_NET_OWNERSHIP" in {d.code for d in validate_circuit(
        duplicate, {xp_p.identifier: xp_p}, {xp_s.identifier: xp_s}
    )}


def test_connection_targets_use_physical_identity_not_a_fake_text_net():
    symbol, part = pair("connector.socket_4")
    inst = ComponentInstance("XS3", part.identifier)
    wrong_part = replace(part, identifier="not_a_real_connector")
    with pytest.raises(ValueError, match="identity mismatch"):
        connection_targets(inst, wrong_part, symbol)
    altered = replace(part, pins=part.pins[:-1])
    with pytest.raises(ValueError, match="inventory mismatch"):
        connection_targets(inst, altered, symbol)
    pins = symbol.pins
    with pytest.raises(ValueError, match="Duplicate graphic"):
        replace(symbol, pins=(replace(pins[0], at=pins[1].at), *pins[1:]))


def test_editor_targets_supported_for_old_discretes_without_ink_leak():
    # Generalize the contract to all preexisting static physical catalog entries,
    # not only new XP/XS or integrated circuits.
    for physical in sorted((ROOT / "parts").rglob("*.json")):
        relative = physical.relative_to(ROOT / "parts")
        symbol = load_symbol(ROOT / "symbols" / relative)
        part = load_part(physical)
        inst = ComponentInstance("S1", part.identifier, Point(20000, 20000))
        targets = connection_targets(inst, part, symbol)
        assert len(targets) == len(part.pins) == len(symbol.pins)
        assert len({x.point for x in targets}) == len(targets)
        root = ET.fromstring(render_symbol_svg(symbol))
        assert not root.findall(f".//{SVG}rect[@data-editor-target]")
        assert not root.findall(f".//{SVG}image")


@pytest.mark.parametrize("identifier", ("connector.plug_4", "connector.socket_4"))
def test_grouped_contacts_spacing_and_keepout_do_not_collide(identifier):
    symbol, _ = pair(identifier)
    assert len(symbol.pins) == 4
    ys = sorted(pin.at.y for pin in symbol.pins)
    assert all(b - a >= 8000 for a, b in itertools.pairwise(ys))
    # Four 2mm high contact shapes or V-forks separated by 8mm row pitch.
    rows = [g for g in symbol.graphics if isinstance(g, Rectangle)]
    if "plug_" in identifier:
        assert len(rows) == 4
        boxes = [g.box for g in rows]
        assert all(not a.overlaps(b) for i, a in enumerate(boxes)
                   for b in boxes[i + 1:])
    # Separate pin corridors cannot occupy identical physical endpoints.
    assert len({p.at for p in symbol.pins}) == 4


def test_full_catalog_preserves_36_old_and_adds_exact_4_draft_pairs():
    audit = audit_catalog()
    assert audit["total_symbols"] == 40
    assert audit["draft_count"] == 40
    assert audit["topologies_verified"] == 40
    assert audit["hard_errors"] == 0, audit["error_details"]
    assert not audit["without_physical_part"]
    entries = {e["id"] for e in audit["entries"]}
    assert set(IDS).issubset(entries)
    assert "resistor.variable" in entries
    assert "diode.schottky" in entries
    assert "transistor.bjt_npn" in entries
    assert "fuse.general" in entries


def test_review_gallery_is_clean_deterministic_and_has_green_squares_only_in_debug(tmp_path):
    first = generate(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in first["files"]}
    assert first["gallery_count"] == 4
    assert first["approved_count"] == 0
    assert len(first["files"]) == 10
    for filename in first["files"]:
        root = ET.fromstring((tmp_path / filename).read_bytes())
        diagnostic = filename.endswith("-diagnostic.svg")
        marks = root.findall(f".//{SVG}rect[@data-editor-target='true']")
        if diagnostic:
            assert marks
            assert {item.attrib["fill"] for item in marks} == {"#14a56d"}
        else:
            assert not marks
    assert generate(tmp_path) == first
    assert before == {name: (tmp_path / name).read_bytes() for name in first["files"]}
    manifest = json.loads((tmp_path / "cycle8-connectors-manifest.json").read_text())
    assert manifest == first
