"""Issue #44: manual six-part C3 placement correction, NOT an auto-placer."""

import json

from examples.review_end_to_end_circuit import (
    authored_specimen,
    c3_manual_layout_metrics,
    definitions,
    report_json,
    scenarios,
    specimen_svg,
)
from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.circuit import PinRef
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    validate_external_wires,
)


def test_manual_c3_move_preserves_catalog_identity_nets_and_physical_polarity():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    assert len(circuit.components) == 6
    assert len(circuit.nets) == 5
    assert len(graph.segments) == 16
    assert len(graph.junctions) == 3
    assert graph.junctions == (
        Point(40000, 20000), Point(40000, 40000), Point(120000, 40000),
    )
    c3 = next(item for item in circuit.components if item.reference == "C3")
    assert c3.part_id == "capacitor.electrolytic"
    assert c3.origin == Point(100000, 80000)
    assert c3.pin_positions(symbols[c3.part_id]) == {
        "1": Point(91000, 80000), "2": Point(109000, 80000),
    }
    assert [(item.number, item.polarity.value) for item in parts[c3.part_id].pins] == [
        ("1", "positive"), ("2", "negative"),
    ]
    assert {
        net.name for net in circuit.nets if PinRef("C3", "1") in net.members
    } == {"TOP"}
    assert {
        net.name for net in circuit.nets if PinRef("C3", "2") in net.members
    } == {"RIGHT"}
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    assert not [
        item for item in validate_circuit(circuit, parts, symbols)
        if item.severity.value == "error"
    ]


def test_exact_manual_four_segment_replacement_has_no_old_dogleg():
    _, graph = authored_specimen()
    paths = tuple(
        ((a.start.x, a.start.y), (a.end.x, a.end.y), a.net_name)
        for a in graph.segments[-4:]
    )
    assert paths == (
        ((40000, 40000), (40000, 80000), "TOP"),
        ((40000, 80000), (91000, 80000), "TOP"),
        ((120000, 40000), (120000, 80000), "RIGHT"),
        ((120000, 80000), (109000, 80000), "RIGHT"),
    )
    assert all(
        Point(84000, 75000) not in (segment.start, segment.end)
        for segment in graph.segments
    )


def test_metrics_before_after_show_two_fewer_bends_but_equal_combined_length():
    values = c3_manual_layout_metrics()
    assert values["method"] == "manual-authored-specimen-correction-not-auto-placement"
    assert values["c3_origin_before_um"] == [100000, 75000]
    assert values["c3_origin_after_um"] == [100000, 80000]
    before, after = values["before"], values["after"]
    assert before["TOP"] == {
        "length_um": 96000,
        "bends": 3,
        "manhattan_excess_um": 10000,
        "backtrack_um": 5000,
    }
    assert after["TOP"] == {
        "length_um": 91000,
        "bends": 1,
        "manhattan_excess_um": 0,
        "backtrack_um": 0,
    }
    assert before["RIGHT"]["length_um"] == 46000
    assert after["RIGHT"]["length_um"] == 51000
    assert before["RIGHT"]["bends"] == after["RIGHT"]["bends"] == 1
    assert before["combined_length_um"] == after["combined_length_um"] == 142000
    assert before["combined_bends"] == 4
    assert after["combined_bends"] == 2
    assert json.loads(report_json())["manual_c3_layout_comparison"] == values


def test_new_lines_clear_every_real_body_keepout_including_C2_L1_and_C3():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    bodies = {
        component.reference: component.transform.box(
            symbols[parts[component.part_id].symbol_id].body_keepout
        ).translated(component.origin).expanded(550)
        for component in circuit.components
    }
    assert {"C2", "L1", "C3"} <= bodies.keys()
    new_branches = graph.segments[-4:]
    assert all(
        not segment_intersects_box(Line(wire.start, wire.end), box)
        for wire in new_branches for box in bodies.values()
    )
    # 550um = 400um clearance + half of 300um printed wire.
    assert all(wire.start != wire.end for wire in new_branches)


def test_manual_demo_keeps_unjoined_x_and_authored_t_semantics():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    assert Point(40000, 60000) not in graph.junctions
    assert Point(40000, 40000) in graph.junctions
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    explicit_short = ExternalWireGraph(
        graph.segments, (*graph.junctions, Point(40000, 60000))
    )
    assert "WIRE_NET_SHORT" in {
        item.code for item in validate_external_wires(
            circuit, explicit_short, parts, symbols
        )
    }
    no_t = ExternalWireGraph(graph.segments, graph.junctions[1:])
    errors = {
        item.code for item in validate_external_wires(
            circuit, no_t, parts, symbols
        )
    }
    assert {"WIRE_DANGLING_END", "WIRE_NET_DISCONNECTED"} <= errors


def test_existing_negative_scenarios_and_svg_from_same_authored_graph():
    cases = scenarios()
    assert [case.identifier for case in cases] == [
        "valid", "electrolytic_pin_unwired", "short_at_unmarked_crossing",
        "one_micrometre_gap", "missing_t_junction", "reverse_electrolytic_bias",
    ]
    assert all(len(case.circuit.components) == 6 for case in cases)
    assert all(len(case.circuit.nets) == 5 for case in cases)
    assert specimen_svg() == specimen_svg()
    assert specimen_svg(review=True) == specimen_svg(review=True)
    assert report_json() == report_json()
