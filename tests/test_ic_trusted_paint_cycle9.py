"""MAIN3 next sprint: true #93 at 161c31bd and verified 23/15/62 overlays.

The lower-level PAINT hotspot API is a drawable, unauthenticated selection.
Only IcCircuitBinding.seal_paint_overlay -> verify_against -> render can
authorize a full physical contact/Net sheet. No mock PAINT or fake netlist.
"""
import hashlib
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.tl494_cycle9_circuit_integration import (
    assert_frozen_photo_topology,
    build_frozen_photo_23,
)
from gost_schematic.core.geometry import Point
from gost_schematic.electrical.ic import (
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_circuit_adapter import (
    IcVerifiedPaintSnapshot,
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
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

pytest.importorskip("gost_schematic.rendering.ic_sheet_composition")
from gost_schematic.rendering.ic_sheet_composition import (
    compose_authoritative_ic_layers,
)

_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def typographic_source():
    path = os.environ.get("IC_TYPE_A_FONT_PATH")
    if not path:
        pytest.skip("Real exact Type A font is injected by current pinned #93 CI")
    font = Path(path)
    assert font.is_file()
    checked = inspect_type_a_font(font, h_um=3500)
    assert checked.measured_cap_height_um == 3500
    assert checked.style.font_sha256 == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    )
    return checked.style, PillowTextMeasurer()


def _actual_authoritative_binding(style, measurer):
    physical, frozen = build_frozen_photo_23()
    old = resolve_ic_pin_positions(
        physical.record.device, physical.record.specs, physical.record.placements,
    )
    proposal = propose_ic_paint_binding(physical.record, style, measurer)
    new = resolve_ic_pin_positions(
        proposal.record.device, proposal.record.specs, proposal.record.placements,
    )
    moved = tuple(ref for ref in old if old[ref] != new[ref])
    active = {
        ref for net in physical.circuit.nets for ref in net.members if ref in old
    }
    consent = IcGeometryConsent(
        ic_record_fingerprint(physical.record), moved,
        tuple(ref for ref in moved if ref in active),
    )
    updated, delta = physical.revise(proposal.record, consent=consent)
    assert set(delta.moved) == set(moved)
    assert set(delta.connected_moved) == {ref for ref in moved if ref in active}
    assert updated.circuit is physical.circuit
    assert_frozen_photo_topology(updated, frozen)
    sealed = updated.seal_paint_overlay(proposal)
    assert isinstance(sealed, IcVerifiedPaintSnapshot)
    sealed.verify_against(updated, proposal)
    return updated, proposal, sealed


def _sheet_root():
    root = ET.Element(_NS + "svg")
    ET.SubElement(root, _NS + "g", {
        "data-reference": "DA1", "data-layer": "symbols",
        "data-test-placeholder": "native-symbol-surrogate-to-be-replaced",
    })
    return root


def _compose(physical, drawing, *, diagnostic):
    assert physical.symbol_surrogate is not None
    root = _sheet_root()
    compose_authoritative_ic_layers(
        root, physical.circuit,
        {physical.part.identifier: physical.symbol_surrogate},
        {"DA1": drawing}, diagnostic=diagnostic,
    )
    return root


@pytest.mark.parametrize("debug", (False, True))
def test_new_real_paint_full_16_tip_snapshot_composes_into_23_part_circuit(
    typographic_source, debug,
):
    style, measure = typographic_source
    physical, proposal, snap = _actual_authoritative_binding(style, measure)
    assert snap.component_ref == "DA1"
    assert snap.circuit_sha256 == hashlib.sha256(
        physical.to_json().encode("utf-8")
    ).hexdigest()
    assert len(snap.manifest.contacts) == len(snap.per_unit_targets[0]) == 16
    assert len(physical.circuit.components) == 23
    assert len(physical.circuit.nets) == 15
    assert sum(len(n.members) for n in physical.circuit.nets) == 62
    assert {c.pin_ref for c in snap.manifest.contacts} == {
        PinRef("DA1", str(n)) for n in range(1, 17)
    }
    assert all(c.net_id for c in snap.manifest.contacts)
    rendered = snap.render(
        physical, proposal, style, measure, diagnostics=debug,
    )
    assert len(rendered) == 1
    assert len(rendered[0].pin_anchors) == 16
    assert len(rendered[0].connection_targets) == 16
    assert all(
        p.anchor == physical.contact(p.pin_ref).world_anchor
        for p in snap.manifest.contacts
    )
    assert physical.contact(PinRef("DA1", "3")).net_id == "FEEDBACK"
    assert physical.contact(PinRef("DA1", "3")).electrical_type.value == "input"
    assert physical.contact(PinRef("DA1", "13")).electrical_type.value == "input"
    sheet = _compose(physical, rendered[0], diagnostic=debug)
    assert sheet.get("data-native-ic-composition") == "exact-circuit-pinrefs"
    groups = [
        node for node in sheet
        if node.get("data-composed-engine") == "physical-ic-renderer"
    ]
    assert len(groups) == 1
    marks = [
        node for node in sheet.iter()
        if node.tag == _NS + "rect" and node.get("data-pin-ref")
    ]
    assert len(marks) == (16 if debug else 0)
    if debug:
        assert all(
            p.get("data-circuit-provenance")
            == "verified-pinrefs-and-nets"
            for p in sheet
            if p.get("data-layer") == "editor-connection-targets"
        )
    assert physical.circuit.nets == build_frozen_photo_23()[0].circuit.nets


@pytest.mark.parametrize("kind", (
    "foreign_ref", "wrong_net", "disabled_input", "wrong_um",
    "missing_contact", "duplicate_contact", "wrong_pin_number",
))
def test_sealed_23_part_hotspot_forgery_fails_before_export(
    typographic_source, kind,
):
    physical, paint, sealed = _actual_authoritative_binding(
        *typographic_source,
    )
    targets = list(sealed.per_unit_targets[0])
    original = targets[2]  # DA1.3 = INPUT FEEDBACK, electrically occupied
    if kind == "foreign_ref":
        targets[2] = replace(original, pin_ref=PinRef("BAD1", "3"))
    elif kind == "wrong_net":
        targets[2] = replace(original, net_id="COMMON")
    elif kind == "disabled_input":
        targets[2] = replace(original, connectable=False, reason="NC")
    elif kind == "wrong_um":
        targets[2] = replace(
            original, anchor=Point(original.anchor.x + 1, original.anchor.y),
        )
    elif kind == "missing_contact":
        targets.pop(2)
    elif kind == "duplicate_contact":
        targets[2] = targets[1]
    else:
        targets[2] = replace(original, pin_ref=PinRef("DA1", "99"))
    forged = replace(sealed, per_unit_targets=(tuple(targets),))
    with pytest.raises(ValueError, match="IC_TRUSTED_OVERLAY"):
        forged.verify_against(physical, paint)
    with pytest.raises(ValueError, match="IC_TRUSTED_OVERLAY"):
        forged.render(physical, paint, *typographic_source, diagnostics=True)


@pytest.mark.parametrize("kind", (
    "missing16", "wrong_active_net", "false_nc_input", "foreign_component",
    "forged_world_um", "altered_source", "wrong_unit",
))
def test_sealed_complete_editor_manifest_refuses_semantic_forgery(
    typographic_source, kind,
):
    physical, paint, snapshot = _actual_authoritative_binding(
        *typographic_source,
    )
    full = list(snapshot.manifest.contacts)
    original = full[2]
    if kind == "missing16":
        full.pop(2)
    elif kind == "wrong_active_net":
        full[2] = replace(original, net_id="WRONG_NET")
    elif kind == "false_nc_input":
        # Consistent internal fake disabled metadata must still fail at origin.
        full[2] = replace(
            original, electrical_type=original.electrical_type,
            connectable=False, reason="LOCKED",
        )
    elif kind == "foreign_component":
        full[2] = replace(
            original, component_ref="BAD1", pin_ref=PinRef("BAD1", "3"),
        )
    elif kind == "forged_world_um":
        full[2] = replace(
            original, anchor=Point(original.anchor.x + 1, original.anchor.y),
        )
    elif kind == "altered_source":
        snapshot = replace(snapshot, circuit_sha256="0" * 64)
    else:
        full[2] = replace(original, unit_id="not-control")
    if kind != "altered_source":
        snapshot = replace(
            snapshot, manifest=replace(
                snapshot.manifest, contacts=tuple(full),
            ),
        )
    with pytest.raises(ValueError, match="IC_TRUSTED_OVERLAY"):
        snapshot.verify_against(physical, paint)


@pytest.mark.parametrize("kind", (
    "missing_ink_lead", "wrong_circuit_net", "extra_physical_contact",
    "missing_physical_contact", "missing_svg_editor_mark", "disabled_input",
    "bad_owner",
))
def test_current_paint_composition_refuses_counterfeit_pin_or_net(
    typographic_source, kind,
):
    physical, paint, snapshot = _actual_authoritative_binding(
        *typographic_source,
    )
    actual = snapshot.render(
        physical, paint, *typographic_source, diagnostics=True,
    )[0]
    corrupt = actual
    if kind == "missing_ink_lead":
        root = ET.fromstring(actual.svg)
        layer = next(
            node for node in root.iter()
            if node.get("data-layer") == "ic-physical-pin-leads"
        )
        layer.remove(next(iter(layer)))
        corrupt = replace(actual, svg=ET.tostring(root, encoding="unicode"))
    elif kind == "wrong_circuit_net":
        targets = list(actual.connection_targets)
        targets[2] = replace(targets[2], net_id="NO_SUCH_NET")
        corrupt = replace(actual, connection_targets=tuple(targets))
    elif kind == "extra_physical_contact":
        corrupt = replace(
            actual, connection_targets=(
                *actual.connection_targets, actual.connection_targets[0],
            ),
        )
    elif kind == "missing_physical_contact":
        corrupt = replace(
            actual, connection_targets=actual.connection_targets[:-1],
        )
    elif kind == "missing_svg_editor_mark":
        root = ET.fromstring(actual.svg)
        group = next(
            node for node in root.iter()
            if node.get("data-layer") == "editor-connection-targets"
        )
        group.remove(next(iter(group)))
        corrupt = replace(actual, svg=ET.tostring(root, encoding="unicode"))
    elif kind == "disabled_input":
        targets = list(actual.connection_targets)
        targets[2] = replace(
            targets[2], connectable=False, reason="LOCKED",
        )
        corrupt = replace(actual, connection_targets=tuple(targets))
    else:
        targets = list(actual.connection_targets)
        targets[2] = replace(targets[2], pin_ref=PinRef("WRONG", "3"))
        corrupt = replace(actual, connection_targets=tuple(targets))
    with pytest.raises(ValueError, match="SHEET_IC_"):
        _compose(physical, corrupt, diagnostic=True)


@pytest.mark.parametrize("angle", (
    IcTextAngle.HORIZONTAL, IcTextAngle.VERTICAL, IcTextAngle.BOTTOM_TO_TOP,
))
def test_trusted_source_paint_word_rotation_preserves_all_nets_and_endpoints(
    typographic_source, angle,
):
    style, measure = typographic_source
    physical, proposal, snapshot = _actual_authoritative_binding(style, measure)
    baseline = {p.pin_ref: p.world_anchor for p in physical.contacts}
    original_nets = physical.circuit.nets
    revised = revise_ic_text_orientation(physical.record, angle)
    updated, delta = physical.revise(revised)
    assert delta.moved == ()
    assert delta.connected_moved == ()
    paint = bind_ic_paint_text_only(proposal, revised)
    rebased = updated.seal_paint_overlay(paint)
    assert rebased.circuit_sha256 != "" and len(rebased.manifest.contacts) == 16
    assert {p.pin_ref: p.world_anchor for p in updated.contacts} == baseline
    assert updated.circuit.nets == original_nets
    with pytest.raises(ValueError, match="IC_TRUSTED_OVERLAY"):
        snapshot.verify_against(updated, paint)
    assert rebased.render(updated, paint, style, measure, diagnostics=True)


def test_no_implicit_authority_when_circuit_or_paint_snapshot_is_modified(
    typographic_source,
):
    physical, paint, snapshot = _actual_authoritative_binding(
        *typographic_source,
    )
    original = physical.circuit.nets[0]
    corrupt = replace(
        physical.circuit, nets=(
            replace(original, name="UNTRUSTED_NEW_NET"),
            *physical.circuit.nets[1:],
        ),
    )
    forged_physical = replace(physical, circuit=corrupt)
    with pytest.raises(ValueError, match="IC_ADAPTER_INTEGRITY_MISMATCH"):
        snapshot.verify_against(forged_physical, paint)
    with pytest.raises(ValueError, match="IC_ADAPTER_INTEGRITY_MISMATCH"):
        snapshot.verify_against(
            replace(physical, record=replace(
                physical.record, specs=tuple(
                    replace(p, revision=p.revision + 1)
                    for p in physical.record.specs
                ),
            )),
            paint,
        )
