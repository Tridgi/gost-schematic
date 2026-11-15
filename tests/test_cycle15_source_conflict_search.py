"""Cycle15 tests of real typed copper dependency and safe sparse candidate search."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.multiterminal_router import (
    _conflict_group_reroute,
    _physical_conflict_dependencies,
    _visibility_path,
)
from gost_schematic.validation.external_wire_checks import ExternalWireGraph
from tests.test_cycle14_physical_ripup import preexisting_blocked_preview


def test_cycle15_large_unused_lattice_does_not_fake_grid_too_dense_failure():
    """Many remote real keepouts cannot veto a clear outward physical aisle."""
    source = Point(5000, 5000)
    target = Point(25000, 5000)
    # All 120 obstacle boxes lie away from the wire's y=5000. Their x/y
    # boundaries formerly created >8*1000 potential Cartesian cells and
    # rejected before the real legal single-segment check could even run.
    far_boxes = tuple(
        Box(27000 + 135 * i, 15000 + 135 * i,
            27100 + 135 * i, 15100 + 135 * i)
        for i in range(120)
    )
    path, diagnostic = _visibility_path(
        source, Point(1, 0), (target,),
        net_name="SOURCE_PIN", occupied=ExternalWireGraph(()),
        tree=(), existing_dots=(), goal_pin_normals={},
        ink_obstacles=(), authorized_pins=frozenset(),
        boxes=far_boxes, page=Box(0, 0, 90000, 80000),
        stroke_um=300, search_node_cap=1000,
        grid_um=5000, max_detour_ratio=3.0,
    )
    assert diagnostic is None
    assert path == (source, target)


def test_cycle15_no_foreign_short_under_sparse_grid_overflow():
    """Compressed search lanes still reject touching existing foreign copper."""
    source = Point(5000, 5000)
    target = Point(25000, 5000)
    far_boxes = tuple(
        Box(27000 + 135 * i, 15000 + 135 * i,
            27100 + 135 * i, 15100 + 135 * i)
        for i in range(120)
    )
    from gost_schematic.validation.external_wire_checks import WireSegment
    prior = WireSegment(Point(15000, 3500), Point(15000, 6500), "FOREIGN")
    route, diagnostic = _visibility_path(
        source, Point(1, 0), (target,),
        net_name="SOURCE_PIN", occupied=ExternalWireGraph((prior,)),
        tree=(), existing_dots=(), goal_pin_normals={},
        ink_obstacles=(), authorized_pins=frozenset(),
        boxes=far_boxes, page=Box(0, 0, 90000, 80000),
        stroke_um=300, search_node_cap=1000,
        grid_um=5000, max_detour_ratio=3.0,
    )
    if route:
        from itertools import pairwise

        from gost_schematic.validation.route_drc import candidate_wire_clearance
        assert all(candidate_wire_clearance(
            WireSegment(a, b, "SOURCE_PIN"), prior,
        ).valid for a, b in pairwise(route))
        # An orthogonal crossing without a junction is not electrical contact.
        assert ExternalWireGraph((prior,)).junctions == ()
    else:
        assert diagnostic is not None


@pytest.mark.parametrize("attempts", [-1, 4, True, 1.5])
def test_cycle15_group_ripup_rejects_unbounded_or_invalid_argument(attempts):
    _circuit, parts, symbols, page, source = preexisting_blocked_preview()
    with pytest.raises(ValueError, match="ROUTE_INVALID_CONFLICT_GROUP_ATTEMPTS"):
        _conflict_group_reroute(
            source, parts, symbols, page_box=page,
            annotation_placements=(), stroke_um=300,
            search_node_cap=1000, max_detour_ratio=3.0,
            attempts=attempts,
        )


def test_cycle15_source_only_ink_and_unrelated_wire_veto_not_conflict_edge():
    _circuit, parts, symbols, page, source = preexisting_blocked_preview()
    first, second = source.net_trees
    failed = replace(second, diagnostics=(
        "ROUTE_FAILED:INK_VETO=DA1#9:DA1.13",
        "ROUTE_FAILED:WIRE_VETO=UNKNOWN:DRC_FOREIGN_NET_ENDPOINT_CONTACT",
        "ROUTE_FAILED:WIRE_VETO=B:DRC_PARALLEL_STROKE_CLEARANCE",
    ))
    assert _physical_conflict_dependencies((first, failed)) == {"B": ()}
    assert not _conflict_group_reroute(
        replace(source, net_trees=(first, failed)),
        parts, symbols, page_box=page, annotation_placements=(),
        stroke_um=300, search_node_cap=1000,
        max_detour_ratio=3.0, attempts=2,
    ).print_pass
