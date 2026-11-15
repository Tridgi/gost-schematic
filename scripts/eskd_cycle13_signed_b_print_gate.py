"""ESKD source-typed b-X2/b-R5 printed-stub audit, separate from electrical wires.

Purpose: reject a drawing with only labels/circles but *no actual two local
lines*. Never forge a 16th Net or infer physical junctions from marker ink.
This checks owner-produced SVG against real typed ContinuationStub values.
No source figure or production 15/15 route is certified by this module.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from gost_schematic.electrical.netrefs import ContinuationStub
from gost_schematic.model.circuit import Circuit, PinRef

SVG = "{http://www.w3.org/2000/svg}"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
EXPECTED = {"b-X2": PinRef("X2", "1"), "b-R5": PinRef("R5", "2")}
B_MEMBERS = frozenset((PinRef("FU1", "2"), *EXPECTED.values()))


class SignedBPrintError(ValueError):
    """Real source b ink missing, forged or ambiguous."""


def insist(condition: bool, code: str) -> None:
    if not condition:
        raise SignedBPrintError(code)


def _um(value: str | None) -> int:
    """Fail closed for rounded, fractional micrometre, NaN and locale drift."""
    try:
        um = Decimal(value) * 1000
        insist(um.is_finite() and um == um.to_integral_value(),
               "SOURCE_B_PRINT_COORDINATE_NOT_EXACT_MICROMETRE")
        return int(um)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SignedBPrintError(
            "SOURCE_B_PRINT_COORDINATE_NOT_EXACT_MICROMETRE"
        ) from exc


def audit_source_b_printed_lines(
    root: ET.Element, circuit: Circuit, stubs: tuple[ContinuationStub, ...],
) -> dict:
    insist(isinstance(root, ET.Element), "SOURCE_B_REAL_SVG_ELEMENT_REQUIRED")
    insist(isinstance(circuit, Circuit), "SOURCE_B_NATIVE_TYPED_CIRCUIT_REQUIRED")
    insist(isinstance(stubs, tuple)
           and len(stubs) == 2
           and all(isinstance(s, ContinuationStub) for s in stubs),
           "SOURCE_B_NATIVE_TWO_TYPED_STUBS_REQUIRED")
    insist(len(circuit.components) == 23 and len(circuit.nets) == 15
           and sum(len(net.members) for net in circuit.nets) == 62,
           "SOURCE_B_EXPECTED_23_15_62_SOURCE_CIRCUIT")
    source_b = [net for net in circuit.nets if net.name == "b_NEGATIVE_OUTPUT"]
    insist(len(source_b) == 1
           and frozenset(source_b[0].members) == B_MEMBERS,
           "SOURCE_B_ORIGINAL_NEGATIVE_OUTPUT_MEMBERSHIP_CHANGED")
    signed = {s.endpoint_id: s for s in stubs}
    insist(set(signed) == set(EXPECTED)
           and all(signed[ref].pin == pin for ref, pin in EXPECTED.items()),
           "SOURCE_B_TYPED_STUB_PINREF_FORGED")
    region = root.findall(f".//{SVG}g[@data-layer='typed-nonphysical-continuations']")
    insist(len(region) == 1
           and region[0].get("data-nonphysical") == "true"
           and region[0].get("data-do-not-infer-net-from-shapes") == "true",
           "SOURCE_B_REAL_GRAPHIC_REGION_MISSING")
    actual_lines = region[0].findall(
        f".//{SVG}line[@data-layer='nonphysical-continuation-stub']"
    )
    insist(len(actual_lines) == 2, "SOURCE_B_TWO_ACTUAL_PHYSICAL_LOCAL_INK_LINES_MISSING")
    insist(len(region[0].findall(f".//{SVG}line")) == 2,
           "SOURCE_B_UNMARKED_FOREIGN_GRAPHICAL_LINE")
    by_endpoint = {
        line.get("data-nonphysical-net-continuation"): line
        for line in actual_lines
    }
    insist(set(by_endpoint) == set(EXPECTED),
           "SOURCE_B_REAL_LOCAL_LINE_ENDPOINT_IDS_CHANGED")
    real_wires = root.findall(f".//{SVG}line[@data-layer='wires']")
    insist(not any(line.get("data-nonphysical-net-continuation")
                   in EXPECTED for line in real_wires),
           "SOURCE_B_STUB_INSERTED_IN_ELECTRICAL_WIRE_GRAPH")
    # Also catch a copied physical wire whose author deliberately stripped
    # all b metadata. Geometric line overlap must never create a phantom Net.
    for conductor in real_wires:
        try:
            coords = tuple(_um(conductor.get(axis))
                           for axis in ("x1", "y1", "x2", "y2"))
        except SignedBPrintError:
            raise SignedBPrintError(
                "SOURCE_B_PRINT_ELECTRICAL_WIRE_COORDINATES_UNVERIFIED"
            ) from None
        for stub in stubs:
            seg = (stub.start.x, stub.start.y, stub.end.x, stub.end.y)
            insist(coords != seg and coords != seg[2:] + seg[:2],
                   "SOURCE_B_EXACT_STUB_COPIED_INTO_ELECTRICAL_GRAPH")
    for endpoint_id, expected_pin in EXPECTED.items():
        line = by_endpoint[endpoint_id]
        source = signed[endpoint_id]
        actual_start = (_um(line.get("x1")), _um(line.get("y1")))
        actual_end = (_um(line.get("x2")), _um(line.get("y2")))
        insist(actual_start == (source.start.x, source.start.y)
               and actual_end == (source.end.x, source.end.y),
               "SOURCE_B_REAL_INK_DOES_NOT_REACH_SIGNED_STUB_ENDPOINTS")
        insist(line.get("data-source-pin-ref") ==
               f"{expected_pin.reference}.{expected_pin.number}"
               and line.get("data-source-stub-id") == source.id
               and line.get("data-electrical-junction") == "false"
               and line.get("data-connectable") == "false"
               and line.get("data-nonphysical") == "true",
               "SOURCE_B_REAL_INK_FORGED_AS_PHYSICAL_WIRE")
        insist(line.get("stroke-width") == "0.3",
               "SOURCE_B_PRINT_STUB_0P3MM_STROKE_REQUIRED")
    markers = region[0].findall(f".//{SVG}circle")
    insist(len(markers) == 2
           and {e.get("data-nonphysical-net-continuation") for e in markers}
           == set(EXPECTED)
           and all(e.get("data-electrical-junction") == "false"
                   for e in markers),
           "SOURCE_B_PRINT_MARKER_CIRCLES_NOT_TWO_NONPHYSICAL")
    by_marker = {m.get("data-nonphysical-net-continuation"): m for m in markers}
    for marker_id, stub in signed.items():
        marker = by_marker[marker_id]
        insist((_um(marker.get("cx")), _um(marker.get("cy"))) ==
               (stub.end.x, stub.end.y),
               "SOURCE_B_PRINT_MARKER_CIRCLE_NOT_AT_SIGNED_ENDPOINT")
    texts = region[0].findall(f".//{SVG}text")
    insist(len(texts) == 2 and all(
        "".join(t.itertext()).strip() == "b"
        and t.get("data-font-sha256") == FONT_SHA
        and t.get("font-family") == "OpenGOST type A"
        and t.get("data-nonphysical") == "true"
        for t in texts),
        "SOURCE_B_PRINT_LABELS_NOT_AUTHENTIC_TYPE_A")
    insist({(_um(t.get("x")), _um(t.get("y"))) for t in texts} ==
           {(s.end.x, s.end.y - 4000) for s in signed.values()},
           "SOURCE_B_PRINT_LABEL_NOT_AT_SIGNED_SOURCE_MARKER")
    insist(root.get("data-release") != "PRINT_PASS",
           "SOURCE_B_GRAPHIC_NOT_INDEPENDENT_FULL_PRINT_APPROVAL")
    return {
        "typed_source_b_net": "b_NEGATIVE_OUTPUT",
        "original_physical_members": sorted(
            f"{p.reference}.{p.number}" for p in B_MEMBERS
        ),
        "real_stubs": {
            k: {"source_pin": f"{v.pin.reference}.{v.pin.number}",
                "start_um": [v.start.x, v.start.y],
                "end_um": [v.end.x, v.end.y]}
            for k, v in sorted(signed.items())
        },
        "actual_nonphysical_svg_lines": 2,
        "nonphysical_labels": 2,
        "actual_electrical_added_nets": 0,
        "verdict": "PASS_SOURCE_TYPED_B_INK_ONLY_NO_ELECTRICAL_EDGE",
        "whole_sheet_print_accepted": False,
    }
