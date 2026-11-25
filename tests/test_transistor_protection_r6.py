"""R6: actual semiconductor outlines and arrows stay protected in every pose."""
import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from scripts.audit_routing_protection import audit_symbol

IDS = (
    "transistor.bjt_npn",
    "transistor.bjt_npn.with_case",
    "transistor.bjt_pnp.with_case",
    "transistor.mosfet_n_enh.with_case",
    "transistor.mosfet_p_enh.with_case",
)


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_transistor_functional_ink_and_exit(identifier, rotation, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    assert symbol.revision == 2
    assert symbol.routing_keepouts
    assert len(part.pins) == len(symbol.pins) == 3
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",), ("3",))
    tx = Transform(rotation, mirror)
    for index, shape in enumerate(symbol.graphics):
        if index in symbol.conductor_topology.conductor_indices:
            continue
        ink = tx.box(primitive_stroked_bounds(shape, symbol.line_width_um))
        assert any(tx.box(zone).includes(Point(ink.min_x, ink.min_y))
                   and tx.box(zone).includes(Point(ink.max_x, ink.max_y))
                   for zone in symbol.routing_keepouts)
    for pin in symbol.pins:
        assert not any(tx.box(zone).expanded(550).includes(tx.apply(pin.at))
                       for zone in symbol.routing_boxes)
    row = audit_symbol(symbol)
    assert row["uncovered_functional_bounds"] == []
    assert row["blocked_cardinal_escapes"] == []
