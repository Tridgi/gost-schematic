"""Read-only 15-Net router preflight using ACTUAL PAINT vector geometry.

This file never writes or post-processes an E3 SVG. The only DA1 footprint
used for DRC is programmatically derived from PAINT's genuine SVG outline
and 16 actual rendered lead strokes; it is explicitly a routing-only
obstacle, NOT a substitute for the approved DA1 UGO.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_v5.compact_layout import (
    A3_LANDSCAPE_UM,
    actual_component_occupied_mm,
    compact_source_assembly,
)
from gost_schematic.core.geometry import Box, Line, Point, Rectangle
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"
ROUTER_OWNER_SHA = "b3a8263944c5a687492a49555d8149e538f0902b"


@dataclass(frozen=True, slots=True)
class MeasuredInkGuard:
    owner: str
    collision_bounds: Box


def um_from_mm(number: str) -> int:
    """Exact printed 3-digit mm -> integer-µm PAINT coordinate conversion."""
    return round(float(number) * 1000)


def _owner_ic_obstacle(view, clean_svg: str, instance):
    """Convert existing PAINT SVG strokes into model obstacles; never author art.

    Print rendering continues to belong to PAINT, not this collision adapter.
    """
    root = ET.fromstring(clean_svg)
    if root.get("data-function-reading-local") != "bottom_to_top":
        raise ValueError("V5_ROUTE_PWM_NOT_BOTTOM_TO_TOP")
    rects = root.findall(
        f".//{SVG}g[@data-layer='ic-outline']/{SVG}rect"
    )
    leads = root.findall(
        f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
    )
    if len(rects) != 1 or len(leads) != 16:
        raise ValueError("V5_ROUTE_OWNER_PAINT_16_LEADS_AND_ONE_BODY_REQUIRED")
    body = rects[0]
    ox, oy = instance.origin.x, instance.origin.y
    x = um_from_mm(body.attrib["x"]) - ox
    y = um_from_mm(body.attrib["y"]) - oy
    w = um_from_mm(body.attrib["width"])
    h = um_from_mm(body.attrib["height"])
    keepout = Box(x, y, x + w, y + h)
    graphics = [Rectangle(keepout)]
    numbers = []
    for line in leads:
        numbers.append(line.attrib["data-pin-number"])
        p = Point(
            um_from_mm(line.attrib["x1"]) - ox,
            um_from_mm(line.attrib["y1"]) - oy,
        )
        q = Point(
            um_from_mm(line.attrib["x2"]) - ox,
            um_from_mm(line.attrib["y2"]) - oy,
        )
        graphics.append(Line(p, q))
    if sorted(numbers, key=int) != [str(i) for i in range(1, 17)]:
        raise ValueError("V5_ROUTE_PAINT_REAL_LEAD_IDS_DRIFT")
    pins = tuple(GraphicPin(
        pin.number,
        Point(pin.anchor.x - ox, pin.anchor.y - oy),
        pin.side, pin.visible_label,
    ) for pin in view.pins)
    symbol = SymbolDefinition(
        identifier="reference.tl494cn", revision=1,
        graphics=tuple(graphics), pins=pins,
        body_keepout=keepout, line_width_um=300,
        status=SymbolStatus.DRAFT,
        standard_refs=(
            "SOURCE: actual ELEKTRIK #97 physical PinRef with PAINT #93 rendered body",
            "NONPRINTABLE_ROUTER_OBSTACLE_ONLY; owner PAINT renders real DA1 text",
        ),
    )
    for pin in view.pins:
        derived = instance.pin_positions(symbol)[pin.number]
        if derived != pin.anchor:
            raise ValueError(
                f"V5_ROUTE_PHYSICAL_PIN_MOVED_{pin.number}: {derived}!={pin.anchor}"
            )
    return symbol


def audit_source_route(font_file: Path, output: Path, *, node_cap=25000) -> dict:
    """Route preflight (possibly failed) from frozen native 23/15 Circuit.

    Any partial route is always a nonprintable report. Fail closed on pin move,
    source identity change, unknown runtime owner, DRC or incompleteness.
    """
    source = compact_source_assembly()
    source.verify()
    typography = inspect_type_a_font(
        font_file, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    style = typography.style
    measurer = PillowTextMeasurer()
    bridge = import_module(
        "gost_schematic.electrical.ic_paint_bridge"
    ).propose_ic_paint_binding(source.owner_ic_record, style, measurer)
    bridge.verify_endpoints()
    render_ic = import_module(
        "gost_schematic.rendering.ic_rectangular"
    ).render_resolved_ic
    rendered = render_ic(
        bridge.views[0], style, measurer, glyph_detail=True
    )
    da1 = next(c for c in source.circuit.components if c.reference == "DA1")
    obstacle = _owner_ic_obstacle(bridge.views[0], rendered.svg, da1)
    symbols = dict(source.symbols)
    symbols["reference.tl494cn"] = obstacle
    # All owner real measured glyph positions, plus source discrete annotations.
    protect = tuple(
        MeasuredInkGuard(ink.owner, ink.box.expanded(500))
        for ink in rendered.ink
        if ink.kind in (
            "refdes", "pin-label", "pin-number", "function", "main-text",
            "field-text",
        )
    )
    from gost_schematic.engines.sheet_layout import layout_sheet

    label_layout = layout_sheet(
        source.circuit, symbols, style, measurer
    )
    guards = (*protect, *label_layout.placements)
    owner_router = import_module(
        "gost_schematic.engines.multiterminal_router"
    ).route_circuit_net_trees
    # New type-locked A3 paper; old 679.3mm source remains immutable.
    page = Box(0, 0, *A3_LANDSCAPE_UM)
    result = owner_router(
        source.circuit, source.parts, symbols, page_box=page,
        annotation_placements=guards,
        search_node_cap=node_cap, stop_on_first_failure=True,
    )
    source.verify()
    record = result.as_dict()
    record["source_sha"] = source.manifest()["source_sha"]
    record["owner_router_sha"] = ROUTER_OWNER_SHA
    record["origin_component_count"] = 23
    record["origin_net_count"] = 15
    record["old_source_negative_drc"] = {
        "errors": 9, "warnings": 32,
        "segments": 91, "junctions": 37,
    }
    record["DA1_obstacle_source"] = (
        "PAINT_real_clean_SVG_body_and_16_pin_strokes_as_DRC_only"
    )
    record["DA1_real_anchor_count"] = len(bridge.views[0].pins)
    record["owner_type_a_sha256"] = style.font_sha256
    record["annotation_guards"] = len(guards)
    record["source_label_layout_valid"] = label_layout.valid
    record["source_label_layout_errors"] = [
        d.code for d in label_layout.diagnostics
        if d.severity.value == "error"
    ]
    measured = actual_component_occupied_mm(source, symbols)
    record["compact_A3"] = measured
    record["a3_print_fit"] = measured["A3_capacity_fit"]
    record["technical_route_eligible"] = bool(
        result.print_pass and label_layout.valid and record["a3_print_fit"]
    )
    # This component/model preflight is not the final sheet assembler.
    # Only an independent QA-approved PRINT stage may release SVG/PNG.
    record["print_after_released"] = False
    record["decision"] = (
        "QA_RELEASE_STILL_REQUIRED" if record["technical_route_eligible"] else
        "BLOCKED until all 15 Net trees, DRC and print-scale compact A3 gate pass"
    )
    record["incomplete_nets"] = [
        {
            "name": tree.net_name,
            "connected": [
                f"{p.reference}.{p.number}" for p in tree.completed_pins
            ],
            "declared_contacts": len(tree.pin_refs),
            "diagnostics": list(tree.diagnostics),
        }
        for tree in result.net_trees if not tree.complete
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    return record
