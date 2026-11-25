"""Three phase winding graph, actual node patterns, and terminal clearance."""
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Circle, Line, Point, Semicircle, StyledLine
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transformer.three_phase_y_yn", "Y", "YN", (("1", "2", "3"), ("4", "5", "6", "7"),)),
    ("transformer.three_phase_yn_yn", "YN", "YN", (("1", "2", "3", "4"), ("5", "6", "7", "8"),)),
    ("transformer.three_phase_y_y", "Y", "Y", (("1", "2", "3"), ("4", "5", "6"),)),
    ("transformer.three_phase_yn_delta", "YN", "D", (("1", "2", "3", "4"), ("5", "6", "7"),)),
    ("transformer.three_phase_delta_yn", "D", "YN", (("1", "2", "3"), ("4", "5", "6", "7"),)),
    ("choke.three_phase_star", None, "Y", (("1", "2", "3"),)),
)


@pytest.mark.parametrize("identifier,primary,secondary,groups", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_three_phase_banks(identifier, primary, secondary, groups, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == groups
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert len(symbol.pins) == len(part.pins) == sum(map(len, groups))
    assert sum(isinstance(g, Semicircle) for g in symbol.graphics) == (18 if primary else 9)
    assert sum(isinstance(g, StyledLine) for g in symbol.graphics) == 1
    assert all(not isinstance(symbol.graphics[i], (StyledLine, Circle))
               for i in symbol.conductor_topology.conductor_indices)
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(box).expanded(550).includes(tx.apply(pin.at))
                       for box in symbol.routing_boxes)
    for mode, sign in ((primary, -1), (secondary, 1)):
        if mode is None:
            continue
        points = {p for p in symbol.conductor_topology.junctions if p.y * sign > 0}
        expected = {(0, 4)} if mode == "Y" else (
            {(0, 4), (10, 4)} if mode == "YN" else {(-10, 21), (0, 21), (10, 21)}
        )
        assert points == {Point(x * 1000, y * sign * 1000) for x, y in expected}
        assert any(p.name.endswith("_N") for p in part.pins
                   if symbol.pins[int(p.number) - 1].at.y * sign > 0) == (mode == "YN")
    ns = "{http://www.w3.org/2000/svg}"
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert len(review.findall(f"{ns}circle")) == len(symbol.pins)
    assert len(review.findall(f"{ns}rect[@data-kind='routing-keepout']")) == 1
    # Three-phase winding paths must not include a conductive bridge across the core.
    for i in symbol.conductor_topology.conductor_indices:
        item = symbol.graphics[i]
        if isinstance(item, Line):
            assert item.start.y * item.end.y > 0
