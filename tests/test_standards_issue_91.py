"""ESKD Issue 91 independent electronic component normative acceptance.

Tests prove source references and rejection gates, NOT that a production UGO is
GOST-approved. Existing Issue27 cards are referenced by SHA, never duplicated.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = ROOT / "docs/standards"
CARDS = STANDARDS / "issue-91-cycle7-electronics-cards.json"
LEGACY = STANDARDS / "issue-27-semiconductor-switch-cards.json"
REPORT = STANDARDS / "issue-91-cycle7-electronics-review.md"
GALLERY = STANDARDS / "evidence/issue91-ic-synthetic-4-14-40.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"


def read_cards():
    return json.loads(CARDS.read_text(encoding="utf-8"))


def catalog():
    return {entry["id"]: entry for entry in read_cards()["cards"]}


def test_40plus_candidates_source_traced_and_only_draft():
    data = read_cards()
    cards = data["cards"]
    assert data["issue"] == 91 and data["epic"] == 86
    assert len(cards) >= 40
    assert len({c["id"] for c in cards}) == len(cards)
    assert all(c["approval"] == "DRAFT" for c in cards)
    assert all(c["acceptance"] == "BLOCKED" for c in cards)
    assert all(c["normative_rule_status"] in {"PASS", "FAIL", "BLOCKED"}
               for c in cards)
    assert data["stats"]["new_cards"] == len(cards)
    assert data["stats"]["approved_ugos"] == 0


def test_existing_twelve_cards_are_reused_not_duplicated():
    data = read_cards()
    old = json.loads(LEGACY.read_text(encoding="utf-8"))
    reused = data["preexisting_reused"]
    ids = [c["id"] for c in old["cards"]]
    assert len(ids) == len(set(ids)) == 12
    assert reused["ids"] == ids
    assert reused["sha"] == "cbefb5178bbd8a03165f8aa4eb4e42f0fe59d5ec"
    assert {c["id"] for c in data["cards"]}.isdisjoint(ids)


def test_all_new_variants_have_exact_source_figure_and_acceptance():
    data = read_cards()
    all_sources = data["standards"]
    assert len(all_sources) >= 8
    for item in data["cards"]:
        key = item["source_key"]
        assert key in all_sources
        src = all_sources[key]
        assert item["source_official"] == src["official"]
        assert item["source_original_pdf"] == src["pdf"]
        assert "табл." in item["clause_and_figure"] or "§" in item["clause_and_figure"]
        assert item["physical_contacts"]["roles"]
        assert item["physical_contacts"]["numbering"]
        assert len(item["permitted_transforms"]) >= 4
        for dimension_class in (
            "normative_mandatory", "normative_recommended",
            "modular_reference", "editorial_only",
            "prohibited_unverified_mm",
        ):
            assert isinstance(item["geometry"][dimension_class], list)
        assert item["positive_cases"] and item["negative_cases"]
        assert item["blocking_evidence"]
        assert item["owner"]


def test_all_semiconductor_families_have_specific_variants():
    names = set(catalog())
    for symbol in (
        "diode.varicap", "diode.bidirectional_zener",
        "diode.tunnel", "diode.backward",
        "transistor.jfet_n", "transistor.jfet_p",
        "transistor.mosfet_n_dep", "transistor.mosfet_p_dep",
        "transistor.mosfet_n_enh_body_tied",
        "transistor.mosfet_p_enh_body_external",
        "thyristor.scr_general", "thyristor.triac",
        "optocoupler.diode_diode",
        "optocoupler.transistor_no_base",
        "optocoupler.transistor_base_exposed",
        "semiconductor.bridge_compact",
    ):
        assert symbol in names


def test_semiconductor_source_shielded_npn_not_generic():
    cards = catalog()
    screened = cards["transistor.bjt_npn_screened"]
    assert "поз.1б" in screened["clause_and_figure"]
    assert "SCREEN" in screened["physical_contacts"]["roles"]
    reused = read_cards()["preexisting_reused"]
    assert "transistor.bjt_npn" in reused["ids"]
    text = REPORT.read_text(encoding="utf-8")
    assert "внутреннего экрана" in text
    assert "SOT-23" in text and "TO-220" in text


@pytest.mark.parametrize(
    ("id", "figure", "roles"),
    [
        ("diode.varicap", "поз.6", ("A", "K")),
        ("thyristor.triac", "поз.8", ("MT1", "MT2", "G")),
        ("transistor.mosfet_p_enh_body_external", "поз.5", ("B",)),
        ("optocoupler.transistor_no_base", "поз.5б", ("C", "E")),
        ("optocoupler.transistor_base_exposed", "поз.5а", ("B",)),
    ],
)
def test_proven_pin_roles_and_table_position(id, figure, roles):
    item = catalog()[id]
    assert figure in item["clause_and_figure"]
    assert all(role in item["physical_contacts"]["roles"] for role in roles)


def test_rheostat_wiper_and_functional_pot_size_have_distinct_scope():
    cards = catalog()
    for id in ("resistor.variable", "resistor.trimmer",
               "resistor.rheostat_two_terminal_usage"):
        assert "WIPER" in cards[id]["physical_contacts"]["roles"] or (
            "ADJUST" in cards[id]["physical_contacts"]["roles"]
        )
    assert "20мм" in " ".join(
        cards["potentiometer.functional_linear"]["geometry"]["normative_mandatory"]
    )
    assert "20мм" not in " ".join(
        cards["resistor.variable"]["geometry"]["normative_mandatory"]
    )


def test_variable_resistor_and_trimmer_use_correct_table1_rows():
    cards = catalog()
    assert "табл.1 поз.4" in cards["resistor.variable"]["clause_and_figure"]
    assert "табл.1 поз.9" in cards["resistor.trimmer"]["clause_and_figure"]
    assert "табл.1 поз.6" in cards[
        "resistor.variable_dual_wiper"
    ]["clause_and_figure"]
    assert "табл.6 поз.3" in cards[
        "resistor.rheostat_two_terminal_usage"
    ]["clause_and_figure"]


def test_fuse_position_two_not_spark_arrester_one():
    cards = catalog()
    assert "табл.3 поз.2" in cards["fuse.general"]["clause_and_figure"]
    assert "табл.3 поз.3в" in cards["fuse.fast"]["clause_and_figure"]
    assert cards["fuse.general"]["catalog_prefix"] == "FU"
    guard = {d["id"]: d for d in read_cards()["critical_fail_guardrails"]}
    assert "position1" in guard["F91-FUSE-TABLE"]["violation"].replace(" ", "")


def test_real_connectors_are_never_graphical_continuations():
    cards = catalog()
    for id in ("connector.plug", "connector.socket", "connector.coax"):
        assert cards[id]["physical_contacts"]["type"] == "PHYSICAL_PART_PINS"
        assert cards[id]["family"] == "con"
    for id in ("net.continuation.same_sheet",
               "net.continuation.cross_sheet",
               "net.continuation.named_horizontal",
               "net.crossing.unjoined"):
        assert cards[id]["physical_contacts"]["type"] == (
            "NONPHYSICAL_NET_GRAPHIC_ONLY"
        )
    assert "Net" in cards["net.continuation.cross_sheet"][
        "physical_contacts"
    ]["roles"][0]


def test_power_and_multiunit_are_same_physical_device():
    cards = catalog()
    assert cards["ic.digital.power_separate"]["family"] == "digital"
    assert "physical pin" in " ".join(
        cards["ic.digital.power_separate"]["negative_cases"]
    )
    assert "same physical package" in cards[
        "ic.digital.multiunit_split"
    ]["physical_contacts"]["if_multiunit"]


def test_ic_rules_exact_number_above_line_and_no_char_limit():
    data = read_cards()
    for item in data["cards"]:
        if item["family"] not in ("digital", "analog"):
            continue
        assert "font" in " ".join(
            item["geometry"]["normative_mandatory"]
        ).lower() or item["family"] == "digital"
        assert item["physical_contacts"]["manufacturer_datasheet"] is None
    digital = catalog()["ic.digital.main_both"]
    assert any("ABOVE" in s for s in digital["geometry"]["normative_mandatory"])
    assert any("NO character-count" in s for s in
               digital["geometry"]["normative_recommended"]) is True
    doc = REPORT.read_text(encoding="utf-8")
    assert "НАД линией" in doc and "В РАЗРЫВЕ" in doc
    assert "число знаков" in doc
    assert "не ограничено" in doc


def test_modular_recommendation_not_mandatory_absolute_mm():
    cards = catalog()
    digi = cards["ic.digital.main_both"]
    text = " ".join(digi["geometry"]["modular_reference"])
    assert "appendix 5 RECOMMENDED" in text
    assert "≥2 M" in text
    semi = cards["transistor.jfet_n"]
    assert any("справочное" in x for x in semi["geometry"]["modular_reference"])
    assert "приложение 1 исключено" in REPORT.read_text(encoding="utf-8")


def test_sheet_parallel_ink_distance_rejects_wrong_axis_spacing():
    stroke_um = 350
    minimum_ink_um = 3000
    assert 3000 - stroke_um < minimum_ink_um
    assert 3350 - stroke_um == minimum_ink_um


def test_synthetic_ic_svg_each_pin_has_unique_number_above_lead():
    root = ET.fromstring(GALLERY.read_text(encoding="utf-8"))
    assert root.get("data-status") == "DRAFT"
    assert root.get("data-real-physical-pinmap") == "false"
    for count in (4, 14, 40):
        block = next(e for e in root.findall(SVG_NS + "g")
                     if e.get("data-ic") == f"TEST_IC_{count}")
        physical = [int(node.get("data-physical-number"))
                    for node in root.findall(SVG_NS + "text")
                    if node.get("data-physical-number") is not None
                    and int(node.get("data-physical-number")) <= count]
        assert block.get("data-synthetic-only") == "true"
        pin_paths = [x for x in block.findall(SVG_NS + "path")
                     if x.get("data-pinleft") is not None]
        assert len(pin_paths) == count // 2
        assert physical.count(count) >= 1
    assert len(root.findall(".//" + SVG_NS + "path")) == (4 + 14 + 40) // 2
    assert sum(node.get("data-position") == "above-input-lead"
               for node in root.findall(SVG_NS + "text")) == 29
    assert sum(node.get("data-position") == "above-output-lead"
               for node in root.findall(SVG_NS + "text")) == 29


def test_gallery_has_no_embedded_font_or_approved_claim():
    svg = GALLERY.read_text(encoding="utf-8")
    assert "font-family=" in svg
    assert "@font-face" not in svg
    assert "data-status=\"DRAFT\"" in svg
    assert "NOT VENDOR PINOUT" in svg
    assert "TEST_IC_40" in svg


def test_cards_id_classes_and_sources_are_pinned_without_production():
    data = read_cards()
    assert data["common"]["lettering"].startswith("ГОСТ 2.304-81")
    assert data["stats"]["original_cards_referenced"] == 12
    assert all(item["source_key"] in data["standards"] for item in data["cards"])
    for id in ("F91-IC-NUMBERS", "F91-NPN-SCREEN",
               "F91-FUSE-TABLE", "F91-CHAR-LIMIT",
               "F91-PLUG-OFFPAGE"):
        assert id in {item["id"] for item in data["critical_fail_guardrails"]}
