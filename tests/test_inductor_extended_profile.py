"""Extended winding profiles, exact arc-boundary taps and legacy compatibility."""
from dataclasses import replace

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.catalog.inductors import CoreKind, InductorSpec, LeadStyle, build_inductor
from gost_schematic.core.geometry import Point, Semicircle, Side, StyledLine, primitive_stroked_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

IDS = (
    "inductor.short_core",
    "inductor.perpendicular_air",
    "inductor.perpendicular_core",
    "inductor.core_junction_tap",
    "inductor.core_double_junction_tap",
    "inductor.core_perpendicular_taps",
)


@pytest.mark.parametrize("turns", range(1, 13))
@pytest.mark.parametrize("style", tuple(LeadStyle))
def test_exact_lobes_and_terminal_directions(turns, style):
    built = build_inductor(InductorSpec(
        "inductor.custom", turns=turns, lead_style=style,
        core=CoreKind.FERROMAGNETIC, protect_functional=True,
    ))
    symbol = built.symbol
    assert sum(isinstance(g, Semicircle) for g in symbol.graphics) == turns
    assert len(symbol.pins) == 2
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2"),)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert all(p.side == Side.BOTTOM for p in symbol.pins) == (style == LeadStyle.PERPENDICULAR)


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_installed_extended_profiles_preserve_ink_and_pin_clearance(identifier, rotation, mirror):
    part, symbol = CatalogResolver().resolve(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid
    assert trace.pin_islands == (tuple(sorted(p.number for p in part.pins)),)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    transform = Transform(rotation, mirror)
    assert symbol.routing_keepouts
    for pin in symbol.pins:
        assert not any(transform.box(box).expanded(550).includes(transform.apply(pin.at))
                       for box in symbol.routing_boxes)
    for shape in symbol.graphics:
        if isinstance(shape, (Semicircle, StyledLine)):
            ink = transform.box(primitive_stroked_bounds(shape, symbol.line_width_um))
            assert any(transform.box(box).includes(Point(ink.min_x, ink.min_y))
                       and transform.box(box).includes(Point(ink.max_x, ink.max_y))
                       for box in symbol.routing_keepouts)


def test_core_taps_join_exact_arc_boundaries_and_share_bottom_alignment():
    base = InductorSpec("inductor.custom", turns=4, core=CoreKind.FERROMAGNETIC,
                        lead_style=LeadStyle.PERPENDICULAR, tap_junctions=(1, 3))
    built = build_inductor(base)
    assert [p.at for p in built.symbol.pins] == [
        Point(-8000, 4000), Point(8000, 4000), Point(-4000, 4000), Point(4000, 4000)
    ]
    assert built.symbol.conductor_topology.junctions == (Point(-4000, 0), Point(4000, 0))
    assert inspect_conductor_topology(built.symbol).pin_islands == (("1", "2", "3", "4"),)
    for taps in ((0,), (4,), (1, 1)):
        with pytest.raises(ValueError):
            replace(base, tap_junctions=taps)
    with pytest.raises(ValueError):
        replace(base, tap_turns=(1,))
    with pytest.raises(ValueError):
        replace(base, lead_um=1000)
