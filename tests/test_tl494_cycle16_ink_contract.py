"""Cycle16 real frozen 23-part geometry comparator adversarial regressions."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.verify_tl494_cycle16_ink_contract import InkContractMismatch, verify_contract


BASELINE = (
    Path(__file__).resolve().parents[1]
    / "reports/tl494-cycle15-true-23-ink.json"
)


@pytest.fixture
def original() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def check(base: dict, candidate: dict) -> dict:
    return verify_contract(
        base, candidate,
        actual_recon_sha=candidate["recon_exact_sha"],
    )


def test_original_same_platform_source_23_15_62_contract(original):
    verdict = check(original, copy.deepcopy(original))
    assert verdict["source_parts"] == 23
    assert verdict["source_nets"] == 15
    assert verdict["physical_pin_refs"] == 62
    assert verdict["DA1_real_pins"] == 16
    assert verdict["measured_text_guards_per_layout"] == 73
    assert verdict["full_print_pass"] is False


def test_recon_new_sha_alone_cannot_forge_real_ink_change(original):
    new = copy.deepcopy(original)
    new["recon_exact_sha"] = "a" * 40
    assert check(original, new)["current_recon_sha"] == "a" * 40
    new["control"]["parts"]["C1"]["actual_glyph_stroke_box_um"][0] += 1
    with pytest.raises(InkContractMismatch, match="PHYSICAL_INK_OR_NET_DRIFT"):
        check(original, new)


@pytest.mark.parametrize("changed", (
    ("DA1", "contact_um"),
    ("VD1", "contact_um"),
    ("VT1", "contact_um"),
    ("R5", "contact_um"),
))
def test_physical_pin_one_micrometre_is_never_text_waived(original, changed):
    candidate = copy.deepcopy(original)
    ref, field = changed
    candidate["control"]["parts"][ref]["real_physical_contacts"][0][field][0] += 1
    with pytest.raises(InkContractMismatch, match="PHYSICAL_INK_OR_NET_DRIFT"):
        check(original, candidate)


def test_same_net_count_but_wrong_original_pin_ref_is_rejected(original):
    candidate = copy.deepcopy(original)
    item = candidate["control"]["parts"]["R5"]["real_physical_contacts"][0]
    item["canonical_source_net"] = "UNAUTHORIZED"
    with pytest.raises(InkContractMismatch, match="PHYSICAL_INK_OR_NET_DRIFT"):
        check(original, candidate)


def test_distinct_platform_text_metric_width_can_change_not_anchor(original):
    actual = copy.deepcopy(original)
    actual["recon_exact_sha"] = "a" * 40
    for name in ("control", "moved_R2_Y_2p5_C1_Y_2p5"):
        guard = actual[name]["actual_PAINT_TypeA_text_guards"][0]
        # A known form of Windows/Linux font-metric differences: new
        # extent is measured, but its original text anchor is preserved.
        guard["collision_box_um"][1] += 21
        guard["collision_box_um"][3] -= 21
    result = check(original, actual)
    assert result["type_a_os_specific_box_variations"] == 2
    assert result["physical_1um_coordinate_tolerance"] == 0


def test_text_is_not_allowed_to_move_one_micrometre(original):
    actual = copy.deepcopy(original)
    for name in ("control", "moved_R2_Y_2p5_C1_Y_2p5"):
        rect = actual[name]["actual_PAINT_TypeA_text_guards"][0][
            "collision_box_um"
        ]
        rect[0] += 1
        rect[2] += 1
    with pytest.raises(InkContractMismatch, match="TEXT_ANCHOR_1UM_DRIFT"):
        check(original, actual)


def test_text_identity_owner_is_not_waived(original):
    actual = copy.deepcopy(original)
    actual["control"]["actual_PAINT_TypeA_text_guards"][0]["owner"] = "OTHER"
    with pytest.raises(InkContractMismatch, match="TEXT_IDENTITY_DRIFT"):
        check(original, actual)


def test_text_frame_fit_cannot_be_forged(original):
    actual = copy.deepcopy(original)
    actual["moved_R2_Y_2p5_C1_Y_2p5"][
        "project_10mm_text_collision_frame_fit"
    ] = False
    with pytest.raises(InkContractMismatch, match="TEXT_FRAME_FIT_FORGED"):
        check(original, actual)


def test_unknown_text_collision_box_is_blocked(original):
    actual = copy.deepcopy(original)
    actual["control"]["actual_PAINT_TypeA_text_guards"][0][
        "collision_box_um"
    ] = None
    with pytest.raises(InkContractMismatch, match="INVALID_MEASURED_BOX"):
        check(original, actual)


def test_source_sha_or_font_sha_cannot_be_changed(original):
    for field in ("source_reference_sha", "font_type_a_sha256"):
        actual = copy.deepcopy(original)
        actual[field] = "a" * 40
        with pytest.raises(InkContractMismatch):
            check(original, actual)


def test_source_symbol_ink_obstacle_one_micrometre_is_rejected(original):
    actual = copy.deepcopy(original)
    actual["control"]["parts"]["VD1"][
        "individual_stroked_primitives_um"
    ][0]["conservative_box_um"][0] += 1
    with pytest.raises(InkContractMismatch, match="PHYSICAL_INK_OR_NET_DRIFT"):
        check(original, actual)
