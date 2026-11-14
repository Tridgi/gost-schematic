"""Cycle9 native whole-23 paint integration, real and hostile tests.

Generic negative fixtures run on normal CI. Full source integration is
MANDATORY in the separate workflow that stages pinned #97/#113/reference.
"""
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.render_tl494_full_native_cycle9 import (
    _render_variant,
    construct_native_paint,
)
from gost_schematic.core.geometry import SIDE_VECTORS, Box, Point, Rectangle, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent,
    IcFunctionReading,
    IcResolvedUnit,
    ResolvedIcPin,
    propose_ic_dimensions,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_sheet_composition import (
    compose_authoritative_ic_layers,
)

NS = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("/tmp/testfont-placeholder.ttf", "Synthetic Fixed Ink", 3500, 500)


class FixedInk:
    def measure(self, text, style):
        return MeasuredText(
            Box(0, -3500, max(1, len(text))*500, 1),
            max(1, len(text))*500,
        )


def fixture(diagnostic=False):
    dummy = []
    for number, side, row, role in (
        ("1", Side.LEFT, 1, "in"), ("2", Side.LEFT, 2, "in"),
        ("3", Side.RIGHT, 1, "out"), ("4", Side.RIGHT, 2, "out"),
    ):
        dummy.append(ResolvedIcPin(
            f"DD1.P{number}", number, "A" if side is Side.LEFT else "Q",
            side, row, Point(1, int(number)), role,
        ))
    content = IcFieldContent("AND")
    layout = propose_ic_dimensions(
        content, tuple(dummy), STYLE, FixedInk(),
    )
    origin = Point(100000, 150000)
    body = Box(0, 0, layout.width_um, layout.height_um)
    resolved = []
    for pin in dummy:
        local = Point(
            0 if pin.side is Side.LEFT else layout.width_um,
            pin.row*layout.row_pitch_um + layout.row_pitch_um//2,
        )
        normal = SIDE_VECTORS[pin.side]
        resolved.append(replace(pin, anchor=Point(
            origin.x+local.x+normal.x*layout.lead_length_um,
            origin.y+local.y+normal.y*layout.lead_length_um,
        )))
    unit = IcResolvedUnit("DD1", body, tuple(resolved), content, origin)
    graphics = tuple(GraphicPin(
        pin.number, pin.anchor-origin, pin.side, pin.label,
    ) for pin in resolved)
    symbol = SymbolDefinition(
        "test.ic", 1, (Rectangle(body),), graphics,
        body_keepout=body, line_width_um=300, status=SymbolStatus.DRAFT,
    )
    circuit = Circuit(
        (ComponentInstance("DD1", "test.ic", origin, Transform()),),
        (
            Net("A", (PinRef("DD1", "1"), PinRef("DD1", "3"))),
            Net("B", (PinRef("DD1", "2"), PinRef("DD1", "4"))),
        ),
    )
    target_nets = {
        pin: net.name for net in circuit.nets for pin in net.members
    }
    targets = tuple(IcConnectionTarget(
        pin.pin_id, PinRef("DD1", pin.number), pin.anchor, True,
        target_nets[PinRef("DD1", pin.number)],
    ) for pin in unit.pins)
    paint = render_resolved_ic(
        unit, STYLE, FixedInk(), editor_targets=targets,
        editor_overlay=diagnostic,
    )
    root = ET.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g data-reference="DD1" data-layer="symbols" /></svg>'
    )
    return root, circuit, {"test.ic": symbol}, paint


@pytest.mark.parametrize("diagnostic", (False, True))
def test_native_compositor_authoritative_pinrefs_and_debug_policy(diagnostic):
    root, circuit, symbols, paint = fixture(diagnostic)
    before = tuple(circuit.nets)
    compose_authoritative_ic_layers(
        root, circuit, symbols, {"DD1": paint},
        diagnostic=diagnostic,
    )
    assert root.get("data-native-ic-composition") == "exact-circuit-pinrefs"
    assert circuit.nets == before
    group = root.find(f"./{NS}g[@data-composed-engine='physical-ic-renderer']")
    assert group is not None and group.get("data-physical-pin-count") == "4"
    squares = group.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect"
    )
    assert len(squares) == (4 if diagnostic else 0)
    assert not squares or all(x.get("fill") == "#148645" for x in squares)


@pytest.mark.parametrize("change,error", (
    ("wrong_net", "SHEET_IC_FORGED_TARGET_PINREF_OR_NET"),
    ("wrong_ref", "SHEET_IC_FORGED_TARGET_PINREF_OR_NET"),
    ("partial", "SHEET_IC_INCOMPLETE_TARGET_MANIFEST"),
    ("false_nc", "SHEET_IC_FORGED_NC_OR_DISABLED_TARGET"),
    ("one_um", "SHEET_IC_PINREF_POINT_INVENTORY_MISMATCH"),
    ("missing_marker", "SHEET_IC_DEBUG_LAYER_POLICY_MISMATCH"),
))
def test_native_sheet_rejects_untrusted_targets(change, error):
    root, circuit, symbols, paint = fixture(diagnostic=True)
    targets = list(paint.connection_targets)
    if change == "wrong_net":
        targets[0] = replace(targets[0], net_id="FORGED_NET")
    elif change == "wrong_ref":
        targets[0] = replace(targets[0], pin_ref=PinRef("XX1", "1"))
    elif change == "partial":
        targets.pop()
    elif change == "false_nc":
        targets[0] = replace(targets[0], connectable=False, reason="NC")
    elif change == "one_um":
        first = paint.pin_anchors[0]
        paint = replace(paint, pin_anchors=(
            (first[0], Point(first[1].x+1, first[1].y)),
            *paint.pin_anchors[1:],
        ))
    elif change == "missing_marker":
        root, circuit, symbols, paint = fixture(diagnostic=False)
    paint = replace(paint, connection_targets=tuple(targets))
    with pytest.raises((ValueError, TypeError), match=error):
        compose_authoritative_ic_layers(
            root, circuit, symbols, {"DD1": paint}, diagnostic=True,
        )


def _pinned_font():
    font = os.environ.get("REVIEW_FONT")
    exists = (
        Path("src/gost_schematic/electrical/tl494cn.py").exists()
        and Path("src/gost_schematic/catalog/source_profiles.py").exists()
        and Path("examples/tl494_named_photo_sheet.py").exists()
    )
    mandatory = os.environ.get("PAINT_PINNED_NATIVE_REQUIRED") == "1"
    if mandatory:
        assert exists and font and Path(font).exists(), (
            "PINNED_NATIVE_SOURCE_STAGING_OR_TRUE_TYPE_A_FONT_MISSING"
        )
    elif not exists or not font:
        pytest.skip("Owner snapshots exist only in pinned native integration CI")
    return Path(font)


def test_real_complete_23_source_circuit_and_electrik_ic_source():
    loaded = construct_native_paint(_pinned_font())
    (
        circuit, graph, symbols, portrait, old, style, measure,
        policy, pair, owner, catalog,
    ) = loaded
    assert (len(circuit.components), len(circuit.nets)) == (23, 15)
    assert (len(graph.segments), len(graph.junctions)) == (91, 37)
    assert len(catalog) == 13
    assert len(pair.endpoints) == 2
    assert len(portrait.pins) == 16
    assert owner.device.pin_map["3"].electrical_type.value == "input"
    assert owner.device.pin_map["13"].electrical_type.value == "input"
    assert owner.device.package.manufacturer == "Texas Instruments"
    assert portrait.function_rotation == 270
    assert all(len(p.visible_label) <= 6 for p in portrait.pins)
    assert tuple((p.number, p.anchor) for p in portrait.pins) == tuple(
        (p.number, p.anchor) for p in old.pins
    )
    net_copy = tuple(circuit.nets)
    sheet, result = _render_variant(
        circuit, graph, symbols, portrait, style, measure, policy,
        diagnostic=True, reading=IcFunctionReading.BOTTOM_TO_TOP,
    )
    assert circuit.nets == net_copy
    assert len(result.connection_targets) == 16
    assert sheet.svg.count("data-composed-engine") == 1


def test_real_full_native_clean_vs_diagnostic_no_net_or_ref_mutations():
    loaded = construct_native_paint(_pinned_font())
    circuit, graph, symbols, portrait, _, style, measure, policy, *_ = loaded
    visual = []
    for diagnostic in (False, True):
        sheet, rendered = _render_variant(
            circuit, graph, symbols, portrait, style, measure, policy,
            diagnostic=diagnostic,
            reading=IcFunctionReading.BOTTOM_TO_TOP,
        )
        visual.append((sheet, rendered))
    a, b = visual
    assert a[1].pin_anchors == b[1].pin_anchors
    root_a = ET.fromstring(a[0].svg)
    root_b = ET.fromstring(b[0].svg)
    for root in (root_a, root_b):
        assert len(root.findall(f"./{NS}g[@data-layer='symbols']")) == 23
        assert len(root.findall(f".//{NS}line[@data-layer='wires']")) == 91
        assert len(root.findall(
            f".//{NS}circle[@data-kind='authored-junction']"
        )) == 37
    assert "editor-connection-targets" not in a[0].svg
    assert b[0].svg.count("data-pin-ref") == 16
    assert root_b.findall(
        f".//{NS}g[@data-layer='geometry-review']/{NS}circle"
    ) == []  # Generic green dots cannot impersonate verified green squares.
    native = root_b.find(
        f"./{NS}g[@data-composed-engine='physical-ic-renderer']"
    )
    assert native is not None
    leads = native.findall(
        f".//{NS}g[@data-layer='ic-physical-pin-leads']/{NS}line"
    )
    assert len(leads) == 16
    physical = {
        line.get("data-pin-number"): line.get(
            "data-manufacturer-electrical-type"
        ) for line in leads
    }
    assert physical["3"] == "input"
    assert physical["13"] == "input"
    assert physical["12"] == "power_input"
    markers = native.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect"
    )
    assert len(markers) == 16
    assert all(m.get("fill") == "#148645" for m in markers)
    assert all(m.get("data-net-id") for m in markers
               if m.get("data-pin-number") != "15")
