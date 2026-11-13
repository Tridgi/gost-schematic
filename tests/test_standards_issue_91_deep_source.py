"""Issue #91 deep source crosschecks: explicitly bounded GOST conclusions.

These tests deliberately prove norm/source traceability and block false approval.
They never import other contributors' production branches or call rendering code.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = ROOT / "docs/standards"
BASE = STANDARDS / "issue-91-cycle7-electronics-cards.json"
DEEP = STANDARDS / "issue-91-deep-source-audit.json"
REPORT = STANDARDS / "issue-91-deep-primary-audit.md"


def _base():
    return json.loads(BASE.read_text(encoding="utf-8"))


def _deep():
    return json.loads(DEEP.read_text(encoding="utf-8"))


def _rules():
    return {x["id"]: x for x in _deep()["rules"]}


def test_base_107_and_pinned_12_from_issue_27_still_intact():
    base = _base()
    assert len(base["cards"]) == 107
    assert base["preexisting_reused"]["sha"] == (
        "cbefb5178bbd8a03165f8aa4eb4e42f0fe59d5ec"
    )
    assert len(base["preexisting_reused"]["ids"]) == 12
    assert len(set(base["preexisting_reused"]["ids"])) == 12
    assert set(base["preexisting_reused"]["ids"]).isdisjoint(
        {c["id"] for c in base["cards"]}
    )
    assert all(c["approval"] == "DRAFT" for c in base["cards"])
    assert all(c["acceptance"] == "BLOCKED" for c in base["cards"])
    assert base["stats"]["approved_ugos"] == 0


def test_deep_revision_makes_no_all_ugo_approval_claim():
    audit = _deep()
    assert audit["issue"] == 91
    assert audit["baseline_card_count"] == 107
    assert audit["reused_issue27_count"] == 12
    assert audit["totals"]["product_approved"] == 0
    assert len(audit["rules"]) >= 50
    assert len({r["id"] for r in audit["rules"]}) == len(audit["rules"])
    assert set(Counter(r["status"] for r in audit["rules"])) <= {
        "PASS", "FAIL", "BLOCKED"
    }
    assert all(r["product_approval"] == "DRAFT_ONLY" for r in audit["rules"])


def test_text_vertical_is_profile_scoped_not_generic_function_rotation():
    d = _rules()
    assert d["IC-FIG3-A"]["status"] == "PASS"
    assert d["IC-FIG3-B"]["status"] == "PASS"
    assert d["IC-FIG4"]["status"] == "PASS"
    assert d["IC-ONLY-FUNCTION-90"]["status"] == "BLOCKED"
    assert "rotate_function_text_only" in d[
        "IC-ONLY-FUNCTION-90"
    ]["acceptance_or_negative"]
    assert d["IC-ROLE-LABEL-ROTATE"]["status"] == "BLOCKED"
    assert "2.1.6" in d["IC-FIG3-B"]["clause"]
    assert "черт.3" in d["IC-FIG3-A"]["clause"]


def test_ic_fig4_reverse_requires_arrows_and_function_semantics():
    rule = _rules()["IC-FIG4"]
    assert "arrows" in rule["observed_source_rule"]
    assert "function" in rule["observed_source_rule"]
    assert "reversed" in rule["acceptance_or_negative"]


@pytest.mark.parametrize("physical_pins", [4, 8, 14, 40, 64])
def test_synthetic_4_8_14_40_64_acceptance_is_size_scoped(physical_pins):
    case = next(
        x for x in _deep()["per_variant_pin_matrix"]
        if x["count"] == physical_pins
    )
    assert case["case"] == f"TEST_IC_{physical_pins}"
    assert case["negative"]
    assert case["status"].startswith(("PASS_DRAFT_", "BLOCKED_"))


def test_module_m_relative_and_actual_font_transition_year():
    d = _rules()
    assert ">=2M" in d["IC-MODULAR-M"]["observed_source_rule"]
    assert d["IC-MODULAR-M"]["status"] == "PASS"
    assert d["IC-CHAR-HARDCAP"]["status"] == "FAIL"
    f = next(s for s in _deep()["primary_sources"]
             if s["standard"] == "ГОСТ 2.304-81")
    assert f["applied_as_of"] == "2026-11-14"
    assert f["successor_start"] == "2027-10-01"


def test_corrections_mark_primitive_effect_and_typical_bridge_not_finished_part():
    base = {c["id"]: c for c in _base()["cards"]}
    for sid in (
        "diode.avalanche",
        "diode.bidirectional_avalanche",
        "semiconductor.bridge_full",
        "semiconductor.bridge_compact",
    ):
        c = base[sid]
        assert c["normative_rule_status"] == "BLOCKED"
        assert c["deep_audit_2026_11_14"]["status"] == "BLOCKED_SOURCE_SCOPE"
        assert c["approval"] == "DRAFT"
    assert _base()["stats"]["source_scope_blocked"] == 4


def test_variable_resistor_unused_pin_may_be_omitted_visually_but_not_physically():
    rule = _rules()["RES-UNUSED-PIN-OMIT"]
    assert rule["status"] == "PASS"
    assert "MAY NOT BE DRAWN" in rule["observed_source_rule"]
    c = next(x for x in _base()["cards"] if x["id"] == "resistor.variable")
    assert any("physical PinRef not deleted" in x for x in c["positive_cases"])
    assert "tab1" not in c["physical_contacts"]["numbering"].lower()


def test_general_fuse_is_not_spark_gap():
    a = _rules()["FUSE-POS2"]
    assert a["status"] == "PASS"
    assert "table3 pos2" in a["clause"]
    assert "pos1" in a["observed_source_rule"]


def test_shielded_npn_not_a_generic_npn_and_mos_gate_is_isolated():
    d = _rules()
    assert d["SEM-PNP-NPN-SHIELD"]["status"] == "PASS"
    assert d["SEM-GENERIC-NPN"]["status"] == "BLOCKED"
    assert "G-channel" in d["SEM-MOS-CHANNEL"]["acceptance_or_negative"]
    assert d["SEM-MOS-BODY"]["status"] == "PASS"
    assert d["SEM-LED-PHOTO"]["status"] == "PASS"


def test_recipient_addresses_not_just_sheet_coordinate_strings():
    d = _rules()
    assert d["NET-ADDRESS-RECIPROCAL"]["status"] == "PASS"
    assert d["NET-MIXED"]["status"] == "PASS"
    assert d["NET-SHEETZONE-ONLY"]["status"] == "BLOCKED"
    assert "A7:X16" in d["NET-ADDRESS-RECIPROCAL"]["acceptance_or_negative"]
    assert "arrow" in d["NET-BREAK-X"]["observed_source_rule"]
    assert "arrow" not in d["NET-NAME-LOCATION"]["acceptance_or_negative"]


def test_green_ui_does_not_appear_as_gost_printed_circuit_marking():
    d = _rules()
    assert d["UX-GREEN-CLEAN"]["status"] == "FAIL"
    assert d["UX-DIAGNOSTIC"]["status"] == "PASS"
    assert "clean export" in d["UX-GREEN-CLEAN"]["acceptance_or_negative"]
    text = REPORT.read_text(encoding="utf-8")
    assert 'data-layer="editor-connection-targets"' in text
    assert "8–12 CSS px" in text


def test_source_scopes_cover_all_required_families_and_no_extra_files():
    d = _deep()
    texts = {x["standard"] for x in d["primary_sources"]}
    for name in (
        "ГОСТ 2.743-91", "ГОСТ 2.759-82", "ГОСТ 2.730-73",
        "ГОСТ 2.728-74", "ГОСТ 2.727-68", "ГОСТ 2.755-87",
        "ГОСТ 2.721-74", "ГОСТ 2.709-89", "ГОСТ 2.702-2011",
        "ГОСТ 2.710-81", "ГОСТ 2.304-81", "ГОСТ 2.701-2008",
    ):
        assert name in texts
    assert len(d["exceptions_for_legacy_107"]) >= 10
    assert set(d["owner_handoffs"]) == {
        "PAINT93", "ELEKTRIK97", "YGO94", "QA99"
    }


def test_nonnormative_glyph_ink_px_and_1to1_remain_blocked():
    report = REPORT.read_text(encoding="utf-8")
    assert "самостоятельный режим" not in report or "BLOCKED" in report
    assert "1:1" in report
    assert "SOT-23" in report
    assert "не являются" in report
