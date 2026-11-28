"""Real transformer parts, separate winding islands and protected core."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.catalog.transformers import TransformerSpec, WindingSpec, build_transformer
from gost_schematic.core.geometry import (
    Circle,
    Point,
    Semicircle,
    StyledLine,
    primitive_stroked_bounds,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

CASES = (
    ("transformer.air_core", (2, 2)),
    ("transformer.ferromagnetic", (2, 2)),
    ("transformer.center_tapped", (2, 3)),
    ("transformer.double_tapped", (2, 4)),
    ("transformer.three_winding", (2, 2, 2)),
)


@pytest.mark.parametrize("identifier,counts", CASES)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_catalog_transformer_islands_and_keepouts(identifier, counts, angle, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert tuple(map(len, trace.pin_islands)) == counts
    assert len(part.pins) == len(symbol.pins) == sum(counts)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    for index, item in enumerate(symbol.graphics):
        if isinstance(item, (Circle, StyledLine, Semicircle)):
            b = tx.box(primitive_stroked_bounds(item, symbol.line_width_um))
            assert any(tx.box(z).includes(Point(b.min_x, b.min_y))
                       and tx.box(z).includes(Point(b.max_x, b.max_y))
                       for z in symbol.routing_keepouts)
        if isinstance(item, (Circle, StyledLine)):
            assert index not in symbol.conductor_topology.conductor_indices


def test_marked_winding_start_is_not_a_physical_pin():
    spec = TransformerSpec("transformer.custom", (WindingSpec(3), WindingSpec(4)),
                           mark_starts=True)
    normal = build_transformer(spec)
    reversed_phase = build_transformer(replace(
        spec, windings=(WindingSpec(3), WindingSpec(4, start_bottom=True)),
    ))
    assert len(normal.symbol.pins) == len(reversed_phase.symbol.pins) == 4
    assert normal.part.pins == reversed_phase.part.pins
    assert normal.symbol.pins[2].at == reversed_phase.symbol.pins[3].at
    assert inspect_conductor_topology(reversed_phase.symbol).pin_islands == (("1", "2"), ("3", "4"))
    ns = "{http://www.w3.org/2000/svg}"
    clean = ET.fromstring(render_symbol_svg(normal.symbol))
    review = ET.fromstring(render_symbol_svg(normal.symbol, review_overlay=True))
    assert len(clean.findall(f"{ns}g/{ns}circle")) == 2
    assert len(review.findall(f"{ns}circle")) == 4


@pytest.mark.parametrize("taps", [(0,), (4,), (2, 2), (3, 1)])
def test_reject_invalid_taps(taps):
    with pytest.raises(ValueError):
        WindingSpec(4, taps)
