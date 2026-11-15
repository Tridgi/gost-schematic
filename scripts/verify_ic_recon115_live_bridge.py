"""Live #115 compact A3 -> #97 TI physical -> #93 PAINT trust gate.

ONLY invoked in an isolated CI checkout containing genuine pinned PR #115,
#113 catalog and #93 renderer sources. NOT a synthetic stand-in or printable
15-Net sheet. Never rewrites the frozen source, and never merges PRs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.tl494_cycle9_circuit_integration import (
    FROZEN_SOURCE_COMMIT,
    assert_frozen_photo_topology,
    bind_positioned_photo_circuit_from_catalog,
    load_frozen_source,
)
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.ic import (
    IcPinType,
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_circuit_adapter import (
    IcCircuitBinding,
    bind_ic_circuit_from_catalog,
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
from gost_schematic.electrical.tl494cn import (
    TI_DEVICE_ID,
    tl494cn_device,
    verify_tl494cn_ti_pinout,
)
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

_NS = "{http://www.w3.org/2000/svg}"
_FONT_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def compact_source_assembly():
    """Load actual pinned #115 only at live integration runtime."""
    return import_module("examples.tl494_v5.compact_layout").compact_source_assembly()


def live_reconstruction():
    """Use actual owner catalog and A3 placements, not a forged part fixture."""
    native = compact_source_assembly()
    native.verify()
    original = native.circuit
    original_nets = original.nets
    signed = bind_positioned_photo_circuit_from_catalog(
        original, native.owner_ic_record, native.parts,
        aliases=native.owner_aliases,
    )
    source = load_frozen_source()
    assert_frozen_photo_topology(signed, source)
    assert original.nets is original_nets
    assert signed.circuit.nets is original_nets
    assert signed.circuit.components is not original.components
    assert next(c for c in original.components if c.reference == "DA1").part_id == (
        "reference.tl494cn"
    )
    assert next(c for c in signed.circuit.components if c.reference == "DA1").part_id == (
        TI_DEVICE_ID
    )
    restored = replace(signed.circuit, components=tuple(
        replace(c, part_id="reference.tl494cn")
        if c.reference == "DA1" else c for c in signed.circuit.components
    ))
    assert restored == original
    assert restored.nets is original.nets
    return native, signed


def live_paint(font_file: Path):
    """Real Type A measured overlay, explicit geometry consent, no reroute."""
    native, signed = live_reconstruction()
    checked = inspect_type_a_font(font_file, h_um=3500)
    assert checked.measured_cap_height_um == 3500
    assert checked.style.font_sha256 == _FONT_SHA256
    measurer = PillowTextMeasurer()
    proposal = propose_ic_paint_binding(signed.record, checked.style, measurer)
    before = resolve_ic_pin_positions(
        signed.record.device, signed.record.specs, signed.record.placements,
    )
    after = resolve_ic_pin_positions(
        proposal.record.device, proposal.record.specs, proposal.record.placements,
    )
    moved = tuple(ref for ref in before if before[ref] != after[ref])
    active = {
        p for net in signed.circuit.nets for p in net.members if p in before
    }
    consent = IcGeometryConsent(
        ic_record_fingerprint(signed.record), moved,
        tuple(ref for ref in moved if ref in active),
    )
    revised, delta = signed.revise(proposal.record, consent=consent)
    assert set(delta.moved) == set(moved)
    assert revised.circuit is signed.circuit
    assert revised.circuit.nets is native.circuit.nets
    verified = revised.seal_paint_overlay(proposal)
    verified.verify_against(revised, proposal)
    return native, revised, proposal, verified, checked.style, measurer


def _checks(binding):
    assert len(binding.circuit.components) == 23
    assert len(binding.circuit.nets) == 15
    assert sum(len(n.members) for n in binding.circuit.nets) == 62
    assert len(binding.contacts) == 16
    assert {p.pin_ref for p in binding.contacts} == {
        PinRef("DA1", str(i)) for i in range(1, 17)
    }
    assert binding.contact(PinRef("DA1", "3")).manufacturer_pin_name == "FEEDBACK"
    assert binding.contact(PinRef("DA1", "3")).schematic_short_label == "FB"
    assert binding.contact(PinRef("DA1", "3")).electrical_type.value == "input"
    assert binding.contact(PinRef("DA1", "13")).manufacturer_pin_name == "OUTPUT CTRL"
    assert binding.contact(PinRef("DA1", "13")).schematic_short_label == "OC"
    assert binding.contact(PinRef("DA1", "13")).electrical_type.value == "input"


def test_real_115_compact_trusted_identifier_mapping_is_exact_and_reversible():
    native, signed = live_reconstruction()
    _checks(signed)
    assert IcCircuitBinding.from_json(signed.to_json()) == signed
    assert native.circuit.nets is signed.circuit.nets
    assert_frozen_photo_topology(signed, load_frozen_source())



def test_real_115_owner_verified_compact_ti_consumes_exact_source_tuple():
    """Exercise RECON's actual owner consumer, not only IC's direct adapter."""
    owner = import_module("examples.tl494_v5.cycle11_ti_bridge")
    native = compact_source_assembly()
    actual = owner.bind_verified_compact_ti(native, native.circuit)
    actual.verify()
    assert actual.reverse_source() is native.circuit
    assert actual.signed.circuit.nets is native.circuit.nets
    assert actual.signed.circuit is not native.circuit
    assert actual.signed.part.identifier == TI_DEVICE_ID
    assert actual.part == actual.signed.part
    _checks(actual.signed)

    # A numerically equal clone is NOT the owner's exact same source tuple.
    new_tuple = (*native.circuit.components,)
    assert new_tuple == native.circuit.components
    assert new_tuple is not native.circuit.components
    unauthorized = replace(native.circuit, components=new_tuple)
    with pytest.raises(
        ValueError, match="TL494_C11_SOURCE_COMPONENT_INVENTORY_NOT_IDENTICAL"
    ):
        owner.bind_verified_compact_ti(native, unauthorized)


def test_real_115_source_b_electrical_net_is_not_continuation_ink():
    """Two b glyphs must never become an extra PinRef or electrical Net."""
    native, signed = live_reconstruction()
    expected = frozenset({
        PinRef("FU1", "2"), PinRef("X2", "1"), PinRef("R5", "2"),
    })
    source_b = next(net for net in native.circuit.nets if net.name == "OUTPUT_NEG")
    signed_b = next(net for net in signed.circuit.nets if net.name == "OUTPUT_NEG")
    assert signed_b is source_b
    assert len(source_b.members) == 3
    assert frozenset(source_b.members) == expected
    assert len(native.circuit.nets) == 15
    assert sum(len(net.members) for net in native.circuit.nets) == 62

    # An invented electrical leg for historic non-electrical b continuation
    # must be rejected even when the visible glyph could still look correct.
    counterfeit_b = replace(
        source_b, members=(*source_b.members, PinRef("X2", "2")),
    )
    forged = replace(native.circuit, nets=tuple(
        counterfeit_b if net is source_b else net
        for net in native.circuit.nets
    ))
    with pytest.raises((ValueError, TypeError), match=(
        "TL494_PHOTO_REBIND_|IC_ADAPTER_|TL494_|IC_"
    )):
        bind_positioned_photo_circuit_from_catalog(
            forged, native.owner_ic_record, native.parts,
            aliases=native.owner_aliases,
        )
    assert signed.circuit.nets is native.circuit.nets


@pytest.mark.parametrize("pin_number", ("3", "13", "14"))
def test_real_115_ti_factory_nc_counterfeit_rejected(pin_number):
    """TI TL494 has no NC contact: neither FB, OC nor REF can become NC."""
    authentic = tl494cn_device()
    assert len(authentic.pins) == 16
    assert not any(pin.electrical_type is IcPinType.NC for pin in authentic.pins)
    verify_tl494cn_ti_pinout(authentic)
    counterfeit = replace(authentic, pins=tuple(
        replace(pin, electrical_type=IcPinType.NC)
        if pin.number == pin_number else pin
        for pin in authentic.pins
    ))
    with pytest.raises(
        ValueError, match="TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE_MISMATCH"
    ):
        verify_tl494cn_ti_pinout(counterfeit)


@pytest.mark.parametrize(
    ("attack", "expected"),
    (
        ("no_consent", "IC_GEOMETRY_REAUTHORIZATION_REQUIRED"),
        ("stale_consent", "IC_GEOMETRY_CONSENT_SOURCE_STALE"),
        ("not_connected_consent", "IC_CONNECTED_REROUTE_CONSENT_MISMATCH"),
        ("foreign_pinref_consent", "IC_GEOMETRY_CONSENT_PINREF_MISMATCH"),
    ),
)
def test_real_115_one_um_connected_pin_requires_exact_reroute_consent(
    attack, expected,
):
    """A 1um physical pin movement needs source-bound exact consent."""
    native, source = live_reconstruction()
    record = source.record
    spec = record.specs[0]
    row = spec.rows[0]
    physical = PinRef("DA1", row.number)
    assert any(physical in net.members for net in source.circuit.nets)
    moved_row = replace(
        row, anchor=Point(row.anchor.x + 1, row.anchor.y),
    )
    moved_spec = replace(
        spec, revision=spec.revision + 1,
        rows=(moved_row, *spec.rows[1:]),
    )
    candidate = replace(record, specs=(moved_spec,))
    before = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    after = resolve_ic_pin_positions(
        candidate.device, candidate.specs, candidate.placements,
    )
    assert after[physical] != before[physical]
    assert len(before) == len(after) == 16
    assert {p for p in before if before[p] != after[p]} == {physical}
    consent = None
    if attack == "stale_consent":
        consent = IcGeometryConsent("0" * 64, (physical,), (physical,))
    elif attack == "not_connected_consent":
        consent = IcGeometryConsent(
            ic_record_fingerprint(record), (physical,), (),
        )
    elif attack == "foreign_pinref_consent":
        consent = IcGeometryConsent(
            ic_record_fingerprint(record), (PinRef("DA1", "99"),), (),
        )
    with pytest.raises(ValueError, match=expected):
        source.revise(candidate, consent=consent)
    permitted = IcGeometryConsent(
        ic_record_fingerprint(record), (physical,), (physical,),
    )
    updated, delta = source.revise(candidate, consent=permitted)
    assert delta.moved == delta.connected_moved == (physical,)
    assert updated.circuit is source.circuit
    assert updated.circuit.nets is native.circuit.nets
    assert len(updated.contacts) == 16
    assert updated.contact(physical).world_anchor == after[physical]


def _true_source_b_rendering(font: Path):
    """Resolve two typed original-name b stubs using live owner sources."""
    native = compact_source_assembly()
    driver = import_module("examples.tl494_v5.route_candidate_driver")
    fixture, _ = driver.load_original_owner_fixture()
    original_named = driver.restore_original_named_nets(native, fixture)
    assert {net.name for net in original_named.nets} == set(
        load_frozen_source()["nets"]
    )
    physical = bind_positioned_photo_circuit_from_catalog(
        original_named, native.owner_ic_record, native.parts,
        aliases=native.owner_aliases,
    )
    assert physical.circuit.nets is original_named.nets
    style = inspect_type_a_font(
        font, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    ).style
    assert style.font_sha256 == _FONT_SHA256
    symbols = {
        part_id: native.symbols[part.symbol_id]
        for part_id, part in native.parts.items()
        if part.symbol_id in native.symbols
    }
    project = import_module(
        "examples.render_tl494_compact_new_router_cycle10"
    )._bind_verified_source_b(font, physical.circuit, symbols)
    assert project.circuit.nets is original_named.nets
    assert len(project.endpoints) == len(project.stubs) == 2
    assert {s.pin for s in project.stubs} == {
        PinRef("X2", "1"), PinRef("R5", "2"),
    }
    return physical, style, project, symbols


def test_real_current_paint_renders_b_source_stubs_not_electrical_junctions():
    """Real SOURCE verified X2.1/R5.2 -> 2 b labels: 2 exact SVG lines."""
    physical, style, project, symbols = _true_source_b_rendering(
        Path(os.environ["IC_TYPE_A_FONT_PATH"])
    )
    owner = import_module("gost_schematic.rendering.ic_sheet_composition")
    for diagnostic in (False, True):
        root = ET.Element(_NS + "svg")
        owner.append_verified_sheet_continuations(
            root, physical.circuit, project, style,
            diagnostic=diagnostic, symbols_by_part=symbols,
        )
        group = next(n for n in root if n.get("data-layer") == (
            "typed-nonphysical-continuations"
        ))
        by_id = {
            node.get("data-source-stub-id"): node
            for node in group if node.get("data-layer") == (
                "nonphysical-continuation-stub"
            )
        }
        assert len(by_id) == 2
        for stub in project.stubs:
            line = by_id[stub.id]
            assert line.tag == _NS + "line"
            assert line.get("data-nonphysical-net-continuation") == (
                stub.endpoint_id
            )
            assert line.get("data-source-pin-ref") == (
                f"{stub.pin.reference}.{stub.pin.number}"
            )
            assert tuple(line.get(name) for name in ("x1", "y1", "x2", "y2")) == (
                format_mm(stub.start.x), format_mm(stub.start.y),
                format_mm(stub.end.x), format_mm(stub.end.y),
            )
            assert line.get("data-nonphysical") == "true"
            assert line.get("data-electrical-junction") == "false"
            assert line.get("data-connectable") == "false"
        assert {
            n.get("data-nonphysical-net-continuation")
            for n in group if n.tag == _NS + "circle"
        } == {"b-X2", "b-R5"}
        assert {
            n.text for n in group if n.tag == _NS + "text"
        } == {"b"}
        assert not any(n.get("data-pin-ref") for n in group.iter())
    assert len(physical.circuit.components) == 23
    assert len(physical.circuit.nets) == 15
    assert sum(len(n.members) for n in physical.circuit.nets) == 62


@pytest.mark.parametrize(
    "attack", ("missing_stub", "wrong_physical_pin", "one_um_marker_drift"),
)
def test_real_current_paint_rejects_forged_b_local_stubs(attack):
    """The two b markers are not free-form decorative wires or fake pins."""
    physical, style, project, symbols = _true_source_b_rendering(
        Path(os.environ["IC_TYPE_A_FONT_PATH"])
    )
    expected = "SHEET_CONTINUATION_SOURCE_B_STUB_INVENTORY_DRIFT"
    if attack == "missing_stub":
        forged = replace(project, stubs=project.stubs[:1])
    elif attack == "wrong_physical_pin":
        forged = replace(project, stubs=(
            replace(project.stubs[0], pin=PinRef("X2", "2")),
            project.stubs[1],
        ))
    else:
        stub = project.stubs[0]
        moved_end = Point(
            stub.end.x + int(stub.start.y == stub.end.y),
            stub.end.y + int(stub.start.x == stub.end.x),
        )
        forged = replace(project, stubs=(
            replace(stub, end=moved_end), project.stubs[1],
        ))
        expected = "SHEET_CONTINUATION_SOURCE_B_STUB_GEOMETRY_DRIFT"
    root = ET.Element(_NS + "svg")
    with pytest.raises(ValueError, match=expected):
        import_module(
            "gost_schematic.rendering.ic_sheet_composition"
        ).append_verified_sheet_continuations(
            root, physical.circuit, forged, style, diagnostic=False,
            symbols_by_part=symbols,
        )
    assert not list(root)
    assert project.circuit.nets is physical.circuit.nets


def test_real_current_type_a_font_does_not_accept_obsolete_family_silently():
    """Real upstream Type A is SHA checked, not an alias for obsolete TT."""
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    current = inspect_type_a_font(
        font, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    assert current.style.font_sha256 == _FONT_SHA256
    assert current.measured_cap_height_um == 3500
    with pytest.raises(ValueError):
        inspect_type_a_font(
            font, h_um=3500, family="OpenGost Type A TT",
            require_family_match=True,
        )

def test_legacy_id_is_not_implicitly_equivalent_to_ti_manufacturer():
    native = compact_source_assembly()
    with pytest.raises(ValueError, match="IC_ADAPTER_CATALOG_IC_PART_ID_MISMATCH"):
        bind_ic_circuit_from_catalog(
            native.owner_ic_record, native.circuit, native.parts,
            aliases=native.owner_aliases,
        )


@pytest.mark.parametrize("kind", (
    "wrong_da1_id", "foreign_resistor", "moved_da1_one_um",
    "moved_record_one_um", "missing_component", "missing_pinref",
    "foreign_pinref", "duplicate_pinref", "renamed_net",
    "changed_nominal", "missing_catalog", "spoofed_catalog",
    "mixed_label_namespace", "swapped_physical_net", "forged_vendor",
))
def test_real_115_source_changes_fail_closed(kind):
    native = compact_source_assembly()
    circuit = native.circuit
    record = native.owner_ic_record
    catalog = dict(native.parts)
    if kind in ("wrong_da1_id", "foreign_resistor", "moved_da1_one_um",
                "changed_nominal"):
        ref = "DA1" if kind in ("wrong_da1_id", "moved_da1_one_um") else "R1"
        replacement = {}
        if kind in ("wrong_da1_id", "foreign_resistor"):
            replacement["part_id"] = "untrusted.spoofed"
        elif kind == "moved_da1_one_um":
            old = next(c for c in circuit.components if c.reference == ref)
            replacement["origin"] = Point(old.origin.x + 1, old.origin.y)
        else:
            replacement["nominal"] = None
        circuit = replace(circuit, components=tuple(
            replace(c, **replacement) if c.reference == ref else c
            for c in circuit.components
        ))
    elif kind == "moved_record_one_um":
        record = replace(record, placements=tuple(
            replace(p, origin=Point(p.origin.x + 1, p.origin.y))
            for p in record.placements
        ))
    elif kind == "missing_component":
        circuit = replace(circuit, components=tuple(
            c for c in circuit.components if c.reference != "C1"
        ))
    elif kind in ("missing_pinref", "foreign_pinref", "duplicate_pinref",
                  "renamed_net"):
        target = circuit.nets[0]
        members = target.members
        if kind == "missing_pinref":
            members = members[1:]
        elif kind == "foreign_pinref":
            members = (PinRef("ZZ1", "1"), *members[1:])
        elif kind == "duplicate_pinref":
            members = (members[0], *members)
        new_net = replace(
            target, members=members,
            name="UNTRUSTED_NET" if kind == "renamed_net" else target.name,
        )
        circuit = replace(circuit, nets=(new_net, *circuit.nets[1:]))
    elif kind == "mixed_label_namespace":
        circuit = replace(circuit, nets=tuple(
            replace(n, name="a_INPUT_PLUS") if n.name == "INPUT_POS" else n
            for n in circuit.nets
        ))
    elif kind == "swapped_physical_net":
        target = next(n for n in circuit.nets if n.name == "FEEDBACK")
        circuit = replace(circuit, nets=tuple(
            replace(n, members=tuple(
                PinRef("DA1", "4") if p == PinRef("DA1", "3") else p
                for p in n.members
            )) if n == target else n
            for n in circuit.nets
        ))
    elif kind == "missing_catalog":
        catalog.pop("resistor.fixed")
    elif kind == "spoofed_catalog":
        catalog["resistor.fixed"] = replace(
            catalog["resistor.fixed"], identifier="foreign.resistor",
        )
    else:
        # The record itself rejects this forged device/spec before binding.
        with pytest.raises(ValueError, match="Unknown or invalid IC symbol"):
            replace(
                record,
                device=replace(record.device, identifier="foreign.vendor"),
            )
        return
    with pytest.raises((TypeError, ValueError), match=(
        "TL494_PHOTO_REBIND_|IC_ADAPTER_|TL494_|IC_"
    )):
        bind_positioned_photo_circuit_from_catalog(
            circuit, record, catalog, aliases=native.owner_aliases,
        )


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_115_a3_d4_does_not_rewrite_net_or_invent_pin(rotation, mirror):
    native = compact_source_assembly()
    pose = Transform(rotation, mirror)
    changed = replace(native.circuit, components=tuple(
        replace(c, transform=pose) if c.reference == "DA1" else c
        for c in native.circuit.components
    ))
    record = replace(native.owner_ic_record, placements=tuple(
        replace(p, transform=pose) for p in native.owner_ic_record.placements
    ))
    signed = bind_positioned_photo_circuit_from_catalog(
        changed, record, native.parts, aliases=native.owner_aliases,
    )
    assert signed.circuit.nets is native.circuit.nets
    _checks(signed)
    actual = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    assert {c.pin_ref: c.world_anchor for c in signed.contacts} == actual


@pytest.mark.parametrize("angle", (
    IcTextAngle.HORIZONTAL, IcTextAngle.VERTICAL, IcTextAngle.BOTTOM_TO_TOP,
))
def test_real_115_pwm_text_rotation_keeps_all_16_endpoints(angle):
    _, signed = live_reconstruction()
    source_endpoints = {c.pin_ref: c.world_anchor for c in signed.contacts}
    new_record = revise_ic_text_orientation(signed.record, angle)
    revised, delta = signed.revise(new_record)
    assert not delta.moved and not delta.connected_moved
    assert revised.circuit is signed.circuit
    assert {c.pin_ref: c.world_anchor for c in revised.contacts} == source_endpoints
    _checks(revised)


def _expected_marker_count(svg):
    root = ET.fromstring(svg)
    return len([
        node for node in root.iter()
        if node.tag == _NS + "rect" and node.get("data-pin-ref") is not None
    ])


def test_real_115_paint_seal_clean_vs_diagnostic():
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    native, physical, paint, verified, style, measurer = live_paint(font)
    clean = verified.render(
        physical, paint, style, measurer, diagnostics=False,
    )[0]
    diagnostic = verified.render(
        physical, paint, style, measurer, diagnostics=True,
    )[0]
    assert _expected_marker_count(clean.svg) == 0
    assert _expected_marker_count(diagnostic.svg) == 16
    assert len(verified.manifest.contacts) == 16
    assert all(c.net_id for c in verified.manifest.contacts)
    assert physical.circuit.nets is native.circuit.nets
    _checks(physical)


def test_real_115_paint_text_only_toggle_keeps_trusted_physical_points():
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    native, physical, paint, _, style, measure = live_paint(font)
    original_endpoints = {c.pin_ref: c.world_anchor for c in physical.contacts}
    for angle in (IcTextAngle.HORIZONTAL, IcTextAngle.BOTTOM_TO_TOP):
        rotated_record = revise_ic_text_orientation(physical.record, angle)
        rotated_binding, delta = physical.revise(rotated_record)
        assert delta.moved == ()
        rotated_paint = bind_ic_paint_text_only(paint, rotated_record)
        authorized = rotated_binding.seal_paint_overlay(rotated_paint)
        authorized.verify_against(rotated_binding, rotated_paint)
        assert {c.pin_ref: c.world_anchor for c in rotated_binding.contacts} == (
            original_endpoints
        )
        assert rotated_binding.circuit.nets is native.circuit.nets
        assert authorized.render(
            rotated_binding, rotated_paint, style, measure, diagnostics=True,
        )




def test_real_115_latest_paint_routed_native_requires_genuine_15_net_graph():
    """Exercise PAINT's actual whole-sheet API, safely blocked without NET114."""
    render_routed_native_sheet = import_module(
        "gost_schematic.rendering.routed_native_sheet"
    ).render_routed_native_sheet

    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    native, signed, paint, verified, style, measure = live_paint(font)
    clean = verified.render(
        signed, paint, style, measure, diagnostics=False,
    )[0]
    diagnostic = verified.render(
        signed, paint, style, measure, diagnostics=True,
    )[0]
    # PAINT's whole-sheet renderer does NOT accept legacy Part-ID pretending
    # to be TI; bind a separate source-validated, typed manufacturer catalog.
    parts = {**native.parts, signed.part.identifier: signed.part}
    assert signed.symbol_surrogate is not None
    symbols = {
        part_id: native.symbols[part.symbol_id]
        for part_id, part in native.parts.items()
        if part.symbol_id in native.symbols
    }
    symbols[signed.part.identifier] = signed.symbol_surrogate
    da1 = next(c for c in signed.circuit.components if c.reference == "DA1")
    assert da1.pin_positions(signed.symbol_surrogate) == {
        c.pin_ref.number: c.world_anchor for c in signed.contacts
    }
    result = render_routed_native_sheet(
        signed.circuit, ExternalWireGraph(()), parts, symbols,
        style, measure,
        physical_ic_renderings_clean={"DA1": clean},
        physical_ic_renderings_diagnostic={"DA1": diagnostic},
        verified_ic_source=signed,
        verified_ic_paint_binding=paint,
        verified_ic_snapshot=verified,
        source_continuation_project=None,
        expected_component_count=23,
        expected_net_count=15,
        expected_net_pinrefs=62,
        physical_page_box=Box(0, 0, 420000, 297000),
    )
    assert result.printable_candidate is False
    assert result.manifest["source_components"] == 23
    assert result.manifest["source_nets"] == 15
    assert result.manifest["source_net_pinrefs"] == 62
    assert result.manifest["route_segments"] == 0
    assert result.manifest["blockers"]
    assert result.manifest["gost_approved"] is False
    assert result.manifest["source_graph_mutated"] is False
    assert result.manifest["signed_manufacturer_ic_16_verified"] is True
    assert "ROUTED_SHEET_SIGNED_MANUFACTURER_PHYSICAL_BINDING_MISSING" not in (
        result.manifest["blockers"]
    )
    assert _expected_marker_count(result.clean_svg) == 0
    assert _expected_marker_count(result.diagnostic_svg) == 16
    assert ET.fromstring(result.clean_svg).get("data-release") == (
        "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
    )
    # Two superficially plausible 16-tip IcRendered objects never certify
    # the manufacturer's factory identities without the exact signed triple.
    unsigned = render_routed_native_sheet(
        signed.circuit, ExternalWireGraph(()), parts, symbols,
        style, measure,
        physical_ic_renderings_clean={"DA1": clean},
        physical_ic_renderings_diagnostic={"DA1": diagnostic},
        source_continuation_project=None,
        expected_component_count=23,
        expected_net_count=15,
        expected_net_pinrefs=62,
        physical_page_box=Box(0, 0, 420000, 297000),
    )
    assert unsigned.manifest["signed_manufacturer_ic_16_verified"] is False
    assert "TL494_SIGNED_MANUFACTURER_PHYSICAL_BINDING_MISSING" in (
        unsigned.manifest["blockers"]
    )
    assert unsigned.printable_candidate is False
    assert _expected_marker_count(unsigned.clean_svg) == 0
    assert _expected_marker_count(unsigned.diagnostic_svg) == 16
    # A completed 15-Net global route is NOT invented for this smoke test.
    assert signed.circuit.nets is native.circuit.nets



@pytest.mark.parametrize(
    ("attack", "error_code"),
    (
        ("foreign_net_segment", "ROUTED_SHEET_FORGED_FOREIGN_NET"),
        ("wrong_total_members", "ROUTED_SHEET_SOURCE_NET_PINREFS_DRIFT"),
        ("partial_diagnostic", "ROUTED_SHEET_CLEAN_DEBUG_PINREF_NET_DRIFT"),
        ("one_um_diagnostic_anchor", "ROUTED_SHEET_CLEAN_DEBUG_PINREF_NET_DRIFT"),
    ),
)
def test_real_115_paint_routed_native_adversarial_source_gate(attack, error_code):
    """Cross-owner PAINT rejects forged graph, count and 16-tip UI mutations."""
    renderer = import_module(
        "gost_schematic.rendering.routed_native_sheet"
    ).render_routed_native_sheet
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    native, signed, paint, verified, style, measure = live_paint(font)
    clean = verified.render(
        signed, paint, style, measure, diagnostics=False,
    )[0]
    diagnostic = verified.render(
        signed, paint, style, measure, diagnostics=True,
    )[0]
    parts = {**native.parts, signed.part.identifier: signed.part}
    symbols = {
        part_id: native.symbols[part.symbol_id]
        for part_id, part in native.parts.items()
        if part.symbol_id in native.symbols
    }
    assert signed.symbol_surrogate is not None
    symbols[signed.part.identifier] = signed.symbol_surrogate
    graph = ExternalWireGraph(())
    required_members = 62
    if attack == "foreign_net_segment":
        graph = ExternalWireGraph((
            WireSegment(Point(1000, 1000), Point(2000, 1000), "FORGED_NET"),
        ))
    elif attack == "wrong_total_members":
        required_members = 61
    elif attack == "partial_diagnostic":
        diagnostic = replace(diagnostic, connection_targets=())
    else:
        anchors = list(diagnostic.pin_anchors)
        pin_id, p = anchors[0]
        anchors[0] = (pin_id, Point(p.x + 1, p.y))
        diagnostic = replace(diagnostic, pin_anchors=tuple(anchors))
    with pytest.raises(ValueError, match=error_code):
        renderer(
            signed.circuit, graph, parts, symbols, style, measure,
            physical_ic_renderings_clean={"DA1": clean},
            physical_ic_renderings_diagnostic={"DA1": diagnostic},
            verified_ic_source=signed,
            verified_ic_paint_binding=paint,
            verified_ic_snapshot=verified,
            source_continuation_project=None,
            expected_component_count=23,
            expected_net_count=15,
            expected_net_pinrefs=required_members,
            physical_page_box=Box(0, 0, 420000, 297000),
        )
    assert len(signed.circuit.nets) == 15
    assert sum(len(net.members) for net in signed.circuit.nets) == 62
    assert signed.circuit.nets is native.circuit.nets


@pytest.mark.parametrize(
    ("attack", "error_code"),
    (
        ("unsigned_partial_triple", "ROUTED_SHEET_SIGNED_IC_TRIPLE_REQUIRED"),
        ("forged_digest", "IC_TRUSTED_OVERLAY_PROVENANCE_OR_TARGET_MISMATCH"),
        ("forged_clean_ink", "ROUTED_SHEET_SIGNED_IC_SERIALIZED_INK_CHANGED"),
    ),
)
def test_real_115_paint_signed_manufacturer_trust_gate(attack, error_code):
    """A real 16-tip overlay cannot replace source-signed proof or SVG ink."""
    renderer = import_module(
        "gost_schematic.rendering.routed_native_sheet"
    ).render_routed_native_sheet
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    native, signed, paint, verified, style, measure = live_paint(font)
    clean = verified.render(
        signed, paint, style, measure, diagnostics=False,
    )[0]
    diagnostic = verified.render(
        signed, paint, style, measure, diagnostics=True,
    )[0]
    parts = {**native.parts, signed.part.identifier: signed.part}
    symbols = {
        part_id: native.symbols[part.symbol_id]
        for part_id, part in native.parts.items()
        if part.symbol_id in native.symbols
    }
    assert signed.symbol_surrogate is not None
    symbols[signed.part.identifier] = signed.symbol_surrogate
    trust = {
        "verified_ic_source": signed,
        "verified_ic_paint_binding": paint,
        "verified_ic_snapshot": verified,
    }
    if attack == "unsigned_partial_triple":
        trust["verified_ic_paint_binding"] = None
    elif attack == "forged_digest":
        trust["verified_ic_snapshot"] = replace(
            verified, circuit_sha256="0" * 64,
        )
    else:
        clean = replace(clean, svg=clean.svg + "<!-- unauthorized ink -->")
    with pytest.raises((ValueError, TypeError), match=error_code):
        renderer(
            signed.circuit, ExternalWireGraph(()), parts, symbols,
            style, measure,
            physical_ic_renderings_clean={"DA1": clean},
            physical_ic_renderings_diagnostic={"DA1": diagnostic},
            **trust,
            expected_component_count=23,
            expected_net_count=15,
            expected_net_pinrefs=62,
            physical_page_box=Box(0, 0, 420000, 297000),
        )
    assert signed.circuit.nets is native.circuit.nets
    assert len(verified.manifest.contacts) == 16


def canonical_signed_tl494_and_b(font: Path):
    """Real RECON source-named -> TI -> PAINT consent -> native b evidence.

    No route is supplied or reconstructed here. The genuine manufacturer
    contact snapshot can only attest exact Circuit and graphical endpoints.
    """
    native = compact_source_assembly()
    driver = import_module("examples.tl494_v5.route_candidate_driver")
    fixture, _source = driver.load_original_owner_fixture()
    original = driver.restore_original_named_nets(native, fixture)
    assert {net.name for net in original.nets} == set(
        load_frozen_source()["nets"]
    )
    bridge = import_module("examples.tl494_v5.cycle11_ti_bridge")
    owner = bridge.bind_verified_compact_ti(native, original)
    owner.verify()
    assert owner.reverse_source() is original
    inspection = inspect_type_a_font(
        font, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    assert inspection.style.font_sha256 == _FONT_SHA256
    assert inspection.measured_cap_height_um == 3500
    style = inspection.style
    measure = PillowTextMeasurer()
    proposal = propose_ic_paint_binding(owner.signed.record, style, measure)
    signed, snapshot = owner.seal_paint(proposal)
    snapshot.verify_against(signed, proposal)
    assert signed.circuit.nets is original.nets
    assert len(snapshot.manifest.contacts) == 16
    _checks(signed)
    symbols = {
        part_id: native.symbols[part.symbol_id]
        for part_id, part in native.parts.items()
        if part.symbol_id in native.symbols
    }
    assert signed.symbol_surrogate is not None
    symbols[signed.part.identifier] = signed.symbol_surrogate
    project = import_module(
        "examples.render_tl494_compact_new_router_cycle10"
    )._bind_verified_source_b(font, signed.circuit, symbols)
    assert project.circuit.nets is original.nets
    assert len(project.stubs) == 2
    parts = {**native.parts, signed.part.identifier: signed.part}
    return original, signed, proposal, snapshot, style, measure, project, parts, symbols


def _canonical_source_witness(font: Path):
    """Emit audit facts from typed source objects; hashes are not credentials."""
    (
        source, signed, paint, snapshot, style, measure, project, parts, symbols,
    ) = canonical_signed_tl494_and_b(font)
    renderer = import_module(
        "gost_schematic.rendering.routed_native_sheet"
    ).render_routed_native_sheet
    clean = snapshot.render(
        signed, paint, style, measure, diagnostics=False,
    )[0]
    diagnostic = snapshot.render(
        signed, paint, style, measure, diagnostics=True,
    )[0]
    result = renderer(
        signed.circuit, ExternalWireGraph(()), parts, symbols, style, measure,
        physical_ic_renderings_clean={"DA1": clean},
        physical_ic_renderings_diagnostic={"DA1": diagnostic},
        verified_ic_source=signed,
        verified_ic_paint_binding=paint,
        verified_ic_snapshot=snapshot,
        source_continuation_project=project,
        expected_component_count=23,
        expected_net_count=15,
        expected_net_pinrefs=62,
        physical_page_box=Box(0, 0, 420000, 297000),
    )
    assert result.manifest["signed_manufacturer_ic_16_verified"] is True
    assert result.manifest["source_b_two_physical_vectors_verified"] is True
    assert not result.printable_candidate
    assert result.manifest["blockers"]
    assert _expected_marker_count(result.clean_svg) == 0
    assert _expected_marker_count(result.diagnostic_svg) == 16
    for view in (result.clean_svg, result.diagnostic_svg):
        root = ET.fromstring(view)
        ink = {
            node.get("data-source-stub-id"): node
            for node in root.iter()
            if node.get("data-layer") == "nonphysical-continuation-stub"
        }
        assert len(ink) == 2
        for stub in project.stubs:
            stroke = ink[stub.id]
            assert stroke.tag == _NS + "line"
            assert (
                stroke.get("data-nonphysical"),
                stroke.get("data-electrical-junction"),
                stroke.get("data-connectable"),
            ) == ("true", "false", "false")
            assert tuple(
                stroke.get(label) for label in ("x1", "y1", "x2", "y2")
            ) == (
                format_mm(stub.start.x), format_mm(stub.start.y),
                format_mm(stub.end.x), format_mm(stub.end.y),
            )
    # QA C11 vendor-row mutant: the record is the vendor authority;
    # missing a redundant catalog entry must not invent/lose signed pins.
    # A PRESENT but contradictory vendor definition MUST fail closed.
    assembly = compact_source_assembly()
    trusted_parts = dict(assembly.parts)
    assert TI_DEVICE_ID not in trusted_parts
    without_vendor = bind_positioned_photo_circuit_from_catalog(
        source, assembly.owner_ic_record, trusted_parts,
        aliases=assembly.owner_aliases,
    )
    with_vendor = bind_positioned_photo_circuit_from_catalog(
        source, assembly.owner_ic_record,
        {**trusted_parts, TI_DEVICE_ID: signed.part},
        aliases=assembly.owner_aliases,
    )
    assert with_vendor == without_vendor
    assert with_vendor.circuit.nets is source.nets
    forged_pins = tuple(
        replace(p, name="FORGED_FEEDBACK") if p.number == "3" else p
        for p in signed.part.pins
    )
    counterfeit = replace(signed.part, pins=forged_pins)
    try:
        bind_positioned_photo_circuit_from_catalog(
            source, assembly.owner_ic_record,
            {**trusted_parts, TI_DEVICE_ID: counterfeit},
            aliases=assembly.owner_aliases,
        )
    except ValueError as exc:
        assert str(exc) == "IC_ADAPTER_CATALOG_MANUFACTURER_PINOUT_CONFLICT"
    else:
        raise AssertionError("IC_C15_FORGED_VENDOR_PART_UNSAFE_ACCEPTED")
    manufacturer_pinlist = [
        (p.number, p.name, p.electrical_type.value)
        for p in signed.part.pins
    ]
    manufacturer_bytes = json.dumps(
        manufacturer_pinlist, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    netlist = [
        {
            "name": net.name,
            "members": [f"{p.reference}.{p.number}" for p in net.members],
        } for net in source.nets
    ]
    netlist_data = json.dumps(
        netlist, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    pins = sorted(signed.contacts, key=lambda c: int(c.pin_ref.number))
    witness = {
        "schema_version": 1,
        "status": "DRAFT_TRUSTED_SOURCE_PHYSICAL_NOT_FULL_ROUTED_PRINT",
        "frozen_original_git_sha": FROZEN_SOURCE_COMMIT,
        "owner_sha": {
            "ic97": os.environ.get("GITHUB_SHA", "LOCAL_NO_GITHUB_SHA"),
            "recon115": os.environ.get(
                "IC_OWNER_RECON_SHA", "LOCAL_OWNER_SHA_NOT_VERIFIED",
            ),
            "paint93": os.environ.get(
                "IC_OWNER_PAINT_SHA", "LOCAL_OWNER_SHA_NOT_VERIFIED",
            ),
            "ygo113": os.environ.get(
                "IC_OWNER_YGO_SHA", "LOCAL_OWNER_SHA_NOT_VERIFIED",
            ),
        },
        "legacy_part_id": "reference.tl494cn",
        "verified_manufacturer_part_id": TI_DEVICE_ID,
        "manufacturer_partdefinition_pinlist_sha256": hashlib.sha256(
            manufacturer_bytes
        ).hexdigest(),
        "manufacturer_catalog_absent_uses_source_signed_record": True,
        "manufacturer_catalog_explicit_matching_entry_accepted": True,
        "manufacturer_catalog_spoofed_pin3_rejected": True,
        "manufacturer_catalog_spoof_error": (
            "IC_ADAPTER_CATALOG_MANUFACTURER_PINOUT_CONFLICT"
        ),
        "part_id_translation_only_da1": True,
        "original_net_names_preserved": True,
        "source_circuit_net_tuple_identity_preserved": (
            signed.circuit.nets is source.nets
        ),
        "original_netlist_sha256": hashlib.sha256(netlist_data).hexdigest(),
        "source_component_count": len(source.components),
        "source_net_count": len(source.nets),
        "source_physical_pinref_count": sum(
            len(net.members) for net in source.nets
        ),
        "source_original_named_nets": netlist,
        "tl494_factory_pins": [{
            "pin_ref": f"{c.pin_ref.reference}.{c.pin_ref.number}",
            "manufacturer_name": c.manufacturer_pin_name,
            "display_alias": c.schematic_short_label,
            "electrical_type": c.electrical_type.value,
            "source_named_net": c.net_id,
            "physical_tip_um": [c.world_anchor.x, c.world_anchor.y],
        } for c in pins],
        "sealed_source_circuit_sha256": snapshot.circuit_sha256,
        "source_b_nonphysical_stubs": [{
            "id": stub.id,
            "endpoint_id": stub.endpoint_id,
            "source_pin_ref": f"{stub.pin.reference}.{stub.pin.number}",
            "start_um": [stub.start.x, stub.start.y],
            "end_um": [stub.end.x, stub.end.y],
            "not_electrical_wire_segment": True,
        } for stub in project.stubs],
        "font_type_a_sha256": style.font_sha256,
        "font_cap_height_um": 3500,
        "clean_green_contacts": _expected_marker_count(result.clean_svg),
        "diagnostic_green_contacts": _expected_marker_count(
            result.diagnostic_svg
        ),
        "new_route_segments": 0,
        "new_route_15_of_15_complete": False,
        "printable_candidate": result.printable_candidate,
        "whole_sheet_blockers": result.manifest["blockers"],
        "normative_eskd_approved": False,
    }
    return witness


def test_real_cycle14_canonical_signed_source_and_b_print_witness():
    """Canonical 15 frozen names, 16 TI tips, 2 real b SVG lines, NO release."""
    witness = _canonical_source_witness(
        Path(os.environ["IC_TYPE_A_FONT_PATH"])
    )
    assert witness["source_component_count"] == 23
    assert witness["source_net_count"] == 15
    assert witness["source_physical_pinref_count"] == 62
    assert len(witness["tl494_factory_pins"]) == 16
    assert len(witness["source_b_nonphysical_stubs"]) == 2
    assert witness["original_net_names_preserved"] is True
    assert witness["manufacturer_catalog_absent_uses_source_signed_record"]
    assert witness["manufacturer_catalog_explicit_matching_entry_accepted"]
    assert witness["manufacturer_catalog_spoofed_pin3_rejected"]
    assert witness["manufacturer_catalog_spoof_error"] == (
        "IC_ADAPTER_CATALOG_MANUFACTURER_PINOUT_CONFLICT"
    )
    assert witness["source_circuit_net_tuple_identity_preserved"] is True
    assert witness["clean_green_contacts"] == 0
    assert witness["diagnostic_green_contacts"] == 16
    assert witness["new_route_15_of_15_complete"] is False
    assert witness["printable_candidate"] is False
    assert {s["source_pin_ref"] for s in witness["source_b_nonphysical_stubs"]} == {
        "X2.1", "R5.2",
    }
    assert {
        item["name"] for item in witness["source_original_named_nets"]
    } == set(load_frozen_source()["nets"])
    contacts = {
        p["pin_ref"]: p for p in witness["tl494_factory_pins"]
    }
    assert contacts["DA1.3"]["manufacturer_name"] == "FEEDBACK"
    assert contacts["DA1.3"]["electrical_type"] == "input"
    assert contacts["DA1.13"]["manufacturer_name"] == "OUTPUT CTRL"
    assert contacts["DA1.13"]["electrical_type"] == "input"
    assert contacts["DA1.14"]["manufacturer_name"] == "REF"
    assert contacts["DA1.14"]["electrical_type"] == "power_output"

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    original, signed, paint, verified, style, measurer = live_paint(args.font_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    images = {}
    for debug, name in ((False, "clean"), (True, "diagnostic")):
        rendered = verified.render(
            signed, paint, style, measurer, diagnostics=debug,
        )[0]
        count = _expected_marker_count(rendered.svg)
        assert count == (16 if debug else 0)
        dst = args.output_dir / f"DA1-recon115-ic97-paint93-{name}.svg"
        dst.write_text(rendered.svg, encoding="utf-8")
        images[name] = {"svg": dst.name, "green_targets": count}
    snapshot = {
        "status": "PASS_DRAFT_SOURCE_BRIDGE_ONLY_NOT_FULL_SHEET_PRINT",
        "original_source_commit": FROZEN_SOURCE_COMMIT,
        "legacy_da1_id": "reference.tl494cn",
        "verified_ti_da1_id": TI_DEVICE_ID,
        "reversible_original_circuit": True,
        "source_components": len(original.circuit.components),
        "source_nets": len(original.circuit.nets),
        "source_physical_memberships": sum(len(n.members) for n in original.circuit.nets),
        "tl494_physical_pins": len(signed.contacts),
        "unchanged_nets": signed.circuit.nets is original.circuit.nets,
        "diagnostic_only_target_marks": images,
        "all_15_net_routed": False,
        "gost_normatively_approved": False,
    }
    (args.output_dir / "bridge-manifest.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    witness = _canonical_source_witness(args.font_file)
    (args.output_dir / "source-physical-witness.json").write_text(
        json.dumps(witness, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8",
    )
    print(json.dumps(snapshot, sort_keys=True))


if __name__ == "__main__":
    main()
