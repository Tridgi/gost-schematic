"""Signed source physical pin corridor E3 diagnostics (negative and A2/A3)."""
import os
from decimal import Decimal
from pathlib import Path

import pytest

from examples.tl494_v5.cycle14_pin_corridor_probe import measure_pin_corridors


def _font() -> Path:
    return Path(os.environ["TL494_TYPE_A_FONT"])


@pytest.fixture(scope="module")
def sheet() -> dict:
    return measure_pin_corridors(_font(), page_format="A3")


def test_all_62_real_pin_escapes_preserve_original_graph(sheet):
    assert (sheet["components"], sheet["original_net_count"]) == (23, 15)
    assert (sheet["physical_pinref_memberships"],
            sheet["manufacturer_signed_DA1_pins"]) == (62, 16)
    assert len(sheet["pin_escapes"]) == 62
    assert len(sheet["original_nets"]) == 15
    assert sum(len(v) for v in sheet["original_nets"].values()) == 62
    assert sheet["source_sha"] == "e695c415fdced164b0e0c39c5249d030795a0aa6"
    assert sheet["source_UGO_bbox_um"] == [
        10850, 14800, 405150, 243151,
    ]
    assert sheet["absolute_10mm_component_ink_fit"]
    assert sheet["real_measured_text_layout_valid"]
    assert sheet["real_measured_text_guard_count"] == 73
    assert sheet["measured_text_10mm_frame_fit"] is False
    assert sheet["measured_text_frame_violations"] == [{
        "owner": "C1", "label": "C1", "kind": "AnnotationPlacement",
        "bounds_um": [261362, 9100, 265638, 13600],
    }]
    assert sheet["full_15_net_print_release"] == "BLOCKED_NOT_A_ROUTER"
    assert "existing routed Net wires" in sheet["excluded_from_this_probe"]


def test_true_16_manufacturer_tip_coordinates_and_2p5mm_escape(sheet):
    pins = sheet["pin_escapes"]
    assert pins["DA1.3"]["source_physical_anchor_um"] == [125000, 116250]
    assert pins["DA1.6"]["source_physical_anchor_um"] == [125000, 138750]
    assert pins["DA1.10"]["source_physical_anchor_um"] == [205000, 116250]
    assert pins["DA1.13"]["source_physical_anchor_um"] == [125000, 146250]
    assert sum(key.startswith("DA1.") for key in pins) == 16
    assert all(
        item["escape_samples_um"]["2500"]["native_symbol_ink_clear"]
        for item in pins.values()
    )
    assert all(
        item["escape_samples_um"]["2500"]["inside_page_margin"]
        for item in pins.values()
    )


def test_real_5mm_contact_collision_not_waived(sheet):
    # FU1 and X2 are genuinely adjacent original components on one Net;
    # a straight 5mm escape enters the NEXT genuine component stroke.
    blocked = {
        key: item["escape_samples_um"]["5000"]["first_blocked_UGO"]
        for key, item in sheet["pin_escapes"].items()
        if not item["escape_samples_um"]["5000"][
            "native_symbol_ink_clear"
        ]
    }
    assert set(blocked) == {"FU1.2", "X2.1"}
    assert blocked["FU1.2"]["component"] == "X2"
    assert blocked["X2.1"]["component"] == "FU1"
    assert sheet["pin_escapes"]["FU1.2"]["net"] == "b_NEGATIVE_OUTPUT"
    assert sheet["pin_escapes"]["X2.1"]["net"] == "b_NEGATIVE_OUTPUT"


def test_actual_nonphysical_b_stubs_remain_typed_and_not_electrical(sheet):
    assert sheet["true_nonphysical_b_labels_count"] == 2
    assert sheet["true_b_source_stubs"] == {
        "b-X2": {
            "physical_PinRef": "X2.1",
            "start_um": [389000, 35000],
            "end_um": [374000, 35000],
            "electrical": False,
        },
        "b-R5": {
            "physical_PinRef": "R5.2",
            "start_um": [25000, 224000],
            "end_um": [25000, 236000],
            "electrical": False,
        },
    }
    assert set(sheet["original_nets"]["b_NEGATIVE_OUTPUT"]) == {
        "FU1.2", "X2.1", "R5.2",
    }


def test_A2_extra_paper_does_not_alter_62_real_pin_tip_positions(sheet):
    larger = measure_pin_corridors(_font(), page_format="A2")
    assert larger["page_size_um"] == [594000, 420000]
    assert larger["source_UGO_bbox_um"] == sheet["source_UGO_bbox_um"]
    assert larger["absolute_10mm_component_ink_fit"]
    assert larger["measured_text_frame_violations"] == sheet[
        "measured_text_frame_violations"
    ]
    assert larger["pin_escapes"] == sheet["pin_escapes"]
    assert larger["true_b_source_stubs"] == sheet["true_b_source_stubs"]
    assert larger["full_15_net_print_release"] == "BLOCKED_NOT_A_ROUTER"


@pytest.mark.parametrize("page_format", ("A3", "A2"))
def test_true_C1_down_2p5_repairs_paper_text_without_fake_net(
    sheet, page_format,
):
    # The real source C1 label is at top 9.1mm, so its UGO being inside
    # the margin is NOT enough. The actual 2.5mm source-preserving relocation
    # fixes this geometric defect while not changing any original Net/PinRef.
    legal = measure_pin_corridors(
        _font(), page_format=page_format,
        move_mm=(("C1", 0, Decimal("2.5")),),
    )
    assert legal["real_measured_text_guard_count"] == 73
    assert legal["real_measured_text_layout_valid"]
    assert legal["measured_text_10mm_frame_fit"]
    assert legal["measured_text_frame_violations"] == []
    assert legal["absolute_10mm_component_ink_fit"]
    assert legal["source_UGO_bbox_um"] == [10850, 17300, 405150, 243151]
    assert legal["original_nets"] == sheet["original_nets"]
    assert legal["true_b_source_stubs"] == sheet["true_b_source_stubs"]
    assert (legal["physical_pinref_memberships"],
            legal["manufacturer_signed_DA1_pins"]) == (62, 16)
    assert legal["full_15_net_print_release"] == "BLOCKED_NOT_A_ROUTER"


@pytest.mark.parametrize(
    ("page", "steps", "message"),
    [
        ("A0", (2500,), "UNSUPPORTED_PAPER_FORMAT"),
        ("A3", (), "UNVERIFIED_PIN_ESCAPE_STEP"),
        ("A3", (True,), "UNVERIFIED_PIN_ESCAPE_STEP"),
        ("A3", (0,), "UNVERIFIED_PIN_ESCAPE_STEP"),
        ("A3", (2501,), "UNVERIFIED_PIN_ESCAPE_STEP"),
        ("A3", (2500, 2500), "UNVERIFIED_PIN_ESCAPE_STEP"),
    ],
)
def test_untrusted_paper_or_step_cannot_bypass_e3_gate(page, steps, message):
    with pytest.raises(ValueError, match=message):
        measure_pin_corridors(
            Path("/invalid/missing/verified-font.ttf"),
            page_format=page, steps_um=steps,
        )
