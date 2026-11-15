"""Compact real 23/15 TL494 A3 candidate: #115 placement + #114 new route.

This is explicitly a rejected/blocked pre-print **new-route attempt** until
all 15 Nets and independent QA+ESKD print geometry pass. The only rendered
artwork comes from the PAINT engine and exact owner records. No SVG patch or
retrospective fake 91-wire reconstruction.
"""
import argparse
import json
from importlib import import_module
from pathlib import Path

from examples.tl494_v5.compact_layout import (
    A3_LANDSCAPE_UM,
    actual_component_occupied_mm,
    compact_source_assembly,
)
from examples.tl494_v5.route_preflight import (
    MeasuredInkGuard,
    _owner_ic_obstacle,
)

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import render_resolved_ic
from gost_schematic.rendering.routed_native_sheet import render_routed_native_sheet
from gost_schematic.standards.type_a_font import inspect_type_a_font

SOURCE = "e695c415fdced164b0e0c39c5249d030795a0aa6"
IC = "a640f2c5e78bd37506d438d5f533382ec75f4666"
NET = "8499d2311681b60f3c510ad65bd4ee5cbc61882a"
RECON = "8f8b3645beacdc3b7c4382ec97b12268624fdd76"


def generate_compact_attempt(out: Path, font_file: Path, *, node_cap: int = 25000):
    # Optional unmerged owner modules are staged only in isolated CI.
    # Resolve at use site to pass Ruff in both base and cross-owner checkouts.
    from dataclasses import replace

    from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
    from examples.tl494_v5.route_candidate_driver import (
        load_original_owner_fixture,
        restore_original_named_nets,
    )
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding

    assembly = compact_source_assembly()
    assembly.verify()
    frozen_source, _trusted_source = load_original_owner_fixture()
    # #115 explicitly and reversibly maps V5 INPUT_POS/OUTPUT_NEG/ENERGY_TRANSFER
    # to the actual photographed a_INPUT_PLUS/b_NEGATIVE_OUTPUT/TRANSFER.
    # Never issue a new full-sheet drawing with only the convenient aliases.
    original_named = restore_original_named_nets(assembly, frozen_source)
    signed = bind_verified_compact_ti(assembly, original_named)
    signed.verify()
    canonical_parts = {**assembly.parts, signed.part.identifier: signed.part}
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
    net_by_pin = {
        pin: net.name for net in circuit.nets for pin in net.members
    }
    targets = tuple(IcConnectionTarget(
        pin.pin_id, PinRef("DA1", pin.number), pin.anchor, True,
        net_id=net_by_pin.get(PinRef("DA1", pin.number)),
    ) for pin in view.pins)
    clean = render_resolved_ic(
        view, style, measurer, editor_targets=targets,
        editor_overlay=False, review_overlay=False,
    )
    diagnostic = render_resolved_ic(
        view, style, measurer, editor_targets=targets,
        editor_overlay=True, review_overlay=True,
        glyph_detail=True,
    )
    da = next(c for c in circuit.components if c.reference == "DA1")
    by_part = {
        part_id: assembly.symbols[part.symbol_id]
        for part_id, part in assembly.parts.items()
        if part.symbol_id in assembly.symbols
    }
    ic_obstacle = _owner_ic_obstacle(view, clean.svg, da)
    by_part["reference.tl494cn"] = ic_obstacle
    by_part[signed.part.identifier] = replace(
        ic_obstacle, identifier=signed.part.symbol_id,
    )
    if any(c.part_id not in by_part for c in circuit.components):
        raise ValueError("COMPACT_CATALOG_SYMBOL_NOT_RESOLVED")
    footprint = actual_component_occupied_mm(assembly, by_part)
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
        route_preview=route,
        source_continuation_project=None,  # no fabricated old b at new coords
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
        "router_attempt": route.as_dict(),
        "A3_nominal_1_to_1_mm": [420, 297],
        "A3_true_catalog_bounds": footprint,
        "A3_native_circuit_placement": True,
        "original_net_memberships_unchanged": True,
        "manufacturer_DA1_physical_pin_count": 16,
        "real_GOST_Type_A_h_mm": 3.5,
        "source_photo_raster_comparison": "BLOCKED_NO_AUTHORITATIVE_RASTER",
        "real_print_release": False,
        "nonphysical_b_marker_status": (
            "BLOCKED_OWNER_NO_COMPACT_RELOCATION_VALIDATED"
        ),
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
