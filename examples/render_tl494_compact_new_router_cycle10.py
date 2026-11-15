"""Compact real 23/15 TL494 A3 candidate: #115 placement + #114 new route.

This is explicitly a rejected/blocked pre-print **new-route attempt** until
all 15 Nets and independent QA+ESKD print geometry pass. The only rendered
artwork comes from the PAINT engine and exact owner records. No SVG patch or
retrospective fake 91-wire reconstruction.
"""
import argparse
import hashlib
import json
from importlib import import_module
from pathlib import Path

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.rendering.routed_native_sheet import render_routed_native_sheet
from gost_schematic.standards.type_a_font import inspect_type_a_font

SOURCE = "e695c415fdced164b0e0c39c5249d030795a0aa6"
IC = "1b007cbe878c45a52632f83fc138aefc99cd7924"
NET = "b2a7a46c2f031dd125dd0879c9d59d24e27decbf"
RECON = "3de150124103686d4d8f3fd764dc4a4486c341b5"



def _bind_verified_source_b(font_file: Path, circuit, symbols_by_part):
    """Rebind *only* the two frozen source b endpoints to actual compact pins.

    Use the source's typed NetContinuationProject and RECON's checked exact
    historical stub vectors; never move marker artwork by guessed pixels.
    """
    old_native = import_module(
        "examples.render_tl494_full_native_cycle9"
    ).construct_native_paint(font_file)
    original_b = old_native[8]
    rebound = import_module(
        "examples.tl494_v5.cycle11_b_continuation"
    ).rebind_true_source_b(original_b, circuit, symbols_by_part)
    errors = import_module(
        "gost_schematic.electrical.netrefs"
    ).validate_net_continuations(
        rebound,
        physical_pin_anchors={stub.pin: stub.start for stub in rebound.stubs},
    )
    if errors:
        raise ValueError(
            "PAINT_COMPACT_B_REBIND_REVALIDATION_FAILED:"
            + ",".join(item.code for item in errors)
        )
    if (
        rebound.circuit.nets is not circuit.nets
        or len(rebound.endpoints) != 2
        or {item.id for item in rebound.endpoints} != {"b-X2", "b-R5"}
        or {item.label for item in rebound.endpoints} != {"b"}
    ):
        raise ValueError("PAINT_COMPACT_B_SOURCE_TWO_NONPHYSICAL_ONLY_REQUIRED")
    return rebound


def generate_compact_attempt(out: Path, font_file: Path, *, node_cap: int = 25000):
    # Optional unmerged owner modules are staged only in isolated CI.
    # Resolve at use site to pass Ruff in both base and cross-owner checkouts.
    from dataclasses import replace

    # These modules are supplied by separately pinned owner branches in CI.
    # A late import is required because the base checkout has no v5 package.
    compact = import_module("examples.tl494_v5.compact_layout")
    preflight = import_module("examples.tl494_v5.route_preflight")
    driver = import_module("examples.tl494_v5.route_candidate_driver")
    bind_verified_compact_ti = import_module(
        "examples.tl494_v5.cycle11_ti_bridge"
    ).bind_verified_compact_ti
    propose_ic_paint_binding = import_module(
        "gost_schematic.electrical.ic_paint_bridge"
    ).propose_ic_paint_binding
    A3_LANDSCAPE_UM = compact.A3_LANDSCAPE_UM
    actual_component_occupied_mm = compact.actual_component_occupied_mm
    compact_source_assembly = compact.compact_source_assembly
    MeasuredInkGuard = preflight.MeasuredInkGuard
    _owner_ic_obstacle = preflight._owner_ic_obstacle
    load_original_owner_fixture = driver.load_original_owner_fixture
    restore_original_named_nets = driver.restore_original_named_nets

    assembly = compact_source_assembly()
    assembly.verify()
    frozen_source, _trusted_source = load_original_owner_fixture()
    # #115 explicitly and reversibly maps V5 INPUT_POS/OUTPUT_NEG/ENERGY_TRANSFER
    # to the actual photographed a_INPUT_PLUS/b_NEGATIVE_OUTPUT/TRANSFER.
    # Never issue a new full-sheet drawing with only the convenient aliases.
    original_named = restore_original_named_nets(assembly, frozen_source)
    signed = bind_verified_compact_ti(assembly, original_named)
    signed.verify()
    circuit = signed.signed.circuit
    if circuit.nets != original_named.nets or (
        circuit.components != tuple(
            replace(component, part_id=signed.signed_part_id)
            if component.reference == "DA1" else component
            for component in original_named.components
        )
    ):
        raise AssertionError("COMPACT_TRUSTED_PART_REBIND_CHANGED_PHYSICAL_SOURCE")
    assert (len(circuit.components), len(circuit.nets)) == (23, 15)
    assert sum(len(n.members) for n in circuit.nets) == 62
    inspected = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    style = inspected.style
    measurer = PillowTextMeasurer()
    physical_ic = propose_ic_paint_binding(
        assembly.owner_ic_record, style, measurer,
    )
    physical_ic.verify_endpoints()
    if len(physical_ic.views) != 1:
        raise ValueError("COMPACT_SINGLE_TL494_UNIT_REQUIRED")
    view = physical_ic.views[0]
    if len(view.pins) != 16:
        raise ValueError("COMPACT_16_TI_PHYSICAL_PINS_REQUIRED")
    # The signed circuit owns ALL sixteen real manufacturer PinRef targets.
    # Raw PAINT-provided editor targets are not independently authoritative.
    revised, snapshot = signed.seal_paint(physical_ic)
    snapshot.verify_against(revised, physical_ic)
    if revised.circuit is not circuit or (
        revised.part.identifier != signed.signed_part_id
    ):
        raise ValueError("COMPACT_TRUSTED_SIGNED_CIRCUIT_OR_PART_DRIFT")
    (clean,) = snapshot.render(
        revised, physical_ic, style, measurer, diagnostics=False,
    )
    (diagnostic,) = snapshot.render(
        revised, physical_ic, style, measurer, diagnostics=True,
    )
    canonical_parts = {**assembly.parts, revised.part.identifier: revised.part}
    da = next(c for c in circuit.components if c.reference == "DA1")
    by_part = {
        part_id: assembly.symbols[part.symbol_id]
        for part_id, part in assembly.parts.items()
        if part.symbol_id in assembly.symbols
    }
    ic_obstacle = _owner_ic_obstacle(view, clean.svg, da)
    by_part["reference.tl494cn"] = ic_obstacle
    by_part[revised.part.identifier] = replace(
        ic_obstacle, identifier=revised.part.symbol_id,
    )
    if any(c.part_id not in by_part for c in circuit.components):
        raise ValueError("COMPACT_CATALOG_SYMBOL_NOT_RESOLVED")
    footprint = actual_component_occupied_mm(assembly, by_part)
    source_b = _bind_verified_source_b(font_file, circuit, by_part)
    original_nets = circuit.nets
    placement = layout_sheet(circuit, by_part, style, measurer)
    # This true independent owner measured ink is a router keepout, NOT
    # editor-visible green pads and NOT a synthetic replacement IC symbol.
    ic_ink = tuple(
        MeasuredInkGuard(ink.owner, ink.box.expanded(500))
        for ink in clean.ink
        if ink.kind in (
            "refdes", "pin-label", "pin-number", "function",
            "main-text", "field-text",
        )
    )
    route = import_module(
        "gost_schematic.engines.multiterminal_router"
    ).route_circuit_net_trees(
        circuit, canonical_parts, by_part,
        page_box=Box(0, 0, *A3_LANDSCAPE_UM),
        annotation_placements=(*ic_ink, *placement.placements),
        stop_on_first_failure=False,
        search_node_cap=node_cap,
        max_order_restarts=1,
    )
    if circuit.nets != original_nets or (
        route.source_circuit != circuit
    ):
        raise AssertionError("COMPACT_ROUTER_CHANGED_SOURCE_NETS_OR_PARTS")
    native = render_routed_native_sheet(
        circuit, route.graph, canonical_parts, by_part,
        style, measurer,
        physical_ic_renderings_clean={"DA1": clean},
        physical_ic_renderings_diagnostic={"DA1": diagnostic},
        verified_ic_source=revised,
        verified_ic_paint_binding=physical_ic,
        verified_ic_snapshot=snapshot,
        route_preview=route,
        source_continuation_project=source_b,  # typed checked real b pair
        expected_component_count=23,
        expected_net_count=15,
        expected_net_pinrefs=62,
        physical_page_box=Box(0, 0, *A3_LANDSCAPE_UM),
    )
    # Do NOT call a partial route a print-accepted A3. #114's known failed
    # DA1.12 INPUT_POS and 6 other Net trees must remain visible blockers.
    if native.printable_candidate:
        raise ValueError(
            "COMPACT_ROUTE_REQUIRES_SEPARATE_MAIN3_QA_SIGNOFF_NOT_AUTO_RELEASE"
        )
    out.mkdir(parents=True, exist_ok=True)
    for mode, svg in (
        ("clean", native.clean_svg),
        ("diagnostic", native.diagnostic_svg),
    ):
        (out/f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{mode}.svg").write_text(
            svg, encoding="utf-8",
        )
    manifest = {
        **native.manifest,
        "model_source": SOURCE,
        "IC97_owner_sha": IC,
        "NET114_owner_sha": NET,
        "RECON115_owner_sha": RECON,
        "source_reference": assembly.manifest(),
        "original_named_nets_verified": [
            net.name for net in original_named.nets
        ],
        "canonical_ti_part_id_verified": signed.part.identifier,
        "legacy_part_id_preserved_only_in_frozen_fixture": True,
        "trusted_97_part_rebinding": True,
        "source_signed_16_pin_overlay": True,
        "source_signed_overlay_sha256": snapshot.circuit_sha256,
        "router_attempt": route.as_dict(),
        "A3_nominal_1_to_1_mm": [420, 297],
        "A3_true_catalog_bounds": footprint,
        "A3_native_circuit_placement": True,
        "original_net_memberships_unchanged": True,
        "manufacturer_DA1_physical_pin_count": 16,
        "real_GOST_Type_A_h_mm": 3.5,
        "source_photo_raster_comparison": "BLOCKED_NO_AUTHORITATIVE_RASTER",
        "real_print_release": False,
        "nonphysical_b_marker_status": "VERIFIED_SOURCE_B_REBOUND",
        "two_source_b_markers": {
            ep.id: {
                "net": next(n.net_name for n in source_b.nets
                            if n.id == ep.net_id),
                "x_um": ep.anchor.x,
                "y_um": ep.anchor.y,
                "printed_label": ep.label,
            }
            for ep in source_b.endpoints
        },
        "source_b_stubs_um": {
            stub.endpoint_id: {
                "source_pin_ref": (
                    f"{stub.pin.reference}.{stub.pin.number}"
                ),
                "start": [stub.start.x, stub.start.y],
                "end": [stub.end.x, stub.end.y],
                "source_stub_id": stub.id,
                "nonphysical": True,
            }
            for stub in source_b.stubs
        },
    }
    # Source-backed BOM and Netlist are valid even when NET114 routes only
    # some trees. Their source is the same signed, 23/15/62 immutable Circuit,
    # never conductors guessed from SVG ink or the negative 91-wire fixture.
    component_rows = [
        {
            "reference": comp.reference,
            "part_id": comp.part_id,
            "symbol_id": canonical_parts[comp.part_id].symbol_id,
            "nominal": (
                comp.nominal.to_record() if comp.nominal is not None else None
            ),
        }
        for comp in circuit.components
    ]
    net_rows = [
        {
            "name": net.name,
            "pinrefs": [
                {"reference": pin.reference, "number": pin.number}
                for pin in net.members
            ],
        }
        for net in circuit.nets
    ]
    all_refs = [
        (pin["reference"], pin["number"])
        for net in net_rows for pin in net["pinrefs"]
    ]
    if (
        len(component_rows) != 23
        or len({row["reference"] for row in component_rows}) != 23
        or len(net_rows) != 15
        or len({row["name"] for row in net_rows}) != 15
        or len(all_refs) != 62
        or len(set(all_refs)) != 62
    ):
        raise ValueError("PAINT_BOM_NETLIST_PHYSICAL_SOURCE_IDENTITY_DRIFT")
    exports = {
        "TL494_COMPACT_A3_SOURCE_BOM_DRAFT.json": {
            "schema": "paint.source-bom.v1",
            "source_sha": SOURCE,
            "signed_ic_owner_sha": IC,
            "print_approved": False,
            "components": component_rows,
        },
        "TL494_COMPACT_A3_SOURCE_NETLIST_DRAFT.json": {
            "schema": "paint.source-netlist.v1",
            "source_sha": SOURCE,
            "signed_ic_owner_sha": IC,
            "print_approved": False,
            "nets": net_rows,
        },
    }
    manifest["source_model_exports"] = {}
    for name, payload in exports.items():
        encoded = (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        (out/name).write_bytes(encoded)
        manifest["source_model_exports"][name] = {
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
        }
    (out/"TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "BLOCKED_QA_NOT_FULL_ROUTE",
        "source": SOURCE[:10], "parts": 23, "nets": 15,
        "net_pinrefs": 62, "physical_DA1": 16,
        "routed_complete": sum(t.complete for t in route.net_trees),
        "router_segments": len(route.graph.segments),
        "A3_true_1_to_1_graphic_fit": native.manifest[
            "physical_page_fits_1_to_1"
        ],
        "blockers": native.manifest["blockers"][:18],
    }, ensure_ascii=False))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--node-cap", type=int, default=25000)
    args = parser.parse_args()
    generate_compact_attempt(args.output, args.font_file,
                             node_cap=args.node_cap)


if __name__ == "__main__":
    main()
