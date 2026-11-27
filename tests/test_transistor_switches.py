"""S4.5: source-derived terminal geometry, arrows and independent nets."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_transistor_switches import SVG, generate
from gost_schematic.catalog.transistor_switches import (
    SwitchKind,
    SwitchSpec,
    build_switch,
    switch_review_variants,
)
from gost_schematic.core.geometry import SIDE_VECTORS, Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

VARIANTS = tuple(v for kind in SwitchKind for v in switch_review_variants(kind))


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.spec.identifier)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_switch_roles_and_clearance(variant, angle, mirror):
    symbol, part, spec = variant.symbol, variant.part, variant.spec
    roles = ("G", "C", "E") if spec.kind == SwitchKind.IGBT_N else ("G", "D", "S")
    assert tuple(p.name for p in part.pins) == roles
    assert tuple(p.label for p in symbol.pins) == roles
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == (("1",), ("2",), ("3",))
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert sum(isinstance(g, Circle) for g in symbol.graphics) == int(spec.with_case)
    tip = {
        SwitchKind.JFET_N: Point(0, 3000),
        SwitchKind.JFET_P: Point(-2000, 3000),
        SwitchKind.IGBT_N: Point(3000, 4000),
    }[spec.kind]
    marks = symbol.graphics[-3:-1] if spec.with_case else symbol.graphics[-2:]
    assert all(isinstance(g, Line) and g.end == tip for g in marks)
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


@pytest.mark.parametrize("kind", tuple(SwitchKind))
def test_injected_short_rejected(kind):
    symbol = build_switch(SwitchSpec(kind)).symbol
    wrong = replace(symbol, graphics=(
        *symbol.graphics, Line(symbol.pins[0].at, symbol.pins[2].at),
    ), conductor_topology=replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices,
                           len(symbol.graphics)),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(wrong).diagnostics
    }


def test_switch_options_and_ids():
    assert len({v.symbol.identifier for v in VARIANTS}) == 24
    with pytest.raises(TypeError):
        SwitchSpec("jfet_n")
    with pytest.raises(TypeError):
        SwitchSpec(SwitchKind.JFET_N, upper_exit="h")
    with pytest.raises(TypeError):
        SwitchSpec(SwitchKind.IGBT_N, with_case=1)


@pytest.mark.parametrize("kind", tuple(SwitchKind))
def test_native_matrices(tmp_path, kind):
    assert generate(tmp_path, kind) == 8
    for view in ("clean", "diagnostic", "protection"):
        root = ET.parse(tmp_path / f"switch-{view}.svg").getroot()
        groups = root.findall(f"{SVG}g[@data-symbol-id]")
        assert [g.get("data-symbol-id") for g in groups] == [
            v.symbol.identifier for v in switch_review_variants(kind)
        ]
        if view == "protection":
            for group in groups:
                assert not group.findall(SVG + "g")
                assert len(group.findall(SVG + "circle")) == 3
