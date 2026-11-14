"""Actual pinned PAINT #93 + true 23-part Circuit integration; no mock glyphs.

In isolated PR #97 this is skipped because PAINT is a different unmerged
owner. Cross-PR workflow pins the source and executes tests with real Type A.
"""
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from examples.tl494_cycle9_circuit_integration import (
    assert_frozen_photo_topology,
    build_frozen_photo_23,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcKind,
    IcPinType,
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_circuit_adapter import (
    IcCircuitBinding,
    bind_ic_circuit,
)
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
    revise_ic_text_orientation,
)
from gost_schematic.electrical.ic_paint_bridge import (
    bind_ic_paint_text_only,
    propose_ic_paint_binding,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
render_resolved_ic = paint.render_resolved_ic


@pytest.fixture(scope="module")
def typography():
    raw = os.environ.get("IC_TYPE_A_FONT_PATH")
    if not raw:
        pytest.skip("Real OpenGOST Type A font provided in pinned joint CI")
    font = Path(raw)
    assert font.is_file()
    inspection = inspect_type_a_font(font, h_um=3500)
    assert inspection.measured_cap_height_um == 3500
    return inspection.style, PillowTextMeasurer()


def _real_paint_source(style, measure, *, pose=None):
    binding, source = build_frozen_photo_23()
    if pose is not None and pose != Transform():
        record = IcLibraryRecord(
            binding.record.device, binding.record.specs,
            tuple(replace(p, transform=pose) for p in binding.record.placements),
        )
        circ = replace(binding.circuit, components=tuple(
            replace(c, transform=pose)
            if c.reference == "DA1" else c
            for c in binding.circuit.components
        ))
        binding = bind_ic_circuit(
            record, circ, aliases=binding.aliases,
            external_pin_numbers=dict(binding.external_pin_numbers),
        )
    before_nets = binding.circuit.nets
    first_pts = resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    proposal = propose_ic_paint_binding(binding.record, style, measure)
    after_pts = resolve_ic_pin_positions(
        proposal.record.device, proposal.record.specs, proposal.record.placements,
    )
    moved = tuple(p for p in first_pts if first_pts[p] != after_pts[p])
    connected = {
        p for n in before_nets for p in n.members if p in first_pts
    }
    consent = IcGeometryConsent(
        ic_record_fingerprint(binding.record), moved,
        tuple(p for p in moved if p in connected),
    )
    updated, delta = binding.revise(proposal.record, consent=consent)
    assert delta.moved == moved
    assert delta.connected_moved == tuple(p for p in moved if p in connected)
    assert updated.circuit is binding.circuit
    assert updated.circuit.nets is before_nets
    assert_frozen_photo_topology(updated, source)
    manifest = updated.bind_paint(proposal)
    assert len(manifest.contacts) == 16
    assert {p.net_id for p in manifest.contacts} <= {
        net.name for net in before_nets
    }
    assert {p.pin_ref for p in manifest.contacts} == {
        PinRef("DA1", str(i)) for i in range(1, 17)
    }
    for p in manifest.contacts:
        original = updated.contact(p.pin_ref)
        assert p.anchor == original.world_anchor
        assert p.electrical_type is original.electrical_type
        assert p.net_id == original.net_id
        assert p.pin_name == original.manufacturer_pin_name
    assert IcCircuitBinding.from_json(updated.to_json()) == updated
    return updated, proposal


@pytest.mark.parametrize("angle", (
    IcTextAngle.HORIZONTAL,
    IcTextAngle.VERTICAL,
    IcTextAngle.BOTTOM_TO_TOP,
))
def test_real_photo_circuit_paint_0_90_270_words_do_not_move_any_contacts(
    typography, angle,
):
    style, measure = typography
    binding, candidate = _real_paint_source(style, measure)
    if angle is not candidate.record.specs[0].profile.function_angle:
        revised = revise_ic_text_orientation(candidate.record, angle)
        updated, delta = binding.revise(revised)
        assert not delta.moved
        candidate = bind_ic_paint_text_only(candidate, revised)
        binding = updated
    contacts = binding.bind_paint(candidate)
    assert len(contacts.contacts) == 16
    actual = render_resolved_ic(candidate.views[0], style, measure)
    assert len(actual.pin_anchors) == 16
    from gost_schematic.core.units import format_mm

    root = ET.fromstring(actual.svg)
    lead_lines = [
        node for g in root.iter()
        if g.get("data-layer") == "ic-physical-pin-leads"
        for node in g if node.tag.endswith("line")
    ]
    assert len(lead_lines) == 16
    by_num = {p.physical_number: p for p in contacts.contacts}
    for line in lead_lines:
        source = by_num[line.get("data-pin-number")]
        assert line.get("x2") == format_mm(source.anchor.x)
        assert line.get("y2") == format_mm(source.anchor.y)
    function = [
        t for t in root.iter()
        if t.tag.endswith("text") and t.get("data-kind") == "function"
    ]
    assert len(function) == 1
    assert function[0].text == "PWM"
    matrix = function[0].get("transform", "")
    if angle is IcTextAngle.BOTTOM_TO_TOP:
        assert matrix.startswith("matrix(0 -1 1 0 ")
    elif angle is IcTextAngle.VERTICAL:
        assert matrix.startswith("matrix(0 1 -1 0 ")
    else:
        assert not matrix
    assert binding.circuit.nets == build_frozen_photo_23()[0].circuit.nets


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_eight_d4_poses_really_bind_paint_on_photo_23_nets(
    typography, rotation, mirror,
):
    style, measure = typography
    pose = Transform(rotation, mirror)
    binding, proposal = _real_paint_source(style, measure, pose=pose)
    assert binding.symbol_surrogate is not None
    instance = next(
        c for c in binding.circuit.components if c.reference == "DA1"
    )
    assert instance.pin_positions(binding.symbol_surrogate) == {
        pin.pin_ref.number: pin.world_anchor for pin in binding.contacts
    }
    for view in proposal.views:
        assert view.transform == pose
        assert {
            p.number: p.anchor for p in view.pins
        } == {
            c.pin_ref.number: c.world_anchor for c in binding.contacts
        }
    # PAINT may reject an entire D4 pose on refdes/ink collision;
    # that must fail CLOSED with a named condition, never move PinRef.
    try:
        drawn = render_resolved_ic(proposal.views[0], style, measure)
    except ValueError as exc:
        assert str(exc).startswith((
            "IC_TEXT_OVERFLOW", "IC_INK_", "IC_TEXT_COLLISION",
            "IC_REF", "IC_COLLISION",
        )), str(exc)
    else:
        assert len(drawn.pin_anchors) == 16
        assert drawn.pin_anchors == tuple(
            (p.pin_id, p.anchor) for p in proposal.views[0].pins
        )


def test_multi_unit_real_paint_binding_preserves_single_physical_component(
    typography,
):
    style, measure = typography
    source = synthetic_ic(14, IcKind.DIGITAL)
    device = replace(source.device, pins=tuple(
        replace(p, electrical_type=IcPinType.PASSIVE)
        if p.electrical_type is IcPinType.NC else p
        for p in source.device.pins
    ))
    record = IcLibraryRecord(device, source.specs, source.placements)
    circuit = Circuit((ComponentInstance("DD1", device.identifier),), (
        Net("CTRL", (PinRef("DD1", "1"), PinRef("DD1", "8"))),
    ))
    initial = bind_ic_circuit(record, circuit)
    propose = propose_ic_paint_binding(record, style, measure)
    positions_a = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    positions_b = resolve_ic_pin_positions(
        propose.record.device, propose.record.specs, propose.record.placements,
    )
    movable = tuple(pin for pin in positions_a if positions_a[pin] != positions_b[pin])
    consent = IcGeometryConsent(
        ic_record_fingerprint(record), movable,
        tuple(pin for pin in movable if pin in circuit.nets[0].members),
    )
    latest, delta = initial.revise(propose.record, consent=consent)
    assert len(delta.moved) >= 1
    assert latest.symbol_surrogate is None
    assert latest.circuit.nets == initial.circuit.nets
    assert len(latest.contacts) == 14
    overlay = latest.bind_paint(propose)
    assert len(overlay.contacts) == 14
    assert {c.unit_id for c in overlay.contacts} == {"U1", "U2"}
    assert IcCircuitBinding.from_json(latest.to_json()) == latest
