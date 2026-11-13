"""E1 / YGO2 quantization contract, exact coordinates and view-only guards."""

import json
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree

import pytest

from examples.review_structural_e1 import (
    report,
    specimen,
    ygo2_visual_seed,
)
from gost_schematic.core.geometry import Point, Side
from gost_schematic.structural import (
    BlockPort,
    FunctionalBlock,
    PortDirection,
    PortRef,
    StructuralDiagram,
    resolve_port_positions,
    structural_from_json,
    structural_to_json,
    validate_port_clearances,
    validate_structural_diagram,
)

FIXTURES = Path(__file__).parent / "fixtures" / "structural-e1"


def _diagram(
    width: int, height: int, positions: tuple[Fraction | None, ...],
    side: Side = Side.TOP, origin: Point | None = None,
) -> StructuralDiagram:
    if origin is None:
        origin = Point(0, 0)
    return StructuralDiagram(
        (FunctionalBlock("B", "Блок", origin, width, height),),
        tuple(
            BlockPort("B", f"p{i}", side, PortDirection.OUTPUT, position)
            for i, position in enumerate(positions)
        ), (),
    )


def _codes(diagram: StructuralDiagram) -> set[str]:
    return {issue.code for issue in validate_structural_diagram(diagram)}


def _visual_codes(diagram: StructuralDiagram) -> set[str]:
    return {issue.code for issue in validate_port_clearances(diagram)}


def test_20000_two_automatic_ports_resolve_exactly_at_6667_and_13333_um():
    diagram = _diagram(10000, 20000, (None, None), Side.RIGHT)
    assert resolve_port_positions(diagram) == {
        PortRef("B", "p0"): Point(10000, 6667),
        PortRef("B", "p1"): Point(10000, 13333),
    }
    assert diagram.ports[0].position is None
    assert diagram.ports[1].position is None
    assert validate_structural_diagram(diagram) == ()
    assert validate_port_clearances(diagram) == ()


@pytest.mark.parametrize("side", list(Side))
@pytest.mark.parametrize("length", (1, 2, 3, 10001, 17999, 20000, 20001, 25003))
@pytest.mark.parametrize("fraction", (
    Fraction(1, 3), Fraction(2, 3), Fraction(1, 2),
    Fraction(1, 4), Fraction(5, 8),
))
@pytest.mark.parametrize("origin", (Point(0, 0), Point(-10001, -10001)))
def test_exact_absolute_half_up_matches_independent_decimal_reference(
    side, length, fraction, origin,
):
    """YGO2's Decimal(ROUND_HALF_UP) rounds the FINAL document coordinate."""
    dims = (length, 36000) if side in (Side.TOP, Side.BOTTOM) else (36000, length)
    diagram = _diagram(*dims, (fraction,), side, origin)
    point = resolve_port_positions(diagram)[PortRef("B", "p0")]
    if side in (Side.TOP, Side.BOTTOM):
        absolute = Decimal(origin.x) + Decimal(length) * (
            Decimal(fraction.numerator) / Decimal(fraction.denominator)
        )
        assert point.x == int(absolute.to_integral_value(rounding=ROUND_HALF_UP))
        assert point.y == origin.y + (dims[1] if side is Side.BOTTOM else 0)
    else:
        absolute = Decimal(origin.y) + Decimal(length) * (
            Decimal(fraction.numerator) / Decimal(fraction.denominator)
        )
        assert point.y == int(absolute.to_integral_value(rounding=ROUND_HALF_UP))
        assert point.x == origin.x + (dims[0] if side is Side.RIGHT else 0)
    assert diagram.ports[0].position == fraction
    assert "E1_PORT_OFF_GRID" not in _codes(diagram)


@pytest.mark.parametrize(
    ("origin", "fraction", "expected"),
    [
        (-1, Fraction(1, 2), -1),
        (-2, Fraction(1, 2), -2),
        (0, Fraction(1, 2), 1),
        (1, Fraction(1, 2), 2),
        (-3, Fraction(1, 2), -3),
    ],
)
def test_negative_absolute_ties_go_away_from_zero(origin, fraction, expected):
    diagram = _diagram(1, 20000, (fraction,), Side.TOP, Point(origin, 0))
    assert resolve_port_positions(diagram)[PortRef("B", "p0")] == Point(expected, 0)


def test_rounded_collision_rejected_even_when_original_fractions_are_distinct():
    diagram = _diagram(
        1, 20000, (Fraction(1, 3), Fraction(2, 5)), Side.TOP,
    )
    assert "E1_PORT_COLLISION" in _codes(diagram)
    assert "E1_PORT_COLLISION" in _visual_codes(diagram)
    with pytest.raises(ValueError, match="E1_PORT_COLLISION"):
        resolve_port_positions(diagram)
    with pytest.raises(ValueError, match="E1_PORT_COLLISION"):
        structural_to_json(diagram)


def test_many_auto_ports_on_tiny_side_fail_closed_post_quantization():
    diagram = _diagram(1, 20000, (None, None, None, None), Side.TOP)
    assert "E1_PORT_COLLISION" in _codes(diagram)


def test_rounded_corner_conflict_across_different_sides_detected():
    diagram = _diagram(1, 20000, (Fraction(1, 3),), Side.TOP)
    diagram = replace(diagram, ports=(
        *diagram.ports,
        BlockPort("B", "corner", Side.LEFT, PortDirection.INPUT, Fraction(0)),
    ))
    assert "E1_PORT_COLLISION" in _codes(diagram)


def test_view_pitch_is_editorial_but_5999um_fails_and_6000um_passes():
    good = _diagram(20000, 18000, (None, None), Side.RIGHT)
    bad = _diagram(20000, 17999, (None, None), Side.RIGHT)
    assert validate_port_clearances(good) == ()
    assert _visual_codes(bad) == {"E1_PORT_PITCH"}
    assert validate_structural_diagram(bad) == ()


def test_view_corner_minimum_is_editorial_and_semantic_fraction_zero_stays_legal():
    good = _diagram(20000, 20000, (Fraction(1, 4),), Side.TOP)
    bad = _diagram(20000, 20000, (Fraction(1, 5),), Side.TOP)
    corner = _diagram(20000, 20000, (Fraction(0),), Side.TOP)
    assert validate_port_clearances(good) == ()
    assert _visual_codes(bad) == {"E1_PORT_CORNER_CLEARANCE"}
    assert _visual_codes(corner) == {"E1_PORT_CORNER_CLEARANCE"}
    assert validate_structural_diagram(corner) == ()


@pytest.mark.parametrize("min_corner,min_pitch", [
    (-1, 0), (0, -1), (True, 6000), (5000, False), (5.2, 3),
])
def test_illegal_view_profile_parameters_rejected(min_corner, min_pitch):
    with pytest.raises(ValueError):
        validate_port_clearances(
            specimen(), min_corner_um=min_corner, min_pitch_um=min_pitch,
        )


def test_7_block_18_port_9_link_compatible_seed_matches_model_and_roundtrip():
    diagram = specimen()
    assert (len(diagram.blocks), len(diagram.ports), len(diagram.links)) == (7, 18, 9)
    assert validate_port_clearances(diagram) == ()
    encoded = structural_to_json(diagram)
    assert structural_from_json(encoded) == diagram
    assert structural_to_json(structural_from_json(encoded)) == encoded
    view = ygo2_visual_seed()
    assert view["diagram_type"] == "E1" and view["status"] == "DRAFT"
    assert "electrical_nets" not in view and not hasattr(diagram, "nets")
    assert view == json.loads((FIXTURES / "ygo2-seven-view.json").read_text("utf-8"))
    assert report()["electrical_nets"] is None

    original = resolve_port_positions(diagram)
    for box in view["blocks"]:
        semantic = next(b for b in diagram.blocks if b.id == box["id"])
        assert box["name"] == " ".join(box["title_lines"])
        assert box["center_um"] == [
            semantic.origin.x + semantic.width_um // 2,
            semantic.origin.y + semantic.height_um // 2,
        ]
        for item in box["ports"]:
            ref = PortRef(box["id"], item["id"])
            logical = next(p for p in diagram.ports if p.ref == ref)
            assert item["side"].lower() == logical.side.value
            assert Fraction(Decimal(item["relative_position"])) == logical.position
            if item["side"] in ("TOP", "BOTTOM"):
                length, low = semantic.width_um, semantic.origin.x
                axis = "x"
            else:
                length, low = semantic.height_um, semantic.origin.y
                axis = "y"
            exact = Decimal(low) + Decimal(length) * Decimal(
                item["relative_position"]
            )
            expected = int(exact.to_integral_value(rounding=ROUND_HALF_UP))
            assert getattr(original[ref], axis) == expected
    for link in view["links"]:
        authored = next(l for l in diagram.links if l.id == link["id"])
        assert link["source"] == {
            "block_id": authored.source.block_id, "port_id": authored.source.port_id,
        }
        assert link["target"] == {
            "block_id": authored.target.block_id, "port_id": authored.target.port_id,
        }
        assert link["arrow_at"] == "target"


def test_pinned_ygo2_diagnostic_svg_ports_physically_match_typed_model():
    svg = (FIXTURES / "ygo2-seven-diagnostic.svg").read_text(encoding="utf-8")
    root = ElementTree.fromstring(svg)
    assert root.attrib["data-diagram-type"] == "E1"
    assert root.attrib["data-approval-status"] == "DRAFT"
    circles = [
        item for item in root.iter()
        if item.attrib.get("data-role") == "functional-port"
    ]
    links = [
        item for item in root.iter()
        if item.attrib.get("data-role") == "functional-link"
    ]
    arrows = [
        item for item in root.iter()
        if item.attrib.get("data-role") == "functional-arrow"
    ]
    assert (len(circles), len(links), len(arrows)) == (18, 9, 9)
    anchors = resolve_port_positions(specimen())
    seen = set()
    for circle in circles:
        ref = PortRef(circle.attrib["data-block-id"], circle.attrib["data-port-id"])
        assert ref not in seen
        seen.add(ref)
        pt = anchors[ref]
        assert int(Decimal(circle.attrib["cx"]) * 1000) == pt.x
        assert int(Decimal(circle.attrib["cy"]) * 1000) == pt.y
    assert seen == set(anchors)
