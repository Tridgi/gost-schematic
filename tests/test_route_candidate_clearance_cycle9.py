"""Owner review MAIN3: candidate planner must obey SAME scoped print DRC."""
from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.orthogonal_route_planner import _legality
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment
from gost_schematic.validation.route_drc import candidate_wire_clearance


def w(a, b, c, d, net="A"):
    return WireSegment(Point(a, b), Point(c, d), net)


@pytest.mark.parametrize(("center", "legal"), (
    (1000, False),  # 0.700mm actual ink gap: formerly incorrectly passed.
    (3299, False),  # 2.999mm edge gap below exact 3mm.
    (3300, True),   # 3.000mm edge gap is legal.
    (3301, True),
))
def test_route_preview_same_stroke_print_parallel_threshold(center, legal):
    existing = w(0, 0, 12000, 0, "A")
    candidate = w(0, center, 12000, center, "B")
    result = candidate_wire_clearance(candidate, existing)
    assert result.valid is legal
    assert result.parallel_rule_applies
    assert result.edge_gap_um == center - 300
    assert ("DRC_PARALLEL_STROKE_CLEARANCE" in result.errors) is not legal
    ok = _legality(
        candidate.start, candidate.end, net_name="B",
        graph=ExternalWireGraph((existing,)),
        bounds=Box(-20000, -20000, 30000, 20000), boxes=(),
        stroke_um=300,
    )
    assert ok is legal


def test_orthogonal_nonconnecting_foreign_net_X_is_not_false_3mm_violation():
    existing = w(-10000, 0, 10000, 0, "POWER")
    candidate = w(0, -10000, 0, 10000, "CONTROL")
    check = candidate_wire_clearance(candidate, existing)
    assert check.valid
    assert not check.parallel_rule_applies
    assert check.warnings == ("DRC_UNMARKED_DIFFERENT_NET_X",)
    assert _legality(
        candidate.start, candidate.end, net_name="CONTROL",
        graph=ExternalWireGraph((existing,)),
        bounds=Box(-20000, -20000, 20000, 20000),
        boxes=(), stroke_um=300,
    )
    assert candidate.net_name != existing.net_name


def test_true_same_net_T_requires_expressly_authored_dot():
    existing = w(-10000, 0, 10000, 0, "COMMON")
    candidate = w(0, 0, 0, 10000, "COMMON")
    no_dot = candidate_wire_clearance(candidate, existing)
    assert not no_dot.valid
    assert no_dot.errors == ("DRC_SAME_NET_T_NO_DOT",)
    with_dot = candidate_wire_clearance(
        candidate, existing, explicit_junctions=frozenset({Point(0, 0)}),
    )
    assert with_dot.valid
    assert _legality(
        candidate.start, candidate.end, net_name="COMMON",
        graph=ExternalWireGraph((existing,), (Point(0, 0),)),
        bounds=Box(-20000, -20000, 20000, 20000),
        boxes=(), stroke_um=300,
    )
    assert not _legality(
        candidate.start, candidate.end, net_name="COMMON",
        graph=ExternalWireGraph((existing,)),
        bounds=Box(-20000, -20000, 20000, 20000),
        boxes=(), stroke_um=300,
    )


def test_foreign_net_T_and_real_short_are_rejected_even_with_dot():
    existing = w(-10000, 0, 10000, 0, "COMMON")
    candidate = w(0, 0, 0, 10000, "PE")
    original = ExternalWireGraph((existing,), (Point(0, 0),))
    verdict = candidate_wire_clearance(
        candidate, existing, explicit_junctions=frozenset(original.junctions),
    )
    assert not verdict.valid
    assert "DRC_FOREIGN_NET_ENDPOINT_CONTACT" in verdict.errors
    assert not _legality(
        candidate.start, candidate.end, net_name="PE",
        graph=original, bounds=Box(-20000, -20000, 20000, 20000),
        boxes=(), stroke_um=300,
    )
    assert original == replace(original, segments=(existing,))


def test_same_net_collinear_continuity_only_foreign_net_overprint_fails():
    existing = w(0, 0, 10000, 0, "A")
    same = w(5000, 0, 12000, 0, "A")
    foreign = w(5000, 0, 12000, 0, "B")
    assert candidate_wire_clearance(same, existing).valid
    assert not candidate_wire_clearance(foreign, existing).valid
    assert not candidate_wire_clearance(same, existing).errors


def test_parallel_boundary_with_asymmetric_actual_strokes():
    existing = w(0, 0, 10000, 0, "A")
    at = w(0, 3350, 10000, 3350, "B")
    assert candidate_wire_clearance(
        at, existing, candidate_stroke_um=400,
        existing_stroke_um=300,
    ).valid
    below = w(0, 3349, 10000, 3349, "B")
    assert not candidate_wire_clearance(
        below, existing, candidate_stroke_um=400,
        existing_stroke_um=300,
    ).valid
