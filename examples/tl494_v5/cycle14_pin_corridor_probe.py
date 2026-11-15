"""Cycle14 source-authentic PIN escape ink probe; NOT a second router.

For each of the original 62 manufacturer-signed physical PinRefs, inspect an
outward 2.5 mm or 5 mm Manhattan segment against real transformed UGO strokes.
No component placement, Net, route or b continuation is changed or approved.
Text and already-routed wire obstacles require the actual NET engine separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from examples.tl494_named_photo_sheet import compose_circuit
from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_b_continuation import rebind_true_source_b
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.route_candidate_driver import (
    OWNER_SHAS,
    SOURCE_SHA,
    _build_obstacles,
    load_original_owner_fixture,
    parse_candidate_moves,
    position_only_move,
    restore_original_named_nets,
)
from gost_schematic.core.geometry import Point
from gost_schematic.engines.multiterminal_router import (
    _source_ink_collision,
    _source_ink_obstacles,
)
from gost_schematic.engines.orthogonal_route_planner import _resolve_real_pin
from gost_schematic.validation.external_wire_checks import WireSegment

SHEET_UM = {"A3": (420000, 297000), "A2": (594000, 420000)}
MARGIN_UM = 10000
SAMPLE_ESCAPE_UM = (2500, 5000)


def measure_pin_corridors(
    font_file: Path,
    *,
    page_format: str = "A3",
    move_mm: tuple = (),
    steps_um: tuple[int, ...] = SAMPLE_ESCAPE_UM,
) -> dict:
    """Measured component-ink vetoes from every genuine source physical tip."""
    if page_format not in SHEET_UM:
        raise ValueError("C14_UNSUPPORTED_PAPER_FORMAT")
    if (
        not steps_um
        or any(type(step) is not int or step <= 0 or step % 2500
               for step in steps_um)
        or len(set(steps_um)) != len(steps_um)
    ):
        raise ValueError("C14_UNVERIFIED_PIN_ESCAPE_STEP")
    frozen, _owner = load_original_owner_fixture()
    assembly = position_only_move(compact_source_assembly(), move_mm)
    original = restore_original_named_nets(assembly, frozen)
    pins = {
        (pin.reference, pin.number): net.name
        for net in original.nets for pin in net.members
    }
    if (
        len(original.components) != 23
        or len(original.nets) != 15
        or len(pins) != 62
        or len({num for ref, num in pins if ref == "DA1"}) != 16
    ):
        raise ValueError("C14_SOURCE_23_15_62_16_CHANGED")
    manufacturer = bind_verified_compact_ti(assembly, original)
    symbols, guards, layout, occupied, _style = _build_obstacles(
        assembly, original, font_file, verified_ti=manufacturer,
    )
    original_b = compose_circuit(font_file)[-1]
    true_b = rebind_true_source_b(
        original_b, manufacturer.signed.circuit, symbols,
    )
    if (
        len(true_b.stubs) != 2
        or {s.endpoint_id for s in true_b.stubs} != {"b-X2", "b-R5"}
        or true_b.nets[0].net_name != "b_NEGATIVE_OUTPUT"
    ):
        raise ValueError("C14_SOURCE_NONPHYSICAL_B_DRIFT")
    source_ink = _source_ink_obstacles(original, symbols, stroke_um=300)
    page_w, page_h = SHEET_UM[page_format]
    bbox = occupied["bbox_um"]
    on_sheet = (
        MARGIN_UM <= bbox[0] <= bbox[2] <= page_w - MARGIN_UM
        and MARGIN_UM <= bbox[1] <= bbox[3] <= page_h - MARGIN_UM
    )
    # The real stroke bbox does NOT imply Type A measured labels fit.
    # C1 was measured at y=9100um even while all 23 UGO fit A3/A2.
    measured_text_overflow = []
    for item in guards:
        rect = item.collision_bounds
        if (
            rect.min_x < MARGIN_UM
            or rect.max_x > page_w - MARGIN_UM
            or rect.min_y < MARGIN_UM
            or rect.max_y > page_h - MARGIN_UM
        ):
            measured_text_overflow.append({
                "owner": getattr(item, "owner", None),
                "label": getattr(item, "text", None),
                "bounds_um": [
                    rect.min_x, rect.min_y, rect.max_x, rect.max_y,
                ],
                "kind": type(item).__name__,
            })
    physical = {}
    for net in original.nets:
        for pin in net.members:
            tip, normal, _instance = _resolve_real_pin(
                original, pin, assembly.parts, symbols,
            )
            sampled = {}
            for step in steps_um:
                target = Point(
                    tip.x + normal.x * step, tip.y + normal.y * step,
                )
                segment = WireSegment(tip, target, net.name)
                strike = _source_ink_collision(
                    segment, source_ink, authorized_pins=frozenset({pin}),
                )
                sampled[str(step)] = {
                    "end_um": [target.x, target.y],
                    "native_symbol_ink_clear": strike is None,
                    "first_blocked_UGO": (
                        None if strike is None else {
                            "component": strike.owner,
                            "primitive_index": strike.primitive_index,
                            "primitive_kind": strike.primitive_kind,
                            "collision_box_um": [
                                strike.collision_bounds.min_x,
                                strike.collision_bounds.min_y,
                                strike.collision_bounds.max_x,
                                strike.collision_bounds.max_y,
                            ],
                        }
                    ),
                    "inside_page_margin": (
                        MARGIN_UM <= target.x <= page_w - MARGIN_UM
                        and MARGIN_UM <= target.y <= page_h - MARGIN_UM
                    ),
                }
            physical[f"{pin.reference}.{pin.number}"] = {
                "net": net.name,
                "source_physical_anchor_um": [tip.x, tip.y],
                "outward_direction": [normal.x, normal.y],
                "escape_samples_um": sampled,
            }
    return {
        "schema": "C14_SOURCE_SIGNED_UGO_PIN_CORRIDOR_PROBE_V1",
        "source_sha": SOURCE_SHA,
        "owner_exact_shas": OWNER_SHAS,
        "original_nets": {
            net.name: [
                f"{p.reference}.{p.number}" for p in net.members
            ] for net in original.nets
        },
        "components": 23,
        "original_net_count": 15,
        "manufacturer_signed_DA1_pins": 16,
        "physical_pinref_memberships": 62,
        "source_UGO_bbox_um": bbox,
        "page_format": page_format,
        "page_size_um": [page_w, page_h],
        "absolute_10mm_component_ink_fit": on_sheet,
        "real_measured_text_guard_count": len(guards),
        "real_measured_text_layout_valid": layout.valid,
        "measured_text_10mm_frame_fit": not measured_text_overflow,
        "measured_text_frame_violations": measured_text_overflow,
        "source_position_only_moves_mm": [
            [ref, str(dx), str(dy)] for ref, dx, dy in move_mm
        ],
        "source_font_sha256": hashlib.sha256(font_file.read_bytes()).hexdigest(),
        "true_nonphysical_b_labels_count": len(true_b.endpoints),
        "true_b_source_stubs": {
            stub.endpoint_id: {
                "physical_PinRef": (
                    f"{stub.pin.reference}.{stub.pin.number}"
                ),
                "start_um": [stub.start.x, stub.start.y],
                "end_um": [stub.end.x, stub.end.y],
                "electrical": False,
            } for stub in true_b.stubs
        },
        "pin_escapes": physical,
        "measures": "TRUE_NATIVE_UGO_STROKE_COLLISION_ONLY",
        "excluded_from_this_probe": [
            "measured text guards", "existing routed Net wires",
            "junction clearance", "global post-route DRC",
            "final clean SVG", "PNG300",
        ],
        "full_15_net_print_release": "BLOCKED_NOT_A_ROUTER",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-format", choices=tuple(SHEET_UM), default="A3")
    parser.add_argument(
        "--move", action="append", default=[], metavar="REF:DX_MM:DY_MM",
        help="Source-preserving 2.5mm signed component-only move",
    )
    args = parser.parse_args()
    result = measure_pin_corridors(
        args.font_file, page_format=args.page_format,
        move_mm=parse_candidate_moves(tuple(args.move)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "source": result["source_sha"], "format": result["page_format"],
        "original_nets": result["original_net_count"],
        "pins": result["physical_pinref_memberships"],
        "paper": result["absolute_10mm_component_ink_fit"],
        "measured_text_10mm_frame_fit": result["measured_text_10mm_frame_fit"],
        "blocked_escape_count_2500": sum(
            not p["escape_samples_um"]["2500"]["native_symbol_ink_clear"]
            for p in result["pin_escapes"].values()
        ),
        "release": result["full_15_net_print_release"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
