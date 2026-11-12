"""Issue #27: documentary evidence gates for proposed semiconductor/contact UGO.

This guards source traceability and refusal to infer certification.
It does not validate vector outlines, physical pinouts or GOST approval.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

STANDARDS_DIR = Path(__file__).resolve().parents[1] / "docs" / "standards"
CARDS_PATH = STANDARDS_DIR / "issue-27-semiconductor-switch-cards.json"
REPORT_PATH = STANDARDS_DIR / "issue-27-next-families.md"

EXPECTED = {
    "diode.general",
    "diode.zener",
    "diode.schottky",
    "diode.led",
    "diode.photodiode",
    "transistor.bjt_pnp",
    "transistor.bjt_npn",
    "transistor.mosfet_n_enh",
    "transistor.mosfet_p_enh",
    "contact.no",
    "contact.nc",
    "contact.changeover",
}


def _evidence():
    return json.loads(CARDS_PATH.read_text(encoding="utf-8"))


def _by_id():
    return {card["id"]: card for card in _evidence()["cards"]}


def test_source_and_baseline_are_explicit():
    data = _evidence()
    assert data["schema_version"] == 1
    assert data["issue"] == 27
    assert data["baseline_sha"] == "840576d31ac7ff201fe64144c273e3aefbb1ab83"
    assert data["jurisdiction"] == "RU"
    assert data["review_status"] == "PROPOSED_UNAPPROVED"
    assert set(data["standards"]) == {"GOST-2.730-73", "GOST-2.755-87"}
    for source in data["standards"].values():
        assert source["official_url"].startswith("https://protect.gost.ru/gost/details/")
        assert source["public_figure_pdf"].endswith(".pdf")
        assert source["figures_verified_by_pdf_screenshot"]
        assert "справочн" in source["size_reference"] + source["dimensional_scope"]


def test_twelve_independent_ugo_cards_and_family_balance():
    data = _evidence()
    cards = data["cards"]
    assert len(cards) == len(EXPECTED) == 12
    assert {c["id"] for c in cards} == EXPECTED
    assert Counter(c["group"] for c in cards) == {
        "diode": 5,
        "transistor": 4,
        "contact": 3,
    }
    for c in cards:
        assert c["priority"] in {"P0", "P1", "P2"}
        assert c["status"] == "DRAFT"
        assert c["acceptance"] == "BLOCKED"
        assert c["standard"] in data["standards"]
        assert c["source"] == data["standards"][c["standard"]]["public_figure_pdf"]
        assert c["pdf_pages_1_based"]
        assert c["clause_and_figure"]
        assert c["source_relation"] in {
            "direct_table_example",
            "direct_basic_contact",
            "conditional_composition",
        }
        roles = c["terminals"]["roles"]
        ids = c["terminals"]["proposed_ids"]
        assert len(roles) == len(ids) == len(set(ids)) == len(set(roles))
        assert c["terminals"]["numbering_source"] == "project_only_not_gost_or_datasheet"
        assert "мм НЕ определены" in c["dimensional_evidence"]
        assert len(c["negative_cases"]) >= 2
        assert len(c["manual_approval_needed"]) >= 4


def test_no_fabricated_normative_millimetre_or_premature_approval():
    data = _evidence()
    for c in data["cards"]:
        assert "normative_mm" not in c
        assert c["status"] != "APPROVED"
        assert c["acceptance"] != "PASS_MANUAL"
    report = REPORT_PATH.read_text(encoding="utf-8")
    for phrase in ("19 DRAFT", "модуль", "BLOCKED", "КОМПАС", "ГОСТ 2.702-2011"):
        assert phrase in report


@pytest.mark.parametrize(("symbol", "roles"), [
    ("diode.general", ["A", "K"]),
    ("diode.led", ["A", "K"]),
    ("diode.photodiode", ["A", "K"]),
    ("transistor.bjt_npn", ["B", "C", "E"]),
    ("transistor.mosfet_n_enh", ["G", "D", "S"]),
    ("contact.no", ["COM", "NO"]),
    ("contact.nc", ["COM", "NC"]),
    ("contact.changeover", ["COM", "NC", "NO"]),
])
def test_physical_pin_roles_are_explicit_and_not_guessed_numbers(symbol, roles):
    card = _by_id()[symbol]
    assert card["terminals"]["roles"] == roles
    assert "project_only" in card["terminals"]["numbering_source"]


def test_npn_screen_and_printing_regime_not_misrepresented():
    c = _by_id()["transistor.bjt_npn"]
    assert c["source_relation"] == "conditional_composition"
    assert "экран" in c["graphic_evidence"]
    assert "табл.13" in c["clause_and_figure"]
    assert "7/1б" in REPORT_PATH.read_text(encoding="utf-8")


def test_optical_arrows_are_opposite_and_nonconducting():
    led, detector = _by_id()["diode.led"], _by_id()["diode.photodiode"]
    assert "излучения наружу" in led["graphic_evidence"]
    assert "направленными к диоду" in detector["graphic_evidence"]
    assert "не являются контактами" in led["graphic_evidence"]
    assert "оптическая стрелка стала электрическим выводом" in detector["negative_cases"]


def test_mos_gate_and_contact_initial_state_are_preserved():
    data = _by_id()
    for name in ("transistor.mosfet_n_enh", "transistor.mosfet_p_enh"):
        assert "G" in data[name]["terminals"]["roles"]
        assert "без вывода подложки" in data[name]["title"]
        assert any("G" in case for case in data[name]["negative_cases"])
    assert "разомкнут" in data["contact.no"]["graphic_evidence"]
    assert "замкнут" in data["contact.nc"]["graphic_evidence"]
    assert "одним неподвижным" in data["contact.changeover"]["graphic_evidence"]


def test_every_card_appears_in_readable_report():
    report = REPORT_PATH.read_text(encoding="utf-8")
    for symbol_id in EXPECTED:
        assert "`" + symbol_id + "`" in report
