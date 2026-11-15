"""True typed Circuit + ContinuationStub graphic tests; no phantom Net."""
from __future__ import annotations

from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import ContinuationStub
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from scripts import eskd_cycle13_signed_b_print_gate as gate

NETS = {
    "ADJUSTED_DIVIDER": ["R4.2", "R5.1", "R5.3"],
    "COMMON": [
        "X1.2", "X2.2", "VT1.3", "VD1.2", "C5.1", "C6.1",
        "DA1.7", "DA1.1", "DA1.16", "DA1.13", "R6.2", "R7.2",
        "R8.2", "C7.2",
    ],
    "CONTROL_REFERENCE": ["DA1.14", "DA1.15", "R1.1", "R2.1", "C3.1"],
    "ERROR_INPUT": ["DA1.2", "R2.2", "R4.1", "C4.1"],
    "FEEDBACK": ["R3.2", "DA1.3"],
    "GATE_DRIVE": ["DA1.9", "DA1.10", "R8.1", "VT1.1"],
    "OSCILLATOR_CT": ["C7.1", "DA1.5"],
    "OSCILLATOR_RT": ["R7.1", "DA1.6"],
    "OUT_BEFORE_FUSE": ["L2.2", "FU1.1", "C5.2", "C6.2"],
    "RC_CORRECTION": ["C4.2", "R3.1"],
    "SOFT_START": ["DA1.4", "R1.2", "C3.2", "R6.1"],
    "SWITCH": ["L1.2", "VT1.2", "C1.1", "C2.1"],
    "TRANSFER": ["C1.2", "C2.2", "VD1.1", "L2.1"],
    "a_INPUT_PLUS": ["X1.1", "L1.1", "DA1.12", "DA1.8", "DA1.11"],
    "b_NEGATIVE_OUTPUT": ["FU1.2", "X2.1", "R5.2"],
}


def native_source():
    members = {
        name: tuple(PinRef(*pin.split(".")) for pin in pins)
        for name, pins in NETS.items()
    }
    names = sorted({pin.reference for pins in members.values() for pin in pins})
    assert len(names) == 23
    assert sum(len(m) for m in members.values()) == 62
    return Circuit(
        tuple(ComponentInstance(ref, "source." + ref) for ref in names),
        tuple(Net(name, pins) for name, pins in members.items()),
    )


def native_stubs():
    return (
        ContinuationStub("S-X2", "b-X2", PinRef("X2", "1"),
                         Point(35000, 50000), Point(45000, 50000)),
        ContinuationStub("S-R5", "b-R5", PinRef("R5", "2"),
                         Point(145000, 110000), Point(145000, 123000)),
    )


def _point_mm(point: int) -> str:
    return str(point // 1000) if point % 1000 == 0 else str(point / 1000)


def real_native_b_graphics(*, no_lines: bool = False):
    root = ET.Element(f"{gate.SVG}svg", {"data-release": "BLOCKED_PARTIAL"})
    region = ET.SubElement(root, f"{gate.SVG}g", {
        "data-layer": "typed-nonphysical-continuations",
        "data-nonphysical": "true",
        "data-do-not-infer-net-from-shapes": "true",
    })
    for s in native_stubs():
        if not no_lines:
            ET.SubElement(region, f"{gate.SVG}line", {
                "x1": _point_mm(s.start.x), "y1": _point_mm(s.start.y),
                "x2": _point_mm(s.end.x), "y2": _point_mm(s.end.y),
                "stroke-width": "0.3",
                "data-layer": "nonphysical-continuation-stub",
                "data-nonphysical": "true",
                "data-connectable": "false",
                "data-electrical-junction": "false",
                "data-source-pin-ref": f"{s.pin.reference}.{s.pin.number}",
                "data-source-stub-id": s.id,
                "data-nonphysical-net-continuation": s.endpoint_id,
            })
        ET.SubElement(region, f"{gate.SVG}circle", {
            "cx": _point_mm(s.end.x), "cy": _point_mm(s.end.y),
            "data-nonphysical-net-continuation": s.endpoint_id,
            "data-electrical-junction": "false",
        })
        ET.SubElement(region, f"{gate.SVG}text", {
            "x": _point_mm(s.end.x),
            "y": _point_mm(s.end.y - 4000),
            "font-family": "OpenGOST type A",
            "data-font-sha256": gate.FONT_SHA,
            "data-nonphysical": "true",
        }).text = "b"
    return root, region


def test_true_typed_b_has_two_printed_lines_and_never_physical_edge():
    source = native_source()
    root, _ = real_native_b_graphics()
    evidence = gate.audit_source_b_printed_lines(root, source, native_stubs())
    assert evidence["actual_nonphysical_svg_lines"] == 2
    assert evidence["actual_electrical_added_nets"] == 0
    assert evidence["original_physical_members"] == ["FU1.2", "R5.2", "X2.1"]
    assert not evidence["whole_sheet_print_accepted"]
    assert source.nets == native_source().nets


@pytest.mark.parametrize(("mutation", "reason"), [
    ("no_lines", "SOURCE_B_TWO_ACTUAL_PHYSICAL_LOCAL_INK_LINES_MISSING"),
    ("wrong_second_start_1um", "SOURCE_B_REAL_INK_DOES_NOT_REACH_SIGNED_STUB_ENDPOINTS"),
    ("wrong_first_end_1um", "SOURCE_B_REAL_INK_DOES_NOT_REACH_SIGNED_STUB_ENDPOINTS"),
    ("wrong_pinref", "SOURCE_B_REAL_INK_FORGED_AS_PHYSICAL_WIRE"),
    ("fake_connectable", "SOURCE_B_REAL_INK_FORGED_AS_PHYSICAL_WIRE"),
    ("duplicate_b_id", "SOURCE_B_REAL_LOCAL_LINE_ENDPOINT_IDS_CHANGED"),
    ("fake_electrical_layer", "SOURCE_B_STUB_INSERTED_IN_ELECTRICAL_WIRE_GRAPH"),
    ("missing_circle", "SOURCE_B_PRINT_MARKER_CIRCLES_NOT_TWO_NONPHYSICAL"),
    ("wrong_label", "SOURCE_B_PRINT_LABELS_NOT_AUTHENTIC_TYPE_A"),
    ("fake_font", "SOURCE_B_PRINT_LABELS_NOT_AUTHENTIC_TYPE_A"),
    ("wrong_source_net", "SOURCE_B_ORIGINAL_NEGATIVE_OUTPUT_MEMBERSHIP_CHANGED"),
    ("faked_approval", "SOURCE_B_GRAPHIC_NOT_INDEPENDENT_FULL_PRINT_APPROVAL"),
    ("source_type_mismatch", "SOURCE_B_NATIVE_TWO_TYPED_STUBS_REQUIRED"),
    ("cross_pin_stub", "SOURCE_B_TYPED_STUB_PINREF_FORGED"),
    ("stroke_change", "SOURCE_B_PRINT_STUB_0P3MM_STROKE_REQUIRED"),
    ("submicrometre", "SOURCE_B_PRINT_COORDINATE_NOT_EXACT_MICROMETRE"),
    ("circle_shift", "SOURCE_B_PRINT_MARKER_CIRCLE_NOT_AT_SIGNED_ENDPOINT"),
    ("label_shift", "SOURCE_B_PRINT_LABEL_NOT_AT_SIGNED_SOURCE_MARKER"),
    ("extra_unmarked_line", "SOURCE_B_UNMARKED_FOREIGN_GRAPHICAL_LINE"),
    ("copied_electrical_wire", "SOURCE_B_EXACT_STUB_COPIED_INTO_ELECTRICAL_GRAPH"),
])
def test_printed_b_adversarial_physical_and_graphic_invariants(mutation, reason):
    source = native_source()
    root, region = real_native_b_graphics(no_lines=mutation == "no_lines")
    stubs = native_stubs()
    lines = region.findall(f"{gate.SVG}line")
    texts = region.findall(f"{gate.SVG}text")
    if mutation == "wrong_second_start_1um":
        lines[1].set("x1", "145.001")
    elif mutation == "wrong_first_end_1um":
        lines[0].set("x2", "45.001")
    elif mutation == "wrong_pinref":
        lines[0].set("data-source-pin-ref", "X2.2")
    elif mutation == "fake_connectable":
        lines[0].set("data-connectable", "true")
    elif mutation == "duplicate_b_id":
        lines[1].set("data-nonphysical-net-continuation", "b-X2")
    elif mutation == "fake_electrical_layer":
        ET.SubElement(root, f"{gate.SVG}line", {
            "data-layer": "wires",
            "data-nonphysical-net-continuation": "b-X2",
        })
    elif mutation == "missing_circle":
        region.remove(region.findall(f"{gate.SVG}circle")[0])
    elif mutation == "wrong_label":
        texts[0].text = "PE"
    elif mutation == "fake_font":
        texts[0].set("font-family", "DejaVu Sans")
    elif mutation == "wrong_source_net":
        corrupt = list(source.nets)
        last = corrupt[-1]
        corrupt[-1] = Net(last.name, (PinRef("R5", "1"), *last.members[1:]))
        source = replace(source, nets=tuple(corrupt))
    elif mutation == "faked_approval":
        root.set("data-release", "PRINT_PASS")
    elif mutation == "source_type_mismatch":
        stubs = stubs[0]  # type: ignore[assignment]
    elif mutation == "cross_pin_stub":
        stubs = (replace(stubs[0], pin=PinRef("X2", "2")), stubs[1])
    elif mutation == "stroke_change":
        lines[1].set("stroke-width", "0.15")
    elif mutation == "submicrometre":
        lines[0].set("x1", "35.0005")
    elif mutation == "circle_shift":
        region.findall(f"{gate.SVG}circle")[0].set("cx", "45.001")
    elif mutation == "label_shift":
        texts[0].set("y", "46.001")
    elif mutation == "extra_unmarked_line":
        ET.SubElement(region, f"{gate.SVG}line", {
            "x1": "1", "x2": "2", "y1": "1", "y2": "1",
        })
    elif mutation == "copied_electrical_wire":
        ET.SubElement(root, f"{gate.SVG}line", {
            "data-layer": "wires",
            "x1": "35", "y1": "50", "x2": "45", "y2": "50",
        })
    with pytest.raises(gate.SignedBPrintError, match=reason):
        gate.audit_source_b_printed_lines(root, source, stubs)
