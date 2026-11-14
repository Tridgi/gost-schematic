"""Multi-terminal source-real PinRef tree connectivity and unsafe routing gates."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.multiterminal_router import (
    _nearest_net_order,
    _source_ink_collision,
    _source_ink_obstacles,
    route_circuit_net_trees,
    route_circuit_with_order_fallback,
    route_multi_terminal_net,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
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


def test_global_functional_order_restart_is_deterministic_and_readonly():
    circuit, parts, symbols = native_three_terminal()
    a = route_circuit_with_order_fallback(
        circuit, parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
        try_priorities=3, max_order_restarts=1,
    )
    b = route_circuit_with_order_fallback(
        circuit, parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
        try_priorities=3, max_order_restarts=1,
    )
    assert a.source_circuit == b.source_circuit == circuit
    assert a.graph == b.graph
    assert a.routing_strategy == b.routing_strategy == "SOURCE_FUNCTIONAL"
    assert len(a.route_order_trials) == 3
    assert all(x[1] == 1 and x[2] == 0
               for x in a.route_order_trials)
    assert a.as_dict()["route_order_trials"][1]["strategy"] == "COMMON_FIRST"
    assert all(x.net_name == "A" for x in a.graph.segments)
    assert not a.print_pass


@pytest.mark.parametrize("n", (0, -1, 4, 99, 2.5))
def test_route_priority_trial_count_rejects_invalid_or_unbounded_inputs(n):
    circuit, parts, symbols = native_three_terminal()
    with pytest.raises(ValueError, match="ROUTE_INVALID_FUNCTIONAL_ORDER"):
        route_circuit_with_order_fallback(
            circuit, parts, symbols,
            page_box=Box(0, 0, 90000, 60000),
            try_priorities=n,
        )


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


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_eight_D4_poses_preserve_real_multi_pin_net_and_one_T(rotation, mirror):
    circuit, parts, symbols = native_three_terminal()
    tx = Transform(rotation, mirror)
    transformed = replace(
        circuit, components=tuple(
            replace(component, origin=tx.apply(component.origin), transform=tx)
            for component in circuit.components
        ),
    )
    tree = route_circuit_net_trees(
        transformed, parts, symbols,
        page_box=Box(-100000, -100000, 100000, 100000),
    )
    assert tree.complete, tree.diagnostics
    assert len(tree.graph.junctions) == 1
    assert tree.graph.junctions[0] == tx.apply(Point(33000, 17000))
    assert tree.drc is not None and tree.drc.valid
    assert tree.source_circuit.nets == circuit.nets


def test_four_real_physical_contacts_reuse_one_shared_authored_junction():
    circuit, parts, symbols = native_three_terminal()
    sym = SymbolDefinition(
        "terminal-top", 1,
        (Rectangle(Box(0, 0, 4000, 4000)),
         Line(Point(2000, 0), Point(2000, -3000))),
        (GraphicPin("1", Point(2000, -3000), Side.TOP),),
        Box(0, 0, 4000, 4000), 300,
    )
    parts = {**parts, "terminal-top": PartDefinition(
        "terminal-top", "X", "terminal-top",
        (PhysicalPin("1", "P", ElectricalType.PASSIVE),),
    )}
    symbols = {**symbols, sym.identifier: sym}
    circuit = replace(
        circuit,
        components=(*circuit.components,
                    ComponentInstance("X4", "terminal-top", Point(31000, 25000))),
        nets=(replace(
            circuit.nets[0],
            members=(*circuit.nets[0].members, PinRef("X4", "1")),
        ),),
    )
    result = route_circuit_net_trees(
        circuit, parts, symbols, page_box=Box(0, 0, 90000, 60000),
    )
    assert result.complete, result.diagnostics
    assert result.net_trees[0].complete
    assert len(result.graph.segments) == 3
    assert result.graph.junctions == (Point(33000, 17000),)
    assert not [d for d in validate_external_wires(circuit, result.graph,
                                                    parts, symbols)
                if d.severity.value == "error"]
    assert result.drc is not None and result.drc.valid


def test_grid_overflow_and_invalid_sheet_are_typed_fail_closed():
    circuit, parts, symbols = native_three_terminal()
    result = route_circuit_net_trees(
        circuit, parts, symbols,
        page_box=Box(0, 0, 90000, 60000), search_node_cap=4,
    )
    assert not result.complete and not result.print_pass
    assert "ROUTE_GRID_TOO_DENSE" in " ".join(result.diagnostics)


def test_large_common_net_prims_nearest_contacts_before_far_same_net_tip():
    pins = tuple(PinRef(f"X{i}", "1") for i in range(1, 7))
    places = (
        Point(30000, 60000),  # X1.2 entrance
        Point(450000, 60000),  # X2.2 long-range return
        Point(60000, 120000),
        Point(90000, 130000),
        Point(135000, 155000),
        Point(385000, 170000),
    )
    positions = {pin: (at, Point(1, 0))
                 for pin, at in zip(pins, places, strict=True)}
    expected = (pins[0], pins[2], pins[3], pins[4], pins[5], pins[1])
    assert _nearest_net_order(pins, positions) == expected
    assert _nearest_net_order(pins, positions) == expected
    assert set(expected) == set(pins)


def test_own_lead_ink_guard_rejects_nearby_noncontact_parallel_trunk():
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    ink = _source_ink_obstacles(circuit, symbols, stroke_um=300)
    # 1 mm to the LEFT of real physical lead tip is still on actual lead ink;
    # an owned DA1 pin elsewhere cannot waive this source primitive.
    across = WireSegment(
        Point(204000, 130000), Point(204000, 163000), "INPUT_POS",
    )
    conflict = _source_ink_collision(
        across, ink,
        authorized_pins=frozenset({PinRef("DA1", "12")}),
    )
    assert conflict is not None
    assert conflict.primitive_kind == "Line"
    assert conflict.owner == "DA1"


def _mock_real_tl494_lead_forest():
    """Pin 12 world at real compact A3 (205000, 138750) µm."""
    symbol = SymbolDefinition(
        "mock.paint.leads", 1,
        (
            Rectangle(Box(0, 0, 8000, 40000)),
            Line(Point(8000, 5000), Point(18000, 5000)),
            Line(Point(8000, 13000), Point(18000, 13000)),
            Line(Point(8000, 21000), Point(18000, 21000)),
        ),
        (
            GraphicPin("12", Point(18000, 5000), Side.RIGHT),
            GraphicPin("8", Point(18000, 13000), Side.RIGHT),
            GraphicPin("11", Point(18000, 21000), Side.RIGHT),
        ),
        Box(0, 0, 8000, 40000), 300,
    )
    part = PartDefinition(
        "mock.paint.leads", "DA", "mock.paint.leads",
        (
            PhysicalPin("12", "VCC", ElectricalType.POWER_INPUT),
            PhysicalPin("8", "C1", ElectricalType.OPEN_COLLECTOR),
            PhysicalPin("11", "C2", ElectricalType.OPEN_COLLECTOR),
        ),
    )
    net = Net("INPUT_POS", (PinRef("DA1", "12"),))
    circuit = Circuit(
        (ComponentInstance("DA1", part.identifier, Point(187000, 133750)),),
        (net,),
    )
    return circuit, {part.identifier: part}, {symbol.identifier: symbol}


def test_real_DA1_failed_x203460_vertical_cannot_cross_other_leads():
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    ink = _source_ink_obstacles(circuit, symbols, stroke_um=300)
    old_rejected = WireSegment(
        Point(203460, 138750), Point(203460, 43201), "INPUT_POS",
    )
    collision = _source_ink_collision(
        old_rejected, ink,
        authorized_pins=frozenset({PinRef("DA1", "12")}),
    )
    assert collision is not None
    assert collision.owner == "DA1"
    assert collision.primitive_kind == "Line"
    assert collision.permitted_pin is not None
    assert collision.permitted_pin.reference == "DA1"


def test_real_DA1_exterior_x208150_lane_and_pin_12_exit_are_legal():
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    ink = _source_ink_obstacles(circuit, symbols, stroke_um=300)
    pins = frozenset({PinRef("DA1", "12")})
    source = Point(205000, 138750)
    assert _source_ink_collision(
        WireSegment(source, Point(208150, source.y), "INPUT_POS"),
        ink, authorized_pins=pins,
    ) is None
    assert _source_ink_collision(
        WireSegment(Point(208150, 138750), Point(208150, 43201),
                    "INPUT_POS"), ink, authorized_pins=pins,
    ) is None
    forbidden = _source_ink_collision(
        WireSegment(source, Point(190000, source.y), "INPUT_POS"),
        ink, authorized_pins=pins,
    )
    assert forbidden is not None


def test_lead_exemption_requires_exact_authorized_PinRef_not_same_owner():
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    ink = _source_ink_obstacles(circuit, symbols, stroke_um=300)
    lead_8 = WireSegment(
        Point(205000, 146750), Point(208150, 146750), "INPUT_POS",
    )
    blocked = _source_ink_collision(
        lead_8, ink,
        authorized_pins=frozenset({PinRef("DA1", "12")}),
    )
    assert blocked is not None
    assert blocked.permitted_pin == PinRef("DA1", "8")
    allowed = _source_ink_collision(
        lead_8, ink,
        authorized_pins=frozenset({PinRef("DA1", "8")}),
    )
    assert allowed is None


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_IC_fanout_primitive_D4_preserves_per_pin_exemption(rotation, mirror):
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    tx = Transform(rotation, mirror)
    instance = circuit.components[0]
    transformed = replace(
        circuit, components=(replace(
            instance, transform=tx, origin=tx.apply(instance.origin),
        ),),
    )
    ink = _source_ink_obstacles(transformed, symbols, stroke_um=300)
    p = tx.apply(Point(205000, 138750))
    out = tx.apply(Point(208150, 138750))
    valid = _source_ink_collision(
        WireSegment(p, out, "INPUT_POS"), ink,
        authorized_pins=frozenset({PinRef("DA1", "12")}),
    )
    assert valid is None
    # The same sourced pin may NOT authorize a separate physical lead.
    q = tx.apply(Point(205000, 146750))
    r = tx.apply(Point(208150, 146750))
    invalid = _source_ink_collision(
        WireSegment(q, r, "INPUT_POS"), ink,
        authorized_pins=frozenset({PinRef("DA1", "12")}),
    )
    assert invalid is not None
    assert invalid.permitted_pin == PinRef("DA1", "8")


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
