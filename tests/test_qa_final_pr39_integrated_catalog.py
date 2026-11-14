"""Post-merge QA: test the REAL integrated modules against 21+ draft parts.

Unlike frozen-source review, every routing import here resolves from the
installed gost_schematic package. No mocked physical contacts, no SVG net
inference, and no production source modifications.
"""

from importlib.resources import files
from pathlib import Path

import pytest

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.two_pin_sheet import route_circuit_two_pins
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import validate_external_wires
from scripts.audit_symbol_catalog import audit_catalog
from scripts.qa_final_pr39_metrics import score_path


@pytest.fixture(scope="module")
def all_parts():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    parts = {}
    symbols = {}
    for path in sorted((root / "parts").rglob("*.json")):
        part = load_part(path)
        parts[part.identifier] = part
    for path in sorted((root / "symbols").rglob("*.json")):
        symbol = load_symbol(path)
        symbols[symbol.identifier] = symbol
    for path in sorted((root / "inductors").glob("*.json")):
        item = load_inductor(path)
        parts[item.part.identifier] = item.part
        symbols[item.symbol.identifier] = item.symbol
    assert len(parts) == len(symbols) >= 21  # 21 baseline, extendable catalog
    assert set(parts) == set(symbols)
    assert {"diode.general", "diode.zener"}.issubset(parts)
    return parts, symbols


def _place(parts, symbols, name, part_id, pin_number, at, transform):
    part = parts[part_id]
    pin = next(p for p in symbols[part.symbol_id].pins if p.number == pin_number)
    origin = at - transform.apply(pin.at)
    component = ComponentInstance(name, part_id, origin, transform)
    assert component.pin_positions(symbols[part.symbol_id])[pin_number] == at
    return component


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_21_draft_physical_pin_passports_and_transforms(
    all_parts, angle, mirror,
):
    """All discovered symbol/part pairs × 8 D4 transforms, with stable pin identity."""
    parts, symbols = all_parts
    transform = Transform(angle, mirror)
    for identifier, part in sorted(parts.items()):
        graphic = symbols[part.symbol_id]
        assert identifier == graphic.identifier
        physical = {pin.number for pin in part.pins}
        assert physical == {pin.number for pin in graphic.pins}
        assert len(physical) >= (1 if identifier in {
            "connector.plug_contact", "connector.socket_contact"
        } else 2)
        instance = ComponentInstance(
            "X1", identifier, Point(100000, 200000), transform
        )
        positions = instance.pin_positions(graphic)
        assert set(positions) == physical
        for pin in graphic.pins:
            assert positions[pin.number] == (
                transform.apply(pin.at) + instance.origin
            )


def test_installed_catalog_is_exactly_21_draft_and_has_no_hard_errors(
    all_parts,
):
    parts, symbols = all_parts
    report = audit_catalog()
    assert report["total_symbols"] == len(parts)
    assert report["draft_count"] == len(parts)
    assert report["hard_errors"] == 0
    assert report["without_physical_part"] == []
    assert {entry["id"] for entry in report["entries"]} == set(parts)
    assert set(parts) == set(symbols)
    assert {"diode.general", "diode.zener"}.issubset(parts)


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_installed_safe_adapter_keeps_all_21_real_pin_families_out_of_link(
    all_parts, angle, mirror,
):
    """All discovered physical families × 8 transforms routed against integrated adapter."""
    parts, symbols = all_parts
    transform = Transform(angle, mirror)
    start = transform.apply(Point(0, -60000))
    end = transform.apply(Point(0, 60000))
    source = _place(
        parts, symbols, "R1", "resistor.fixed", "1", start, transform
    )
    destination = _place(
        parts, symbols, "R2", "resistor.fixed", "1", end, transform
    )
    for identifier in sorted(parts):
        blocker_pin = PinRef("X3", "1")
        blocker = _place(
            parts, symbols, "X3", identifier, "1",
            transform.apply(Point(0, 0)), transform,
        )
        circuit = Circuit(
            (source, blocker, destination),
            (Net("LINK", (PinRef("R1", "1"), PinRef("R2", "1"))),),
        )
        result = route_circuit_two_pins(
            circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
            net_name="LINK", grid_um=1000, max_cells=25000,
        )
        assert result.ok and not result.diagnostics, (
            identifier, angle, mirror, result.diagnostics
        )
        assert result.points[0] == start and result.points[-1] == end
        foreign_pin = blocker.pin_positions(symbols[identifier])["1"]
        for segment in result.external_graph("LINK").segments:
            low, high = segment.start, segment.end
            if low.x == high.x == foreign_pin.x:
                assert not (
                    min(low.y, high.y) <= foreign_pin.y
                    <= max(low.y, high.y)
                ), (identifier, transform, segment)
            if low.y == high.y == foreign_pin.y:
                assert not (
                    min(low.x, high.x) <= foreign_pin.x
                    <= max(low.x, high.x)
                ), (identifier, transform, segment)
        assert validate_external_wires(circuit, result.external_graph("LINK"),
                                       parts, symbols) == ()
        assert blocker_pin not in circuit.nets[0].members


def test_c3_actual_80mm_placement_and_real_electrical_branches():
    """Keep real six-component layout and #44 metric, not a stale 75mm mock."""
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    c3 = next(item for item in circuit.components if item.reference == "C3")
    assert c3.origin == Point(100000, 80000)
    pin_positions = c3.pin_positions(symbols["capacitor.electrolytic"])
    assert pin_positions == {"1": Point(91000, 80000), "2": Point(109000, 80000)}
    assert len(circuit.components) == 6
    assert len(circuit.nets) == 5
    assert len(graph.junctions) == 3
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    top = graph.segments[-4:-2]
    right = graph.segments[-2:]
    assert [(w.start, w.end, w.net_name) for w in top] == [
        (Point(40000, 40000), Point(40000, 80000), "TOP"),
        (Point(40000, 80000), Point(91000, 80000), "TOP"),
    ]
    assert [(w.start, w.end, w.net_name) for w in right] == [
        (Point(120000, 40000), Point(120000, 80000), "RIGHT"),
        (Point(120000, 80000), Point(109000, 80000), "RIGHT"),
    ]
    top_metric = score_path((
        Point(40000, 40000), Point(40000, 80000), Point(91000, 80000),
    ))
    right_metric = score_path((
        Point(120000, 40000), Point(120000, 80000), Point(109000, 80000),
    ))
    assert top_metric.wire_length_um + right_metric.wire_length_um == 142000
    assert top_metric.bends + right_metric.bends == 2
    assert top_metric.backtrack_um == 0
    assert right_metric.backtrack_um == 0
