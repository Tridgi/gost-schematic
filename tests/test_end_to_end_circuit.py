"""Cycle 3: real six-part netlist, actual authored wire geometry and SVG regression."""

import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import (
    SVG_NAMESPACE,
    authored_specimen,
    definitions,
    diagnose,
    potentials,
    renderer_wires,
    report,
    report_json,
    scenarios,
    specimen_svg,
)
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import mm
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.pins import TerminalFunction, TerminalPolarity
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)
from gost_schematic.validation.polarity_checks import PolarityStatus, assess_polarity

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "electrical-layout44"


@pytest.fixture(scope="module")
def catalog():
    return definitions()


def test_six_real_parts_include_draft_electrolytic_and_real_tapped_winding(catalog):
    parts, symbols = catalog
    circuit, graph = authored_specimen()
    assert len(circuit.components) == 6
    assert len(circuit.nets) == 5
    assert len(graph.segments) == 16
    assert len(graph.junctions) == 3
    assert [part.reference for part in circuit.components] == [
        "R1", "R2", "C1", "C2", "L1", "C3",
    ]
    assert {part.part_id for part in circuit.components} == {
        "resistor.fixed", "capacitor.fixed", "capacitor.polarized",
        "inductor.tapped", "capacitor.electrolytic",
    }
    assert all(symbol.status == SymbolStatus.DRAFT for symbol in symbols.values())
    for part_id, physical in parts.items():
        assert {pin.number for pin in physical.pins} == {
            pin.number for pin in symbols[part_id].pins
        }
    electrolytic = parts["capacitor.electrolytic"]
    assert [(pin.number, pin.polarity) for pin in electrolytic.pins] == [
        ("1", TerminalPolarity.POSITIVE), ("2", TerminalPolarity.NEGATIVE),
    ]
    assert [(pin.number, pin.function) for pin in parts["inductor.tapped"].pins] == [
        ("1", TerminalFunction.WINDING_START),
        ("2", TerminalFunction.WINDING_END),
        ("3", TerminalFunction.WINDING_TAP),
    ]
    capacitor = next(item for item in circuit.components if item.reference == "C3")
    assert capacitor.pin_positions(symbols[electrolytic.symbol_id]) == {
        "1": Point(91000, 80000), "2": Point(109000, 80000),
    }


def test_authored_netlist_has_distinct_internal_component_terminals(catalog):
    parts, symbols = catalog
    circuit, graph = authored_specimen()
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    erc = validate_circuit(circuit, parts, symbols, scenario=potentials())
    assert not [d for d in erc if d.severity.value == "error"]
    membership = {pin: net.name for net in circuit.nets for pin in net.members}
    for ref in ("R1", "R2", "C1", "C2", "C3"):
        assert membership[PinRef(ref, "1")] != membership[PinRef(ref, "2")]
    assert {membership[PinRef("L1", number)] for number in ("1", "2", "3")} == {
        "TOP", "RIGHT", "TAP",
    }
    assert membership[PinRef("C3", "1")] == "TOP"
    assert membership[PinRef("C3", "2")] == "RIGHT"
    # Inside-the-UGO conducting ink never defines an external net/short.
    assert symbols["inductor.tapped"].conductor_topology.pin_groups == (("1", "2", "3"),)
    assert symbols["capacitor.electrolytic"].conductor_topology.pin_groups == (
        ("1",), ("2",),
    )


@pytest.mark.parametrize("name", [
    "resistor.fixed", "capacitor.fixed", "capacitor.polarized",
    "capacitor.electrolytic", "inductor.tapped",
])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_real_pin_identity_attaches_through_all_discrete_transforms(
    catalog, name, rotation, mirror,
):
    parts, symbols = catalog
    transform = Transform(rotation, mirror)
    first = ComponentInstance("X1", name, Point(200000, 200000), transform)
    second = ComponentInstance("X2", name, Point(500000, 250000))
    pin_number = "3" if name == "inductor.tapped" else "2"
    contact = first.pin_positions(symbols[name])[pin_number]
    expected = (
        transform.apply(next(pin.at for pin in symbols[name].pins
                             if pin.number == pin_number)) + first.origin
    )
    assert contact == expected
    other = second.pin_positions(symbols[name])["1"]
    circuit = Circuit(
        (first, second),
        (Net("LINK", (PinRef("X1", pin_number), PinRef("X2", "1"))),),
    )
    assert validate_external_wires(
        circuit,
        ExternalWireGraph((WireSegment(contact, other, "LINK"),)),
        parts, symbols,
    ) == ()


def test_static_potential_is_explicit_and_only_reverses_electrolytic(catalog):
    parts, _ = catalog
    circuit, graph = authored_specimen()
    nominal = {item.component: item for item in assess_polarity(
        circuit, parts, scenario=potentials(),
    )}
    assert nominal["C3"].status == PolarityStatus.FORWARD
    assert nominal["C3"].differential_volts == Decimal(12)
    assert nominal["C2"].status == PolarityStatus.FORWARD
    reverse = {item.component: item for item in assess_polarity(
        circuit, parts, scenario=potentials(reverse_electrolytic=True),
    )}
    assert reverse["C3"].status == PolarityStatus.REVERSED
    assert reverse["C3"].differential_volts == Decimal(-2)
    assert reverse["C2"].status == PolarityStatus.FORWARD
    assert validate_external_wires(circuit, graph, *catalog) == ()


@pytest.mark.parametrize("case", scenarios(), ids=lambda case: case.identifier)
def test_positive_and_negative_scenarios_explain_diagnostics(catalog, case):
    parts, symbols = catalog
    wire_issues = validate_external_wires(case.circuit, case.graph, parts, symbols)
    erc_issues = validate_circuit(case.circuit, parts, symbols, scenario=case.scenario)
    assert {d.code for d in wire_issues} == set(case.expected_wire_codes)
    assert {d.code for d in erc_issues if d.severity.value == "error"} == set(
        case.expected_erc_codes
    )
    record = diagnose(case)
    assert record["id"] == case.identifier
    assert len(record["wire_diagnostics"]) == len(wire_issues)
    if case.identifier == "valid":
        assert not wire_issues
        assert not [d for d in erc_issues if d.severity.value == "error"]


@pytest.mark.parametrize("point", [
    Point(40000, 60000), Point(70000, 40000), Point(98000, 27000),
])
def test_unmarked_crossings_are_not_shorts_but_declared_contacts_are(catalog, point):
    parts, symbols = catalog
    circuit, graph = authored_specimen()
    assert point not in graph.junctions
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    with_dot = ExternalWireGraph(graph.segments, (*graph.junctions, point))
    assert "WIRE_NET_SHORT" in {
        d.code for d in validate_external_wires(circuit, with_dot, parts, symbols)
    }


def _svg_root(review: bool):
    return ET.fromstring(specimen_svg(review=review))


@pytest.mark.parametrize("review", [False, True])
def test_svg_wire_geometry_is_identical_to_external_graph_endpoints(review):
    _, graph = authored_specimen()
    obstacles = renderer_wires(graph)
    assert len(obstacles) == len(graph.segments)
    assert [(wire.line.start, wire.line.end, wire.net_name) for wire in obstacles] == [
        (segment.start, segment.end, segment.net_name) for segment in graph.segments
    ]
    root = _svg_root(review)
    svg_wires = [
        item for item in root.iter(f"{{{SVG_NAMESPACE}}}line")
        if item.get("data-layer") == "wires"
    ]
    assert len(svg_wires) == len(graph.segments)
    for rendered, authored in zip(svg_wires, graph.segments, strict=True):
        assert (
            Point(mm(rendered.attrib["x1"]), mm(rendered.attrib["y1"])),
            Point(mm(rendered.attrib["x2"]), mm(rendered.attrib["y2"])),
        ) == (authored.start, authored.end)
        assert rendered.attrib["stroke-width"] == "0.3"
    dots = [
        item for item in root.iter(f"{{{SVG_NAMESPACE}}}circle")
        if item.get("data-kind") == "authored-junction"
    ]
    assert [Point(mm(item.attrib["cx"]), mm(item.attrib["cy"])) for item in dots] == [
        *graph.junctions,
    ]
    labels = [
        item for item in root.iter(f"{{{SVG_NAMESPACE}}}text")
        if item.get("data-owner") in {"R1", "R2", "C1", "C2", "C3", "L1"}
    ]
    assert {item.get("data-owner") for item in labels} == {
        "R1", "R2", "C1", "C2", "C3", "L1",
    }
    overlays = [
        item for item in root.iter(f"{{{SVG_NAMESPACE}}}g")
        if item.get("data-layer") == "geometry-review"
    ]
    assert bool(overlays) == review


def test_diagnostics_report_and_svg_are_reproducible_golden_fixtures():
    blob = report_json()
    assert blob == report_json()
    document = json.loads(blob)
    assert document == report()
    assert document["schema_version"] == 1
    assert document["status"] == "experimental_not_eskd_approved"
    assert [c["id"] for c in document["cases"]] == [
        "valid", "electrolytic_pin_unwired", "short_at_unmarked_crossing",
        "one_micrometre_gap", "missing_t_junction", "reverse_electrolytic_bias",
    ]
    files = (
        ("end-to-end-clean.svg", specimen_svg()),
        ("end-to-end-review.svg", specimen_svg(review=True)),
        ("end-to-end-diagnostics.json", blob),
    )
    for name, value in files:
        assert (FIXTURE_DIR / name).read_bytes().replace(b"\r\n", b"\n") == (
            value.encode("utf-8")
        )
