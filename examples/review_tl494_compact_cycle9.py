"""Independent compact-A3 23/15/16 source-real router proof for MAIN 3.

Pins come from immutable Circuit + TI physical bridge; UGO from native
catalogue and DA1 ink from genuine PAINT SVG. The new graph is produced by
the owner router, not by editing a legacy 91-wire SVG. Any partial image
is diagnostic-only and must remain blocked from certified ESKD print.
"""
import argparse
import hashlib
import json
from importlib import import_module
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_v5.compact_layout import (
    A3_LANDSCAPE_UM,
    actual_component_occupied_mm,
    compact_source_assembly,
)
from examples.tl494_v5.route_preflight import _owner_ic_obstacle
from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.multiterminal_router import (
    _source_ink_collision,
    _source_ink_obstacles,
    route_circuit_net_trees,
)
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.rendering.external_wire_sheet import (
    build_external_wire_obstacles,
    render_external_wire_sheet,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.external_wire_checks import (
    WireSegment,
    validate_external_wires,
)
from gost_schematic.validation.route_drc import audit_route_drc

_SVG = "{http://www.w3.org/2000/svg}"
_SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"


def produce(
    output: Path, font_file: Path, *,
    owner_sha: str, reference_sha: str, node_cap: int = 25000,
) -> dict:
    if len(owner_sha) != 40 or len(reference_sha) != 40:
        raise ValueError("COMPACT_UNPINNED_OWNER_SHA")
    model = compact_source_assembly()
    model.verify()
    source = model.manifest()
    if source["source_sha"] != _SOURCE_SHA:
        raise ValueError("COMPACT_ORIGINAL_TL494_SOURCE_DRIFT")
    circuit = model.circuit
    if (len(circuit.components), len(circuit.nets)) != (23, 15):
        raise ValueError("COMPACT_SOURCE_23_15_DRIFT")
    net_members = {
        n.name: tuple(f"{p.reference}.{p.number}" for p in n.members)
        for n in circuit.nets
    }
    if sum(len(n.members) for n in circuit.nets) != 62:
        raise ValueError("COMPACT_SOURCE_62_PHYSICAL_PINREF_DRIFT")
    report_font = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    style = report_font.style
    measurer = PillowTextMeasurer()
    bridge = import_module(
        "gost_schematic.electrical.ic_paint_bridge"
    ).propose_ic_paint_binding(model.owner_ic_record, style, measurer)
    bridge.verify_endpoints()
    if len(bridge.views) != 1 or len(bridge.views[0].pins) != 16:
        raise ValueError("COMPACT_REAL_DA1_16_PIN_BRIDGE_REQUIRED")
    real_ic = import_module(
        "gost_schematic.rendering.ic_rectangular"
    ).render_resolved_ic(
        bridge.views[0], style, measurer, glyph_detail=True,
    )
    da1 = next(component for component in circuit.components
               if component.reference == "DA1")
    symbols = dict(model.symbols)
    symbols["reference.tl494cn"] = _owner_ic_obstacle(
        bridge.views[0], real_ic.svg, da1,
    )
    actual_tip = da1.pin_positions(symbols[da1.part_id])["12"]
    if actual_tip != Point(205000, 138750):
        raise ValueError(
            f"COMPACT_DA1_12_SOURCE_ANCHOR_DRIFT:{actual_tip}"
        )
    lead_ink = tuple(
        ink for ink in _source_ink_obstacles(
            circuit, symbols, stroke_um=300,
        ) if ink.owner == "DA1"
    )
    if len({ink.permitted_pin for ink in lead_ink
            if ink.permitted_pin is not None}) != 16:
        raise ValueError("COMPACT_PAINT_16_PHYSICAL_LEADS_NOT_TRACKED")
    repro_wire = WireSegment(
        Point(203460, 138750), Point(203460, 43201),
        "INPUT_POS",
    )
    repro_block = _source_ink_collision(
        repro_wire, lead_ink,
        authorized_pins=frozenset({
            p for net in circuit.nets if net.name == "INPUT_POS"
            for p in net.members
        }),
    )
    if repro_block is None or repro_block.owner != "DA1":
        raise ValueError("COMPACT_HISTORICAL_W2_LEAD_FOREST_VETO_MISSING")
    protected = tuple(
        _MeasuredInkGuard(ink.owner, ink.box.expanded(500))
        for ink in real_ic.ink
        if ink.kind in {
            "refdes", "pin-label", "pin-number",
            "function", "main-text", "field-text",
        }
    )
    source_labels = layout_sheet(
        circuit, symbols, style, measurer,
    )
    annotations = (*protected, *source_labels.placements)
    if len(annotations) < 39:
        raise ValueError("COMPACT_MEASURED_TEXT_PROTECTION_MISSING")
    occupancy = actual_component_occupied_mm(model, symbols)
    page = Box(0, 0, *A3_LANDSCAPE_UM)
    route = route_circuit_net_trees(
        circuit, model.parts, symbols, page_box=page,
        annotation_placements=annotations, search_node_cap=node_cap,
        stop_on_first_failure=False, max_order_restarts=2,
    )
    model.verify()
    if {
        n.name: tuple(f"{p.reference}.{p.number}" for p in n.members)
        for n in circuit.nets
    } != net_members:
        raise ValueError("COMPACT_ROUTER_MODIFIED_SOURCE_NETS")
    after_labels = layout_sheet(
        circuit, symbols, style, measurer,
        wires=build_external_wire_obstacles(route.graph),
    )
    after_drc = audit_route_drc(
        circuit, route.graph, symbols_by_part=symbols,
        annotation_placements=(*protected, *after_labels.placements),
    )
    electrical = validate_external_wires(
        circuit, route.graph, model.parts, symbols,
    ) if route.complete else ()
    erc_errors = [
        d.code for d in electrical if d.severity.value == "error"
    ]
    errors = [
        finding.as_dict() for finding in after_drc.findings
        if finding.severity == "error"
    ]
    geometric_pass = bool(
        route.complete and route.drc is not None
        and route.drc.valid and after_drc.valid
        and source_labels.valid and after_labels.valid
        and occupancy["A3_capacity_fit"]
        and not erc_errors
    )
    output.mkdir(parents=True, exist_ok=True)
    # Genuine renderer uses exactly the newly generated Graph; it is NOT
    # the legacy 91-segment photo rendering. No diagnostic overlay in print.
    for mode in ("clean", "diagnostic"):
        native = render_external_wire_sheet(
            circuit, route.graph, symbols, style, measurer,
            diagnostic=(mode == "diagnostic"), strict_layout=False,
        )
        root = ET.fromstring(native.svg)
        rendered = root.findall(
            f".//{_SVG}line[@data-layer='wires']"
        )
        if len(rendered) != len(route.graph.segments):
            raise ValueError("COMPACT_SVG_DROPPED_ROUTED_WIRES")
        root.set(
            "data-release",
            "DRC_PASS_QA_NOT_APPROVED" if geometric_pass else "BLOCKED_PARTIAL",
        )
        root.set("data-owner-router-sha", owner_sha)
        root.set("data-reference-layout-sha", reference_sha)
        root.set("data-physical-net-diff", "ZERO")
        target = output / f"TL494-compact-A3-{mode}.svg"
        target.write_text(
            ET.tostring(root, encoding="unicode") + "\n",
            encoding="utf-8",
        )
        ET.fromstring(target.read_text(encoding="utf-8"))
    record = {
        "status": "DRC_PASS_INDEPENDENT_QA_REQUIRED" if geometric_pass else
                  "BLOCKED_PARTIAL_NOT_PRINTABLE",
        "source_sha": _SOURCE_SHA,
        "owner_router_sha": owner_sha,
        "reference_recon_sha": reference_sha,
        "font_sha256": style.font_sha256,
        "source_components": 23,
        "source_nets": 15,
        "physical_DA1_pin_count": 16,
        "all_Circuit_PinRef_memberships": 62,
        "source_net_diff": {
            "added": [], "removed": [], "physical_members_changed": [],
        },
        "net_members": net_members,
        "paper": "A3_LANDSCAPE_420x297mm_DRAFT",
        "occupied_mm": occupancy,
        "real_PAINT_leads": 16,
        "verified_legacy_illegal_W2": {
            "first": [203460, 138750],
            "second": [203460, 43201],
            "owner": repro_block.owner,
            "primitive": repro_block.primitive_index,
            "source_pin": (
                f"{repro_block.permitted_pin.reference}."
                f"{repro_block.permitted_pin.number}"
                if repro_block.permitted_pin else None
            ),
            "preflight": "REJECTED_INK_INTERSECTION",
            "actual_target_DA1_12_um": [actual_tip.x, actual_tip.y],
        },
        "measured_annotation_guards": len(annotations),
        "source_label_layout_valid": source_labels.valid,
        "after_label_layout_valid": after_labels.valid,
        "routing": route.as_dict(),
        "new_after_drc": after_drc.as_dict(),
        "after_erc_errors": erc_errors if route.complete else [
            "INCOMPLETE_GRAPH_NOT_SUBMITTED_AS_ERC_PASS"
        ],
        "actual_new_drc_errors": errors,
        "routed_nets": sum(t.complete for t in route.net_trees),
        "routed_segments": len(route.graph.segments),
        "routed_length_um": after_drc.total_wire_length_um,
        "geom_drc_pass": geometric_pass,
        "independent_QA_approved": False,
        "certified_UGO": False,
        "print_pass": False,
        "known_bad_original_source": {
            "wire_segments": 91, "drc_errors": 9, "drc_warnings": 32,
            "source_shares_same_electrical_net_members": True,
        },
        "reason": route.diagnostics,
        "image_scope": (
            "Native Circuit+new ExternalWireGraph partial proof only; "
            "complete PAINT compositor and QA are separate owners"
        ),
    }
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True,
                         indent=2) + "\n"
    (output / "TL494-compact-A3-route-drc.json").write_text(
        payload, encoding="utf-8",
    )
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob("*.svg"))
    }
    (output / "SHA256.json").write_text(
        json.dumps(hashes, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source": _SOURCE_SHA, "router": owner_sha,
        "routed_nets": record["routed_nets"],
        "required_nets": 15, "wires": record["routed_segments"],
        "new_drc_errors": len(errors),
        "length_mm": round(record["routed_length_um"] / 1000, 3),
        "guards": len(annotations),
        "status": record["status"],
        "blocked_nets": [
            {"name": t.net_name, "diagnostics": t.diagnostics}
            for t in route.net_trees if not t.complete
        ],
    }, ensure_ascii=False))
    return record


class _MeasuredInkGuard:
    """Minimal source-renderer measured glyph guard adapter."""

    def __init__(self, owner: str, collision_bounds: Box):
        self.owner = owner
        self.collision_bounds = collision_bounds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--owner-sha", type=str, required=True)
    parser.add_argument("--reference-sha", type=str, required=True)
    parser.add_argument("--max-nodes", type=int, default=25000)
    args = parser.parse_args()
    produce(
        args.output, args.font_file, owner_sha=args.owner_sha,
        reference_sha=args.reference_sha, node_cap=args.max_nodes,
    )


if __name__ == "__main__":
    main()
