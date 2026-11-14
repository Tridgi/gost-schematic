"""Cycle 11: test real HEAD #97/#115 source-typed IC part bridge, not a stub.

The published owner adapter performs every authorized REFERENCE->TI part-ID
change in a NEW Circuit. This check must never repair, drop or relabel a Net.
No route/print claim follows from successful source-identity inspection.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from importlib import import_module
from pathlib import Path

from gost_schematic.model.circuit import Circuit, PinRef


def check_active_owners(out: Path, *, owner_heads: dict[str, str]) -> dict:
    from examples.tl494_v5.compact_layout import compact_source_assembly

    source = compact_source_assembly()
    source.verify()
    if source.manifest()["source_sha"] != (
        "e695c415fdced164b0e0c39c5249d030795a0aa6"
    ):
        raise ValueError("C11_SOURCE_PINNED_ORIGINAL_SHA_CHANGED")
    circuit = source.circuit
    before = {n.name: n.members for n in circuit.nets}
    if (
        len(circuit.components), len(before),
        sum(len(n.members) for n in circuit.nets)
    ) != (23, 15, 62):
        raise ValueError("C11_SOURCE_23_15_62_DRIFT")
    from examples.tl494_cycle9_circuit_integration import (
        bind_positioned_photo_circuit_from_catalog,
    )
    from gost_schematic.electrical.ic_circuit_adapter import (
        IcCircuitBinding,
    )
    from gost_schematic.electrical.tl494cn import TI_DEVICE_ID
    from gost_schematic.rendering.routed_native_sheet import (
        render_routed_native_sheet,
    )

    bound = bind_positioned_photo_circuit_from_catalog(
        circuit, source.owner_ic_record, source.parts,
        aliases=source.owner_aliases,
    )
    if not isinstance(bound, IcCircuitBinding):
        raise TypeError("C11_IC_BRIDGE_NOT_OWNER_TYPED_BINDING")
    if bound.circuit.nets is not circuit.nets:
        raise ValueError("C11_OWNER_ADAPTER_CLONED_OR_REWROTE_NETS")
    if before != {n.name: n.members for n in bound.circuit.nets}:
        raise ValueError("C11_OWNER_ADAPTER_CHANGED_PHYSICAL_PINREFS")
    old = {c.reference: c for c in circuit.components}
    new = {c.reference: c for c in bound.circuit.components}
    if any(new[r] != old[r] for r in old if r != "DA1"):
        raise ValueError("C11_OWNER_ADAPTER_MODIFIED_NON_IC_COMPONENTS")
    if (
        old["DA1"].part_id != "reference.tl494cn"
        or new["DA1"].part_id != TI_DEVICE_ID
        or new["DA1"].origin != old["DA1"].origin
        or new["DA1"].transform != old["DA1"].transform
    ):
        raise ValueError("C11_REFERENCE_TO_MANUFACTURER_ID_NOT_REVERSIBLE")
    physical = {
        p for net in circuit.nets for p in net.members
        if p.reference == "DA1"
    }
    if physical != {PinRef("DA1", str(n)) for n in range(1, 17)}:
        raise ValueError("C11_MANUFACTURER_IC_ALL_16_PHYSICAL_PINS_REQUIRED")
    bound.validate()
    if IcCircuitBinding.from_json(bound.to_json()) != bound:
        raise ValueError("C11_MANUFACTURER_SOURCE_ROUNDTRIP_DRIFT")
    if (
        bound.part.identifier != TI_DEVICE_ID
        or bound.symbol_surrogate is None
        or bound.part.symbol_id != bound.symbol_surrogate.identifier
        or len(bound.part.pins) != 16
    ):
        raise ValueError("C11_IC_TYPED_PART_OR_SURROGATE_CONTRACT_DRIFT")
    contacts = tuple(bound.contact(PinRef("DA1", str(n)))
                     for n in range(1, 17))
    if len({c.world_anchor for c in contacts}) != 16:
        raise ValueError("C11_IC_WORLD_ANCHOR_COLLISION")
    # The official IC owner also provides a physical PartDefinition and
    # strictly DRAFT routing surrogate. Consume those typed values rather
    # than fabricating a Part ID or manually constructing pseudo-graphics.
    # Actual artwork must still use PAINT ink and all 16 physical leads.
    from gost_schematic.engines.orthogonal_route_planner import _resolve_real_pin

    manufacturer_parts = {**source.parts, TI_DEVICE_ID: bound.part}
    manufacturer_symbols = {
        **source.symbols, TI_DEVICE_ID: bound.symbol_surrogate,
    }
    for pin in physical:
        resolved, _normal, instance = _resolve_real_pin(
            bound.circuit, pin, manufacturer_parts, manufacturer_symbols,
        )
        if instance.part_id != TI_DEVICE_ID or (
            resolved != bound.contact(pin).world_anchor
        ):
            raise ValueError("C11_NET_ROUTER_TO_TI_CONTACT_WORLD_ENDPOINT_DRIFT")
    if (
        bound.contact(PinRef("DA1", "3")).electrical_type.value != "input"
        or bound.contact(PinRef("DA1", "13")).electrical_type.value != "input"
    ):
        raise ValueError("C11_TI_INPUT_3_13_ROLES_CHANGED")

    # Negative tests use a fresh temporary Circuit only, never source
    # mutation. The manufacturer owner must reject every forged variant.
    failures = {}
    malformed = (
        ("FORGED_DA1_PART_ID", Circuit(
            tuple(replace(c, part_id="forged.tl494") if c.reference == "DA1"
                  else c for c in circuit.components),
            circuit.nets,
        )),
        ("MISSING_ONE_PINREF", Circuit(
            circuit.components, (
                replace(circuit.nets[0],
                        members=circuit.nets[0].members[:-1]),
                *circuit.nets[1:],
            ),
        )),
        ("DA1_POSE_DRIFT", Circuit(
            tuple(replace(c, origin=replace_point(c.origin, 1000))
                  if c.reference == "DA1" else c
                  for c in circuit.components),
            circuit.nets,
        )),
    )
    for label, forged in malformed:
        try:
            bind_positioned_photo_circuit_from_catalog(
                forged, source.owner_ic_record, source.parts,
                aliases=source.owner_aliases,
            )
        except (TypeError, ValueError) as exc:
            failures[label] = str(exc)
        else:
            raise AssertionError("C11_TYPED_OWNER_ACCEPTED_FORGED_" + label)
    import inspect

    signature = inspect.signature(render_routed_native_sheet)
    if not {
        "physical_ic_renderings_clean",
        "physical_ic_renderings_diagnostic",
        "expected_component_count",
        "expected_net_count",
        "expected_net_pinrefs",
        "route_preview",
    } <= set(signature.parameters):
        raise ValueError("C11_CURRENT_PAINT_TYPED_ROUTE_RENDERER_API_DRIFT")
    manifest = {
        "status": "SOURCE_TYPED_PART_ADAPTER_PASS_NO_PRINT_ASSERTION",
        "source": "e695c415fdced164b0e0c39c5249d030795a0aa6",
        "pinned_active_owners": owner_heads,
        "real_components": 23, "real_nets": 15,
        "real_physical_memberships": 62, "real_DA1_pins": 16,
        "source_net_diff": {"added": [], "removed": [], "modified": []},
        "before_part_id": old["DA1"].part_id,
        "after_part_id": new["DA1"].part_id,
        "pose_unchanged": True,
        "official_IC_part_from_owner": bound.part.identifier,
        "official_IC_surrogate_draft_only": True,
        "router_all_16_TI_PinRef_world_anchors_verified": True,
        "official_IC_binding_json_roundtrip": True,
        "source_reference_membership": {
            name: [f"{p.reference}.{p.number}" for p in members]
            for name, members in before.items()
        },
        "forged_negatives_rejected": failures,
        "current_paint_render_route_typed_api": True,
        "actual_route_15_15": False,
        "approved_UGO": False, "print_pass": False,
        "no_source_file_or_net_mutation": True,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return manifest


def replace_point(at, dx: int):
    from gost_schematic.core.geometry import Point

    return Point(at.x + dx, at.y)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ic-sha", required=True)
    parser.add_argument("--paint-sha", required=True)
    parser.add_argument("--recon-sha", required=True)
    parser.add_argument("--ygo-sha", required=True)
    args = parser.parse_args()
    owners = {
        "IC": args.ic_sha,
        "PAINT": args.paint_sha,
        "RECON": args.recon_sha,
        "YGO": args.ygo_sha,
    }
    if any(len(sha) != 40 for sha in owners.values()):
        raise ValueError("C11_OWNER_SHAS_MUST_BE_EXACT_40_HEX")
    print(json.dumps(
        check_active_owners(args.output, owner_heads=owners),
        ensure_ascii=False, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
