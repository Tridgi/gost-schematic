"""Run a REAL source-pinned TL494 23-part / 15-Net routing review (Issue #108).

The reference owner scripts must be provided by a separately checked-out
immutable original SHA e695c415... in CI. This program never fabricates
source symbols or converts the photo into guessed PinRef coordinates.
It will always emit a review-only SVG even when the global route is BLOCKED,
but will NEVER label that partial image PRINT PASS.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.multiterminal_router import route_circuit_net_trees
from gost_schematic.engines.sheet_layout import layout_sheet
from gost_schematic.rendering.external_wire_sheet import (
    build_external_wire_obstacles,
    render_external_wire_sheet,
)
from gost_schematic.validation.route_drc import audit_route_drc

_ROOT = Path(__file__).resolve().parents[1]
_FROZEN = _ROOT / "tests" / "fixtures" / "tl494-routing-source-e695c415.json"
_KNOWN_BAD = _ROOT / "tests" / "fixtures" / "tl494_cycle9_known_bad_nine_drc.json"
_SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"


def _verify_source(circuit, graph, source) -> None:
    if len(circuit.components) != 23 or len(circuit.nets) != 15:
        raise ValueError("ROUTER_TL494_PART_NET_INVENTORY_CHANGED")
    originals = _FROZEN.read_text(encoding="utf-8")
    original = json.loads(originals)
    expected = {
        name: tuple(members)
        for name, members in original["net_members"].items()
    }
    actual = {
        net.name: tuple(p.reference + "." + p.number for p in net.members)
        for net in circuit.nets
    }
    if expected != actual:
        raise ValueError("ROUTER_TL494_PHYSICAL_PINREF_SOURCE_NET_DIFF")
    if len(graph.segments) != 91 or len(graph.junctions) != 37:
        raise ValueError("ROUTER_TL494_SOURCE_WIRE_JUNCTION_DRIFT")
    for index, (wire, entry) in enumerate(
        zip(graph.segments, original["wires"], strict=True)
    ):
        if (
            wire.net_name != entry["net"]
            or (wire.start.x, wire.start.y) != tuple(entry["start_um"])
            or (wire.end.x, wire.end.y) != tuple(entry["end_um"])
        ):
            raise ValueError(
                "ROUTER_TL494_SOURCE_WIRE_DRIFT_AT_INDEX_" + str(index)
            )
    if len({
        p.number for net in circuit.nets for p in net.members
        if p.reference == "DA1"
    }) != 16:
        raise ValueError("ROUTER_TL494_PINLOSS_DA1")


def _fail_codes(report) -> dict[str, int]:
    counts = {}
    for finding in report.findings:
        if finding.severity != "error":
            continue
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return dict(sorted(counts.items()))


def generate(
    output: Path,
    font_file: Path,
    *,
    source_revision: str,
    page: str = "A1",
    node_limit: int = 25000,
) -> dict:
    if source_revision != _SOURCE_SHA:
        raise ValueError("ROUTER_NOT_THE_EXACT_PINNED_SOURCE_COMMIT")
    # The reference copies are never checked into the routing PR.
    from examples.tl494_named_photo_sheet import compose_circuit

    original = compose_circuit(font_file)
    circuit, graph, parts, symbols = original[:4]
    _verify_source(circuit, graph, source_revision)
    # Real material symbol catalogue + physical vendor source native
    # reference geometry, not guessed boxes in a synthetic trial.
    by_part = {id_: symbols[part.symbol_id] for id_, part in parts.items()}
    style = original[7]
    measurer = PillowTextMeasurer()

    # Use measured annotations anchored to existing parts. Original text
    # placement is source-aware of 91 original wires; AFTER must recompute
    # labels in the new wire scene and revalidate native collision boxes.
    source_layout = layout_sheet(
        circuit, by_part, style, measurer,
        wires=build_external_wire_obstacles(graph),
    )
    before = audit_route_drc(
        circuit, graph, symbols_by_part=by_part,
        annotation_placements=source_layout.placements,
    )
    baseline = json.loads(_KNOWN_BAD.read_text("utf-8"))
    if (before.error_count if hasattr(before, "error_count") else
            sum(f.severity == "error" for f in before.findings)) != 9:
        raise ValueError("ROUTER_NEGATIVE_SOURCE_9_ERROR_REGRESSION_CHANGED")
    if sum(f.severity == "warning" for f in before.findings) != 32:
        raise ValueError("ROUTER_NEGATIVE_SOURCE_32_WARNINGS_CHANGED")
    if (
        set(_fail_codes(before))
        != {f["code"] for f in baseline["geometric"]["hard_failures"]}
    ):
        raise ValueError("ROUTER_NEGATIVE_SOURCE_ERROR_CLASS_DRIFT")

    # Original source viewBox width 679.3mm; A1 is a real 841x594mm
    # landscape-capacity preview, with 10mm margins and origin shift.
    # This is NOT claiming a fitted A3 or approved sheet border.
    page_boxes = {
        "A1": Box(-205000, 0, 636000, 594000),
        "A0": Box(-205000, 0, 984000, 841000),
    }
    if page not in page_boxes:
        raise ValueError("ROUTER_UNSUPPORTED_SOURCE_SHEET")
    empty_annotations = layout_sheet(
        circuit, by_part, style, measurer, wires=(),
    )
    planned = route_circuit_net_trees(
        circuit, parts, by_part, page_box=page_boxes[page],
        annotation_placements=empty_annotations.placements,
        search_node_cap=node_limit, max_detour_ratio=3.0,
    )
    # Post-route independent full DRC is always applied, even if routing
    # stopped early. Re-layout with actual AFTER wires before coverage.
    after_layout = layout_sheet(
        circuit, by_part, style, measurer,
        wires=build_external_wire_obstacles(planned.graph),
    )
    after = audit_route_drc(
        circuit, planned.graph, symbols_by_part=by_part,
        annotation_placements=after_layout.placements,
    )
    complete = planned.complete
    after_errors = sum(f.severity == "error" for f in after.findings)
    net_map = {
        net.name: sorted(p.reference + "." + p.number for p in net.members)
        for net in circuit.nets
    }
    original_names = json.loads(_FROZEN.read_text("utf-8"))["net_members"]
    source_net_map = {key: sorted(value) for key, value in original_names.items()}
    exact_net_diff = {
        "added_nets": sorted(set(net_map) - set(source_net_map)),
        "removed_nets": sorted(set(source_net_map) - set(net_map)),
        "changed_pinref_members": {
            name: {"original": source_net_map[name], "candidate": net_map[name]}
            for name in set(net_map) & set(source_net_map)
            if net_map[name] != source_net_map[name]
        },
    }
    if any(exact_net_diff.values()):
        raise ValueError("ROUTER_SOURCE_PHYSICAL_PIN_NET_DIFF")
    # A1 width check is only a capacity check, not a placement guarantee.
    # Avoid PRINT PASS even if the graph happens to have no wire errors:
    # PAINT real IC word orientation and UGO status remain separate.
    print_pass = (
        complete and after_errors == 0
        and after.checked_symbol_geometry and after.checked_measured_text
        and after_layout.valid and not planned.diagnostics
        and planned.print_pass
    )
    output.mkdir(parents=True, exist_ok=True)
    before_svg = render_external_wire_sheet(
        circuit, graph, by_part, style, measurer,
        diagnostic=False, strict_layout=False,
    ).svg
    # This is an honest native engine render of the attempted NEW route,
    # not a manually altered original 91-segment SVG.
    result_svg = render_external_wire_sheet(
        circuit, planned.graph, by_part, style, measurer,
        diagnostic=True, strict_layout=False,
    ).svg
    uri = "{http://www.w3.org/2000/svg}"
    after_root = ET.fromstring(result_svg)
    if after_root.tag != uri + "svg":
        raise ValueError("ROUTER_AFTER_NOT_NATIVE_SVG")
    after_root.set("data-release", "BLOCKED" if not print_pass else "PRINT_DRC_PASS")
    after_root.set("data-source-sha", source_revision)
    after_root.set("data-route-preview", "true")
    after_root.set("data-source-net-diff", "ZERO")
    after_svg = ET.tostring(after_root, encoding="unicode") + "\n"
    for view, svg in (
        ("TL494-original-known-bad.svg", before_svg),
        ("TL494-after-router-attempt.svg", after_svg),
    ):
        root = ET.fromstring(svg)
        count = len(root.findall(f".//{uri}line[@data-layer='wires']"))
        if (view.startswith("TL494-original") and count != 91) or (
            view.startswith("TL494-after") and count != len(planned.graph.segments)
        ):
            raise ValueError("ROUTER_RENDER_LOST_PHYSICAL_WIRE_SEGMENT")
        (output / view).write_text(svg, encoding="utf-8")
    route_metrics = planned.as_dict()
    report = {
        "source_commit": source_revision,
        "model_parts": len(circuit.components),
        "model_nets": len(circuit.nets),
        "model_DA1_physical_pin_count": 16,
        "current_page": page,
        "source_net_diff": exact_net_diff,
        "source_net_members": source_net_map,
        "attempt_net_members": net_map,
        "source_before": before.as_dict(),
        "source_before_known_bad_errors": baseline["geometric"]["errors"],
        "source_before_known_bad_bends": baseline["geometric"]["bends"],
        "after_attempt": after.as_dict(),
        "attempt_routing": route_metrics,
        "source_layout_ok": source_layout.valid,
        "attempt_layout_ok": after_layout.valid,
        "measured_text_box_count": len(after_layout.placements),
        "routed_segments": len(planned.graph.segments),
        "attempt_accepted_print_drc_only": print_pass,
        "user_photo_pixel_comparison": "BLOCKED_SOURCE_RASTER_BYTES_NOT_IN_REPO",
        "normative_UGO_status": "DRAFT_NOT_APPROVED",
        "release": "BLOCKED" if not print_pass else "DRC_PASS_NOT_UGO_APPROVED",
        "notes": (
            "Original before source has genuine 9 geometry ERR/32 WARN, "
            "original 91 segments; AFTER is generated from same 23 real parts "
            "and 15 unchanged Circuit.Net physical PinRefs, not print-certified "
            "while partial or DRC-bad. Font measured with original actual face. "
            "No manual SVG wire edits and no b continuation to fabricated Net."
        ),
    }
    (output / "TL494-before-and-after-drc.json").write_text(
        json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["release"],
        "source_wires": 91,
        "source_DRC_errors": 9,
        "new_wire_segments": len(planned.graph.segments),
        "new_DRC_errors": after_errors,
        "new_crossings": after.crossing_different_net,
        "new_length_mm": round(after.total_wire_length_um / 1000, 3),
        "completed_nets": sum(t.complete for t in planned.net_trees),
        "target_nets": len(circuit.nets),
        "blocked": not print_pass,
        "reason": planned.diagnostics[:4],
    }, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--source-sha", type=str, required=True)
    parser.add_argument("--page", choices=("A1", "A0"), default="A1")
    parser.add_argument("--max-nodes", type=int, default=25000)
    args = parser.parse_args()
    generate(args.output_dir, args.font_file, source_revision=args.source_sha,
             page=args.page, node_limit=args.max_nodes)


if __name__ == "__main__":
    main()
