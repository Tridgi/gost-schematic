"""Multi-terminal source-real PinRef tree connectivity and unsafe routing gates."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side
from gost_schematic.engines.multiterminal_router import (
    route_circuit_net_trees,
    route_multi_terminal_net,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    validate_external_wires,
)
from gost_schematic.validation.route_drc import audit_route_drc


def native_three_terminal():
    """All coordinates are genuine resolved Part/GraphicPin world micrometres."""
    geometries = {}
    for identifier, at, side in (
        ("terminal-right", Point(7000, 2000), Side.RIGHT),
        ("terminal-left", Point(-3000, 2000), Side.LEFT),
        ("terminal-bottom", Point(2000, 7000), Side.BOTTOM),
    ):
        geometries[identifier] = SymbolDefinition(
            identifier, 1,
            (Rectangle(Box(0, 0, 4000, 4000)),
             Line(
                 Point(4000 if side is Side.RIGHT else
                       0 if side is Side.LEFT else 2000,
                       2000 if side is not Side.BOTTOM else 4000),
                 at,
             )),
            (GraphicPin("1", at, side),),
            Box(0, 0, 4000, 4000), 300,
        )
    parts = {
        name: PartDefinition(
            name, "X", name, (PhysicalPin("1", "P", ElectricalType.PASSIVE),),
        ) for name in geometries
    }
    circuit = Circuit((
        ComponentInstance("X1", "terminal-right", Point(10000, 15000)),
        ComponentInstance("X2", "terminal-left", Point(60000, 15000)),
        ComponentInstance("X3", "terminal-bottom", Point(31000, 3000)),
    ), (Net("A", (
        PinRef("X1", "1"), PinRef("X2", "1"), PinRef("X3", "1"),
    )),))
    return circuit, parts, geometries


def test_full_three_terminal_tree_creates_real_authored_T_dot_without_net_change():
    circuit, parts, symbols = native_three_terminal()
    original = circuit
    tree = route_multi_terminal_net(
        circuit, circuit.nets[0], parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
    )
    assert tree.complete, tree.diagnostics
    assert tree.pin_refs == circuit.nets[0].members
    assert len(tree.segments) == 2, tree.segments
    assert len(tree.junctions) == 1
    assert tree.junctions[0] == Point(33000, 17000)
    assert tree.length_um == 40000 + 7000
    assert tree.bend_count == 0
    graph = ExternalWireGraph(tree.segments, tree.junctions)
    assert not [
        d.code for d in validate_external_wires(circuit, graph, parts, symbols)
        if d.severity.value == "error"
    ]
    assert audit_route_drc(circuit, graph, symbols_by_part=symbols).valid
    assert circuit == original


def test_global_router_preserves_source_Net_and_declared_PinRefs_and_rechecks_DRC():
    circuit, parts, symbols = native_three_terminal()
    planned = route_circuit_net_trees(
        circuit, parts, symbols, page_box=Box(0, 0, 90000, 60000),
    )
    assert planned.complete, planned.diagnostics
    assert planned.drc is not None and planned.drc.valid
    assert planned.as_dict()["net_diff"] == {
        "added": [], "removed": [], "modified_physical_PinRef": [],
    }
    assert not planned.print_pass  # No measured source annotations in this demo.
    assert len(planned.graph.junctions) == 1
    assert planned.as_dict()["graph_segments"] == 2
    assert planned.source_circuit == circuit


def test_foreign_nets_no_auto_join_even_if_pin_visually_coincident():
    circuit, parts, symbols = native_three_terminal()
    bad_net = Net("B", (PinRef("X1", "1"), PinRef("X2", "1")))
    illegal = replace(circuit, nets=(circuit.nets[0], bad_net))
    with pytest.raises(ValueError, match="DRC_CROSS_NET_PHYSICAL_PIN"):
        route_circuit_net_trees(
            illegal, parts, symbols, page_box=Box(0, 0, 90000, 60000),
        )


def test_route_exits_sourced_pin_normals_and_no_ghost_junction_on_free_end():
    circuit, parts, symbols = native_three_terminal()
    result = route_multi_terminal_net(
        circuit, circuit.nets[0], parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
    )
    assert result.complete
    assert all(w.start != w.end for w in result.segments)
    assert Point(57000, 17000) in {p for w in result.segments
                                   for p in (w.start, w.end)}
    assert Point(33000, 10000) in {p for w in result.segments
                                   for p in (w.start, w.end)}
    assert Point(57000, 17000) not in result.junctions


def test_trapped_real_pin_failure_does_not_output_print_pass():
    circuit, parts, symbols = native_three_terminal()
    bad = replace(
        symbols["terminal-bottom"],
        pins=(GraphicPin("1", Point(2000, 4500), Side.BOTTOM),),
    )
    updated = {**symbols, "terminal-bottom": bad}
    result = route_circuit_net_trees(
        circuit, parts, updated, page_box=Box(0, 0, 90000, 60000),
    )
    assert not result.complete
    assert not result.print_pass
    assert any("TRAPPED" in message for message in result.diagnostics)
    assert result.as_dict()["blocked_release"]


def test_small_page_rejects_without_fabricating_or_dropping_pin_refs():
    circuit, parts, symbols = native_three_terminal()
    planned = route_circuit_net_trees(
        circuit, parts, symbols, page_box=Box(0, 0, 30000, 12000),
    )
    assert not planned.complete and not planned.print_pass
    assert len(planned.source_circuit.nets) == 1
    assert planned.source_circuit.nets[0] == circuit.nets[0]


def test_actual_source_negative_baseline_is_never_print_pass():
    import json
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / (
        "tl494_cycle9_known_bad_nine_drc.json"
    )
    evidence = json.loads(path.read_text("utf-8"))
    assert evidence["geometric"]["errors"] == 9
    assert evidence["geometric"]["warnings"] == 32
    assert evidence["geometric"]["bends"] == 49
    assert evidence["geometric"]["route_length_mm"] == 4691.25
    assert len(evidence["geometric"]["hard_failures"]) == 9
    assert evidence["expected_print_pass"] is False
    assert evidence["provenance"]["source_head"] == (
        "e695c415fdced164b0e0c39c5249d030795a0aa6"
    )
