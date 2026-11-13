"""Cycle 7 E3 semiconductor regression: 12 source-traced DRAFT visual variants.

Pin numbers are abstract schematic terminal IDs, NOT manufacturer package pinouts.
No NPN three-pin template is claimed to be ГОСТ 2.730 tab 7 pos 1б:
that row explicitly adds an internal shield terminal.
"""

import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_electronic_cycle7_extended import (
    DIODES,
    FIRST_IDS,
    IDS,
    TRANSISTORS,
    generate,
)
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_symbol_catalog import audit_catalog

ROOT = Path(str(files("gost_schematic").joinpath("catalog")))
FOLDERS = {"transistor": "transistors", "diode": "diodes"}
SVG = "{http://www.w3.org/2000/svg}"


def _pair(identifier):
    family, kind = identifier.split(".", 1)
    relative = FOLDERS[family] + "/" + kind.replace(".with_case", "_with_case") + ".json"
    return (
        load_symbol(ROOT / "symbols" / relative),
        load_part(ROOT / "parts" / relative),
    )


def _roles(identifier):
    if identifier.startswith("diode."):
        return ("A", "K")
    if ".bjt_" in identifier:
        return ("B", "C", "E")
    return ("G", "D", "S")


@pytest.mark.parametrize("identifier", TRANSISTORS + DIODES)
def test_real_symbol_part_canonical_roles_separate_pin_identity_and_status(identifier):
    symbol, part = _pair(identifier)
    assert symbol.identifier == part.identifier == part.symbol_id == identifier
    assert part.reference_prefix == ("VD" if identifier.startswith("diode.") else "VT")
    assert part.nominal_kind is None
    assert symbol.status == SymbolStatus.DRAFT
    assert symbol.line_width_um == 300
    assert tuple(pin.name for pin in part.pins) == _roles(identifier)
    assert tuple(pin.label for pin in symbol.pins) == _roles(identifier)
    assert tuple(pin.number for pin in symbol.pins) == tuple(
        str(i) for i in range(1, len(part.pins) + 1)
    )
    assert tuple(pin.number for pin in part.pins) == tuple(
        pin.number for pin in symbol.pins
    )
    assert all(pin.polarity.value == "none" for pin in part.pins)
    assert all(pin.electrical_type.value == "passive" for pin in part.pins)
    assert all(pin.function.value == "general" for pin in part.pins)
    assert len(symbol.standard_refs) >= 3
    assert any("ГОСТ 2.730-73" in text for text in symbol.standard_refs)
    assert any("EDITORIAL_ASSUMPTION" in text for text in symbol.standard_refs)
    assert not [d.code for d in validate_symbol(symbol) if d.severity.value == "error"]
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.explicit_junctions == 0
    assert trace.pin_islands == tuple((str(n),) for n in range(1, len(part.pins) + 1))
    assert symbol.stroked_bounds.min_x < symbol.bounds.min_x
    assert symbol.stroked_bounds.max_x > symbol.bounds.max_x


@pytest.mark.parametrize("identifier", TRANSISTORS + DIODES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_D4_views_preserve_real_ports_semantics_and_not_junctions(identifier, angle, mirror):
    symbol, part = _pair(identifier)
    transform = Transform(rotation=angle, mirror_x=mirror)
    instance = ComponentInstance(
        ("VT17" if identifier.startswith("transistor") else "VD17"),
        part.identifier, Point(95000, 85000), transform,
    )
    places = instance.pin_positions(symbol)
    assert tuple(places) == tuple(pin.number for pin in part.pins)
    assert len(set(places.values())) == len(part.pins)
    assert tuple(places[pin.number] for pin in symbol.pins) == tuple(
        transform.apply(pin.at) + instance.origin for pin in symbol.pins
    )
    corridors = pin_corridors_for_component(symbol, instance)
    assert tuple(c.pin.number for c in corridors) == tuple(places)
    assert tuple(c.side for c in corridors) == tuple(
        transform.side(p.side) for p in symbol.pins
    )
    assert inspect_conductor_topology(symbol).valid
    for number, role in enumerate(_roles(identifier), start=1):
        assert part.pins[number - 1].name == role


@pytest.mark.parametrize("identifier", TRANSISTORS + DIODES)
def test_independent_real_Circuit_Nets_do_not_infer_short_from_symbol_ink(identifier):
    symbol, part = _pair(identifier)
    ref = "VD2" if identifier.startswith("diode") else "VT3"
    component = ComponentInstance(ref, identifier)
    netlist = Circuit((component,), tuple(
        Net(f"NET_{pin.number}", (PinRef(ref, pin.number),))
        for pin in part.pins
    ))
    diagnostics = validate_circuit(
        netlist, {identifier: part}, {identifier: symbol}
    )
    assert not [d.code for d in diagnostics if d.severity.value == "error"]
    assert len(netlist.nets) == len(symbol.pins)
    assert not any(len(net.members) != 1 for net in netlist.nets)


@pytest.mark.parametrize("identifier", TRANSISTORS + DIODES)
def test_fabricated_conductive_cross_body_shunt_is_hard_failure(identifier):
    symbol, _ = _pair(identifier)
    false_bridge = Line(symbol.pins[0].at, symbol.pins[1].at)
    mutated = replace(
        symbol,
        graphics=(*symbol.graphics, false_bridge),
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=(*symbol.conductor_topology.conductor_indices,
                               len(symbol.graphics)),
        ),
    )
    diagnostics = inspect_conductor_topology(mutated).diagnostics
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {x.code for x in diagnostics}


@pytest.mark.parametrize("family", ("bjt_pnp", "bjt_npn", "mosfet_n_enh", "mosfet_p_enh"))
def test_case_is_exactly_one_optional_nonconductive_circle_not_an_extra_pin(family):
    plain, plain_part = _pair("transistor." + family)
    enclosed, enclosed_part = _pair("transistor." + family + ".with_case")
    assert len(plain.pins) == len(enclosed.pins) == 3
    assert plain.pins == enclosed.pins
    assert tuple(p.name for p in plain_part.pins) == tuple(
        p.name for p in enclosed_part.pins
    )
    assert all(not isinstance(g, Circle) for g in plain.graphics)
    assert len([g for g in enclosed.graphics if isinstance(g, Circle)]) == 1
    assert enclosed.graphics[:-1] == plain.graphics
    assert enclosed.conductor_topology == plain.conductor_topology
    assert "with_case" in enclosed.identifier
    assert not any("SOT-" in source for source in enclosed.standard_refs)


@pytest.mark.parametrize("npn", (False, True))
@pytest.mark.parametrize("with_case", (False, True))
def test_bjt_emitter_arrow_correct_physical_direction_without_screen_pin(npn, with_case):
    identifier = "transistor.bjt_npn" if npn else "transistor.bjt_pnp"
    if with_case:
        identifier += ".with_case"
    symbol, part = _pair(identifier)
    assert len(symbol.pins) == 3 and _roles(identifier) == ("B", "C", "E")
    assert symbol.graphics[2] == Line(Point(-2000, 2000), Point(9000, 10000))
    marker = symbol.graphics[4]
    assert isinstance(marker, Line)
    emitter = symbol.graphics[2]
    dx = marker.end.x - marker.start.x
    dy = marker.end.y - marker.start.y
    # Arrow along the E ray: outward NPN / toward the base PNP.
    alignment = dx * (emitter.end.x - emitter.start.x) + dy * (
        emitter.end.y - emitter.start.y
    )
    assert alignment > 0 if npn else alignment < 0
    assert set(symbol.conductor_topology.conductor_indices) == {0, 1, 2}
    assert part.pins[0].name == "B"
    if npn:
        assert any("EXPERIMENTAL_DERIVED_NOT_SOURCE_FIGURE" in item
                   for item in symbol.standard_refs)


@pytest.mark.parametrize("n_channel", (True, False))
@pytest.mark.parametrize("with_case", (False, True))
def test_mos_gate_is_separated_from_broken_enhancement_channel(n_channel, with_case):
    identifier = "transistor.mosfet_n_enh" if n_channel else "transistor.mosfet_p_enh"
    if with_case:
        identifier += ".with_case"
    symbol, part = _pair(identifier)
    assert tuple(p.name for p in part.pins) == ("G", "D", "S")
    assert symbol.graphics[0] == Line(Point(-11000, 0), Point(-4000, 0))
    assert symbol.graphics[3] == Line(Point(-4000, -3000), Point(-4000, 3000))
    assert symbol.graphics[4] == Line(Point(0, -5000), Point(0, -1000))
    assert symbol.graphics[5] == Line(Point(0, 1000), Point(0, 5000))
    assert abs(symbol.graphics[3].start.x - symbol.graphics[4].start.x) >= 4000
    arrow = symbol.graphics[6]
    assert arrow.end.x < arrow.start.x if n_channel else arrow.end.x > arrow.start.x
    assert symbol.conductor_topology.conductor_indices == (0, 1, 2)


@pytest.mark.parametrize("identifier", ("diode.led", "diode.photodiode"))
def test_optical_arrowheads_have_NO_conductor_or_extra_contact(identifier):
    symbol, part = _pair(identifier)
    assert len(symbol.pins) == len(part.pins) == 2
    assert tuple(p.name for p in part.pins) == ("A", "K")
    assert len(symbol.graphics) == 12
    assert symbol.conductor_topology.conductor_indices == (0, 1)
    arrow = symbol.graphics[6]
    assert isinstance(arrow, Line)
    if identifier == "diode.led":
        assert arrow.end.x > arrow.start.x and arrow.end.y < arrow.start.y
    else:
        assert arrow.end.x > arrow.start.x and arrow.end.y > arrow.start.y
    # Negative: declaring a disconnected photon ray as copper is an error.
    corrupt = replace(
        symbol, conductor_topology=replace(
            symbol.conductor_topology, conductor_indices=(0, 1, 6),
        ),
    )
    assert "TOPOLOGY_ORPHAN_CONDUCTOR" in {
        d.code for d in inspect_conductor_topology(corrupt).diagnostics
    }


def test_schottky_has_cathode_hooks_not_zener_ornament_and_varicap_has_true_cap_gap():
    schottky, _ = _pair("diode.schottky")
    varicap, _ = _pair("diode.varicap")
    assert len(schottky.graphics) == 10
    assert len(varicap.graphics) == 7
    assert varicap.graphics[1] == Line(Point(5000, 0), Point(10000, 0))
    assert varicap.graphics[6] == Line(Point(5000, -3300), Point(5000, 3300))
    assert schottky.graphics[-1] == Line(Point(800, 3300), Point(800, 4800))
    assert inspect_conductor_topology(varicap).pin_islands == (("1",), ("2",))


@pytest.mark.parametrize("identifier", TRANSISTORS + DIODES)
def test_mutating_role_or_geometry_is_not_indistinguishable_from_true_catalog_mapping(identifier):
    symbol, part = _pair(identifier)
    fake_part = replace(part, pins=(
        replace(part.pins[0], name="NOT_" + part.pins[0].name),
        *part.pins[1:],
    ))
    assert tuple(p.name for p in fake_part.pins) != _roles(identifier)
    assert tuple(p.name for p in part.pins) == _roles(identifier)
    with pytest.raises(ValueError, match="Duplicate graphic pin"):
        replace(symbol, pins=(
            replace(symbol.pins[0], at=symbol.pins[1].at),
            *symbol.pins[1:],
        ))
