"""Independent PR #39 (SHA-pinned) adversarial routing audit, no production edits.

Unlike the author suite, these cases use extra real physical pin identities,
unassigned terminals, far-away hazards, bounded corridors and seed-controlled
component transformations. Source is loaded from immutable PR commit by
scripts.qa_followup_pr39, not copied into the QA pull request.
"""

from random import Random

import pytest

from examples.review_end_to_end_circuit import definitions
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    WireSegment,
    validate_external_wires,
)
from scripts.qa_followup_pr39 import load_pr39_router


@pytest.fixture(scope="module")
def router():
    return load_pr39_router()


@pytest.fixture(scope="module")
def catalog():
    return definitions()


def _parts(catalog, *instances):
    parts, symbols = catalog
    selected = {item.part_id: parts[item.part_id] for item in instances}
    graphics = {part.symbol_id: symbols[part.symbol_id] for part in selected.values()}
    return selected, graphics


def _pins(catalog, instance):
    parts, symbols = catalog
    return instance.pin_positions(symbols[parts[instance.part_id].symbol_id])


def _keepouts(catalog, *instances):
    parts, symbols = catalog
    return tuple(
        component.transform.box(
            symbols[parts[component.part_id].symbol_id].body_keepout
        ).translated(component.origin)
        for component in instances
    )


def _edges(route):
    return tuple(
        Line(a, b) for a, b in zip(route.points, route.points[1:], strict=False)
    )


def _contains_point(line, point):
    start, end = line.start, line.end
    cross = (end.x - start.x) * (point.y - start.y) - (
        end.y - start.y
    ) * (point.x - start.x)
    return (
        cross == 0
        and min(start.x, end.x) <= point.x <= max(start.x, end.x)
        and min(start.y, end.y) <= point.y <= max(start.y, end.y)
    )


def _assert_route_structure(route, source, target, keepouts=(), margin=550):
    assert route.ok and not route.diagnostics, route.diagnostics
    assert route.points[0] == source and route.points[-1] == target
    assert all(edge.start != edge.end for edge in _edges(route))
    assert all(
        (edge.start.x == edge.end.x) != (edge.start.y == edge.end.y)
        for edge in _edges(route)
    )
    assert all(
        not segment_intersects_box(edge, box.expanded(margin))
        for edge in _edges(route) for box in keepouts
    )
    assert len(route.external_graph("LINK").segments) == len(route.points) - 1
    assert route.external_graph("LINK").junctions == ()


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_pin_routes_with_rotated_and_mirrored_ugo_keep_all_nets_exact(
    router, catalog, rotation, mirror,
):
    tx = Transform(rotation, mirror)
    first = ComponentInstance("R1", "resistor.fixed", Point(0, 0), tx)
    blocker = ComponentInstance("R3", "resistor.fixed", Point(40000, 10000), tx)
    last = ComponentInstance(
        "C1", "capacitor.electrolytic", Point(80000, 20000), tx
    )
    source = _pins(catalog, first)["2"]
    target = _pins(catalog, last)["1"]
    circuit = Circuit(
        (first, blocker, last),
        (Net("LINK", (PinRef("R1", "2"), PinRef("C1", "1"))),),
    )
    keepouts = _keepouts(catalog, *circuit.components)
    result = router.route_two_pins(
        source, target, keepouts=keepouts, max_cells=25000
    )
    _assert_route_structure(result, source, target, keepouts)
    parts, graphics = _parts(catalog, *circuit.components)
    assert validate_external_wires(
        circuit, result.external_graph("LINK"), parts, graphics
    ) == ()


def test_real_pin_blocked_by_an_existing_foreign_wire_never_returns_partial_graph(
    router, catalog,
):
    first = ComponentInstance("R1", "resistor.fixed", Point(0, 0))
    last = ComponentInstance("C1", "capacitor.electrolytic", Point(90000, 0))
    source = _pins(catalog, first)["2"]
    target = _pins(catalog, last)["1"]
    foreign = WireSegment(
        Point(source.x, -10000), Point(source.x, 10000), "FOREIGN"
    )
    result = router.route_two_pins(
        source, target,
        keepouts=_keepouts(catalog, first, last),
        existing_wires=(foreign,),
    )
    assert {item.code for item in result.diagnostics} == {"ROUTE_PORT_BLOCKED"}
    assert not result.ok and result.points == ()
    with pytest.raises(ValueError):
        result.external_graph("LINK")


def test_seeded_component_blocker_permutations_cannot_change_path(router, catalog):
    rng = Random(3944007)
    first = ComponentInstance("R1", "resistor.fixed", Point(0, 0))
    last = ComponentInstance(
        "C1", "capacitor.electrolytic", Point(65000, 20000)
    )
    source = _pins(catalog, first)["2"]
    target = _pins(catalog, last)["1"]
    for index in range(12):
        ox = rng.randrange(24000, 38001, 1000)
        oy = rng.randrange(-10000, 26001, 1000)
        blocker = ComponentInstance(
            "R3", "resistor.fixed", Point(ox, oy),
            Transform((index % 4) * 90, bool(index % 2)),
        )
        hazards = _keepouts(catalog, first, blocker, last)
        canonical = router.route_two_pins(
            source, target, keepouts=hazards, max_cells=25000
        )
        reversed_order = router.route_two_pins(
            source, target, keepouts=tuple(reversed(hazards)), max_cells=25000
        )
        assert canonical == reversed_order, (index, canonical, reversed_order)
        assert canonical.ok, (index, canonical.diagnostics)
        _assert_route_structure(canonical, source, target, hazards)


@pytest.mark.xfail(reason="Confirmed issue #50: real unassigned pin crosses routed wire", strict=True)
def test_pinned_router_passes_through_real_unassigned_pin_outside_all_body_keepouts(
    router, catalog,
):
    """New cross-layer risk: body keepouts alone do not protect free lead tips."""
    first = ComponentInstance("R1", "resistor.fixed", Point(8000, -10000))
    middle = ComponentInstance("R3", "resistor.fixed", Point(8000, 0))
    last = ComponentInstance("R2", "resistor.fixed", Point(8000, 10000))
    circuit = Circuit(
        (first, middle, last),
        (Net("LINK", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    source = _pins(catalog, first)["1"]
    target = _pins(catalog, last)["1"]
    unrelated_pin = _pins(catalog, middle)["1"]
    hazards = _keepouts(catalog, *circuit.components)
    result = router.route_two_pins(
        source, target, keepouts=hazards, max_cells=5000
    )
    _assert_route_structure(result, source, target, hazards)
    parts, graphics = _parts(catalog, *circuit.components)
    # Existing #40 validator also misses the contact, causing false confidence.
    assert validate_external_wires(
        circuit, result.external_graph("LINK"), parts, graphics
    ) == ()
    assert unrelated_pin not in (source, target)
    assert not any(_contains_point(edge, unrelated_pin) for edge in _edges(result)), (
        "Router placed a real unassigned pin R3.1 directly on the new net"
    )


@pytest.mark.xfail(reason="Confirmed issue #51: unrelated keepout triggers cell limit", strict=True)
def test_remote_irrelevant_obstacle_does_not_exhaust_cell_budget_for_clear_direct_path(
    router,
):
    """The source/end region is clear; remote geometry must not doom local routing."""
    remote = Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)
    source, target = Point(0, 0), Point(1000, 0)
    constrained = router.route_two_pins(
        source, target, keepouts=(remote,),
        bounds=Box(-1000, -1000, 2000, 1000),
        max_cells=1000,
    )
    assert constrained.ok and constrained.points == (source, target)
    unconstrained = router.route_two_pins(
        source, target, keepouts=(remote,), max_cells=1000,
    )
    assert unconstrained.ok, unconstrained.diagnostics
    assert unconstrained.points == (source, target)


def test_explicit_protection_of_extra_physical_pin_prevents_accidental_tie(
    router, catalog,
):
    """Positive control: the consumer can pass a physical terminal exclusion."""
    first = ComponentInstance("R1", "resistor.fixed", Point(8000, -10000))
    middle = ComponentInstance("R3", "resistor.fixed", Point(8000, 0))
    last = ComponentInstance("R2", "resistor.fixed", Point(8000, 10000))
    source = _pins(catalog, first)["1"]
    target = _pins(catalog, last)["1"]
    unwanted = _pins(catalog, middle)["1"]
    extra = Box(unwanted.x - 500, unwanted.y - 500,
                unwanted.x + 500, unwanted.y + 500)
    hazards = (*_keepouts(catalog, first, middle, last), extra)
    result = router.route_two_pins(
        source, target, keepouts=hazards, max_cells=5000
    )
    _assert_route_structure(result, source, target, hazards)
    assert not any(_contains_point(edge, unwanted) for edge in _edges(result))


def test_real_blocker_forms_a_no_path_wall_only_inside_constrained_sheet(router, catalog):
    """Negative scenario: one real resistor body spans entire fixed routing window."""
    first = ComponentInstance("R1", "resistor.fixed", Point(-8000, 0))
    last = ComponentInstance("R2", "resistor.fixed", Point(28000, 0))
    blocker = ComponentInstance("R3", "resistor.fixed", Point(10000, 0))
    source = _pins(catalog, first)["2"]
    target = _pins(catalog, last)["1"]
    assert (source, target) == (Point(0, 0), Point(20000, 0))
    keepouts = _keepouts(catalog, first, blocker, last)
    blocked = router.route_two_pins(
        source, target, keepouts=keepouts,
        bounds=Box(0, -2000, 20000, 2000), max_cells=5000,
    )
    assert not blocked.ok and not blocked.points
    assert {issue.code for issue in blocked.diagnostics} == {"ROUTE_NO_PATH"}
    with pytest.raises(ValueError):
        blocked.external_graph("LINK")

    wider = router.route_two_pins(
        source, target, keepouts=keepouts,
        bounds=Box(0, -4000, 20000, 4000), max_cells=5000,
    )
    _assert_route_structure(wider, source, target, keepouts)


def test_real_obstacle_blocking_one_endpoint_fails_without_changing_identity(router, catalog):
    first = ComponentInstance("R1", "resistor.fixed", Point(0, 0))
    last = ComponentInstance("R2", "resistor.fixed", Point(60000, 0))
    hazard = ComponentInstance("R3", "resistor.fixed", Point(8000, 0))
    start = _pins(catalog, first)["2"]
    end = _pins(catalog, last)["1"]
    assert _keepouts(catalog, hazard)[0].includes(start)
    result = router.route_two_pins(
        start, end, keepouts=_keepouts(catalog, first, hazard, last),
    )
    assert not result.points and not result.ok
    assert {item.code for item in result.diagnostics} == {"ROUTE_PORT_BLOCKED"}


def test_real_component_origin_one_um_off_grid_fails_instead_of_snapping(router, catalog):
    first = ComponentInstance("R1", "resistor.fixed", Point(1, 0))
    last = ComponentInstance("R2", "resistor.fixed", Point(60000, 0))
    start = _pins(catalog, first)["2"]
    end = _pins(catalog, last)["1"]
    assert start.x % 1000 == 1
    route = router.route_two_pins(
        start, end, keepouts=_keepouts(catalog, first, last)
    )
    assert {item.code for item in route.diagnostics} == {"ROUTE_OFF_GRID"}
    assert not route.ok and route.points == ()


@pytest.mark.xfail(reason="Confirmed issue #52: foreign stroke width omitted from clearance", strict=True)
def test_mixed_existing_wire_stroke_must_respect_actual_printed_clearance(router):
    """PR39 WireSegment loses existing stroke width; fixed-width assumption is unsafe."""
    source, target = Point(0, 0), Point(10000, 0)
    old = WireSegment(Point(5000, -1000), Point(5000, 1000), "FOREIGN")
    clearance, new_stroke, foreign_stroke = 400, 300, 1000
    route = router.route_two_pins(
        source, target, existing_wires=(old,),
        grid_um=100, clearance_um=clearance, stroke_um=new_stroke,
        max_cells=10000,
    )
    _assert_route_structure(route, source, target)
    # Actual foreign printed line can be 1 mm wide, but WireSegment has NO width.
    # Edge-box clearance: centerline must avoid foreign stroke HALF-WIDTH,
    # new stroke HALF-WIDTH, plus requested 400-um clear gap.
    required_margin = (
        clearance + (foreign_stroke + 1) // 2 + (new_stroke + 1) // 2
    )
    actual_ink_hazard = Box(5000, -1000, 5001, 1001).expanded(required_margin)
    assert not any(
        segment_intersects_box(edge, actual_ink_hazard)
        for edge in _edges(route)
    ), "Router route violates clearance when existing and new strokes differ"


def test_mixed_stroke_preexpanded_foreign_ink_can_be_protected_by_callers(router):
    """Control: a correctly padded foreign stroke AABB avoids the unsafe region."""
    source, target = Point(0, 0), Point(10000, 0)
    old = WireSegment(Point(5000, -1000), Point(5000, 1000), "FOREIGN")
    # Provide the already-known foreign ink half-width as an explicit keepout.
    ink_box = Box(4500, -1500, 5500, 1500)
    result = router.route_two_pins(
        source, target, existing_wires=(old,), keepouts=(ink_box,),
        grid_um=100, clearance_um=400, stroke_um=300, max_cells=10000,
    )
    _assert_route_structure(result, source, target, (ink_box,), margin=550)
