"""Cycle11 exact physical rebinding for the TWO historical nonphysical b markers.

Old b-X2/b-R5 authored marker geometry is read from a typed source
NetContinuationProject, never guessed by visual OCR or by arbitrary SVG.
The one legacy physical net named OUTPUT_NEG is mapped to its exact frozen
original source name b_NEGATIVE_OUTPUT; this is NOT creation of a new Net.
"""
from __future__ import annotations

from dataclasses import replace

from gost_schematic.core.geometry import Box, Point
from gost_schematic.electrical.netrefs import (
    ContinuationAddressKind,
    ContinuationDirection,
    ContinuationScope,
    NetContinuationProject,
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.symbol import SymbolDefinition

OLD_B_NAME = "OUTPUT_NEG"
SOURCE_B_NAME = "b_NEGATIVE_OUTPUT"
B_PHYSICAL = frozenset({
    PinRef("FU1", "2"), PinRef("X2", "1"), PinRef("R5", "2"),
})
SOURCE_B_STUBS = {
    "b-X2": PinRef("X2", "1"),
    "b-R5": PinRef("R5", "2"),
}
PAGE_MARGIN_UM = 10000


def rebind_true_source_b(
    source_project: NetContinuationProject,
    compact: Circuit,
    symbols_by_part: dict[str, SymbolDefinition],
    *,
    page: Box = Box(0, 0, 420000, 297000),
) -> NetContinuationProject:
    """Reposition genuine b stub vectors on REAL compact physical pin tips.

    The old source vector from physical pin to the source marker is copied
    exactly, not transcribed or adjusted to get a pretty diagram. If moving
    it causes a margin violation or any typed provenance issue, fail closed.
    """
    if not isinstance(source_project, NetContinuationProject) or not isinstance(
        compact, Circuit,
    ):
        raise TypeError("TL494_C11_B_TYPED_OLD_AND_NEW_CIRCUIT_REQUIRED")
    if not isinstance(symbols_by_part, dict) or not isinstance(page, Box):
        raise TypeError("TL494_C11_B_TYPED_SYMBOLS_AND_PAGE_REQUIRED")
    if (
        source_project.schema_version != 2
        or len(source_project.nets) != 1
        or source_project.nets[0].net_name != OLD_B_NAME
        or set(source_project.nets[0].members) != B_PHYSICAL
        or len(source_project.nets[0].members) != 3
    ):
        raise ValueError("TL494_C11_B_ORIGINAL_PHYSICAL_NET_UNVERIFIED")
    real_names = {net.name for net in compact.nets}
    if len(compact.components) != 23 or len(real_names) != 15 or (
        sum(len(net.members) for net in compact.nets) != 62
    ) or SOURCE_B_NAME not in real_names or OLD_B_NAME in real_names:
        raise ValueError("TL494_C11_B_SOURCE_23_15_62_IDENTITY_DRIFT")
    b = next(net for net in compact.nets if net.name == SOURCE_B_NAME)
    if set(b.members) != B_PHYSICAL or len(b.members) != 3:
        raise ValueError("TL494_C11_B_SOURCE_PHYSICAL_PINREF_CHANGED")
    if (
        len(source_project.endpoints) != 2
        or len(source_project.pairs) != 1
        or len(source_project.stubs) != 2
        or set(e.id for e in source_project.endpoints) != set(SOURCE_B_STUBS)
        or set(s.endpoint_id for s in source_project.stubs) != set(SOURCE_B_STUBS)
        or source_project.pairs[0].scope != ContinuationScope.SHEET_LOCAL
        or {e.direction for e in source_project.endpoints} != {
            ContinuationDirection.SOURCE, ContinuationDirection.TARGET
        }
    ):
        raise ValueError("TL494_C11_B_NOT_TWO_REAL_SOURCE_MARKERS")
    bindings = {
        item.endpoint_id: item for item in source_project.address_bindings
    }
    if len(bindings) != 2:
        raise ValueError("TL494_C11_B_PROVENANCE_MISSING")
    for endpoint_id, pin in SOURCE_B_STUBS.items():
        owner = bindings.get(endpoint_id)
        if (
            owner is None
            or owner.kind != ContinuationAddressKind.ELEMENT_PIN
            or owner.owner_ref != pin.reference
            or owner.physical_pin != pin
        ):
            raise ValueError("TL494_C11_B_SOURCE_PIN_PROVENANCE_MISMATCH")
    source_stubs = {
        s.endpoint_id: s for s in source_project.stubs
    }
    original_anchors = {
        s.pin: s.start for s in source_project.stubs
    }
    problems = validate_net_continuations(
        source_project, physical_pin_anchors=original_anchors,
    )
    if problems:
        raise ValueError(
            "TL494_C11_B_OLD_SOURCE_TYPED_INVALID:"
            + ",".join(problem.code for problem in problems)
        )
    parts = {component.reference: component for component in compact.components}
    if len(parts) != 23:
        raise ValueError("TL494_C11_B_DUPLICATE_COMPACT_COMPONENT")
    new_tips = {}
    for marker, pin in SOURCE_B_STUBS.items():
        component = parts.get(pin.reference)
        if component is None:
            raise ValueError("TL494_C11_B_MISSING_PHYSICAL_COMPONENT")
        symbol = symbols_by_part.get(component.part_id)
        if not isinstance(symbol, SymbolDefinition):
            raise ValueError("TL494_C11_B_MISSING_REAL_SOURCE_SYMBOL")
        pins = component.pin_positions(symbol)
        if pin.number not in pins:
            raise ValueError("TL494_C11_B_UNKNOWN_PHYSICAL_PIN")
        new_tips[pin] = pins[pin.number]
    mapped_endpoints = []
    for old in source_project.endpoints:
        pin = SOURCE_B_STUBS[old.id]
        old_stub = source_stubs[old.id]
        if old_stub.pin != pin or old_stub.end != old.anchor:
            raise ValueError("TL494_C11_B_OLD_STUB_NOT_FROM_ACTUAL_PIN")
        vector = Point(
            old.anchor.x - old_stub.start.x,
            old.anchor.y - old_stub.start.y,
        )
        if vector.x and vector.y:
            raise ValueError("TL494_C11_B_OLD_MARKER_NONORTHOGONAL")
        proposed = new_tips[pin] + vector
        if not (
            page.min_x + PAGE_MARGIN_UM <= proposed.x
            <= page.max_x - PAGE_MARGIN_UM
            and page.min_y + PAGE_MARGIN_UM <= proposed.y
            <= page.max_y - PAGE_MARGIN_UM
        ):
            raise ValueError(
                "TL494_C11_B_ORIGINAL_VECTOR_OUTSIDE_COMPACT_A3_MARGIN"
            )
        mapped_endpoints.append(replace(old, anchor=proposed))
    endpoints_by_id = {p.id: p for p in mapped_endpoints}
    new_stubs = tuple(replace(
        old_stub, start=new_tips[old_stub.pin],
        end=endpoints_by_id[old_stub.endpoint_id].anchor,
    ) for old_stub in source_project.stubs)
    result = replace(
        source_project,
        circuit=compact,
        nets=(NetIdentity(source_project.nets[0].id, SOURCE_B_NAME, b.members),),
        endpoints=tuple(mapped_endpoints),
        stubs=new_stubs,
    )
    errors = validate_net_continuations(
        result, physical_pin_anchors=new_tips,
    )
    if errors:
        raise ValueError(
            "TL494_C11_B_COMPACT_SOURCE_CONTINUATION_INVALID:"
            + ",".join(e.code for e in errors)
        )
    if (
        result.circuit.nets is not compact.nets
        or any(old.pin != new.pin for old, new in zip(
            source_project.stubs, result.stubs, strict=True
        ))
        or len(result.endpoints) != 2
        or any(
            old.end.x - old.start.x != new.end.x - new.start.x
            or old.end.y - old.start.y != new.end.y - new.start.y
            for old, new in zip(
                source_project.stubs, result.stubs, strict=True,
            )
        )
    ):
        raise ValueError("TL494_C11_B_NONREVERSIBLE_COMPACT_REBIND")
    return result
