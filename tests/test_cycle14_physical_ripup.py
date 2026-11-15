"""Cycle14 source-typed physical rip-up: real pins/wires, strict DRC, no waivers."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.multiterminal_router import (
    GlobalRoutePreview,
    _accepted_tree_graph,
    _conflict_directed_ripup,
    _observed_ripup_pairs,
    route_circuit_net_trees,
    route_circuit_with_order_fallback,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)
from gost_schematic.validation.route_drc import audit_route_drc
from tests.test_multiterminal_router_cycle9 import native_three_terminal


def two_real_nets():
    circuit, parts, symbols = native_three_terminal()
    extended = Circuit(
        (*circuit.components,
         ComponentInstance("Y1", "terminal-right", Point(10000, 45000)),
         ComponentInstance("Y2", "terminal-left", Point(60000, 45000))),
        (*circuit.nets, Net("B", (PinRef("Y1", "1"), PinRef("Y2", "1")))),
    )
    return extended, parts, symbols


def preexisting_blocked_preview():
    circuit, parts, symbols = two_real_nets()
    page = Box(0, 0, 90000, 70000)
    whole = route_circuit_net_trees(
        circuit, parts, symbols, page_box=page,
        priority=("A", "B"), stop_on_first_failure=False,
        max_order_restarts=0,
    )
    assert whole.complete and len(whole.net_trees) == 2
    assert not whole.drc.findings or whole.drc.valid
    old, b = whole.net_trees
    witness = (
        "ROUTE_NO_CLEAR_ORTHOGONAL_TREE_PATH:"
        "WIRE_VETO=A:DRC_FOREIGN_NET_ENDPOINT_CONTACT:"
        "existing=17000,17000->57000,17000:"
        "trial=17000,47000->57000,47000:Y2.1"
    )
    b = replace(
        b, segments=(), junctions=(), bend_count=0, length_um=0,
        diagnostics=(witness,), completed_pins=(PinRef("Y1", "1"),),
    )
    graph = _accepted_tree_graph((old, b))
    assert graph.segments == old.segments
    drc = audit_route_drc(circuit, graph, symbols_by_part=symbols)
    assert drc.valid
    source = GlobalRoutePreview(
        circuit, graph, (old, b), ("B:" + witness,), drc,
    )
    assert not source.complete and not source.print_pass
    return circuit, parts, symbols, page, source


def test_cycle14_ripup_real_sourced_two_net_graph_can_finish_without_spoofed_connections():
    circuit, parts, symbols, page, source = preexisting_blocked_preview()
    assert _observed_ripup_pairs(source.net_trees) == (("B", "A"),)
    old_components, old_nets = circuit.components, circuit.nets
    output = _conflict_directed_ripup(
        source, parts, symbols, page_box=page,
        annotation_placements=(), stroke_um=300,
        search_node_cap=25000, max_detour_ratio=3.0, budget=2,
    )
    assert output.complete
    assert len(output.net_trees) == 2
    assert {t.net_name for t in output.net_trees} == {"A", "B"}
    assert all(t.complete and t.pin_refs == net.members
               for t, net in zip(output.net_trees, circuit.nets, strict=True))
    assert output.graph == _accepted_tree_graph(output.net_trees)
    assert {w.net_name for w in output.graph.segments} == {"A", "B"}
    assert output.drc.valid and not output.diagnostics
    assert output.routing_strategy == "CONFLICT_DIRECTED_PHYSICAL_RIPUP"
    assert output.ripup_trials[0][:3] == ("B", "A", 2)
    assert output.as_dict()["ripup_trials"][0]["status"] == "BOTH_REBUILT"
    assert not [x for x in validate_external_wires(
        circuit, output.graph, parts, symbols,
    ) if x.severity.value == "error"]
    assert (circuit.components, circuit.nets) == (old_components, old_nets)
    # No measured text supplied, so even a connected 2/2 test sample is
    # NOT a valid full printed sheet per the strict official print gate.
    assert output.print_pass is False


@pytest.mark.parametrize("budget", (-1, True, 5, 1.5))
def test_cycle14_ripup_rejects_unbounded_or_invalid_budget(budget):
    circuit, parts, symbols = two_real_nets()
    with pytest.raises(ValueError, match="ROUTE_INVALID_PHYSICAL_RIPUP_BUDGET"):
        route_circuit_with_order_fallback(
            circuit, parts, symbols, page_box=Box(0, 0, 90000, 70000),
            try_priorities=1, max_order_restarts=0,
            physical_ripup_attempts=budget,
        )


def test_cycle14_ripup_does_not_accept_forged_missing_wire_or_ghost_net():
    _circuit, parts, symbols, page, source = preexisting_blocked_preview()
    ghost = WireSegment(Point(1000, 1000), Point(2000, 1000), "PHANTOM")
    forged = replace(
        source,
        graph=ExternalWireGraph((*source.graph.segments, ghost),
                                source.graph.junctions),
    )
    with pytest.raises(ValueError, match="ROUTE_RIPUP_GRAPH_TREE_MISMATCH"):
        _conflict_directed_ripup(
            forged, parts, symbols, page_box=page,
            annotation_placements=(), stroke_um=300,
            search_node_cap=25000, max_detour_ratio=3.0, budget=1,
        )


def test_cycle14_ripup_uses_actual_foreign_wire_not_ink_or_own_net():
    _circuit, parts, symbols, page, source = preexisting_blocked_preview()
    old, b = source.net_trees
    poisoned = replace(b, diagnostics=(
        "ROUTE_NO_CLEAR:INK_VETO=DA1#3:DA1.3",
        "ROUTE_NO_CLEAR:WIRE_VETO=B:DRC_PARALLEL_STROKE_CLEARANCE",
        "ROUTE_NO_CLEAR:WIRE_VETO=GHOST:DRC_FOREIGN_NET_ENDPOINT_CONTACT",
    ))
    preview = replace(source, net_trees=(old, poisoned))
    assert _observed_ripup_pairs(preview.net_trees) == ()
    unchanged = _conflict_directed_ripup(
        preview, parts, symbols, page_box=page, annotation_placements=(),
        stroke_um=300, search_node_cap=25000,
        max_detour_ratio=3.0, budget=2,
    )
    assert unchanged.graph == source.graph
    assert not unchanged.ripup_trials
    assert not unchanged.print_pass
