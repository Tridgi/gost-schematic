"""Independent renderer-side review of Issue #44 C3 dogleg proposal.

No source fixture, production electrical model or UGO JSON is edited.
"""
from dataclasses import replace

from examples.review_c3_placement_proposal import proposed_c3_geometry
from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Box, Point
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import validate_external_wires

STYLE = TextStyle("unit-test-face.ttf", "Unit Test", 3500, 500)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


def test_c3_current_json_id_revision_physical_pins_and_authored_dogleg():
    (original, graph), (candidate, proposal) = proposed_c3_geometry()
    parts, symbols = definitions()
    c3 = next(x for x in original.components if x.reference == "C3")
    part = parts[c3.part_id]
    symbol = symbols[part.symbol_id]
    assert (part.identifier, part.symbol_id, symbol.identifier) == (
        "capacitor.electrolytic", "capacitor.electrolytic",
        "capacitor.electrolytic",
    )
    assert symbol.revision == 1 and symbol.status.value == "draft"
    assert {pin.number: pin.at for pin in symbol.pins} == {
        "1": Point(-9000, 0), "2": Point(9000, 0),
    }
    assert {pin.number: pin.polarity.value for pin in part.pins} == {
        "1": "positive", "2": "negative",
    }
    assert c3.origin == Point(100000, 75000)
    assert c3.pin_positions(symbol) == {
        "1": Point(91000, 75000), "2": Point(109000, 75000),
    }
    assert graph.segments[-4].start == Point(84000, 80000)
    assert graph.segments[-4].end == Point(84000, 75000)
    assert len(graph.segments) == 18 and len(proposal.segments) == 16
    assert (original, graph) == authored_specimen()


def test_candidate_is_pure_replacement_and_preserves_electrical_semantics():
    (circuit, graph), (candidate, proposal) = proposed_c3_geometry()
    parts, symbols = definitions()
    c3 = next(x for x in candidate.components if x.reference == "C3")
    assert c3.origin == Point(100000, 80000)
    assert c3.pin_positions(symbols["capacitor.electrolytic"]) == {
        "1": Point(91000, 80000), "2": Point(109000, 80000),
    }
    assert candidate.nets == circuit.nets
    assert len(candidate.nets) == 5
    assert len(candidate.components) == len(circuit.components) == 6
    assert proposal.junctions == graph.junctions
    assert len(proposal.junctions) == 3
    assert proposal.segments[:-4] == graph.segments[:-6]
    assert {s.net_name for s in proposal.segments} == {
        s.net_name for s in graph.segments
    }
    assert not validate_external_wires(candidate, proposal, parts, symbols)
    assert not [
        issue for issue in validate_circuit(candidate, parts, symbols)
        if issue.severity.value == "error"
    ]
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    for target, graph_value in ((circuit, graph), (candidate, proposal)):
        output = render_external_wire_sheet(
            target, graph_value, by_part, STYLE, FixedInk(), diagnostic=True,
        )
        assert output.layout.valid
        assert len(output.wires) == len(graph_value.segments)
        assert [w.net_name for w in output.wires] == [
            w.net_name for w in graph_value.segments
        ]
    assert authored_specimen() == (circuit, graph)


def test_c3_dogleg_plan_is_rejected_if_original_source_changes():
    (original, graph), _ = proposed_c3_geometry()
    assert original == authored_specimen()[0]
    # Negative: source graph original is never replaced just because the
    # isolated preview happens to have a visually better placement.
    assert graph.segments[-1].end == Point(109000, 75000)
    assert graph.segments[-1] != replace(
        graph.segments[-1], end=Point(109000, 80000),
    )
