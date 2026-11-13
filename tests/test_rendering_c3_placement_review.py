"""Issue #35 archive versus accepted PR #62: never move live C3 again."""
from xml.etree import ElementTree as ET

from examples.review_c3_placement_proposal import (
    archive_c3_svg,
    current_c3_geometry,
)
from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Box, Point
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import validate_external_wires

_SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("unit-test-face.ttf", "Unit Test", 3500, 500)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


def _wire_lines(root: ET.Element) -> list[ET.Element]:
    return root.findall(f".//{_SVG}line[@data-layer='wires']")


def test_historical_issue35_svg_is_immutable_archive_not_current_model():
    for diagnostic in (False, True):
        old = archive_c3_svg(diagnostic=diagnostic)
        assert len(_wire_lines(old)) == 18
        assert len(old.findall(f".//{_SVG}circle[@data-kind='authored-junction']")) == 3
        c3 = old.find(f".//{_SVG}g[@data-reference='C3']")
        assert c3 is not None
        leads = c3.findall(f"./{_SVG}line")[:2]
        assert leads[0].get("x1") == "91" and leads[0].get("y1") == "75"
        assert leads[1].get("x2") == "109" and leads[1].get("y2") == "75"
        assert any(
            edge.get("x1") == edge.get("x2") == "84"
            and edge.get("y1") == "80" and edge.get("y2") == "75"
            for edge in _wire_lines(old)
        )


def test_live_pr62_c3_has_current_revision_two_pins_and_exact_16_wire_graph():
    (circuit, graph) = current_c3_geometry()
    parts, symbols = definitions()
    c3 = next(item for item in circuit.components if item.reference == "C3")
    part, symbol = parts[c3.part_id], symbols[c3.part_id]
    assert part.identifier == part.symbol_id == symbol.identifier == (
        "capacitor.electrolytic"
    )
    assert symbol.revision == 1 and symbol.status.value == "draft"
    assert {pin.number: pin.at for pin in symbol.pins} == {
        "1": Point(-9000, 0), "2": Point(9000, 0),
    }
    assert {pin.number: pin.polarity.value for pin in part.pins} == {
        "1": "positive", "2": "negative",
    }
    assert c3.origin == Point(100000, 80000)
    assert c3.pin_positions(symbol) == {
        "1": Point(91000, 80000), "2": Point(109000, 80000),
    }
    assert len(graph.segments) == 16
    assert len(graph.junctions) == 3
    assert graph.junctions == (
        Point(40000, 20000), Point(40000, 40000), Point(120000, 40000),
    )
    assert tuple(
        ((w.start.x, w.start.y), (w.end.x, w.end.y), w.net_name)
        for w in graph.segments[-4:]
    ) == (
        ((40000, 40000), (40000, 80000), "TOP"),
        ((40000, 80000), (91000, 80000), "TOP"),
        ((120000, 40000), (120000, 80000), "RIGHT"),
        ((120000, 80000), (109000, 80000), "RIGHT"),
    )
    assert len(circuit.nets) == 5 and len(circuit.components) == 6
    assert validate_external_wires(circuit, graph, parts, symbols) == ()
    assert not [
        d for d in validate_circuit(circuit, parts, symbols)
        if d.severity.value == "error"
    ]


def test_live_svg_keepout_annotations_pins_wires_junctions_are_preserved():
    circuit, graph = current_c3_geometry()
    immutable = (circuit, graph)
    parts, symbols = definitions()
    by_part = {pid: symbols[part.symbol_id] for pid, part in parts.items()}
    for diagnostic in (False, True):
        output = render_external_wire_sheet(
            circuit, graph, by_part, STYLE, FixedInk(), diagnostic=diagnostic,
        )
        assert output.layout.valid
        assert len(output.wires) == 16
        root = ET.fromstring(output.svg)
        lines = _wire_lines(root)
        assert len(lines) == 16
        assert [(w.get("data-net"), w.get("data-wire-index"))
                for w in lines] == [
            (w.net_name, str(i)) for i, w in enumerate(graph.segments)
        ]
        assert len(root.findall(
            f".//{_SVG}circle[@data-kind='authored-junction']"
        )) == len(graph.junctions) == 3
        assert len(root.findall(f".//{_SVG}g[@data-layer='symbols']")) == 6
    assert (circuit, graph) == immutable
    assert authored_specimen() == immutable


def test_archive_is_not_used_to_relocate_current_authoritative_c3():
    circuit, graph = current_c3_geometry()
    assert next(item.origin for item in circuit.components if item.reference == "C3") == (
        Point(100000, 80000)
    )
    assert all(
        Point(84000, 75000) not in (edge.start, edge.end)
        for edge in graph.segments
    )
    assert graph.segments[-1].end == Point(109000, 80000)
    assert len(_wire_lines(archive_c3_svg())) == 18
    assert len(graph.segments) == 16
