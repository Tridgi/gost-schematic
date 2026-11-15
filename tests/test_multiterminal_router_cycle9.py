"""Multi-terminal source-real PinRef tree connectivity and unsafe routing gates."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side, StyledLine
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.multiterminal_router import (
    _nearest_net_order,
    _source_priority_name_view,
    _source_ink_collision,
    _source_ink_obstacles,
    _visibility_path,
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
from gost_schematic.validation.route_drc import (
    audit_route_drc,
    candidate_wire_clearance,
)


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


@pytest.mark.parametrize("n", (0, -1, 7, 99, 2.5))
def test_route_priority_trial_count_rejects_invalid_or_unbounded_inputs(n):
    circuit, parts, symbols = native_three_terminal()
    with pytest.raises(ValueError, match="ROUTE_INVALID_FUNCTIONAL_ORDER"):
        route_circuit_with_order_fallback(
            circuit, parts, symbols,
            page_box=Box(0, 0, 90000, 60000),
            try_priorities=n,
        )


def test_cycle12_true_original_15_net_names_use_valid_order_not_artwork_aliases():
    actual = frozenset({
        "a_INPUT_PLUS", "TRANSFER", "b_NEGATIVE_OUTPUT",
        "FEEDBACK", "OSCILLATOR_RT", "COMMON",
    })
    priority = _source_priority_name_view(
        ("INPUT_POS", "ENERGY_TRANSFER", "OUTPUT_NEG", "COMMON"),
        actual,
    )
    assert priority == (
        "a_INPUT_PLUS", "TRANSFER", "b_NEGATIVE_OUTPUT", "COMMON",
    )
    assert "INPUT_POS" not in priority
    assert set(priority) <= actual
    assert _source_priority_name_view(
        ("INPUT_POS", "ENERGY_TRANSFER", "OUTPUT_NEG"),
        frozenset({"INPUT_POS", "ENERGY_TRANSFER", "OUTPUT_NEG"}),
    ) == ("INPUT_POS", "ENERGY_TRANSFER", "OUTPUT_NEG")
    with pytest.raises(ValueError, match="ROUTE_DUPLICATE_SOURCE_ORDER_LABEL"):
        _source_priority_name_view(
            ("INPUT_POS", "INPUT_POS"), frozenset(actual),
        )


def test_cycle12_actual_source_net_identity_survives_global_priority_search():
    circuit, parts, symbols = native_three_terminal()
    circuit = replace(
        circuit, nets=(Net(
            "a_INPUT_PLUS", circuit.nets[0].members,
        ),),
    )
    preview = route_circuit_with_order_fallback(
        circuit, parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
        try_priorities=3, max_order_restarts=1,
    )
    assert preview.source_circuit is circuit
    assert preview.source_circuit.nets[0].name == "a_INPUT_PLUS"
    assert len(preview.route_order_trials) == 3
    assert preview.graph.segments
    assert {w.net_name for w in preview.graph.segments} == {"a_INPUT_PLUS"}
    assert {p for p in preview.source_circuit.nets[0].members} == set(
        circuit.nets[0].members,
    )


def test_cycle12_multicontact_prim_medoid_is_real_pin_and_not_source_rewrite():
    pins = (
        PinRef("X1", "2"), PinRef("X2", "2"),
        PinRef("DA1", "7"), PinRef("R8", "2"), PinRef("C7", "2"),
    )
    physical = {
        pin: (point, Point(1, 0))
        for pin, point in zip(pins, (
            Point(10000, 10000), Point(399000, 10000),
            Point(125000, 138750), Point(225000, 224000),
            Point(140000, 240000),
        ), strict=True)
    }
    source_order = _nearest_net_order(pins, physical)
    assert source_order[0] == pins[0]
    center = min(pins, key=lambda p: (
        sum(abs(physical[p][0].x - physical[q][0].x)
            + abs(physical[p][0].y - physical[q][0].y)
            for q in pins),
        p.reference, p.number,
    ))
    assert center != pins[0]
    retry = _nearest_net_order(pins, physical, root=center)
    assert retry[0] == center
    assert set(retry) == set(source_order) == set(pins)
    assert len(retry) == len(pins)
    assert pins[0] == PinRef("X1", "2")


def test_cycle12_prim_root_forgery_and_duplicate_pinref_rejected():
    pins = (PinRef("X1", "1"), PinRef("X2", "1"))
    locations = {
        pins[0]: (Point(0, 0), Point(1, 0)),
        pins[1]: (Point(10000, 0), Point(-1, 0)),
    }
    with pytest.raises(ValueError, match="ROUTE_PRIM_UNKNOWN_ROOT"):
        _nearest_net_order(
            pins, locations, root=PinRef("FAKE", "999"),
        )
    with pytest.raises(ValueError, match="ROUTE_PRIM_INVALID_SOURCE"):
        _nearest_net_order((pins[0], pins[0]), locations)
    with pytest.raises(ValueError, match="ROUTE_PRIM_INVALID_SOURCE"):
        _nearest_net_order((), {})


def test_cycle12_real_native_lead_cap_creates_only_legal_route_search_lanes():
    # Actual D4-compatible graphic and physical pin: a short printed
    # vertical lead crosses the intended horizontal A Net. A 5mm uniform
    # grid could only detour 5mm, but exact 300µm stroke envelopes expose
    # a shorter valid corridor immediately outside the physical lead cap.
    symbol = SymbolDefinition(
        "native-obstruction", 1,
        (Line(Point(0, -200), Point(0, 200)),),
        (GraphicPin("1", Point(0, 200), Side.BOTTOM),),
        Box(-200, -300, 200, 0), 300,
    )
    circuit = Circuit((
        ComponentInstance(
            "E1", "native-obstruction", Point(20000, 10000),
        ),
    ), ())
    real = _source_ink_obstacles(
        circuit, {"native-obstruction": symbol}, stroke_um=300,
    )
    assert len(real) == 1 and real[0].permitted_pin == PinRef("E1", "1")
    lower = real[0].collision_bounds.min_y - 1
    upper = real[0].collision_bounds.max_y + 1
    start, goal = Point(1000, 10000), Point(39000, 10000)
    path, failure = _visibility_path(
        start, Point(1, 0), (goal,),
        net_name="A", occupied=ExternalWireGraph(()), tree=(),
        existing_dots=(), goal_pin_normals={},
        ink_obstacles=real, authorized_pins=frozenset(),
        boxes=(), page=Box(0, 0, 40000, 20000),
        stroke_um=300, search_node_cap=10000,
        grid_um=5000, max_detour_ratio=2.0,
    )
    assert failure is None, failure
    assert path[0] == start and path[-1] == goal
    assert {point.y for point in path} & {lower, upper}
    for a, b in zip(path, path[1:]):
        assert a.x == b.x or a.y == b.y
        assert _source_ink_collision(
            WireSegment(a, b, "A"), real,
            authorized_pins=frozenset(),
        ) is None
    assert circuit.components[0].origin == Point(20000, 10000)


def test_cycle12_real_tree_target_window_can_reach_25th_physical_T():
    # A compact source Net can have >24 exact authored branch positions.
    # The first 24 are genuinely INSIDE a prohibited component body; the
    # 25th is reachable by walking outside it. Do not synthesize a new T:
    # the only acceptable path ends at a supplied, real branch point.
    source = Point(4000, 5000)
    nearest_blocked = tuple(
        Point(12000 + 200 * i, 5000) for i in range(24)
    )
    actual_far_t = Point(45000, 5000)
    goals = (*nearest_blocked, actual_far_t)
    forbidden = (Box(10000, 2000, 35000, 8000),)

    def route(offset):
        return _visibility_path(
            source, Point(1, 0), goals,
            net_name="A", occupied=ExternalWireGraph(()), tree=(),
            existing_dots=(), goal_pin_normals={},
            ink_obstacles=(), authorized_pins=frozenset(),
            boxes=forbidden, page=Box(0, 0, 50000, 15000),
            stroke_um=300, search_node_cap=10000,
            grid_um=5000, max_detour_ratio=2.0,
            goal_offset=offset,
        )

    missing, reason = route(0)
    assert missing == () and reason is not None
    routed, reason = route(24)
    assert reason is None
    assert routed[0] == source and routed[-1] == actual_far_t
    assert all(
        not forbidden[0].contains_interior(p) for p in routed
    )
    assert all(a.x == b.x or a.y == b.y for a, b in zip(
        routed, routed[1:], strict=False,
    ))


@pytest.mark.parametrize("offset", (-1, 0.5, True))
def test_cycle12_real_tree_goal_window_bad_offset_rejected(offset):
    with pytest.raises(ValueError, match="ROUTE_INVALID_GOAL_WINDOW_OFFSET"):
        _visibility_path(
            Point(0, 0), Point(1, 0), (Point(10000, 0),),
            net_name="A", occupied=ExternalWireGraph(()), tree=(),
            existing_dots=(), goal_pin_normals={},
            ink_obstacles=(), authorized_pins=frozenset(),
            boxes=(), page=Box(-1000, -1000, 20000, 20000),
            stroke_um=300, search_node_cap=10000,
            grid_um=5000, max_detour_ratio=3.0,
            goal_offset=offset,
        )


def test_cycle12_source_congested_first_independent_from_graph_and_circuit():
    circuit, parts, symbols = native_three_terminal()
    preview = route_circuit_with_order_fallback(
        circuit, parts, symbols,
        page_box=Box(0, 0, 90000, 60000),
        priority_offset=3, try_priorities=2,
        max_order_restarts=0,
    )
    assert preview.source_circuit is circuit
    assert preview.route_order_trials == (
        ("CONGESTED_PIN_FANOUT_FIRST", 1, 0),
        ("CONGESTED_REVERSE_ROOTS", 1, 0),
    )
    assert preview.routing_strategy == "CONGESTED_PIN_FANOUT_FIRST"
    assert {w.net_name for w in preview.graph.segments} == {"A"}
    assert not preview.print_pass


@pytest.mark.parametrize("offset,trials", (
    (-1, 1), (6, 1), (5, 2), (3, 4), (0.5, 1),
    (True, 1), (0, False),
))
def test_cycle12_route_profile_range_fails_closed(offset, trials):
    circuit, parts, symbols = native_three_terminal()
    with pytest.raises(ValueError, match="ROUTE_INVALID_FUNCTIONAL_ORDER"):
        route_circuit_with_order_fallback(
            circuit, parts, symbols,
            page_box=Box(0, 0, 90000, 60000),
            priority_offset=offset, try_priorities=trials,
        )


def test_cycle12_duplicate_source_priority_cannot_revisit_occupied_net():
    circuit, parts, symbols = native_three_terminal()
    with pytest.raises(ValueError, match="ROUTE_INVALID_DUPLICATED_NET_PRIORITY"):
        route_circuit_net_trees(
            circuit, parts, symbols,
            page_box=Box(0, 0, 90000, 60000),
            priority=("A", "A"),
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


def test_same_source_two_pin_order_gets_bounded_detour_retry_around_real_UGO():
    circuit, parts, symbols = native_three_terminal()
    # X4 is a REAL but electrically unconnected symbol body blocking the
    # direct X1.1-to-X2.1 line. The frozen A-source membership is unchanged.
    guarded = replace(
        circuit,
        components=(*circuit.components,
                    ComponentInstance("X4", "terminal-bottom",
                                      Point(33000, 14000))),
        nets=(Net("A", (PinRef("X1", "1"), PinRef("X2", "1"))),),
    )
    initial = route_circuit_net_trees(
        guarded, parts, symbols, page_box=Box(0, 0, 90000, 60000),
        max_detour_ratio=1.05, max_order_restarts=0,
    )
    assert not initial.complete and not initial.print_pass
    assert initial.net_trees[0].diagnostics
    expanded = route_circuit_net_trees(
        guarded, parts, symbols, page_box=Box(0, 0, 90000, 60000),
        max_detour_ratio=1.05, max_order_restarts=1,
    )
    assert expanded.complete, expanded.diagnostics
    assert expanded.net_trees[0].search_restarts == 1
    assert expanded.net_trees[0].pin_refs == guarded.nets[0].members
    assert expanded.source_circuit == guarded
    assert expanded.drc is not None and expanded.drc.valid
    assert not expanded.print_pass  # no source-measured glyph authority


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


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_actual_diagonal_stroke_not_false_blocked_by_empty_AABB(rotation, mirror):
    symbol = SymbolDefinition(
        "native.diagonal", 1,
        (StyledLine(Point(0, 0), Point(10000, 10000), 300),),
        (GraphicPin("1", Point(-5000, 0), Side.LEFT),),
        Box(0, 0, 3000, 3000), 300,
    )
    part = PartDefinition(
        "native.diagonal", "X", "native.diagonal",
        (PhysicalPin("1", "P", ElectricalType.PASSIVE),),
    )
    tx = Transform(rotation, mirror)
    circuit = Circuit(
        (ComponentInstance("X1", part.identifier, Point(0, 0), tx),),
        (Net("A", (PinRef("X1", "1"),)),),
    )
    obstacles = _source_ink_obstacles(
        circuit, {symbol.identifier: symbol}, stroke_um=300,
    )
    clear = WireSegment(
        tx.apply(Point(1000, 9000)), tx.apply(Point(2000, 9000)), "A",
    )
    # The AABB around y=x contains the test segment, but the ink does not.
    assert _source_ink_collision(
        clear, obstacles, authorized_pins=frozenset(),
    ) is None
    # Cross y=x at x=1500, not a merely nearby parallel diagonal.
    # The previous y=x-900 probe had a 636µm true gap and could NOT touch
    # two 300µm strokes; asserting that collision was a faulty negative test.
    colliding = WireSegment(
        tx.apply(Point(1000, 900)), tx.apply(Point(2000, 2100)), "A",
    )
    hit = _source_ink_collision(
        colliding, obstacles, authorized_pins=frozenset(),
    )
    assert hit is not None
    assert hit.primitive_kind == "StyledLine"
    assert hit.owner == "X1"


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


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_source_tip_cap_remains_legal_when_outward_lane_split_by_grid(rotation, mirror):
    circuit, _, symbols = _mock_real_tl494_lead_forest()
    tx = Transform(rotation, mirror)
    part = circuit.components[0]
    posed = replace(
        circuit, components=(
            replace(part, origin=tx.apply(part.origin), transform=tx),
        ),
    )
    ink = _source_ink_obstacles(posed, symbols, stroke_um=300)
    allowed = frozenset({PinRef("DA1", "12")})
    tip = Point(205000, 138750)

    def wire(a, b):
        return WireSegment(tx.apply(a), tx.apply(b), "INPUT_POS")

    # Real 0.300mm printed wire plus 0.300mm physical lead: the 150µm
    # cap beyond the manufactured tip is a single continuous exposed lane.
    assert _source_ink_collision(
        wire(tip, Point(205040, 138750)), ink,
        authorized_pins=allowed,
    ) is None
    assert _source_ink_collision(
        wire(Point(205040, 138750), Point(205120, 138750)),
        ink, authorized_pins=allowed,
    ) is None
    assert _source_ink_collision(
        wire(Point(205120, 138750), Point(206000, 138750)),
        ink, authorized_pins=allowed,
    ) is None
    # 50µm behind the physical tip is IN the DA1 pin lead, and cannot be
    # exempted even if the resulting segment eventually goes outward.
    assert _source_ink_collision(
        wire(Point(204950, 138750), Point(205040, 138750)),
        ink, authorized_pins=allowed,
    ) is not None
    # No generic same-owner bypass, even for a segment touching the tip.
    assert _source_ink_collision(
        wire(tip, Point(205040, 138750)),
        ink, authorized_pins=frozenset({PinRef("DA1", "8")}),
    ) is not None
    # A diagonal or transverse move inside the pin cap is never its
    # *sourced* straight physical lead escape.
    assert _source_ink_collision(
        wire(Point(205030, 138750), Point(205080, 138780)),
        ink, authorized_pins=allowed,
    ) is not None


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


def test_no_path_reports_real_foreign_wire_3mm_and_exact_trial_coordinates():
    # With detour ratio exactly 1.0, the only shortest route would
    # longitudinally overprint this real other-Net conductor. It MUST fail
    # even if that projected wire would have been visually connected.
    occupied = ExternalWireGraph((
        WireSegment(Point(15000, 10200), Point(35000, 10200), "B"),
    ))
    source, target = Point(5000, 10000), Point(45000, 10000)
    route, diagnostic = _visibility_path(
        source, Point(1, 0), (target,),
        net_name="A", occupied=occupied, tree=(),
        existing_dots=(), goal_pin_normals={},
        ink_obstacles=(), authorized_pins=frozenset(),
        boxes=(), page=Box(0, 0, 50000, 20000),
        stroke_um=300, search_node_cap=25000,
        grid_um=5000, max_detour_ratio=1.0,
    )
    assert route == ()
    assert diagnostic is not None
    assert diagnostic.startswith("ROUTE_NO_CLEAR_ORTHOGONAL_TREE_PATH")
    # The shortest-path search samples *actual* edges, so its genuine first
    # conflicting edges are endpoint contact/nonparallel guards rather than
    # a guaranteed longitudinally parallel overlap. Assert observed vetoes,
    # not a physically nonexistent candidate which Dijkstra never proposed.
    assert "WIRE_VETO=B:DRC_FOREIGN_NET_ENDPOINT_CONTACT" in diagnostic
    assert "B:DRC_NONPARALLEL_EDITORIAL_INK_GUARD" in diagnostic
    # Check the 3mm parallel rule with two *real* collinear-axis conductor
    # candidates independently instead of relying on a sampled search edge.
    parallel = candidate_wire_clearance(
        WireSegment(Point(16000, 10000), Point(30000, 10000), "A"),
        occupied.segments[0],
    )
    assert not parallel.valid
    assert "DRC_PARALLEL_STROKE_CLEARANCE" in parallel.errors
    assert "existing=15000,10200->35000,10200" in diagnostic
    assert "trial=" in diagnostic
    assert occupied.segments[0].net_name == "B"


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
