"""S4.3: continuous channel is artwork, four-pin body remains independent."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_mosfet_layouts import SVG, generate
from gost_schematic.catalog.transistors import (
    ChannelKind,
    MosfetSpec,
    build_mosfet,
    mosfet_extended_variants,
    mosfet_review_variants,
)
from gost_schematic.core.geometry import SIDE_VECTORS, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

MODES = ((True, False), (True, True), (False, True))
VARIANTS = tuple(
    variant
    for depletion, separate in MODES
    for variant in mosfet_extended_variants(depletion=depletion, separate_body=separate)
)


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.spec.identifier)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_extended_channel_body_and_cardinal_clearance(variant, angle, mirror):
    symbol, part, spec = variant.symbol, variant.part, variant.spec
    roles = ("G", "D", "S", "BODY") if spec.separate_body else ("G", "D", "S")
    assert tuple(p.name for p in part.pins) == roles
    assert tuple(p.label for p in symbol.pins) == roles
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == tuple((p.number,) for p in symbol.pins)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    spans = ((-3800, 3800),) if spec.depletion else (
        (-3800, -2200), (-800, 800), (2200, 3800),
    )
    bars = tuple(Line(Point(0, lo), Point(0, hi)) for lo, hi in spans)
    assert symbol.graphics[8:8 + len(bars)] == bars
    assert not set(range(8, 8 + len(bars))).intersection(
        symbol.conductor_topology.conductor_indices
    )
    tie = Line(Point(4000, 0), Point(4000, 3000))
    assert (tie in symbol.graphics) == (not spec.separate_body)
    tip = Point(0, 0) if spec.channel == ChannelKind.N else Point(4000, 0)
    assert all(g.end == tip for g in symbol.graphics[8 + len(bars):10 + len(bars)])
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
        lead = [g for g in symbol.graphics if isinstance(g, Line)
                and pin.at in (g.start, g.end)]
        assert len(lead) == 1
        neighbor = lead[0].end if lead[0].start == pin.at else lead[0].start
        delta = pin.at - neighbor
        normal = SIDE_VECTORS[pin.side]
        assert delta.x * normal.y == delta.y * normal.x
        assert delta.x * normal.x + delta.y * normal.y > 0
    row = audit_symbol(symbol)
    assert not row["uncovered_functional_bounds"]
    assert not row["blocked_cardinal_escapes"]


@pytest.mark.parametrize("channel", tuple(ChannelKind))
def test_four_terminal_body_cannot_be_silently_tied_to_source(channel):
    symbol = build_mosfet(MosfetSpec(channel, separate_body=True)).symbol
    wrong = replace(symbol, graphics=(
        *symbol.graphics, Line(Point(4000, 0), Point(4000, 3000)),
    ), conductor_topology=replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices,
                           len(symbol.graphics)),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }


@pytest.mark.parametrize("channel", tuple(ChannelKind))
def test_depletion_channel_is_not_an_ideal_short(channel):
    symbol = build_mosfet(MosfetSpec(channel, depletion=True)).symbol
    wrong = replace(symbol, conductor_topology=replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices, 8),
        junctions=(Point(0, -3000), Point(0, 0), Point(0, 3000)),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }


def test_all_mosfet_review_ids_distinct_and_options_strict():
    assert len({v.symbol.identifier for v in (*mosfet_review_variants(), *VARIANTS)}) == 64
    with pytest.raises(TypeError):
        MosfetSpec(ChannelKind.N, depletion=1)
    with pytest.raises(TypeError):
        MosfetSpec(ChannelKind.P, separate_body="yes")


@pytest.mark.parametrize("depletion,separate", MODES)
def test_extended_native_matrices(tmp_path, depletion, separate):
    assert generate(tmp_path, depletion=depletion, separate_body=separate) == 16
    expected = mosfet_extended_variants(depletion=depletion, separate_body=separate)
    for view in ("clean", "diagnostic", "protection"):
        root = ET.parse(tmp_path / f"mosfet-{view}.svg").getroot()
        groups = root.findall(f"{SVG}g[@data-symbol-id]")
        assert [g.get("data-symbol-id") for g in groups] == [
            v.symbol.identifier for v in expected
        ]
        if view == "protection":
            for group in groups:
                assert not group.findall(SVG + "g")
                assert len(group.findall(SVG + "circle")) == (4 if separate else 3)
                assert len(group.findall(f"{SVG}rect[@data-kind='routing-keepout']")) == 1
