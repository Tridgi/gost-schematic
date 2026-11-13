"""Experimental Э1 model regression and adversarial geometry/JSON threat tests."""

import json
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from pathlib import Path

import pytest

from examples.review_structural_e1 import report, specimen
from gost_schematic.core.geometry import Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.structural import (
    BlockPort,
    FunctionalBlock,
    FunctionalLink,
    PortDirection,
    PortRef,
    StructuralDiagram,
    resolve_port_positions,
    structural_from_json,
    structural_to_json,
    validate_structural_diagram,
)
from gost_schematic.validation.external_wire_checks import ExternalWireGraph

IN = PortDirection.INPUT
OUT = PortDirection.OUTPUT
BI = PortDirection.BIDIRECTIONAL


def block(name, x, y, width=20000, height=12000):
    return FunctionalBlock(name, name + " function", Point(x, y), width, height)


def port(block_id, name, side, direction, position=None):
    return BlockPort(block_id, name, side, direction, position)


def link(name, a, src, b, dst):
    return FunctionalLink(name, PortRef(a, src), PortRef(b, dst))


def codes(d):
    return {item.code for item in validate_structural_diagram(d)}


def simple():
    return StructuralDiagram(
        (block("A", 0, 0), block("B", 40000, 0)),
        (port("A", "out", Side.RIGHT, OUT), port("B", "in", Side.LEFT, IN)),
        (link("L", "A", "out", "B", "in"),),
    )


def test_seven_block_real_demo_deterministic_and_no_electrical_semantics():
    d = specimen()
    assert len(d.blocks) == 7
    assert len(d.ports) == 18
    assert len(d.links) == 9
    assert d.schema_version == 1
    assert d.diagram_type == "E1"
    assert validate_structural_diagram(d) == ()
    assert not isinstance(d, Circuit)
    assert not isinstance(d.links[0].source, PinRef)
    assert not isinstance(d.links[0], ExternalWireGraph)
    assert report()["status"] == "EXPERIMENTAL_E1_SCHEMA_NOT_ESKD_APPROVED"
    assert all(item["arrow"] == "source_to_target"
               for item in report()["inspection_chords_um"])
    assert report() == report()


def test_exact_auto_layout_for_two_and_single_ports():
    p = resolve_port_positions(specimen())
    assert p[PortRef("ENTRY", "cmd1")] == Point(60000, 4000)
    assert p[PortRef("ENTRY", "cmd2")] == Point(60000, 8000)
    assert p[PortRef("CTRL", "cmd1")] == Point(80000, 4000)
    assert p[PortRef("CTRL", "cmd2")] == Point(80000, 8000)
    assert p[PortRef("POWER", "feed")] == Point(20000, 6000)
    assert p[PortRef("ACT", "control")] == Point(90000, 30000)


@pytest.mark.parametrize("side", list(Side))
@pytest.mark.parametrize("count", range(1, 9))
def test_one_center_else_ordered_evenly_spaced_side_port_slots(side, count):
    b = block("B", 100000, 200000, 252000, 252000)
    ports = tuple(port("B", f"p{i}", side, BI) for i in range(count))
    d = StructuralDiagram((b,), ports, ())
    points = resolve_port_positions(d)
    assert validate_structural_diagram(d) == ()
    assert len(points) == count
    for i, item in enumerate(ports):
        expected = Fraction(i + 1, count + 1) * 252000
        assert expected.denominator == 1
        v = expected.numerator
        expected_point = {
            Side.LEFT: Point(100000, 200000 + v),
            Side.RIGHT: Point(352000, 200000 + v),
            Side.TOP: Point(100000 + v, 200000),
            Side.BOTTOM: Point(100000 + v, 452000),
        }[side]
        assert points[item.ref] == expected_point


def test_explicit_fraction_and_mixed_auto_ports_keep_individual_positions():
    d = StructuralDiagram(
        (block("B", 0, 0, 24000, 24000),),
        (
            port("B", "p1", Side.TOP, OUT, Fraction(1, 4)),
            port("B", "p2", Side.TOP, OUT),
            port("B", "p3", Side.TOP, OUT, Fraction(3, 4)),
        ), (),
    )
    points = resolve_port_positions(d)
    assert [points[PortRef("B", f"p{i}")] for i in (1, 2, 3)] == [
        Point(6000, 0), Point(12000, 0), Point(18000, 0),
    ]
    assert validate_structural_diagram(d) == ()


def test_one_third_of_ten_thousand_micrometres_fails_no_rounding():
    d = StructuralDiagram(
        (block("B", 0, 0, 10000, 12000),),
        (port("B", "p", Side.TOP, IN, Fraction(1, 3)),), (),
    )
    assert codes(d) == {"E1_PORT_OFF_GRID"}
    with pytest.raises(ValueError, match="E1_PORT_OFF_GRID"):
        resolve_port_positions(d)
    with pytest.raises(ValueError, match="E1_PORT_OFF_GRID"):
        structural_to_json(d)


def test_same_side_and_cross_side_duplicate_anchors_fail_closed():
    same = StructuralDiagram(
        (block("A", 0, 0),),
        (port("A", "p1", Side.RIGHT, IN, Fraction(1, 2)),
         port("A", "p2", Side.RIGHT, OUT, Fraction(1, 2))), (),
    )
    assert codes(same) == {"E1_PORT_COLLISION"}
    corner = StructuralDiagram(
        (block("A", 0, 0),),
        (port("A", "top", Side.TOP, IN, 0),
         port("A", "left", Side.LEFT, OUT, 0)), (),
    )
    assert codes(corner) == {"E1_PORT_COLLISION"}


def test_missing_port_owner_and_endpoint_fail_without_inference():
    original = simple()
    missing_block = replace(
        original, ports=(*original.ports,
                         port("MISSING", "ghost", Side.RIGHT, OUT))
    )
    assert "E1_PORT_BLOCK_UNKNOWN" in codes(missing_block)
    no_target = replace(original, ports=original.ports[:1])
    assert codes(no_target) == {"E1_LINK_PORT_UNKNOWN"}
    bad_source = replace(
        original, links=(link("L", "ABSENT", "out", "B", "in"),)
    )
    assert codes(bad_source) == {"E1_LINK_PORT_UNKNOWN"}


def test_duplicate_block_port_link_and_duplicate_connection():
    d = simple()
    assert codes(replace(d, blocks=(*d.blocks, d.blocks[0]))) == {
        "E1_DUPLICATE_BLOCK"
    }
    assert codes(replace(d, ports=(*d.ports, d.ports[1]))) == {
        "E1_DUPLICATE_PORT"
    }
    assert codes(replace(d, links=(*d.links, d.links[0]))) == {
        "E1_DUPLICATE_LINK"
    }
    assert codes(replace(d, links=(*d.links, replace(d.links[0], id="L2")))) == {
        "E1_DUPLICATE_CONNECTION"
    }


@pytest.mark.parametrize(
    ("source_mode", "target_mode", "expected"),
    [
        (IN, IN, {"E1_SOURCE_DIRECTION"}),
        (OUT, OUT, {"E1_TARGET_DIRECTION"}),
        (IN, OUT, {"E1_SOURCE_DIRECTION", "E1_TARGET_DIRECTION"}),
        (BI, IN, set()),
        (OUT, BI, set()),
        (BI, BI, set()),
    ],
)
def test_connection_direction_contract(source_mode, target_mode, expected):
    d = simple()
    d = replace(d, ports=(
        replace(d.ports[0], direction=source_mode),
        replace(d.ports[1], direction=target_mode),
    ))
    assert codes(d) == expected


def test_self_link_even_between_distinct_local_ports_invalid():
    d = StructuralDiagram(
        (block("A", 0, 0),),
        (port("A", "out", Side.RIGHT, OUT),
         port("A", "in", Side.LEFT, IN)),
        (link("loop", "A", "out", "A", "in"),),
    )
    assert codes(d) == {"E1_SELF_LINK"}


def test_overlapping_rectangles_rejected_touching_only_edge_allowed():
    first = simple()
    overlapping = replace(first, blocks=(
        first.blocks[0], replace(first.blocks[1], origin=Point(10000, 0))
    ))
    assert "E1_BLOCK_OVERLAP" in codes(overlapping)
    touching = replace(first, blocks=(
        first.blocks[0], replace(first.blocks[1], origin=Point(20000, 0))
    ))
    assert "E1_BLOCK_OVERLAP" not in codes(touching)
    assert "E1_ZERO_LENGTH_LINK" in codes(touching)


def test_chord_crossing_unrelated_block_interior_fails_no_auto_reroute():
    d = simple()
    d = replace(d, blocks=(
        d.blocks[0], replace(d.blocks[1], origin=Point(80000, 0)),
        block("OBSTACLE", 40000, 0),
    ))
    assert "E1_LINK_THROUGH_BLOCK" in codes(d)


def test_exact_tangent_at_obstacle_border_is_not_interior_collision():
    d = simple()
    d = replace(d, blocks=(
        d.blocks[0], replace(d.blocks[1], origin=Point(80000, 0)),
        block("OBSTACLE", 40000, 6000),
    ))
    assert "E1_LINK_THROUGH_BLOCK" not in codes(d)


def test_unmarked_chord_x_is_reported_but_never_creates_a_conductive_net():
    d = StructuralDiagram(
        (block("LEFT", 0, 40000), block("RIGHT", 80000, 40000),
         block("TOP", 40000, 0), block("BOTTOM", 40000, 80000)),
        (port("LEFT", "out", Side.RIGHT, OUT),
         port("RIGHT", "in", Side.LEFT, IN),
         port("TOP", "out", Side.BOTTOM, OUT),
         port("BOTTOM", "in", Side.TOP, IN)),
        (link("H", "LEFT", "out", "RIGHT", "in"),
         link("V", "TOP", "out", "BOTTOM", "in")),
    )
    assert codes(d) == {"E1_LINK_CROSSING"}
    assert len(d.links) == 2
    assert not hasattr(d, "nets")
    assert "WIRE_NET_SHORT" not in codes(d)


def test_fanout_from_exact_same_declared_port_is_allowed_without_a_junction():
    d = StructuralDiagram(
        (block("A", 0, 0), block("B", 40000, 0), block("C", 40000, 30000)),
        (port("A", "out", Side.RIGHT, OUT),
         port("B", "in", Side.LEFT, IN),
         port("C", "in", Side.LEFT, IN)),
        (link("AB", "A", "out", "B", "in"),
         link("AC", "A", "out", "C", "in")),
    )
    assert validate_structural_diagram(d) == ()


def test_functional_feedback_cycles_are_allowed_as_process_not_electricity():
    d = StructuralDiagram(
        (block("A", 0, 0), block("B", 40000, 0)),
        (port("A", "out", Side.RIGHT, OUT),
         port("B", "in", Side.LEFT, IN),
         port("B", "feedback", Side.BOTTOM, OUT),
         port("A", "feedback", Side.BOTTOM, IN)),
        (link("AB", "A", "out", "B", "in"),
         link("BA", "B", "feedback", "A", "feedback")),
    )
    assert validate_structural_diagram(d) == ()


def test_immutability_and_no_shared_e3_model_change():
    d = specimen()
    originals = (d.blocks, d.ports, d.links)
    _ = resolve_port_positions(d)
    _ = validate_structural_diagram(d)
    _ = structural_to_json(d)
    assert originals == (d.blocks, d.ports, d.links)
    with pytest.raises(FrozenInstanceError):
        d.links[0].id = "MUTATED"
    with pytest.raises(FrozenInstanceError):
        d.blocks[0].width_um = 0


def test_seven_block_json_golden_fixture_does_not_drift():
    fixture = Path(__file__).parent / "fixtures" / "structural-e1"
    original = (fixture / "structural-e1.json").read_text(encoding="utf-8")
    review = (fixture / "structural-e1-review.json").read_text(encoding="utf-8")
    assert original == structural_to_json(specimen())
    assert review == json.dumps(
        report(), ensure_ascii=False, sort_keys=True, indent=2,
    ) + "\n"
    assert structural_to_json(structural_from_json(original)) == original


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_d4_transform_preserves_real_declared_port_anchors_and_link_semantics(
    rotation, mirror,
):
    """A test-only view transform, not a new public or structural pose API."""
    original = specimen()
    transform = Transform(rotation, mirror)
    original_anchors = resolve_port_positions(original)
    blocks = tuple(
        FunctionalBlock(
            b.id, b.name,
            Point(transform.box(b.bounds).min_x, transform.box(b.bounds).min_y),
            transform.box(b.bounds).max_x - transform.box(b.bounds).min_x,
            transform.box(b.bounds).max_y - transform.box(b.bounds).min_y,
        )
        for b in original.blocks
    )
    by_id = {b.id: b for b in blocks}
    new_ports = []
    for item in original.ports:
        new_side = transform.side(item.side)
        anchor = transform.apply(original_anchors[item.ref])
        box = by_id[item.block_id].bounds
        if new_side in (Side.LEFT, Side.RIGHT):
            fraction = Fraction(anchor.y - box.min_y, box.max_y - box.min_y)
        else:
            fraction = Fraction(anchor.x - box.min_x, box.max_x - box.min_x)
        new_ports.append(replace(item, side=new_side, position=fraction))
    changed = StructuralDiagram(blocks, tuple(new_ports), original.links)
    assert validate_structural_diagram(changed) == ()
    assert resolve_port_positions(changed) == {
        ref: transform.apply(point) for ref, point in original_anchors.items()
    }
    assert [link.id for link in changed.links] == [link.id for link in original.links]
    assert structural_from_json(structural_to_json(changed)) == changed


def test_json_exact_roundtrip_unicode_direction_and_position():
    d = specimen()
    text = structural_to_json(d)
    assert text == structural_to_json(d)
    assert json.loads(text)["schema_version"] == 1
    assert "Контроллер" in text
    assert structural_from_json(text) == d
    assert structural_to_json(structural_from_json(text)) == text
    explicit = StructuralDiagram(
        (block("A", 0, 0),),
        (port("A", "half", Side.TOP, BI, Fraction(1, 2)),), (),
    )
    assert structural_from_json(structural_to_json(explicit)) == explicit
    assert '[\n        1,\n        2\n      ]' in structural_to_json(explicit)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: {**d, "schema_version": 2},
        lambda d: {**d, "schema_version": True},
        lambda d: {**d, "diagram_type": "E3"},
        lambda d: {**d, "diagram_type": None},
        lambda d: {**d, "extra": 1},
        lambda d: {**d, "blocks": [{**d["blocks"][0], "width_um": 10.5},
                                     *d["blocks"][1:]]},
        lambda d: {**d, "blocks": [{**d["blocks"][0], "width_um": False},
                                     *d["blocks"][1:]]},
        lambda d: {**d, "ports": [{**d["ports"][0], "side": "rear"},
                                    *d["ports"][1:]]},
        lambda d: {**d, "ports": [{**d["ports"][0], "direction": "electric"},
                                    *d["ports"][1:]]},
        lambda d: {**d, "ports": [{**d["ports"][0], "position": [1, 0]},
                                    *d["ports"][1:]]},
        lambda d: {**d, "ports": [{**d["ports"][0], "position": [1.0, 2]},
                                    *d["ports"][1:]]},
        lambda d: {**d, "links": [
            {**d["links"][0], "target": {"block_id": "GHOST", "port_id": "x"}},
            *d["links"][1:],
        ]},
        lambda d: {**d, "links": [
            {**d["links"][0], "target": ["B", "in"]}, *d["links"][1:],
        ]},
    ],
)
def test_json_decoder_rejects_invalid_or_unknown_fields(mutator):
    data = json.loads(structural_to_json(specimen()))
    data = mutator(data)
    with pytest.raises((ValueError, TypeError)):
        structural_from_json(json.dumps(data))


def test_json_rejects_duplicate_keys_and_float_nan():
    source = structural_to_json(simple())
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        structural_from_json('{"schema_version":1,"schema_version":1,"blocks":[],'
                             '"ports":[],"links":[]}')
    with pytest.raises(ValueError):
        structural_from_json(source.replace('"schema_version": 1',
                                          '"schema_version": NaN'))


@pytest.mark.parametrize(
    "bad",
    [
        lambda: block("x", 0, 0, 0),
        lambda: block("x", 0, 0, width=True),
        lambda: FunctionalBlock("  ", "name", Point(0, 0), 1000, 1000),
        lambda: port("A", "p", "left", IN),
        lambda: port("A", "p", Side.LEFT, "output"),
        lambda: port("A", "p", Side.LEFT, IN, 1.0),
        lambda: port("A", "p", Side.LEFT, IN, Fraction(-1, 4)),
        lambda: port("A", "p", Side.LEFT, IN, Fraction(5, 4)),
        lambda: port("A", "p", Side.LEFT, IN, True),
        lambda: FunctionalLink("x", Point(0, 0), Point(1, 1)),
        lambda: StructuralDiagram((), (), (), schema_version=9),
        lambda: StructuralDiagram((), (), (), diagram_type="E3"),
        lambda: FunctionalBlock("B", "bad\nlabel", Point(0, 0), 10000, 10000),
        lambda: StructuralDiagram([], (), ()),
    ],
)
def test_typed_fields_reject_invalid_shapes_and_values(bad):
    with pytest.raises((TypeError, ValueError)):
        bad()


def test_block_and_link_input_permutation_does_not_change_diagnostics():
    d = simple()
    invalid = replace(d, links=(
        link("X", "B", "in", "A", "out"),
        *d.links,
    ))
    reordered = replace(invalid, blocks=invalid.blocks[::-1], links=invalid.links[::-1])
    assert validate_structural_diagram(invalid) == validate_structural_diagram(reordered)
