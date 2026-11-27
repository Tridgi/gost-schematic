"""S4.2: insulated gate, broken channel, explicit body tie and stable G/D/S."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_mosfet_layouts import SVG, generate
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.catalog.transistors import (
    ChannelKind,
    MosfetSpec,
    TerminalExit,
    build_mosfet,
    mosfet_review_variants,
)
from gost_schematic.core.geometry import SIDE_VECTORS, Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

VARIANTS = mosfet_review_variants()


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.spec.identifier)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_mosfet_layout_and_protection(variant, angle, mirror):
    symbol, part, spec = variant.symbol, variant.part, variant.spec
    assert tuple(p.name for p in part.pins) == ("G", "D", "S")
    assert tuple(p.label for p in symbol.pins) == ("G", "D", "S")
    legacy = CatalogResolver().parts[f"transistor.mosfet_{spec.channel.value}_enh"]
    assert part.pins == legacy.pins
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == (("1",), ("2",), ("3",))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert sum(isinstance(g, Circle) for g in symbol.graphics) == int(spec.with_case)
    assert symbol.graphics[8:11] == tuple(
        Line(Point(0, lo), Point(0, hi))
        for lo, hi in ((-3800, -2200), (-800, 800), (2200, 3800))
    )
    assert symbol.graphics[6:8] == (
        Line(Point(4000, 0), Point(4000, 3000)),
        Line(Point(0, 0), Point(4000, 0)),
    )
    tip = Point(0, 0) if spec.channel == ChannelKind.N else Point(4000, 0)
    assert all(g.end == tip for g in symbol.graphics[11:13])
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
def test_channel_and_gate_bridges_rejected(channel):
    symbol = build_mosfet(MosfetSpec(channel)).symbol
    for bridge in (
        Line(Point(0, -3000), Point(0, 3000)),
        Line(Point(-1400, 3000), Point(0, 3000)),
    ):
        wrong = replace(symbol, graphics=(*symbol.graphics, bridge),
                        conductor_topology=replace(
                            symbol.conductor_topology,
                            conductor_indices=(*symbol.conductor_topology.conductor_indices,
                                               len(symbol.graphics)),
                        ))
        assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
            d.code for d in inspect_conductor_topology(wrong).diagnostics
        }


def test_mosfet_review_ids_and_validation():
    ids = {v.symbol.identifier for v in VARIANTS}
    assert len(ids) == 16
    assert not ids.intersection(CatalogResolver().symbols)
    with pytest.raises(TypeError):
        MosfetSpec("n")
    with pytest.raises(TypeError):
        MosfetSpec(ChannelKind.N, drain_exit="h")
    with pytest.raises(TypeError):
        MosfetSpec(ChannelKind.N, with_case=1)
    spec = MosfetSpec(ChannelKind.P, TerminalExit.HORIZONTAL)
    assert build_mosfet(spec) == build_mosfet(spec)


def test_native_mosfet_three_view_matrix(tmp_path):
    assert generate(tmp_path) == 16
    positions = {}
    for view in ("clean", "diagnostic", "protection"):
        root = ET.parse(tmp_path / f"mosfet-{view}.svg").getroot()
        groups = root.findall(f"{SVG}g[@data-symbol-id]")
        assert [g.get("data-symbol-id") for g in groups] == [
            v.symbol.identifier for v in VARIANTS
        ]
        for group in groups:
            key = group.get("data-symbol-id")
            if view == "clean":
                positions[key] = group.get("transform")
            else:
                assert positions[key] == group.get("transform")
            if view == "protection":
                assert not group.findall(SVG + "g")
                assert len(group.findall(SVG + "circle")) == 3
                assert len(group.findall(f"{SVG}rect[@data-kind='routing-keepout']")) == 1
