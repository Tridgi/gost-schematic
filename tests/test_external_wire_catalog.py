"""Integration coverage: external wires versus actual immutable catalog JSON."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from examples.review_external_wire_catalog import (
    catalog_definitions,
    catalog_sheet,
    review_cases,
    review_document,
    review_json,
)
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.pins import TerminalFunction, TerminalPolarity
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)


@pytest.fixture(scope="module")
def catalog():
    return catalog_definitions()


def _codes(diagnostics):
    return {item.code for item in diagnostics}


def test_catalog_loading_preserves_four_real_part_and_symbol_identifiers(catalog):
    parts, symbols = catalog
    assert set(parts) == {
        "resistor.fixed", "capacitor.fixed", "capacitor.polarized", "inductor.tapped",
    }
    assert set(symbols) == set(parts)
    assert all(parts[name].symbol_id == name for name in parts)
    assert all(symbol.status == SymbolStatus.DRAFT for symbol in symbols.values())
    for name in parts:
        assert {pin.number for pin in parts[name].pins} == {
            pin.number for pin in symbols[name].pins
        }


def test_catalog_real_pin_roles_and_winding_tap_world_coordinates(catalog):
    parts, symbols = catalog
    polar = parts["capacitor.polarized"]
    assert [(pin.number, pin.polarity) for pin in polar.pins] == [
        ("1", TerminalPolarity.POSITIVE), ("2", TerminalPolarity.NEGATIVE),
    ]
    winding = parts["inductor.tapped"]
    assert [(pin.number, pin.function) for pin in winding.pins] == [
        ("1", TerminalFunction.WINDING_START),
        ("2", TerminalFunction.WINDING_END),
        ("3", TerminalFunction.WINDING_TAP),
    ]
    topology = symbols["inductor.tapped"].conductor_topology
    assert topology is not None
    assert topology.pin_groups == (("1", "2", "3"),)
    assert symbols["capacitor.fixed"].conductor_topology.pin_groups == (
        ("1",), ("2",),
    )
    assert symbols["capacitor.polarized"].conductor_topology.pin_groups == (
        ("1",), ("2",),
    )
    circuit, graph = catalog_sheet()
    instance = next(item for item in circuit.components if item.reference == "L1")
    assert instance.pin_positions(symbols["inductor.tapped"]) == {
        "1": Point(88000, 40000),
        "2": Point(112000, 40000),
        "3": Point(98000, 31000),
    }
    assert graph.junctions == (Point(40000, 20000),)


def test_real_five_component_sheet_never_shorts_through_ugo_graphics(catalog):
    parts, symbols = catalog
    circuit, graph = catalog_sheet()
    assert len(circuit.components) == 5
    assert len(circuit.nets) == 5
    assert len(graph.segments) == 12
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    ownership = {
        member: net.name
        for net in circuit.nets
        for member in net.members
    }
    assert ownership[PinRef("L1", "1")] == "TOP"
    assert ownership[PinRef("L1", "2")] == "RIGHT"
    assert ownership[PinRef("L1", "3")] == "TAP"
    assert ownership[PinRef("R1", "1")] != ownership[PinRef("R1", "2")]
    for ref in ("C1", "C2"):
        assert ownership[PinRef(ref, "1")] != ownership[PinRef(ref, "2")]


@pytest.mark.parametrize("name", [
    "resistor.fixed", "capacitor.fixed", "capacitor.polarized", "inductor.tapped",
])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_real_catalog_mirror_rotation_maintains_physical_contacts(
    catalog, name, rotation, mirror,
):
    parts, symbols = catalog
    first = ComponentInstance(
        "X1", name, Point(200000, 200000), Transform(rotation, mirror),
    )
    second = ComponentInstance("X2", name, Point(500000, 250000))
    special_pin = "3" if name == "inductor.tapped" else "2"
    actual = first.pin_positions(symbols[name])[special_pin]
    expected = (
        first.transform.apply(next(pin.at for pin in symbols[name].pins
                                   if pin.number == special_pin))
        + first.origin
    )
    assert actual == expected
    target = second.pin_positions(symbols[name])["1"]
    assert actual != target
    assert actual != first.pin_positions(symbols[name])["1"]
    circuit = Circuit(
        (first, second),
        (Net("LINK", (PinRef("X1", special_pin), PinRef("X2", "1"))),),
    )
    graph = ExternalWireGraph((WireSegment(actual, target, "LINK"),))
    assert validate_external_wires(circuit, graph, parts, symbols) == ()


@pytest.mark.parametrize("case", review_cases(), ids=lambda case: case.name)
def test_real_catalog_named_case_diagnostics_match_exact_contract(catalog, case):
    parts, symbols = catalog
    diagnostics = validate_external_wires(case.circuit, case.graph, parts, symbols)
    assert _codes(diagnostics) == set(case.expected_codes)
    if case.name == "valid_catalog_sheet":
        assert diagnostics == ()
    else:
        assert all(issue.severity.value == "error" for issue in diagnostics)
    assert len(diagnostics) == len(validate_external_wires(
        case.circuit, case.graph, parts, symbols,
    ))


@pytest.mark.parametrize("junction", [Point(70000, 40000), Point(98000, 27000)])
def test_two_real_crossings_are_isolated_until_marked(catalog, junction):
    parts, symbols = catalog
    circuit, original = catalog_sheet()
    assert validate_external_wires(circuit, original, parts, symbols) == ()
    short = ExternalWireGraph(original.segments, (*original.junctions, junction))
    assert "WIRE_NET_SHORT" in _codes(
        validate_external_wires(circuit, short, parts, symbols)
    )


def test_missing_t_and_one_micrometre_gap_disconnect_without_snapping(catalog):
    parts, symbols = catalog
    cases = {case.name: case for case in review_cases()}
    for name in ("missing_t_junction", "one_micrometre_break"):
        case = cases[name]
        codes = _codes(validate_external_wires(case.circuit, case.graph, parts, symbols))
        assert "WIRE_NET_DISCONNECTED" in codes
        assert "WIRE_NET_SHORT" not in codes


def test_invalid_wire_label_and_orphan_produce_distinct_errors(catalog):
    parts, symbols = catalog
    cases = {case.name: case for case in review_cases()}
    wrong = cases["wrong_bottom_net"]
    orphan = cases["orphan_conductor"]
    assert "WIRE_PIN_NET_MISMATCH" in _codes(
        validate_external_wires(wrong.circuit, wrong.graph, parts, symbols)
    )
    orphan_codes = _codes(
        validate_external_wires(orphan.circuit, orphan.graph, parts, symbols)
    )
    assert "WIRE_ORPHAN_CONDUCTOR" in orphan_codes
    assert "WIRE_NET_DISCONNECTED" not in orphan_codes


def test_real_catalog_sheet_components_and_graph_are_immutable():
    circuit, graph = catalog_sheet()
    with pytest.raises(FrozenInstanceError):
        circuit.components[0].reference = "BROKEN"
    with pytest.raises(FrozenInstanceError):
        graph.segments[0].net_name = "BROKEN"


def test_repeatable_json_report_is_exact_golden_and_all_cases_are_checked():
    first = review_json()
    second = review_json()
    assert first == second
    report = json.loads(first)
    assert report["schema_version"] == 1
    assert report["case_count"] == 7
    assert report == review_document()
    assert [entry["id"] for entry in report["cases"]] == [
        "valid_catalog_sheet", "missing_t_junction", "one_micrometre_break",
        "crossing_short_with_junction", "wrong_bottom_net", "orphan_conductor",
        "unwired_capacitor_pin",
    ]
    assert report["cases"][0]["result"] == "pass"
    assert all(entry["result"] == "diagnostics" for entry in report["cases"][1:])
    fixture = Path(__file__).parent / "fixtures" / "external_wire_catalog_review.json"
    assert fixture.read_bytes().replace(b"\r\n", b"\n") == first.encode("utf-8")
