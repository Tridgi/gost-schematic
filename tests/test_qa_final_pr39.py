"""Independent adversarial regression of NEW PR39 SHA 1a137562, not old PR53.

All route functions execute frozen SHA-verified source extracted from that head.
Real part/symbol data and electrical validator come from current integration.
"""
from itertools import pairwise
from random import Random

import pytest

from examples.review_end_to_end_circuit import definitions
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)
from scripts.qa_final_pr39_loader import HEAD, MODULES, load_frozen_pr39

SOURCE = PinRef("R1", "1")
TARGET = PinRef("R2", "1")
PART_TYPES = (
    "resistor.fixed",
    "capacitor.fixed",
    "capacitor.polarized",
    "capacitor.electrolytic",
    "inductor.tapped",
)


@pytest.fixture(scope="module")
def engine():
    return load_frozen_pr39()


@pytest.fixture(scope="module")
def catalog():
    return definitions()


def _codes(result):
    return {issue.code for issue in result.diagnostics}


def _point(x, y):
    return Point(x, y)


def _place(catalog, ref, part, pin, contact, transform=Transform()):
    _, symbols = catalog
    local = next(p.at for p in symbols[part].pins if p.number == pin)
    offset = transform.apply(local)
    return ComponentInstance(
        ref, part, _point(contact.x - offset.x, contact.y - offset.y),
        transform,
    )


def _edges(route):
    return tuple(Line(a, b) for a, b in pairwise(route.points))


def _on_segment(segment, point):
    a, b = segment.start, segment.end
    return (
        (b.x - a.x) * (point.y - a.y)
        == (b.y - a.y) * (point.x - a.x)
        and min(a.x, b.x) <= point.x <= max(a.x, b.x)
        and min(a.y, b.y) <= point.y <= max(a.y, b.y)
    )


def _sheet(catalog, tx=Transform(), blocker_part="resistor.fixed", miss=0):
    source = tx.apply(_point(0, -14000))
    target = tx.apply(_point(0, 14000))
    middle = tx.apply(_point(miss, 0))
    first = _place(catalog, "R1", "resistor.fixed", "1", source, tx)
    obstacle = _place(catalog, "R3", blocker_part, "1", middle, tx)
    last = _place(catalog, "R2", "resistor.fixed", "1", target, tx)
    return (
        Circuit((first, obstacle, last), (Net("LINK", (SOURCE, TARGET)),)),
        middle, source, target,
    )


def _parts(catalog, circuit):
    parts, symbols = catalog
    chosen = {c.part_id: parts[c.part_id] for c in circuit.components}
    drawn = {p.symbol_id: symbols[p.symbol_id] for p in chosen.values()}
    return chosen, drawn


def _safe(route, start, end):
    assert route.ok and route.diagnostics == (), route.diagnostics
    assert route.points[0] == start and route.points[-1] == end
    assert all(
        (s.start.x == s.end.x) != (s.start.y == s.end.y)
        for s in _edges(route)
    )
    assert route.external_graph("LINK").junctions == ()


def _foreign(width, net="FOREIGN"):
    return WireObstacle(
        f"foreign-{width}", Line(_point(5000, -1000), _point(5000, 1000)),
        stroke_um=width, net_name=net,
    )


def test_pr39_source_is_distinct_from_previously_audited_pr53(engine):
    old_blob = "50b9102191fbe7f5876b14bd9ef10dcbbb1fe600"
    assert HEAD == "1a1375623c0f098cac14f7843c44d75982a4d749"
    assert all(blob != old_blob for _name, _path, blob in MODULES)
    assert engine[0].__file__.endswith("qa_pr39_1a137562_orthogonal.py")
    assert engine[1].__file__.endswith("qa_pr39_1a137562_sheet.py")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("part_id", PART_TYPES)
def test_50_safe_adapter_independently_protects_real_all_8_ugo_transformations(
    engine, catalog, rotation, mirror, part_id,
):
    _, sheet = engine
    circuit, unrelated_pin, start, end = _sheet(
        catalog, Transform(rotation, mirror), part_id
    )
    old_netlist = circuit.nets
    old_components = circuit.components
    parts, symbols = _parts(catalog, circuit)
    route = sheet.route_circuit_two_pins(
        circuit, parts, symbols, SOURCE, TARGET,
        net_name="LINK", max_cells=25000,
    )
    _safe(route, start, end)
    assert not any(_on_segment(s, unrelated_pin) for s in _edges(route)), (
        part_id, rotation, mirror, unrelated_pin, route.points
    )
    assert validate_external_wires(
        circuit, route.external_graph("LINK"), parts, symbols
    ) == ()
    assert (circuit.nets, circuit.components) == (old_netlist, old_components)


def test_50_adapter_routes_around_unassigned_contact_at_exact_old_reproducer(
    engine, catalog,
):
    low, sheet = engine
    circuit, free_pin, source, target = _sheet(catalog)
    parts, symbols = _parts(catalog, circuit)
    # The old GEOMETRY-ONLY entrypoint is explicitly not a safe-sheet API.
    body_only = tuple(
        c.transform.box(symbols[parts[c.part_id].symbol_id].body_keepout)
        .translated(c.origin)
        for c in circuit.components
    )
    old_unsafe = low.route_two_pins(
        source, target, keepouts=body_only, max_cells=25000
    )
    assert old_unsafe.ok
    assert any(_on_segment(seg, free_pin) for seg in _edges(old_unsafe))
    assert "WIRE_PIN_CONTACT_UNDECLARED" in {
        issue.code for issue in validate_external_wires(
            circuit, old_unsafe.external_graph("LINK"), parts, symbols
        )
    }

    result = sheet.route_circuit_two_pins(
        circuit, parts, symbols, SOURCE, TARGET,
        net_name="LINK", max_cells=25000,
    )
    _safe(result, source, target)
    assert not any(_on_segment(seg, free_pin) for seg in _edges(result))
    assert result.points != old_unsafe.points
    assert validate_external_wires(
        circuit, result.external_graph("LINK"), parts, symbols
    ) == ()


@pytest.mark.parametrize("width", [101, 299, 300, 1000, 1401])
def test_52_actual_odd_even_foreign_strokes_obey_independent_printed_clearance(
    engine, width,
):
    low, _sheet_module = engine
    wire = _foreign(width)
    route = low.route_two_pins(
        _point(0, 0), _point(10000, 0),
        foreign_wires=(wire,), grid_um=100,
        stroke_um=300, clearance_um=400, max_cells=15000,
    )
    _safe(route, _point(0, 0), _point(10000, 0))
    margin = 400 + (width + 1) // 2 + (300 + 1) // 2
    ink_occupied = Box(5000, -1000, 5001, 1001).expanded(margin)
    assert all(
        not segment_intersects_box(edge, ink_occupied)
        for edge in _edges(route)
    )


def test_52_unknown_foreign_width_fails_closed_instead_of_assuming_width(
    engine,
):
    low, _sheet_module = engine
    wire = WireSegment(_point(5000, -1000), _point(5000, 1000), "OTHER")
    route = low.route_two_pins(
        _point(0, 0), _point(10000, 0), existing_wires=(wire,),
    )
    assert not route.points and _codes(route) == {"ROUTE_FOREIGN_WIDTH_REQUIRED"}
    with pytest.raises(ValueError):
        route.external_graph("LINK")


def test_51_remote_obstacle_does_not_consume_local_route_cell_budget(engine):
    low, _sheet_module = engine
    remote = Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)
    start, end = _point(0, 0), _point(1000, 0)
    actual = low.route_two_pins(
        start, end, keepouts=(remote,), max_cells=1000,
    )
    _safe(actual, start, end)
    assert actual.points == (start, end)


def test_51_search_window_expands_around_nearby_barrier_without_remote_pollution(
    engine,
):
    low, _sheet_module = engine
    start, end = _point(0, 0), _point(10000, 0)
    nearby = Box(4000, -4000, 6000, 4000)
    remote = Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)
    route = low.route_two_pins(
        start, end, keepouts=(nearby, remote), max_cells=25000,
    )
    _safe(route, start, end)
    assert all(
        not segment_intersects_box(seg, nearby.expanded(550))
        for seg in _edges(route)
    )
    assert route == low.route_two_pins(
        start, end, keepouts=(nearby,), max_cells=25000,
    )


@pytest.mark.parametrize("blocked_type", ["keepout", "foreign"])
def test_blocked_ports_do_not_generate_partial_wires(engine, blocked_type):
    low, _sheet_module = engine
    start, end = _point(0, 0), _point(10000, 0)
    kw = (
        {"keepouts": (Box(-1000, -1000, 1000, 1000),)}
        if blocked_type == "keepout"
        else {
            "foreign_wires": (
                WireObstacle(
                    "cover", Line(_point(0, -1000), _point(0, 1000)),
                    stroke_um=1000,
                ),
            ),
        }
    )
    result = low.route_two_pins(start, end, **kw)
    assert _codes(result) == {"ROUTE_PORT_BLOCKED"} and not result.points
    with pytest.raises(ValueError):
        result.external_graph("LINK")


def test_impossible_bounded_route_returns_no_path_not_false_success(engine):
    low, _sheet_module = engine
    start, end = _point(0, 0), _point(20000, 0)
    result = low.route_two_pins(
        start, end, keepouts=(Box(9000, -10000, 11000, 10000),),
        bounds=Box(0, -10000, 20000, 10000),
        max_cells=25000,
    )
    assert not result.points and _codes(result) == {"ROUTE_NO_PATH"}


def test_cell_cap_reports_explicit_failure_when_even_first_local_window_is_too_big(
    engine,
):
    low, _sheet_module = engine
    result = low.route_two_pins(
        _point(0, 0), _point(50000, 0), max_cells=20,
    )
    assert _codes(result) == {"ROUTE_CELL_LIMIT"} and not result.points


def test_adapter_checks_physical_identity_net_and_extra_keepouts(engine, catalog):
    _low, sheet = engine
    circuit, free, source, target = _sheet(catalog)
    parts, symbols = _parts(catalog, circuit)
    wrong = sheet.route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "2"), TARGET, net_name="LINK",
    )
    assert _codes(wrong) == {"ROUTE_NET_INVALID"}
    extra = sheet.route_circuit_two_pins(
        circuit, parts, symbols, SOURCE, TARGET,
        net_name="LINK", keepouts=(Box(
            source.x - 1000, source.y - 1000,
            source.x + 1000, source.y + 1000,
        ),),
    )
    assert _codes(extra) == {"ROUTE_PORT_BLOCKED"}
    assert not wrong.points and not extra.points
    assert free not in (source, target)


def test_58_foreign_net_touching_already_assigned_terminal_is_blocked_before_erc(
    engine, catalog,
):
    """Known #58 validator hole should not be reachable via typed safe adapter."""
    _low, sheet = engine
    a0, a1 = _point(-20000, 0), _point(0, 0)
    b0, b1 = _point(0, -10000), _point(0, 10000)
    r1 = _place(catalog, "R1", "resistor.fixed", "1", a1)
    r2 = _place(catalog, "R2", "resistor.fixed", "1", a0, Transform(180))
    r3 = _place(catalog, "R3", "resistor.fixed", "1", b0, Transform(270))
    r4 = _place(catalog, "R4", "resistor.fixed", "1", b1, Transform(90))
    circuit = Circuit(
        (r1, r2, r3, r4),
        (
            Net("A", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("B", (PinRef("R3", "1"), PinRef("R4", "1"))),
        ),
    )
    parts, symbols = _parts(catalog, circuit)
    graph = ExternalWireGraph((
        WireSegment(a0, a1, "A"), WireSegment(b0, b1, "B"),
    ))
    # Existing issue #58: validator currently misses this malformed input.
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    unsafe_foreign = WireObstacle(
        "bad-B", Line(b0, b1), stroke_um=300, net_name="B",
    )
    route = sheet.route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R2", "1"), PinRef("R1", "1"),
        net_name="A", foreign_wires=(unsafe_foreign,), max_cells=25000,
    )
    assert _codes(route) == {"ROUTE_PORT_BLOCKED"} and route.points == ()


def test_multi_net_sheet_adapter_fails_closed_on_foreign_net_unverified_graph(
    engine, catalog,
):
    """No silent safety certification for all other nets by checking only LINK."""
    _low, sheet = engine
    a0, a1 = _point(0, 0), _point(20000, 0)
    b0, b1 = _point(0, 30000), _point(20000, 30000)
    components = (
        _place(catalog, "R1", "resistor.fixed", "1", a0),
        _place(catalog, "R2", "resistor.fixed", "1", a1),
        _place(catalog, "R3", "resistor.fixed", "1", b0),
        _place(catalog, "R4", "resistor.fixed", "1", b1),
    )
    circuit = Circuit(
        components,
        (
            Net("A", (PinRef("R1", "1"), PinRef("R2", "1"))),
            Net("B", (PinRef("R3", "1"), PinRef("R4", "1"))),
        ),
    )
    parts, symbols = _parts(catalog, circuit)
    wire = WireObstacle("foreign-B", Line(b0, b1), stroke_um=300, net_name="B")
    result = sheet.route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
        net_name="A", foreign_wires=(wire,), max_cells=25000,
    )
    assert not result.ok and not result.points
    assert _codes(result) == {"ROUTE_ELECTRICAL_REJECTED"}


def test_stable_output_under_randomized_hazard_order_and_repeat_calls(engine):
    low, _sheet_module = engine
    rng = Random(390139)
    hazards = tuple(
        Box(rng.randrange(5000, 13000, 1000),
            rng.randrange(-5000, 6000, 1000),
            rng.randrange(13000, 19000, 1000),
            rng.randrange(6000, 11000, 1000))
        for _ in range(4)
    )
    start, end = _point(0, 0), _point(30000, 0)
    first = low.route_two_pins(
        start, end, keepouts=hazards, max_cells=25000,
    )
    _safe(first, start, end)
    for _ in range(8):
        assert low.route_two_pins(
            start, end, keepouts=hazards[::-1], max_cells=25000,
        ) == first
