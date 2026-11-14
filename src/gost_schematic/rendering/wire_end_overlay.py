"""Read-only E3 editor diagnostics over the EXISTING validated sheet SVG.

No new conductor, junction, connector or electrical net is drawn by this
adapter. Clean mode returns the existing clean SVG unchanged.
"""
import json
from xml.etree import ElementTree as ET

from gost_schematic.core.units import format_mm
from gost_schematic.electrical.netrefs import NetContinuationProject
from gost_schematic.electrical.wire_endpoints import (
    TargetState,
    WireEndpointSnapshot,
    WireEndSide,
    WireTermination,
    collect_wire_endpoints,
    validate_wire_endpoint_snapshot,
)
from gost_schematic.model.circuit import PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition

_URI = "http://www.w3.org/2000/svg"
_NS = "{" + _URI + "}"


def wire_endpoint_svg(
    clean_svg: str,
    snapshot: WireEndpointSnapshot,
    parts: dict[str, PartDefinition],
    symbols: dict[str, SymbolDefinition],
    *,
    diagnostic: bool = False,
    blocked_pins: frozenset[PinRef] = frozenset(),
    blocked_wire_ends: frozenset[tuple[str, WireEndSide]] = frozenset(),
    continuations: NetContinuationProject | None = None,
    marker_size_um: int = 1200,
) -> str:
    """Opt-in green square targets at exact authored electrical anchors.

    World-space marker size is an EDITORIAL SVG preview dimension, NOT an
    interactive pixel hit radius. A future editor must separately hit-test
    CSS-pixel circles using zoom, keyboard and ambiguity resolution.
    """
    if type(clean_svg) is not str or not clean_svg.strip():
        raise ValueError("WIRE_END_CLEAN_SVG_REQUIRED")
    if type(marker_size_um) is not int or not 200 <= marker_size_um <= 4000:
        raise ValueError("WIRE_END_DIAGNOSTIC_MARKER_SIZE_INVALID")
    validate_wire_endpoint_snapshot(snapshot)
    independently_verified = collect_wire_endpoints(
        snapshot.circuit, snapshot.graph, snapshot.nets,
        snapshot.wire_ids, parts, symbols, continuations=continuations,
        blocked_pins=blocked_pins, blocked_wire_ends=blocked_wire_ends,
    )
    if snapshot != independently_verified:
        raise ValueError("WIRE_END_SNAPSHOT_NOT_SOURCE_VERIFIED")
    root = ET.fromstring(clean_svg)
    if root.tag != _NS + "svg":
        raise ValueError("WIRE_END_SVG_ROOT_NOT_NAMESPACED")
    if any(e.attrib.get("data-layer") == "editor-connection-targets" for e in root.iter()):
        raise ValueError("WIRE_END_PREEXISTING_EDITOR_LAYER")
    if any(
        e.attrib.get("stroke", "").lower() in ("#008000", "#00a65a", "#009577")
        for e in root.iter()
    ):
        raise ValueError("WIRE_END_CLEAN_SOURCE_COLORED")
    drawn = [
        e for e in root.iter() if e.tag == _NS + "line"
        and e.attrib.get("data-layer") == "wires"
    ]
    if len(drawn) != len(snapshot.graph.segments):
        raise ValueError("WIRE_END_SVG_WIRE_COUNT_MISMATCH")
    for index, (element, segment) in enumerate(
        zip(drawn, snapshot.graph.segments, strict=True)
    ):
        expected = tuple(format_mm(coord) for coord in (
            segment.start.x, segment.start.y, segment.end.x, segment.end.y
        ))
        actual = tuple(element.attrib.get(k) for k in ("x1", "y1", "x2", "y2"))
        if actual != expected:
            raise ValueError("WIRE_END_SVG_SOURCE_COORDINATE_MISMATCH")
        if element.attrib.get("data-wire-index") not in (None, str(index)):
            raise ValueError("WIRE_END_SVG_SEGMENT_INDEX_MISMATCH")
        if element.attrib.get("data-net") not in (None, segment.net_name):
            raise ValueError("WIRE_END_SVG_NET_MISMATCH")
    # The clean, preexisting document is returned byte-for-byte. No UI
    # metadata, CSS, invisible hit path or green pixel leaks into print.
    if not diagnostic:
        return clean_svg
    layer = ET.SubElement(root, _NS + "g", {
        "data-layer": "editor-connection-targets",
        "data-print": "false",
        "data-approval": "EDITOR_ONLY_NOT_GOST",
        "data-target-space": "world-integer-micrometres",
    })
    # Render only genuinely FREE ends, valid or source-policy blocked. All
    # attached physical ends, junctions, X and offpage labels stay separate.
    for end in snapshot.wire_endpoints:
        if end.termination is not WireTermination.FREE:
            continue
        color = "#008c52" if end.can_accept_connection else "#b34444"
        half = marker_size_um // 2
        square = ET.SubElement(layer, _NS + "rect", {
            "data-kind": end.termination.value, "data-id": end.id,
            "data-wire-id": end.wire_id,
            "data-wire-index": str(end.wire_index),
            "data-net-id": end.net_id, "data-side": end.side.value,
            "data-state": end.state.value,
            "data-connectable": str(end.can_accept_connection).lower(),
            "data-reason": end.reason_code,
            "x": format_mm(end.point.x - half),
            "y": format_mm(end.point.y - half),
            "width": format_mm(marker_size_um),
            "height": format_mm(marker_size_um),
            "fill": "none", "stroke": color, "stroke-width": "0.28",
        })
        ET.SubElement(square, _NS + "title").text = (
            f"{end.id}: {end.state.value}; {end.reason_code}"
        )

    for contact in snapshot.physical_contacts:
        if contact.state is TargetState.CONNECTED:
            continue
        # Distinct physical pin/XP/XS identity is retained in every SVG
        # marker; no PinRef can be manufactured from a visual wire crossing.
        half = marker_size_um // 2
        color = "#008c52" if contact.can_accept_connection else "#b34444"
        el = ET.SubElement(layer, _NS + "rect", {
            "data-kind": "physical-connector-contact" if contact.connector else "physical-pin",
            "data-id": contact.id,
            "data-pin-ref": contact.pin.reference + "." + contact.pin.number,
            "data-net-id": contact.net_id or "",
            "data-state": contact.state.value,
            "data-connectable": str(contact.can_accept_connection).lower(),
            "data-reason": contact.reason_code,
            "x": format_mm(contact.point.x - half),
            "y": format_mm(contact.point.y - half),
            "width": format_mm(marker_size_um), "height": format_mm(marker_size_um),
            "fill": "none", "stroke": color, "stroke-width": "0.28",
        })
        ET.SubElement(el, _NS + "title").text = (
            f"{contact.id}: {contact.state.value}; {contact.reason_code}"
        )
    metadata = ET.SubElement(root, _NS + "metadata", {
        "data-layer": "diagnostic-electrical-endpoint-inventory",
        "data-print": "false",
    })
    metadata.text = json.dumps({
        "schema_version": 1,
        "wire_endpoints": [
            {
                "id": e.id, "wire_id": e.wire_id, "wire_index": e.wire_index,
                "side": e.side.value, "point_um": [e.point.x, e.point.y],
                "net_id": e.net_id, "termination": e.termination.value,
                "state": e.state.value, "connectable": e.can_accept_connection,
                "physical_pin": (
                    e.attached_pin.reference + "." + e.attached_pin.number
                    if e.attached_pin else None
                ),
                "continuation_id": e.continuation_id,
                "reason_code": e.reason_code,
            } for e in snapshot.wire_endpoints
        ],
        "unconnected_crossings": [
            {"id": x.id, "point_um": [x.point.x, x.point.y],
             "wire_ids": [x.first_wire_id, x.second_wire_id],
             "net_ids": [x.first_net_id, x.second_net_id]}
            for x in snapshot.nonjoining_crossings
        ],
        "continuations_nonphysical": list(snapshot.continuation_ids),
        "explicit_junctions_um": [
            [p.x, p.y] for p in snapshot.graph.junctions
        ],
        "notice": "Read-only review, no new electrical junctions or connections",
    }, sort_keys=True, ensure_ascii=False)
    return ET.tostring(root, encoding="unicode") + "\n"
