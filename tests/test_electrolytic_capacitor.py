"""C-EL-P draft is distinct from general polarized capacitor (Issue #10).

GOST 2.728-74, table 4, item 2a and table 6, item 10 describe the
electrolytic UGO. Only plate narrow-side interpretation is traceable;
the chosen overall length, inner gap and leads are EDITORIAL/DRAFT.
"""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Box, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
)
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef
from gost_schematic.model.part import VoltageOrientationRule
from gost_schematic.model.pins import ElectricalType, TerminalPolarity
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.dimensional_checks import check_verified_dimensions
from gost_schematic.validation.symbol_checks import validate_symbol


def _symbol(name="electrolytic"):
    source = files("gost_schematic").joinpath(
        f"catalog/symbols/capacitors/{name}.json"
    )
    return load_symbol(Path(str(source)))


def _part(name="electrolytic"):
    source = files("gost_schematic").joinpath(
        f"catalog/parts/capacitors/{name}.json"
    )
    return load_part(Path(str(source)))


class _Font:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, len(text) * 500, 1), len(text) * 500)


def _circuits(symbol=None):
    part = _part()
    symbol = symbol or _symbol()
    circuit = Circuit(
        (ComponentInstance("C19", "capacitor.electrolytic"),), ()
    )
    return validate_circuit(
        circuit, {part.identifier: part}, {symbol.identifier: symbol}
    )


def _graphic_plate_boxes(symbol):
    """Bounds of two outlined, nonfilled electrodes in the DRAFT profile."""
    result = []
    for offset in (2, 6):
        lines = symbol.graphics[offset:offset + 4]
        xs = [p.x for line in lines for p in (line.start, line.end)]
        ys = [p.y for line in lines for p in (line.start, line.end)]
        result.append((min(xs), min(ys), max(xs), max(ys)))
    return tuple(result)


def test_electrolytic_is_independent_draft_catalog_symbol():
    symbol = _symbol()
    old = _symbol("polarized")
    assert symbol.identifier == "capacitor.electrolytic"
    assert symbol.identifier not in {old.identifier, _symbol("fixed").identifier}
    assert symbol.revision == 1
    assert symbol.status == SymbolStatus.DRAFT
    assert len(symbol.graphics) == 12
    assert all(isinstance(shape, Line) for shape in symbol.graphics)
    assert [pin.number for pin in symbol.pins] == ["1", "2"]
    assert [pin.side for pin in symbol.pins] == [Side.LEFT, Side.RIGHT]
    assert [slot.key for slot in symbol.annotation_slots] == ["refdes", "value"]
    assert "табл. 4, поз. 2а" in " ".join(symbol.standard_refs)
    assert "табл. 6, поз. 10" in " ".join(symbol.standard_refs)
    assert "EDITORIAL_ASSUMPTION" in " ".join(symbol.standard_refs)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]


def test_outlined_electrolytic_plates_have_dedicated_geometry():
    symbol = _symbol()
    assert _graphic_plate_boxes(symbol) == (
        (-2250, -4000, -750, 4000),
        (750, -4000, 2250, 4000),
    )
    # These numbers are a REVIEW FIXTURE, NOT GOST certification.
    assert symbol.graphics[2:10] != _symbol("fixed").graphics[2:10]
    assert symbol.body_keepout.includes(Point(-3500, -4500))
    # First/last leads attach to each plate's outward boundary at y=0.
    assert symbol.graphics[0] == Line(Point(-9000, 0), Point(-2250, 0))
    assert symbol.graphics[1] == Line(Point(2250, 0), Point(9000, 0))


def test_dimensions_of_special_electrolytic_ugo_are_not_normatively_certified():
    assessment = check_verified_dimensions(_symbol())
    assert assessment.applicable_rules == ()
    assert assessment.passed_rules == ()
    assert assessment.valid
    assert check_verified_dimensions(_symbol("polarized")).applicable_rules


def test_physical_pins_are_separate_from_plus_symbol_and_have_stable_polarity():
    part, symbol = _part(), _symbol()
    assert part.symbol_id == part.identifier == symbol.identifier
    assert part.nominal_kind == QuantityKind.CAPACITANCE
    assert part.reference_prefix == "C"
    assert part.voltage_orientation_rule == (
        VoltageOrientationRule.POSITIVE_NOT_BELOW_NEGATIVE
    )
    assert [(pin.number, pin.name, pin.polarity) for pin in part.pins] == [
        ("1", "PLUS", TerminalPolarity.POSITIVE),
        ("2", "MINUS", TerminalPolarity.NEGATIVE),
    ]
    assert all(pin.electrical_type == ElectricalType.PASSIVE for pin in part.pins)
    # GOST graphic '+' is at positive side; '-' need not be printed.
    assert [pin.label for pin in symbol.pins] == ["+", ""]


def test_plus_ink_is_explicitly_nonconductive_and_next_to_positive_plate():
    symbol = _symbol()
    horizontal, vertical = symbol.graphics[-2:]
    assert horizontal.start.y == horizontal.end.y == -4500
    assert horizontal.start.x < vertical.start.x < horizontal.end.x
    assert vertical.start.x == vertical.end.x == -3500
    assert vertical.start.y < horizontal.start.y < vertical.end.y
    assert max(horizontal.start.x, horizontal.end.x) < -2250
    topology = symbol.conductor_topology
    assert topology is not None
    assert set(topology.conductor_indices) == set(range(10))
    assert all(i not in topology.conductor_indices for i in (10, 11))


def test_internal_graph_is_two_independent_conducting_islands():
    symbol = _symbol()
    result = inspect_conductor_topology(symbol)
    assert result.valid, result.diagnostics
    assert result.pin_islands == (("1",), ("2",))
    assert result.visited_primitives == 10
    assert result.explicit_junctions == 2
    assert tuple(symbol.conductor_topology.pin_groups) == (("1",), ("2",))


def test_accidental_conductive_bridge_between_plates_is_a_hard_error():
    symbol = _symbol()
    topology = symbol.conductor_topology
    assert topology is not None
    new_segment = Line(Point(-750, 4000), Point(750, 4000))
    flawed = replace(
        symbol,
        graphics=(*symbol.graphics, new_segment),
        conductor_topology=replace(
            topology, conductor_indices=(*topology.conductor_indices, 12)
        ),
    )
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        issue.code for issue in inspect_conductor_topology(flawed).diagnostics
    }


def test_moved_left_lead_breaks_explicit_junction_and_creates_orphan():
    symbol = _symbol()
    modified = list(symbol.graphics)
    modified[0] = Line(Point(-9000, 0), Point(-3000, 0))
    result = inspect_conductor_topology(
        replace(symbol, graphics=tuple(modified))
    )
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert {"TOPOLOGY_JUNCTION_DANGLING", "TOPOLOGY_ORPHAN_CONDUCTOR"} <= codes


def test_missing_electrode_edge_detected_by_graph_validator():
    symbol = _symbol()
    topology = symbol.conductor_topology
    assert topology is not None
    flawed = replace(
        symbol,
        conductor_topology=replace(
            topology,
            conductor_indices=tuple(
                i for i in topology.conductor_indices if i != 5
            ),
        ),
    )
    assert "TOPOLOGY_ORPHAN_CONDUCTOR" in {
        issue.code for issue in inspect_conductor_topology(flawed).diagnostics
    }


def test_wrong_plus_label_on_negative_physical_pin_is_rejected():
    symbol = _symbol()
    wrong = replace(
        symbol, pins=(symbol.pins[0], replace(symbol.pins[1], label="+"))
    )
    assert "GRAPHIC_POLARITY_MISMATCH" in {
        item.code for item in _circuits(wrong)
    }


def test_swapped_graphical_polarity_is_rejected():
    symbol = _symbol()
    wrong = replace(symbol, pins=(
        replace(symbol.pins[0], label="-"),
        replace(symbol.pins[1], label="+"),
    ))
    codes = {issue.code for issue in _circuits(wrong)}
    assert "GRAPHIC_POLARITY_MISMATCH" in codes
    assert "PIN_MAPPING_MISMATCH" not in codes


def test_draft_ugo_never_raises_false_polarity_approval():
    codes = {issue.code for issue in _circuits()}
    assert "GRAPHIC_POLARITY_MISMATCH" not in codes
    assert "POLARITY_UNVERIFIABLE" in codes
    assert "UNAPPROVED_SYMBOL" in codes


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_orientation_preserves_physical_pins_and_conductive_islands(rotation, mirror):
    symbol, part = _symbol(), _part()
    t = Transform(rotation=rotation, mirror_x=mirror)
    instance = ComponentInstance(
        "C19", part.identifier, Point(20000, 18000), t,
    )
    ports = pin_corridors_for_component(symbol, instance)
    assert [item.pin for item in ports] == [
        PinRef("C19", "1"), PinRef("C19", "2"),
    ]
    assert ports[0].side == t.side(Side.LEFT)
    assert ports[1].side == t.side(Side.RIGHT)
    assert instance.pin_positions(symbol)["1"] == ports[0].contact
    assert instance.pin_positions(symbol)["2"] == ports[1].contact
    assert ports[0].contact != ports[1].contact
    assert part.pins[0].polarity == TerminalPolarity.POSITIVE
    assert part.pins[1].polarity == TerminalPolarity.NEGATIVE
    # Geometric conductor inspection works on transformed actual strokes.
    transformed = replace(
        symbol,
        graphics=tuple(t.primitive(shape) for shape in symbol.graphics),
        pins=tuple(replace(pin, at=t.apply(pin.at), side=t.side(pin.side))
                   for pin in symbol.pins),
        body_keepout=t.box(symbol.body_keepout),
        conductor_topology=replace(
            symbol.conductor_topology,
            junctions=tuple(t.apply(p) for p in symbol.conductor_topology.junctions),
        ),
    )
    result = inspect_conductor_topology(transformed)
    assert result.valid, result.diagnostics
    assert result.pin_islands == (("1",), ("2",))


def test_nominal_labels_have_independent_text_obstacles():
    symbol = _symbol()
    instance = ComponentInstance(
        "C19", "capacitor.electrolytic",
        nominal=Quantity.from_unit("470", Unit.MICROFARAD),
    )
    style = TextStyle("/fake/type-a.ttf", "OpenGost Type A", 3500, 500)
    placed = bind_component_annotations(symbol, instance, style)
    assert [request.text for request in placed.requests] == ["C19", "470мк"]
    layout = place_annotations(
        placed.requests, _Font(), boxes=obstacles_for_component(symbol, instance)
    )
    assert layout.valid
    assert not any(
        item.collision_bounds.overlaps(symbol.body_keepout)
        for item in layout.placements
    )


def test_svg_is_vector_and_keeps_both_separate_electrodes():
    symbol = _symbol()
    xml = ET.fromstring(render_symbol_svg(symbol))
    svg = "{http://www.w3.org/2000/svg}"
    lines = xml.findall(f".//{svg}line")
    assert len(lines) == len(symbol.graphics)
    assert len(lines) == 12
    assert not xml.findall(f".//{svg}image")
