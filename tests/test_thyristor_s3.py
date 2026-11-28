"""Table 6 draft thyristors: no ideal short through semiconductor artwork."""
from dataclasses import replace

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

CASES = (
    ("thyristor.scr_cathode_gate", ("A", "K", "G")),
    ("thyristor.gto_cathode_gate", ("A", "K", "G")),
    ("thyristor.diac", ("T1", "T2")),
    ("thyristor.triac", ("MT1", "MT2", "G")),
)


@pytest.mark.parametrize("identifier,roles", CASES)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_thyristor_identity_and_protection(identifier, roles, rotation, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    assert part.reference_prefix == "VS"
    assert tuple(p.name for p in part.pins) == roles
    assert tuple(p.label for p in symbol.pins) == roles
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == tuple((str(i),) for i in range(1, len(roles) + 1))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    tx = Transform(rotation, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    row = audit_symbol(symbol)
    assert not row["uncovered_functional_bounds"]
    assert not row["blocked_cardinal_escapes"]


def test_gto_has_distinct_turn_off_mark_and_same_terminal_passport():
    catalog = CatalogResolver()
    scr_part, scr = catalog.resolve("thyristor.scr_cathode_gate")
    gto_part, gto = catalog.resolve("thyristor.gto_cathode_gate")
    assert scr_part.pins == gto_part.pins
    assert scr.pins == gto.pins
    assert gto.graphics[:-1] == scr.graphics
    mark = Line(Point(6600, 8000), Point(9400, 8000))
    assert gto.graphics[-1] == mark
    assert len(gto.graphics) - 1 not in gto.conductor_topology.conductor_indices


def test_diac_and_triac_transition_marks_are_distinct():
    catalog = CatalogResolver()
    _, diac = catalog.resolve("thyristor.diac")
    _, triac = catalog.resolve("thyristor.triac")
    bar = Line(Point(0, -6000), Point(0, 6000))
    assert bar in diac.graphics
    assert bar not in triac.graphics
    assert len(diac.pins) == 2
    assert len(triac.pins) == 3


@pytest.mark.parametrize("identifier,roles", CASES)
def test_injected_main_terminal_bridge_is_rejected(identifier, roles):
    _, symbol = CatalogResolver().resolve(identifier)
    bridge = Line(symbol.pins[0].at, symbol.pins[1].at)
    wrong = replace(symbol, graphics=(*symbol.graphics, bridge),
                    conductor_topology=replace(
                        symbol.conductor_topology,
                        conductor_indices=(*symbol.conductor_topology.conductor_indices,
                                           len(symbol.graphics)),
                    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }
