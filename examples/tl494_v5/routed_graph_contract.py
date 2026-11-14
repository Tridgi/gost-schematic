"""Strict rehydration of accepted owner route evidence for future PAINT.

ExternalWireGraph is the only valid hand-off to routed_native_sheet.
Never synthesize a missing Net segment, infer a T/X junction, or release
SVG/PNG. A partial graph stays explicitly nonprintable.
"""
from __future__ import annotations

from gost_schematic.core.geometry import Point
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
)


def _point(value: object, where: str) -> Point:
    if (
        type(value) is not list and type(value) is not tuple
    ) or len(value) != 2 or any(type(x) is not int for x in value):
        raise ValueError("TL494_ROUTE_GRAPH_INVALID_INTEGER_POINT:" + where)
    return Point(*value)


def _contains(segment: WireSegment, point: Point) -> bool:
    a, b = segment.start, segment.end
    cross = (
        (b.x - a.x) * (point.y - a.y)
        - (b.y - a.y) * (point.x - a.x)
    )
    return (
        cross == 0
        and min(a.x, b.x) <= point.x <= max(a.x, b.x)
        and min(a.y, b.y) <= point.y <= max(a.y, b.y)
    )


def rehydrate_verified_route_graph(
    trial: dict, original_frozen_nets: dict,
) -> ExternalWireGraph:
    """Return exact typed graph only when all stored source/ink links match.

    Checks serialization and Net identity, not final physical DRC. The
    renderer still MUST run its own graph/symbol/text print validator.
    """
    if not isinstance(trial, dict) or trial.get("source_unchanged") is not True:
        raise ValueError("TL494_ROUTE_GRAPH_UNTRUSTED_SOURCE")
    source = trial.get("source_nets")
    if (
        type(source) is not dict
        or type(original_frozen_nets) is not dict
        or len(source) != 15
        or len(original_frozen_nets) != 15
        or set(source) != set(original_frozen_nets)
    ):
        raise ValueError("TL494_ROUTE_GRAPH_NAMED_NET_MISMATCH")
    for name, pins in original_frozen_nets.items():
        if tuple(source[name]) != tuple(pins):
            raise ValueError("TL494_ROUTE_GRAPH_SOURCED_PINREF_MISMATCH:" + name)
    if sum(len(members) for members in source.values()) != 62:
        raise ValueError("TL494_ROUTE_GRAPH_62_ORIGINAL_PINS_REQUIRED")
    status = trial.get("named_net_status")
    payload = trial.get("accepted_graph_nonprintable")
    owner = trial.get("owner_router_report")
    if (
        not isinstance(payload, dict) or not isinstance(status, dict)
        or not isinstance(owner, dict)
        or set(status) != set(source)
        or payload.get("status") != "DIAGNOSTIC_ONLY_NOT_PRINT_AFTER"
        or trial.get("print_after_released") is not False
    ):
        raise ValueError("TL494_ROUTE_GRAPH_DIAGNOSTIC_ONLY_REQUIRED")
    for name, state in status.items():
        if tuple(state["expected"]) != tuple(source[name]):
            raise ValueError("TL494_ROUTE_GRAPH_CHANGED_EXPECTED_PINS:" + name)
        if not set(state["connected"]) <= set(source[name]):
            raise ValueError("TL494_ROUTE_GRAPH_FAKE_CONNECTED_PINS:" + name)
    accepted_net_names = {
        name for name, state in status.items()
        if state["complete"] is True
    }
    wire_data = payload.get("segments_um")
    junction_data = payload.get("junctions_um")
    if type(wire_data) is not list or type(junction_data) is not list:
        raise ValueError("TL494_ROUTE_GRAPH_MISSING_TYPED_STROKES")
    segments = []
    for index, item in enumerate(wire_data):
        if type(item) is not dict or set(item) != {"net", "start", "end"}:
            raise ValueError("TL494_ROUTE_GRAPH_EXTRA_OR_MISSING_WIRE_FIELDS")
        net_name = item["net"]
        if type(net_name) is not str or net_name not in accepted_net_names:
            raise ValueError("TL494_ROUTE_GRAPH_UNACCEPTED_OR_FOREIGN_NET")
        a = _point(item["start"], f"wire-{index}-start")
        b = _point(item["end"], f"wire-{index}-end")
        if a == b or (a.x != b.x and a.y != b.y):
            raise ValueError("TL494_ROUTE_GRAPH_DIAGONAL_OR_ZERO_STROKE")
        segments.append(WireSegment(a, b, net_name))
    junctions = tuple(
        _point(item, f"junction-{index}")
        for index, item in enumerate(junction_data)
    )
    if len(junctions) != len(set(junctions)):
        raise ValueError("TL494_ROUTE_GRAPH_DUPLICATE_JUNCTION")
    for point in junctions:
        coincident = [w.net_name for w in segments if _contains(w, point)]
        if len(coincident) < 2 or len(set(coincident)) != 1:
            raise ValueError("TL494_ROUTE_GRAPH_FOREIGN_OR_FAKE_T_X_JUNCTION")
    length_mm = round(sum(
        abs(segment.start.x - segment.end.x)
        + abs(segment.start.y - segment.end.y)
        for segment in segments
    ) / 1000, 3)
    if (
        payload.get("total_segment_count") != len(segments)
        or owner.get("graph_segments") != len(segments)
        or payload.get("total_manhattan_length_mm") != length_mm
        or owner.get("graph_junctions") != len(junctions)
        or payload.get("source_original_wire_count") != 91
        or payload.get("historical_negative_not_overwritten") is not True
    ):
        raise ValueError("TL494_ROUTE_GRAPH_WIRE_OR_NEGATIVE_SNAPSHOT_DRIFT")
    if owner.get("routed_net_count") != len(accepted_net_names):
        raise ValueError("TL494_ROUTE_GRAPH_COMPLETED_NET_COUNT_DRIFT")
    return ExternalWireGraph(tuple(segments), junctions)
