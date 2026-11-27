"""S4.4: body diode orientation, explicit nodes, and ideal-wire isolation."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_mosfet_layouts import SVG, generate
from gost_schematic.catalog.transistors import (
    ChannelKind,
    MosfetSpec,
    build_mosfet,
    mosfet_body_diode_variants,
    mosfet_extended_variants,
)
from gost_schematic.core.geometry import Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

VARIANTS = mosfet_body_diode_variants()


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.spec.identifier)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_body_diode_layout(variant, angle, mirror):
    symbol, part, spec = variant.symbol, variant.part, variant.spec
    assert tuple(p.name for p in part.pins) == ("G", "D", "S")
    baseline = build_mosfet(replace(spec, body_diode=False))
    assert part.pins == baseline.part.pins
    assert symbol.pins == baseline.symbol.pins
    assert symbol.graphics[:len(baseline.symbol.graphics)] == baseline.symbol.graphics
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == (("1",), ("2",), ("3",))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    cathode = -1200 if spec.channel == ChannelKind.N else 1200
    assert Line(Point(6200, cathode), Point(9800, cathode)) in symbol.graphics
    assert Line(Point(6500, -cathode), Point(9500, -cathode)) in symbol.graphics
    assert set(symbol.conductor_topology.junctions) == {
        Point(4000, -3000), Point(4000, 3000),
    }
    assert {g.center for g in symbol.graphics if isinstance(g, Circle)} == {
        Point(4000, -3000), Point(4000, 3000),
    }
    tx = Transform(angle, mirror)
    for pin in symbol.pins:
        assert not any(tx.box(b).expanded(550).includes(tx.apply(pin.at))
                       for b in symbol.routing_boxes)
    row = audit_symbol(symbol)
    assert not row["uncovered_functional_bounds"]
    assert not row["blocked_cardinal_escapes"]


@pytest.mark.parametrize("channel", tuple(ChannelKind))
def test_diode_axis_must_not_short_drain_source(channel):
    symbol = build_mosfet(MosfetSpec(channel, body_diode=True)).symbol
    axis = next(i for i, g in enumerate(symbol.graphics) if isinstance(g, Line)
                and {g.start, g.end} == {Point(8000, -1200), Point(8000, 1200)})
    assert axis not in symbol.conductor_topology.conductor_indices
    wrong = replace(symbol, conductor_topology=replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices, axis),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }


def test_body_diode_options_and_ids():
    for key in ("depletion", "separate_body", "with_case"):
        with pytest.raises(ValueError):
            MosfetSpec(ChannelKind.N, body_diode=True, **{key: True})
    with pytest.raises(TypeError):
        MosfetSpec(ChannelKind.N, body_diode=1)
    all_variants = tuple(
        v for depletion in (False, True) for separate in (False, True)
        for v in mosfet_extended_variants(depletion=depletion, separate_body=separate)
    ) + VARIANTS
    assert len({v.symbol.identifier for v in all_variants}) == 72


def test_native_diode_matrix(tmp_path):
    assert generate(tmp_path, body_diode=True) == 8
    for view in ("clean", "diagnostic", "protection"):
        root = ET.parse(tmp_path / f"mosfet-{view}.svg").getroot()
        groups = root.findall(f"{SVG}g[@data-symbol-id]")
        assert [g.get("data-symbol-id") for g in groups] == [
            v.symbol.identifier for v in VARIANTS
        ]
        if view == "protection":
            for group in groups:
                assert not group.findall(SVG + "g")
                assert len(group.findall(SVG + "circle")) == 3
