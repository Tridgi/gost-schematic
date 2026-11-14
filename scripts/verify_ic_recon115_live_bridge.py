"""Live #115 compact A3 -> #97 TI physical -> #93 PAINT trust gate.

ONLY invoked in an isolated CI checkout containing genuine pinned PR #115,
#113 catalog and #93 renderer sources. NOT a synthetic stand-in or printable
15-Net sheet. Never rewrites the frozen source, and never merges PRs.
"""
from __future__ import annotations

import argparse
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
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import IcTextAngle, resolve_ic_pin_positions
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
from gost_schematic.electrical.tl494cn import TI_DEVICE_ID
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

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
    print(json.dumps(snapshot, sort_keys=True))


if __name__ == "__main__":
    main()
