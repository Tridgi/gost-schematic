"""Current PAINT #93 + actual 23/15/62 Circuit sealed E3 proof (DRAFT).

Produces REAL factory-role verified IC view ink and per-physical-contact
source manifest. Other 22 photo components have no source-authenticated
placement in this fixture; DO NOT call these sheets a full routed A3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from examples.tl494_cycle9_circuit_integration import (
    FROZEN_FIXTURE_GIT_BLOB_SHA1,
    FROZEN_SOURCE_COMMIT,
    assert_frozen_photo_topology,
    build_frozen_photo_23,
)
from gost_schematic.electrical.ic import (
    IcTextAngle,
    resolve_ic_pin_positions,
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
from gost_schematic.standards.type_a_font import inspect_type_a_font

PAINT_COMMIT = "161c31bd0b538c6e827341ae465c3b3a59f6637d"
EXPECTED_FONT_SHA256 = (
    "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
)


def _physical_and_real_paint(style, measurer):
    source, photo = build_frozen_photo_23()
    original = resolve_ic_pin_positions(
        source.record.device, source.record.specs, source.record.placements,
    )
    draft = propose_ic_paint_binding(source.record, style, measurer)
    changed = resolve_ic_pin_positions(
        draft.record.device, draft.record.specs, draft.record.placements,
    )
    moved = tuple(
        contact for contact in original
        if original[contact] != changed[contact]
    )
    net_contacts = {
        member for net in source.circuit.nets for member in net.members
    }
    proposal = IcGeometryConsent(
        ic_record_fingerprint(source.record), moved,
        tuple(member for member in moved if member in net_contacts),
    )
    updated, delta = source.revise(draft.record, consent=proposal)
    if set(delta.moved) != set(moved) or set(delta.connected_moved) != (
        set(moved) & net_contacts
    ):
        raise ValueError("TL494_TRUSTED_UNAPPROVED_PHYSICAL_RELOCATION")
    if updated.circuit is not source.circuit:
        raise ValueError("TL494_TRUSTED_NET_OWNER_CHANGED")
    assert_frozen_photo_topology(updated, photo)
    return updated, draft


def generate(font_file: Path, output_dir: Path) -> dict:
    checked = inspect_type_a_font(font_file, h_um=3500)
    if checked.style.font_sha256 != EXPECTED_FONT_SHA256:
        raise ValueError("TL494_TRUSTED_ACTUAL_OPENGOST_REQUIRED")
    style, measure = checked.style, PillowTextMeasurer()
    source, binding = _physical_and_real_paint(style, measure)
    initial = {
        item.pin_ref: item.world_anchor for item in source.contacts
    }
    nets = source.circuit.nets
    output_dir.mkdir(parents=True, exist_ok=True)
    output = {}
    for angle, name in (
        (IcTextAngle.BOTTOM_TO_TOP, "pwm_bottom_to_top_270"),
        (IcTextAngle.HORIZONTAL, "pwm_horizontal_0"),
    ):
        record = revise_ic_text_orientation(source.record, angle)
        revised, delta = source.revise(record)
        if delta.moved or delta.connected_moved:
            raise ValueError("TL494_TRUSTED_WORD_CHANGED_PIN_WORLD_ANCHOR")
        if revised.circuit.nets != nets or {
            c.pin_ref: c.world_anchor for c in revised.contacts
        } != initial:
            raise ValueError("TL494_TRUSTED_WORD_CHANGED_ELECTRICAL_TOPOLOGY")
        draft = bind_ic_paint_text_only(binding, record)
        sealed = revised.seal_paint_overlay(draft)
        sealed.verify_against(revised, draft)
        renders = {}
        for diagnostic in (False, True):
            mode = "diagnostic" if diagnostic else "clean"
            real = sealed.render(
                revised, draft, style, measure, diagnostics=diagnostic,
            )
            if len(real) != 1 or len(real[0].pin_anchors) != 16:
                raise ValueError("TL494_TRUSTED_MISSING_PAINT_PHYSICAL_CONTACT")
            payload = real[0].svg.encode("utf-8")
            dest = output_dir / f"tl494_{name}_{mode}.svg"
            dest.write_bytes(payload)
            renders[mode] = {
                "file": dest.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "physical_pins": len(real[0].pin_anchors),
                "verified_target_count": len(real[0].connection_targets),
            }
        output[name] = {
            "angle": angle.value,
            "state_sha256": sealed.circuit_sha256,
            "rendering": renders,
        }
    raw = {
        "schema_version": 1,
        "status": "DRAFT_SEALED_CURRENT_PAINT_93_NO_ROUTED_FULL_SHEET",
        "paint_pinned_commit": PAINT_COMMIT,
        "photo_source_commit": FROZEN_SOURCE_COMMIT,
        "photo_source_fixture_git_blob_sha1": FROZEN_FIXTURE_GIT_BLOB_SHA1,
        "device": source.record.device.identifier,
        "components": len(source.circuit.components),
        "named_nets": len(source.circuit.nets),
        "net_members": sum(len(n.members) for n in source.circuit.nets),
        "physical_tl494_pins": len(source.contacts),
        "font_sha256": EXPECTED_FONT_SHA256,
        "modelled_print_route": False,
        "source_original_91_wire_drc_released": False,
        "manufacturer_pins": [{
            "pin_ref": [pin.pin_ref.reference, pin.pin_ref.number],
            "unit_id": pin.unit_id,
            "name": pin.manufacturer_pin_name,
            "display_alias": pin.schematic_short_label,
            "electrical_type": pin.electrical_type.value,
            "world_um": [pin.world_anchor.x, pin.world_anchor.y],
            "net_name": pin.net_id,
        } for pin in source.contacts],
        "variants": output,
    }
    if {p["pin_ref"][1] for p in raw["manufacturer_pins"]} != {
        str(n) for n in range(1, 17)
    }:
        raise ValueError("TL494_TRUSTED_FACTORY_PIN_SET_CHANGED")
    lookup = {
        p["pin_ref"][1]: p for p in raw["manufacturer_pins"]
    }
    if (
        lookup["3"]["name"] != "FEEDBACK"
        or lookup["3"]["display_alias"] != "FB"
        or lookup["3"]["electrical_type"] != "input"
        or lookup["13"]["name"] != "OUTPUT CTRL"
        or lookup["13"]["display_alias"] != "OC"
        or lookup["13"]["electrical_type"] != "input"
    ):
        raise ValueError("TL494_TRUSTED_FACTORY_ROLES_OR_ALIASES_WRONG")
    if {p["net_name"] for p in raw["manufacturer_pins"]} - {
        net.name for net in source.circuit.nets
    }:
        raise ValueError("TL494_TRUSTED_FOREIGN_CONTACT_NET")
    (output_dir / "TL494_23part_verified_pinref_manifest.json").write_text(
        json.dumps(raw, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    opts = parser.parse_args()
    outcome = generate(opts.font_file, opts.output_dir)
    print(json.dumps({
        "status": outcome["status"],
        "components": outcome["components"],
        "nets": outcome["named_nets"],
        "members": outcome["net_members"],
        "contacts": outcome["physical_tl494_pins"],
        "real_svg": sum(
            len(variant["rendering"])
            for variant in outcome["variants"].values()
        ),
        "sealed": True,
        "routed_full_sheet": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
