"""S4.1: stable terminal roles, exact elbow and outward cardinal leads."""
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from examples.review_bipolar_layouts import SVG, generate
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.catalog.transistors import (
    BipolarKind,
    BipolarSpec,
    TerminalExit,
    bipolar_review_variants,
    build_bipolar,
)
from gost_schematic.core.geometry import SIDE_VECTORS, Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_routing_protection import audit_symbol

VARIANTS = bipolar_review_variants()


@pytest.mark.parametrize("variant", VARIANTS, ids=lambda v: v.spec.identifier)
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_layout_preserves_terminal_identity_and_cardinal_exits(variant, angle, mirror):
    symbol, part, spec = variant.symbol, variant.part, variant.spec
    assert tuple(p.name for p in part.pins) == ("B", "C", "E")
    assert tuple(p.label for p in symbol.pins) == ("B", "C", "E")
    assert part.pins == CatalogResolver().parts[f"transistor.bjt_{spec.kind.value}"].pins
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",), ("3",))
    assert inspect_conductor_topology(symbol).valid
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert sum(isinstance(g, Circle) for g in symbol.graphics) == int(spec.with_case)
    assert (symbol.pins[2].at.y > 0) == (spec.kind == BipolarKind.NPN)
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


@pytest.mark.parametrize("kind", tuple(BipolarKind))
def test_arrow_follows_emitter_not_collector(kind):
    symbol = build_bipolar(BipolarSpec(kind)).symbol
    arrows = symbol.graphics[6:8]
    tip = Point(3000, 4000) if kind == BipolarKind.NPN else Point(-1000, -2000)
    assert all(isinstance(a, Line) and a.end == tip for a in arrows)
    # Selecting the drawn base bar and explicit junctions would join B/C/E.
    # This must fail closed instead of silently shorting a semiconductor.
    bad = replace(symbol, conductor_topology=replace(
        symbol.conductor_topology, conductor_indices=tuple(range(6)),
        junctions=(Point(-1000, 0), Point(-1000, -2000), Point(-1000, 2000)),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(bad).diagnostics
    }


def test_variants_unique_and_do_not_replace_legacy_catalog():
    ids = {v.symbol.identifier for v in VARIANTS}
    assert len(ids) == 16
    assert not ids.intersection(CatalogResolver().symbols)
    with pytest.raises(TypeError):
        BipolarSpec("npn")
    with pytest.raises(TypeError):
        BipolarSpec(BipolarKind.NPN, collector_exit="v")
    with pytest.raises(TypeError):
        BipolarSpec(BipolarKind.NPN, with_case=1)
    assert build_bipolar(BipolarSpec(BipolarKind.NPN, TerminalExit.HORIZONTAL)) == (
        build_bipolar(BipolarSpec(BipolarKind.NPN, TerminalExit.HORIZONTAL))
    )


def test_native_three_view_matrix(tmp_path):
    assert generate(tmp_path) == 16
    placements = {}
    for view in ("clean", "diagnostic", "protection"):
        root = ET.parse(tmp_path / f"bjt-{view}.svg").getroot()
        groups = root.findall(f"{SVG}g[@data-symbol-id]")
        assert [g.get("data-symbol-id") for g in groups] == [
            v.symbol.identifier for v in VARIANTS
        ]
        for group in groups:
            key = group.get("data-symbol-id")
            if view == "clean":
                placements[key] = group.get("transform")
            else:
                assert placements[key] == group.get("transform")
            if view == "protection":
                assert not group.findall(SVG + "g")
                assert len(group.findall(SVG + "circle")) == 3
                assert len(group.findall(f"{SVG}rect[@data-kind='routing-keepout']")) == 1
