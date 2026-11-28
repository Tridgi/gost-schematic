"""Source-based geometry contracts for the user's R6 corrections."""
import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Semicircle, Side, StyledLine
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from scripts.audit_routing_protection import audit_symbol

IDS = (
    "magnetic_amplifier.general",
    "magnetic_amplifier.parallel_work",
    "transductor.general",
    "transformer.auto_fixed",
    "transformer.auto_regulated",
)


@pytest.mark.parametrize("identifier", IDS)
def test_reviewed_profiles_keep_pins_and_protect_all_functional_ink(identifier):
    part, symbol = CatalogResolver().resolve(identifier)
    assert symbol.revision == (3 if identifier == "magnetic_amplifier.general" else 2)
    assert len(part.pins) == len(symbol.pins)
    assert inspect_conductor_topology(symbol).valid
    row = audit_symbol(symbol)
    assert not row["blocked_cardinal_escapes"]
    assert not row["uncovered_functional_bounds"]


def test_general_amplifier_has_three_lobes_and_exact_triangle_contact():
    symbol = CatalogResolver().symbols["magnetic_amplifier.general"]
    arcs = [g for g in symbol.graphics if isinstance(g, Semicircle)]
    assert len(arcs) == 3
    assert all(g.bulge == Side.TOP for g in arcs)
    assert [g.center for g in arcs] == [Point(-4600, 0), Point(-2400, 0), Point(-200, 0)]
    assert all(g.radius == 1100 for g in arcs)
    steps = [g for g in symbol.graphics if isinstance(g, StyledLine)]
    assert len(steps) == 3
    assert [(g.start, g.end) for g in steps] == [
        (Point(-2400, -2100), Point(-900, -2100)),
        (Point(-2400, -2100), Point(-2400, 2100)),
        (Point(-3900, 2100), Point(-2400, 2100)),
    ]
    # Inner magnetic strokes must not touch either triangular edge.
    # Triangle edges are y = +/- 0.4*(7000-x), reserve 0.4 mm vertical gap.
    for step in steps:
        for point in (step.start, step.end):
            assert 5 * abs(point.y) + 2000 <= 2 * (7000 - point.x)
    assert Line(Point(-500, 3000), Point(-500, 8000)) in symbol.graphics
    assert symbol.pins[2].at == Point(-500, 8000)
    assert symbol.pins[2].side == Side.BOTTOM
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",), ("3",))
    assert len(symbol.pins) == 3


def test_parallel_work_control_has_vertical_leads_and_separate_cores():
    symbol = CatalogResolver().symbols["magnetic_amplifier.parallel_work"]
    assert Line(Point(-4000, -9000), Point(-4000, -17000)) in symbol.graphics
    assert Line(Point(-4000, 9000), Point(-4000, 17000)) in symbol.graphics
    assert len([g for g in symbol.graphics if isinstance(g, StyledLine)]) == 4
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2"), ("3", "4"))
    assert Point(8000, 0) not in symbol.conductor_topology.junctions


def test_transductor_enclosure_is_horizontal():
    symbol = CatalogResolver().symbols["transductor.general"]
    rect = next(g for g in symbol.graphics if isinstance(g, Rectangle))
    assert rect == Rectangle(Box(-7000, -5000, 7000, 5000))
    assert len([g for g in symbol.graphics if isinstance(g, Semicircle)]) == 3


def test_fixed_auto_core_does_not_touch_vertical_wires():
    symbol = CatalogResolver().symbols["transformer.auto_fixed"]
    core = next(g for g in symbol.graphics if isinstance(g, StyledLine))
    assert core.start == Point(-6000, -4000)
    assert core.end == Point(6000, -4000)
    assert len([g for g in symbol.graphics if isinstance(g, Semicircle)]) == 3
    assert symbol.pins[3].at == Point(2000, 10000)
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2", "3", "4"),)


def test_unneeded_hysteresis_is_removed_from_both_catalogs():
    catalog = CatalogResolver()
    identifier = "magnetic_amplifier.rectangular_hysteresis"
    assert identifier not in catalog.symbols
    assert identifier not in catalog.parts
