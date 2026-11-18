"""Issue #55: independent reproductions of QA #50/#51/#52 and real catalog cases."""

from dataclasses import FrozenInstanceError
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import definitions
from examples.review_two_pin_routing import report_json, specimen_svg
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.two_pin_orthogonal import route_two_pins
from gost_schematic.engines.routing.two_pin_sheet import route_circuit_two_pins
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.validation.external_wire_checks import (
    WireSegment,
    validate_external_wires,
)

CATALOG = (
    "resistor.fixed",
    "capacitor.fixed",
    "capacitor.polarized",
    "capacitor.electrolytic",
    "inductor.tapped",
)


@pytest.fixture(scope="module")
def real_catalog():
    return definitions()


def p(x, y):
    return Point(x, y)


def segments(route):
    return tuple(Line(a, b) for a, b in zip(
        route.points, route.points[1:], strict=False
    ))


def codes(result):
    return {item.code for item in result.diagnostics}


def centerline_through(line, point):
    return segment_intersects_box(
        line, Box(point.x - 1, point.y - 1, point.x + 1, point.y + 1)
    )


def _at_pin(ref, part_id, target, pin, symbols, transform=None):
    if transform is None:
        transform = Transform()
    local = next(item.at for item in symbols[part_id].pins if item.number == pin)
    world_offset = transform.apply(local)
    return ComponentInstance(
        ref, part_id,
        p(target.x - world_offset.x, target.y - world_offset.y),
        transform,
    )


def _catalog_sheet(
    catalog, part_id="resistor.fixed", rotation=0,
    mirror=False, direction=(0, 1), miss=0,
):
    _, symbols = catalog
    dx, dy = direction
    start = p(-50000 * dx, -50000 * dy)
    target = p(50000 * dx, 50000 * dy)
    # One micrometre perpendicular shift of the non-net physical contact.
    contact = p(-dy * miss, dx * miss)
    first = _at_pin("R1", "resistor.fixed", start, "1", symbols)
    blocker = _at_pin(
        "R3", part_id, contact, "1", symbols, Transform(rotation, mirror)
    )
    last = _at_pin("R2", "resistor.fixed", target, "1", symbols)
    circuit = Circuit(
        (first, blocker, last),
        (Net("LINK", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    assert blocker.pin_positions(symbols[part_id])["1"] == contact
    return circuit, contact, start, target


def test_exact_QA_50_resistor_reproducer_with_all_real_body_keepouts(real_catalog):
    parts, symbols = real_catalog
    circuit = Circuit(
        (
            ComponentInstance("R1", "resistor.fixed", p(8000, -10000)),
            ComponentInstance("R3", "resistor.fixed", p(8000, 0)),
            ComponentInstance("R2", "resistor.fixed", p(8000, 10000)),
        ),
        (Net("LINK", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    # The original geometry-only entry point had all three body keepouts,
    # but no physical terminal list. This exact example used to return an
    # unsafe straight conductor through unassigned R3.1 at (0, 0).
    body_keepouts = tuple(
        c.transform.box(symbols[parts[c.part_id].symbol_id].body_keepout)
        .translated(c.origin) for c in circuit.components
    )
    assert all(not box.includes(p(0, 0)) for box in body_keepouts)
    result = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
        net_name="LINK", max_cells=5000,
    )
    assert result.ok, result.diagnostics
    assert result.points[0] == p(0, -10000)
    assert result.points[-1] == p(0, 10000)
    assert len(result.points) >= 4
    assert all(not centerline_through(line, p(0, 0)) for line in segments(result))
    assert validate_external_wires(
        circuit, result.external_graph("LINK"), parts, symbols
    ) == ()
    assert result.external_graph("LINK").junctions == ()
    assert circuit.nets[0].members == (PinRef("R1", "1"), PinRef("R2", "1"))


@pytest.mark.parametrize("part_id", CATALOG)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("direction", ((1, 0), (0, 1), (-1, 0), (0, -1)))
def test_physical_pin_excluded_for_real_catalog_transform_and_all_approaches(
    real_catalog, part_id, rotation, mirror, direction,
):
    parts, symbols = real_catalog
    circuit, contact, start, end = _catalog_sheet(
        real_catalog, part_id, rotation, mirror, direction,
    )
    result = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
        net_name="LINK", max_cells=25000,
    )
    assert result.ok, result.diagnostics
    assert result.points[0] == start and result.points[-1] == end
    assert all(not centerline_through(line, contact) for line in segments(result))
    assert result.external_graph("LINK").junctions == ()
    assert validate_external_wires(
        circuit, result.external_graph("LINK"), parts, symbols
    ) == ()


@pytest.mark.parametrize("part_id", CATALOG)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_one_um_perpendicular_near_miss_preserves_exact_physical_identity(
    real_catalog, part_id, rotation, mirror,
):
    parts, symbols = real_catalog
    circuit, contact, start, end = _catalog_sheet(
        real_catalog, part_id, rotation, mirror, (0, 1), miss=1,
    )
    assert contact == p(-1, 0)
    route = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
        net_name="LINK", max_cells=25000,
    )
    assert route.ok, route.diagnostics
    assert route.points[0] == start and route.points[-1] == end
    # A 1 µm geometric miss is not treated as an electrical attachment.
    assert all(not centerline_through(line, contact) for line in segments(route))
    assert validate_external_wires(
        circuit, route.external_graph("LINK"), parts, symbols
    ) == ()


def test_QA_51_remote_keepout_never_consumes_local_budget():
    a, b = p(0, 0), p(1000, 0)
    remote = Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)
    for keepouts in ((remote,), (remote, Box(-1000000, 20000, -999000, 21000))):
        result = route_two_pins(a, b, keepouts=keepouts, max_cells=1000)
        assert result.points == (a, b) and result.diagnostics == ()
    window = Box(-1000, -1000, 2000, 1000)
    assert route_two_pins(
        a, b, keepouts=(remote,), bounds=window, max_cells=1000,
    ).points == (a, b)


def test_adaptive_search_finds_farther_detour_without_remote_box_growth():
    wall = Box(4000, -3500, 6000, 3500)
    result = route_two_pins(
        p(0, 0), p(10000, 0),
        keepouts=(wall, Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)),
        max_cells=3000,
    )
    assert result.ok, result.diagnostics
    assert len(result.points) == 4
    assert all(
        not segment_intersects_box(edge, wall.expanded(550))
        for edge in segments(result)
    )


def test_QA_52_1000_um_foreign_ink_respects_actual_edge_clearance():
    foreign = WireObstacle(
        "FOREIGN", Line(p(5000, -1000), p(5000, 1000)),
        stroke_um=1000, net_name="OTHER",
    )
    route = route_two_pins(
        p(0, 0), p(10000, 0),
        foreign_wires=(foreign,), grid_um=100,
        stroke_um=300, clearance_um=400, max_cells=10000,
    )
    assert route.ok, route.diagnostics
    protection = Box(5000, -1000, 5001, 1001).expanded(400 + 500 + 150)
    assert all(
        not segment_intersects_box(item, protection) for item in segments(route)
    )
    assert route.external_graph("LINK").junctions == ()


def test_foreign_widths_100_300_1000_all_use_their_own_actual_strokes():
    for foreign_width in (100, 300, 1000):
        wire = WireObstacle(
            f"foreign-{foreign_width}", Line(p(5000, -1000), p(5000, 1000)),
            stroke_um=foreign_width, net_name="OTHER",
        )
        route = route_two_pins(
            p(0, 0), p(10000, 0),
            foreign_wires=(wire,), grid_um=100,
            stroke_um=300, clearance_um=400, max_cells=10000,
        )
        assert route.ok, (foreign_width, route.diagnostics)
        excluded = Box(5000, -1000, 5001, 1001).expanded(
            400 + (300 + 1) // 2 + (foreign_width + 1) // 2
        )
        assert all(
            not segment_intersects_box(edge, excluded) for edge in segments(route)
        )


def test_mixed_widths_and_order_independent_and_original_ink_preserved():
    thick = WireObstacle(
        "thick", Line(p(5000, -1000), p(5000, 1000)),
        stroke_um=1000, net_name="OTHER",
    )
    thin = WireObstacle(
        "thin", Line(p(12000, -1000), p(12000, 1000)),
        stroke_um=100, net_name="LINK",
    )
    original = (thick, thin)
    first = route_two_pins(
        p(0, 0), p(16000, 0), foreign_wires=original,
        grid_um=100, max_cells=14000,
    )
    assert first.ok, first.diagnostics
    for _ in range(5):
        flipped = route_two_pins(
            p(0, 0), p(16000, 0), foreign_wires=original[::-1],
            grid_um=100, max_cells=14000,
        )
        assert flipped == first
    assert (thick.stroke_um, thin.stroke_um) == (1000, 100)
    for wire in original:
        ink_box = Box(
            min(wire.line.start.x, wire.line.end.x),
            min(wire.line.start.y, wire.line.end.y),
            max(wire.line.start.x, wire.line.end.x) + 1,
            max(wire.line.start.y, wire.line.end.y) + 1,
        ).expanded(400 + 150 + (wire.stroke_um + 1) // 2)
        assert all(
            not segment_intersects_box(edge, ink_box)
            for edge in segments(first)
        )


def test_widthless_wire_fails_closed_and_does_not_invent_300_um():
    wire = WireSegment(p(5000, -1000), p(5000, 1000), "OTHER")
    result = route_two_pins(p(0, 0), p(10000, 0), existing_wires=(wire,))
    assert codes(result) == {"ROUTE_FOREIGN_WIDTH_REQUIRED"} and not result.points
    with pytest.raises(ValueError, match="No completed"):
        result.external_graph("LINK")
    zero = WireObstacle(
        "bad-width", Line(p(5000, -1000), p(5000, 1000)),
        stroke_um=0, net_name="OTHER",
    )
    assert codes(route_two_pins(
        p(0, 0), p(10000, 0), foreign_wires=(zero,),
    )) == {"ROUTE_FOREIGN_WIDTH_REQUIRED"}


def test_same_net_foreign_conductor_is_still_conservatively_excluded():
    same = WireObstacle(
        "same", Line(p(5000, -1000), p(5000, 1000)),
        stroke_um=1000, net_name="LINK",
    )
    result = route_two_pins(
        p(0, 0), p(10000, 0), foreign_wires=(same,),
        grid_um=100, max_cells=10000,
    )
    assert result.ok and len(result.points) >= 4
    assert result.external_graph("LINK").junctions == ()


def test_explicit_fixed_window_no_path_and_genuine_budget_limit():
    blocked = route_two_pins(
        p(0, 0), p(10000, 0),
        keepouts=(Box(4000, -10000, 6000, 10000),),
        bounds=Box(0, -10000, 10000, 10000),
    )
    assert codes(blocked) == {"ROUTE_NO_PATH"}
    assert codes(route_two_pins(
        p(0, 0), p(10000, 0), max_cells=10,
    )) == {"ROUTE_CELL_LIMIT"}


def test_adapter_rejects_wrong_membership_no_partial_wire(real_catalog):
    parts, symbols = real_catalog
    circuit, _, _, _ = _catalog_sheet(real_catalog)
    route = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "2"), PinRef("R2", "1"),
        net_name="LINK",
    )
    assert codes(route) == {"ROUTE_NET_INVALID"}
    assert route.points == ()


def test_safe_specimen_svg_and_json_share_the_same_computed_graph():
    clean = specimen_svg()
    review = specimen_svg(review=True)
    assert clean == specimen_svg() and review == specimen_svg(review=True)
    assert ET.fromstring(clean) is not None
    assert ET.fromstring(review) is not None
    assert report_json() == report_json()


def test_no_mutation_of_printed_foreign_width_or_model(real_catalog):
    parts, symbols = real_catalog
    circuit, _, _, _ = _catalog_sheet(real_catalog)
    wire = WireObstacle(
        "other", Line(p(20000, 0), p(20000, 1000)),
        stroke_um=1000, net_name="OTHER",
    )
    before = (circuit.components, circuit.nets, wire)
    _ = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
        net_name="LINK", foreign_wires=(wire,),
    )
    assert before == (circuit.components, circuit.nets, wire)
    with pytest.raises(FrozenInstanceError):
        wire.stroke_um = 300
