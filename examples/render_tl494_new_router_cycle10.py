"""Render genuine new NET #114 route attempt on 23/15/16 frozen-source Circuit.

The old 91-wire source is used ONLY as input identity/negative baseline.
New SVG is created entirely through the native typed PAINT engine, consuming
the actual GlobalRoutePreview.graph. No saved SVG patching or manufactured
electrical connections. Incomplete routing is BLOCKED even if a PNG exists.
"""
import argparse
import json
from importlib import import_module
from pathlib import Path

from examples.render_tl494_full_native_cycle9 import (
    _compose_frozen_circuit_with_real_type_a,
    _net_pin_id_map,
    _real_dependencies,
    construct_native_paint,
)
from gost_schematic.core.geometry import Box
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import (
    IcFunctionReading,
    render_resolved_ic,
)
from gost_schematic.rendering.routed_native_sheet import (
    render_routed_native_sheet,
)

SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
IC97_SHA = "b28428d94218cac777a28897ce9176285d0fab0b"
NET114_SHA = "b3a8263944c5a687492a49555d8149e538f0902b"


def render_new_owner_route(
    out: Path, font_file: Path, *,
    search_node_cap: int = 25000,
) -> dict:
    if type(search_node_cap) is not int or search_node_cap <= 0:
        raise ValueError("PAINT_ROUTE_NODE_CAP_INVALID")
    (
        circuit, old_graph, symbols, portrait, _old_unit,
        style, measurer, policy, b_pair, _ic_record, _catalog,
    ) = construct_native_paint(font_file)
    deps = _real_dependencies()
    from_source = _compose_frozen_circuit_with_real_type_a(
        deps["compose"], font_file,
    )
    parts = dict(from_source[2])
    device = deps["device"][0]()
    deps["device"][1](device)
    parts[device.identifier] = device.to_legacy_part(device.identifier)
    # Resolve real source 23/15/16/62 from the SAME typed IC+catalog contract
    # as PAINT. This does not borrow any old exported SVG from the fixture.
    if (
        len(circuit.components) != 23
        or len(circuit.nets) != 15
        or sum(len(net.members) for net in circuit.nets) != 62
        or len(old_graph.segments) != 91
        or len(portrait.pins) != 16
    ):
        raise ValueError("PAINT_NEW_ROUTE_FROZEN_23_15_16_62_91_DRIFT")
    snap = tuple(circuit.nets)
    # True external route code exactly from isolated NET #114 frozen SHA.
    # This PREVIEW may be incomplete; partial graphs are never a pass.
    routed = import_module(
        "gost_schematic.engines.multiterminal_router"
    ).route_circuit_net_trees(
        circuit, parts, symbols,
        page_box=Box(-205000, 0, 636000, 594000),
        search_node_cap=search_node_cap,
        stop_on_first_failure=False,
        max_order_restarts=1,
    )
    if circuit.nets != snap or routed.graph == old_graph or (
        routed.source_circuit != circuit
    ):
        raise AssertionError("PAINT_ROUTE_NOT_NEW_OR_CHANGED_PHYSICAL_SOURCE")
    resolved = portrait.select_function_text_reading(
        IcFunctionReading.BOTTOM_TO_TOP,
    )
    net_ids = _net_pin_id_map(circuit)
    targets = tuple(IcConnectionTarget(
        pin.pin_id, PinRef("DA1", pin.number), pin.anchor,
        True, net_id=net_ids.get(PinRef("DA1", pin.number)),
    ) for pin in resolved.pins)
    clean = render_resolved_ic(
        resolved, style, measurer, policy=policy, editor_targets=targets,
        editor_overlay=False, review_overlay=False,
    )
    diagnostic = render_resolved_ic(
        resolved, style, measurer, policy=policy, editor_targets=targets,
        editor_overlay=True, review_overlay=True, glyph_detail=True,
    )
    result = render_routed_native_sheet(
        circuit, routed.graph, parts, symbols, style, measurer,
        physical_ic_renderings_clean={"DA1": clean},
        physical_ic_renderings_diagnostic={"DA1": diagnostic},
        route_preview=routed, source_continuation_project=b_pair,
        expected_component_count=23, expected_net_count=15,
        expected_net_pinrefs=62,
    )
    if result.printable_candidate and not routed.print_pass:
        raise AssertionError("PAINT_MUST_NOT_RELEASE_PARTIAL_NET_ROUTE")
    if len(routed.graph.segments) != result.manifest["route_segments"]:
        raise AssertionError("PAINT_ROUTER_TO_VECTOR_SEGMENT_LOSS")
    assert circuit.nets == snap
    manifest = {
        **result.manifest,
        "source_original_sha": SOURCE_SHA,
        "elektrik_current_ic_sha": IC97_SHA,
        "net_114_sha": NET114_SHA,
        "original_negative_wires": 91,
        "original_23_15_16_62": [23, 15, 16, 62],
        "real_router_new_graph": True,
        "real_routed_trees": routed.as_dict(),
        "source_net_memberships_changed": False,
        "new_graph_not_source_91_frozen": True,
        "green_pin_tips_debug_only": True,
        "format": "NATIVE_FULL_SOURCE_PLACEMENT_NOT_COMPACT_A3",
        "A3_print_ready": False,
        "compact_source_layout_dependency": "RECON #115",
        "blocked_release": not result.printable_candidate,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out/"TL494_NEW_NET114_candidate_BLOCKED_clean.svg").write_text(
        result.clean_svg, encoding="utf-8",
    )
    (out/"TL494_NEW_NET114_candidate_BLOCKED_diagnostic.svg").write_text(
        result.diagnostic_svg, encoding="utf-8",
    )
    (out/"TL494_NEW_NET114_vs_source_print_evidence.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "SOURCE_SHA": SOURCE_SHA,
        "NET114_SHA": NET114_SHA,
        "parts": 23, "nets": 15, "physical": 16,
        "source_wires_known_bad": 91,
        "attempt_new_wires": len(routed.graph.segments),
        "complete_nets": sum(t.complete for t in routed.net_trees),
        "print_pass": result.printable_candidate,
        "blockers": manifest["blockers"][:15],
        "whole_new_route_svg_generated": True,
    }))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--node-cap", type=int, default=25000)
    args = parser.parse_args()
    render_new_owner_route(args.output, args.font_file,
                           search_node_cap=args.node_cap)


if __name__ == "__main__":
    main()
