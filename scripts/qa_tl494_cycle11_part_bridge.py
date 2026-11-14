"""QA Cycle 11 genuine manufacturer/legacy Part-ID reversible bridge.

Real RECON positioned 23-part source + frozen TI photo + IC97 exact typed
factory upgrade. No edits to original data or fabricated DA1 surrogate ink.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_cycle9_circuit_integration import (
    assert_frozen_photo_topology,
    bind_positioned_photo_circuit_from_catalog,
)
from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.route_candidate_driver import (
    load_original_owner_fixture,
    restore_original_named_nets,
)
from gost_schematic.core.geometry import Point
from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
from gost_schematic.electrical.tl494cn import TI_DEVICE_ID
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

ORIGINAL = "e695c415fdced164b0e0c39c5249d030795a0aa6"
SVG = "{http://www.w3.org/2000/svg}"


def require(value: bool, code: str) -> None:
    if not value:
        raise AssertionError(code)


def _mutate_component(source: Circuit, reference: str, change) -> Circuit:
    return Circuit(tuple(
        change(instance) if instance.reference == reference else instance
        for instance in source.components
    ), source.nets)


def verify_bridge(font_file: Path) -> dict:
    frozen, baseline = load_original_owner_fixture()
    source = compact_source_assembly()
    source.verify()
    raw = restore_original_named_nets(source, frozen)
    require(len(raw.components) == 23 and len(raw.nets) == 15 and
            sum(len(n.members) for n in raw.nets) == 62,
            "QA_C11_BRIDGE_DID_NOT_USE_SOURCE_23_15_62")
    require({n.name for n in raw.nets} == set(frozen["nets"]),
            "QA_C11_BRIDGE_SOURCE_A_B_NAMED_NET_DRIFT")
    require(next(c for c in raw.components if c.reference == "DA1").part_id ==
            "reference.tl494cn",
            "QA_C11_BRIDGE_NOT_REAL_LEGACY_SOURCE_PART")
    require(baseline.part.identifier == TI_DEVICE_ID and
            TI_DEVICE_ID != "reference.tl494cn",
            "QA_C11_BRIDGE_MANUFACTURER_PART_NOT_DISTINCT")
    parts = dict(source.parts)
    parts[baseline.part.identifier] = baseline.part
    upgraded = bind_positioned_photo_circuit_from_catalog(
        raw, source.owner_ic_record, parts,
        aliases=source.owner_aliases,
    )
    assert_frozen_photo_topology(upgraded, frozen)
    require(upgraded.circuit.nets is raw.nets and
            upgraded.circuit.nets == raw.nets and
            len(upgraded.circuit.components) == 23 and
            upgraded.part.identifier == TI_DEVICE_ID,
            "QA_C11_BRIDGE_CHANGED_NET_TUPLE_OR_BOM")
    source_component_ids = {
        c.reference: c.part_id for c in raw.components
    }
    new_component_ids = {
        c.reference: c.part_id for c in upgraded.circuit.components
    }
    require({ref for ref in source_component_ids
             if source_component_ids[ref] != new_component_ids[ref]} ==
            {"DA1"} and new_component_ids["DA1"] == TI_DEVICE_ID,
            "QA_C11_BRIDGE_CHANGED_NON_IC_PART_ID")
    for pin in range(1, 17):
        contact = upgraded.contact(PinRef("DA1", str(pin)))
        require(contact.net_id in {n.name for n in raw.nets},
                "QA_C11_BRIDGE_IC_NET_NOT_SOURCE")
    require(upgraded.contact(PinRef("DA1", "3")).electrical_type.value ==
            "input" and upgraded.contact(
                PinRef("DA1", "13")
            ).electrical_type.value == "input",
            "QA_C11_BRIDGE_FB_OC_NOT_TI_INPUT")
    font = inspect_type_a_font(font_file, h_um=3500)
    style, measurer = font.style, PillowTextMeasurer()
    actual_paint = propose_ic_paint_binding(
        source.owner_ic_record, style, measurer,
    )
    actual_paint.verify_endpoints()
    snapshot = upgraded.seal_paint_overlay(actual_paint)
    snapshot.verify_against(upgraded, actual_paint)
    clean = snapshot.render(
        upgraded, actual_paint, style, measurer,
        diagnostics=False,
    )
    diagnostic = snapshot.render(
        upgraded, actual_paint, style, measurer,
        diagnostics=True,
    )
    require(len(clean) == len(diagnostic) == 1,
            "QA_C11_BRIDGE_PHYSICAL_DA1_SINGLE_UNIT_LOST")
    modes = {}
    for mode, output in (("clean", clean[0]), ("diagnostic", diagnostic[0])):
        svg = ET.fromstring(output.svg)
        leads = svg.findall(
            f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
        )
        squares = svg.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        require(len(leads) == 16 and
                len(squares) == (16 if mode == "diagnostic" else 0),
                "QA_C11_BRIDGE_TRUSTED_SVG_PHYSICAL_PINLOSS")
        if mode == "diagnostic":
            require({x.get("data-pin-ref") for x in squares} ==
                    {f"DA1.{n}" for n in range(1, 17)},
                    "QA_C11_BRIDGE_TRUSTED_GREEN_PINREF_WRONG")
        modes[mode] = {
            "owner_PAINT_renderer": True,
            "manufacturer_16_real_tip_lines": 16,
            "editor_only_squares": len(squares),
        }
    mutants = {}
    original_common = next(n for n in raw.nets if n.name == "COMMON")
    actual_b = next(n for n in raw.nets if n.name == "b_NEGATIVE_OUTPUT")
    changes = {
        "unknown_legacy_DA1_part": (
            _mutate_component(
                raw, "DA1", lambda c: replace(c, part_id="FRAUD_TL494"),
            ), parts,
        ),
        "DA1_anchor_shift_1um": (
            _mutate_component(raw, "DA1", lambda c: replace(
                c, origin=Point(c.origin.x + 1, c.origin.y),
            )), parts,
        ),
        "source_R8_nominal_dropped": (
            _mutate_component(raw, "R8", lambda c: replace(
                c, nominal=None,
            )), parts,
        ),
        "source_COMMON_foreign_pin": (
            Circuit(raw.components, tuple(
                Net(n.name, (
                    PinRef("DA1", "999"), *n.members[1:]
                )) if n.name == "COMMON" else n for n in raw.nets
            )), parts,
        ),
        "source_b_continuation_net_renamed": (
            Circuit(raw.components, tuple(
                Net("FAKE_OTHER_B", actual_b.members)
                if n.name == actual_b.name else n for n in raw.nets
            )), parts,
        ),
        "missing_real_DA1_pinref": (
            Circuit(raw.components, tuple(
                Net(n.name, tuple(
                    m for m in n.members if m != PinRef("DA1", "7")
                )) if n.name == original_common.name else n
                for n in raw.nets
            )), parts,
        ),
        "missing_vendor_partdefinition": (
            raw, {k: v for k, v in parts.items() if k != TI_DEVICE_ID},
        ),
    }
    for name, (candidate, candidate_parts) in changes.items():
        try:
            bind_positioned_photo_circuit_from_catalog(
                candidate, source.owner_ic_record, candidate_parts,
                aliases=source.owner_aliases,
            )
        except (AssertionError, ValueError, TypeError) as exc:
            require(str(exc).startswith(("TL494_", "IC_")),
                    "QA_C11_BRIDGE_NEGATIVE_UNRELATED_REJECTION:" + name)
            mutants[name] = "REJECTED_TRUE_PHYSICAL_SOURCE"
        else:
            raise AssertionError("QA_C11_BRIDGE_UNSAFE_SOURCE_ACCEPTED:" + name)
    require(len(mutants) == 7, "QA_C11_BRIDGE_NOT_ALL_NEGATIVES_RUN")
    return {
        "original_source": ORIGINAL,
        "legacy_DA1_part_id": "reference.tl494cn",
        "canonical_manufacturer_DA1_part_id": TI_DEVICE_ID,
        "non_IC_partIDs_unchanged": 22,
        "source_23part_15net_62PinRef_preserved": True,
        "raw_a_b_transfer_names_preserved": True,
        "source_nets_tuple_identity_preserved": True,
        "manufacturer_FB_OC_roles_both_input": True,
        "real_trusted_editor_modes": modes,
        "seven_hostile_real_source_mutations": mutants,
        "source_b_continuation_print_rebinding":
            "BLOCKED_NEW_SPATIAL_MARKERS_NOT_VERIFIED",
        "new_net_route_15_of_15": "BLOCKED_SEPARATE_ROUTER_OWNER",
        "print_or_normative_release": "NO_GO",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify_bridge(args.font_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n", encoding="utf-8",
    )
    print("QA_CYCLE11_MANUFACTURER_PART_BRIDGE " +
          json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
