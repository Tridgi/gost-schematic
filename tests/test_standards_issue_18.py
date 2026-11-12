"""Traceability and blocked-status guards for GOST inductor issue #18.

The tests verify normative evidence records and handoff obligations.
They are not automatic GOST-conformance or pixel-comparison tests.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = ROOT / "docs" / "standards"
CARDS = STANDARDS / "issue-18-rule-cards.json"
REPORT = STANDARDS / "issue-18-high-risk-inductors.md"
PREVIOUS_PROTOCOL = STANDARDS / "issue-11-review-protocol.md"

EXPECTED = {
    "inductor.double_tapped": "I18-TAPS2",
    "inductor.sliding_contact": "I18-SLIDER1",
    "inductor.double_sliding": "I18-SLIDER2",
    "inductor.trim_copper": "I18-CU-SOLID",
    "inductor.variable": "I18-VARIABLE",
}


def _cards():
    return json.loads(CARDS.read_text(encoding="utf-8"))


def test_issue18_is_five_independent_blocked_ugo_rule_cards():
    data = _cards()
    assert data["schema_version"] == 1
    assert data["issue"] == 18
    assert data["review_state"] == "BLOCKED"
    assert data["reference_baseline_sha"] == "9e9d056e410c8a54dc3c9fc9d5cc56b74e6f225b"
    records = data["rules"]
    assert len(records) == len(EXPECTED)
    assert {card["symbol_id"]: card["id"] for card in records} == EXPECTED
    for card in records:
        assert card["symbol_status"] == "DRAFT"
        assert card["review_state"] == "BLOCKED"
        assert card["normative_relation"] in {"table_2_example", "editorial_adaptation"}
        assert card["source_locations"]
        assert "ГОСТ 2.723-68" in " ".join(card["source_locations"])
        assert len(card["action"]) > 70
        assert len(card["catalog_observation"]) > 60


def test_issue18_sources_separate_official_status_from_pdf_figures():
    sources = _cards()["sources"]
    assert set(sources) == {"gost_2723", "gost_2721"}
    for value in sources.values():
        assert value["official_status"].startswith("https://protect.gost.ru/")
        assert value["figure_pdf"].startswith("https://")
        assert value["figure_pdf"].endswith(".pdf")
        assert value["amendments"]
    assert sources["gost_2723"]["table_2_pdf_page"] == 3
    assert sources["gost_2721"]["table_5_pdf_pages"] == [6, 7]


@pytest.mark.parametrize(("symbol_id", "expected_relation"), [
    ("inductor.double_tapped", "editorial_adaptation"),
    ("inductor.sliding_contact", "editorial_adaptation"),
    ("inductor.double_sliding", "table_2_example"),
    ("inductor.trim_copper", "table_2_example"),
    ("inductor.variable", "editorial_adaptation"),
])
def test_source_provenance_is_conservative(symbol_id, expected_relation):
    rule = next(r for r in _cards()["rules"] if r["symbol_id"] == symbol_id)
    assert rule["normative_relation"] == expected_relation
    assert rule["review_state"] == "BLOCKED"


def test_copper_stroke_repair_is_specific_and_does_not_conflate_material():
    rule = next(
        r for r in _cards()["rules"] if r["symbol_id"] == "inductor.trim_copper"
    )
    assert "2а" in " ".join(rule["source_locations"])
    assert "поз.7" in " ".join(rule["source_locations"])
    assert "dash_pattern" in rule["catalog_observation"]
    assert "непрерывным" in rule["action"]
    text = REPORT.read_text(encoding="utf-8")
    assert "CoreKind.NONMAGNETIC_COPPER" in text
    assert "CoreKind.MAGNETODIELECTRIC" in text
    assert "не электрический проводник" in text


@pytest.mark.parametrize("identifier", EXPECTED.values())
def test_each_rule_card_has_a_documented_rationale(identifier):
    text = REPORT.read_text(encoding="utf-8")
    assert f"Rule card {identifier}" in text


def test_known_ambiguities_and_electrolytic_form_correction_remain_explicit():
    text = REPORT.read_text(encoding="utf-8")
    for phrase in ("«или»", "например, двумя", "прим. 4", "BLOCKED", "DRAFT"):
        assert phrase in text
    previous = PREVIOUS_PROTOCOL.read_text(encoding="utf-8")
    assert "Для **катушек и дросселей**" in previous
    assert "Для **электролитического конденсатора** форма I/II не применяется" in previous
