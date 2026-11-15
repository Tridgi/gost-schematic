"""C16 independent adversarial tests for real Type A glyph-ink coverage."""
from xml.etree import ElementTree as ET

import pytest

from scripts.eskd_cycle16_label_ink_gate import (
    FONT_SHA,
    NS,
    InkBox,
    audit_type_a_annotations,
)


def _owner_svg() -> tuple[ET.Element, list[dict], dict]:
    root = ET.Element(f"{NS}svg", width="420mm", height="297mm")
    for n in range(39):
        text = ET.SubElement(
            root,
            f"{NS}text",
            {
                "data-layer": "annotations",
                "data-owner": "C1" if n == 0 else f"R{n}",
                "data-key": "refdes",
                "x": "261.868" if n == 0 else "25",
                "y": "13.1" if n == 0 else str(40 + 5 * n),
                "font-family": "OpenGOST type A",
                "data-font-sha256": FONT_SHA,
                "font-size": "5.48",
                "font-style": "normal",
                "fill": "#000000",
                "stroke": "none",
            },
        )
        text.text = "C1" if n == 0 else f"R{n}"
    wires = [
        {"coords": (150000, 50000, 200000, 50000),
         "stroke": 300, "index": 0, "net": "COMMON"}
    ]
    symbols = {"C1": (257000, 20000, 271000, 30000)}
    symbols.update({
        f"P{n}": (5000 + 5000 * n, 190000,
                  7000 + 5000 * n, 192000)
        for n in range(22)
    })
    assert len(symbols) == 23
    return root, wires, symbols


def _mark_first(root: ET.Element, ink: str) -> ET.Element:
    first = root.findall(f".//{NS}text[@data-layer='annotations']")[0]
    first.set("data-ink-um", ink)
    first.set("data-ink-method", "signed-native-type-a-outline-v1")
    first.set("data-ink-font-sha256", FONT_SHA)
    return first


def test_missing_actual_39_font_glyph_boxes_fails_closed():
    root, wires, symbols = _owner_svg()
    audit = audit_type_a_annotations(root, wires, symbols)
    assert audit["source_annotation_count"] == 39
    assert audit["producer_measured_count"] == 0
    assert audit["unmeasured_count"] == 39
    assert audit["measured_pair_count"] == {
        "label_wire": 0, "label_foreign_symbol": 0
    }
    assert audit["full_label_ink_verdict"].startswith("BLOCKED")
    assert audit["independent_raster_outlines"].startswith("BLOCKED")


def test_signed_c1_prior_original_top_intrudes_900um():
    root, wires, symbols = _owner_svg()
    _mark_first(root, "261362,9100,265638,13600")
    audit = audit_type_a_annotations(root, wires, symbols)
    assert audit["producer_measured_count"] == 1
    assert audit["unmeasured_count"] == 38
    assert audit["project_editorial_10mm_frame_intrusions"] == [{
        "identity": "C1:refdes",
        "intrusion_um": 900,
        "rule": "PROJECT_EDITORIAL_10MM_NOT_GOST_FRAME",
    }]
    assert audit["full_label_ink_verdict"].startswith("BLOCKED")


def test_c1_down_2500um_removes_10mm_editorial_violation_only():
    root, wires, symbols = _owner_svg()
    label = _mark_first(root, "261362,11600,265638,16100")
    label.set("y", "15.6")
    audit = audit_type_a_annotations(root, wires, symbols)
    assert audit["project_editorial_10mm_frame_intrusions"] == []
    assert audit["unmeasured_count"] == 38
    assert audit["formal_gost_frame_and_title"].startswith("BLOCKED")


def test_a_single_micron_over_editorial_boundary_is_detected():
    root, wires, symbols = _owner_svg()
    label = _mark_first(root, "261362,9999,265638,14500")
    label.set("y", "14.0")
    audit = audit_type_a_annotations(root, wires, symbols)
    assert audit["project_editorial_10mm_frame_intrusions"][0][
        "intrusion_um"
    ] == 1


def test_measured_label_and_actual_native_wire_overlap_reviewed():
    root, wires, symbols = _owner_svg()
    _mark_first(root, "261362,9100,265638,13600")
    wires[0]["coords"] = (262000, 11500, 264000, 11500)
    audit = audit_type_a_annotations(root, wires, symbols)
    assert any(
        x["kind"] == "label_wire" and x["gap_um"] == 0
        for x in audit["project_1mm_label_collisions"]
    )


@pytest.mark.parametrize("raw", [
    "261362,9100,265638", "261362,9100,261362,13600",
    "261362,9100,265638,not-a-number", " 261362,9100,265638,13600",
])
def test_malformed_or_degenerate_svg_ink_is_not_accepted(raw):
    root, wires, symbols = _owner_svg()
    _mark_first(root, raw)
    with pytest.raises(ValueError, match="LABEL_INK_BBOX"):
        audit_type_a_annotations(root, wires, symbols)


def test_unsigned_fabricated_bbox_rejected():
    root, wires, symbols = _owner_svg()
    first = root.findall(f".//{NS}text")[0]
    first.set("data-ink-um", "261362,9100,265638,13600")
    with pytest.raises(ValueError, match="LABEL_MEASUREMENT_PROVENANCE"):
        audit_type_a_annotations(root, wires, symbols)


def test_changed_font_or_unknown_svg_transform_rejected():
    root, wires, symbols = _owner_svg()
    first = root.findall(f".//{NS}text")[0]
    first.set("data-font-sha256", "0" * 64)
    with pytest.raises(ValueError, match="LABEL_TRUE_TYPE_A_FONT"):
        audit_type_a_annotations(root, wires, symbols)
    first.set("data-font-sha256", FONT_SHA)
    first.set("transform", "rotate(90)")
    with pytest.raises(ValueError, match="LABEL_TRUE_TYPE_A_FONT"):
        audit_type_a_annotations(root, wires, symbols)


def test_duplicate_owner_label_kind_is_rejected():
    root, wires, symbols = _owner_svg()
    items = root.findall(f".//{NS}text")
    items[1].set("data-owner", "C1")
    with pytest.raises(ValueError, match="LABEL_OWNER_KIND_DUPLICATED"):
        audit_type_a_annotations(root, wires, symbols)


def test_nonzero_integer_glyph_precision_and_true_gap():
    a = InkBox(10000, 10000, 20000, 20000)
    assert a.distance_um(InkBox(20001, 10000, 21000, 20000)) == 1
    assert a.editorial_frame_intrusion_um() == 0
    assert InkBox(9999, 10000, 20000, 20000).editorial_frame_intrusion_um() == 1
