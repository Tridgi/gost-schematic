"""Issue 91 independent power-supply source matrix and overlay regression.

Documentation-only: verifies normative source pinning and editorial evidence,
not the unmerged production PAINT/ELEKTRIK renderers or GOST certification.
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
STANDARD = ROOT / "docs/standards"
MATRIX = STANDARD / "issue91-ic-power-and-editor-overlays-matrix.json"
REPORT = STANDARD / "issue91-power-pin-and-pwm-post101-review.md"
EXAMPLES = STANDARD / "evidence"
SVG = "{http://www.w3.org/2000/svg}"


def _matrix():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def _cards():
    return {item["id"]: item for item in _matrix()["cases"]}


def _svg(name):
    path = EXAMPLES / ("issue91-power-hotspot-" + name + "-illustration.svg")
    return ET.fromstring(path.read_text(encoding="utf-8"))


def test_new_branch_based_on_merged_95_and_101_without_approval():
    evidence = _matrix()
    assert evidence["base_sha"] == "1cdd11a3e72e467573d5d660db923b201be21df9"
    assert evidence["previous_merged_prs_not_modified"] == [95, 101]
    assert evidence["normative_ugo_approvals"] == 0
    assert evidence["all_new_ugo_status"] == "DRAFT"


def test_matrix_has_full_source_and_each_positive_negative_example():
    cards = list(_cards().values())
    assert len(cards) == 19
    assert len({card["id"] for card in cards}) == len(cards)
    for card in cards:
        assert card["status"] in {"PASS", "FAIL", "BLOCKED"}
        assert card["clause"] and card["positive_example"]
        assert card["negative_example"] and card["primary_source"].startswith(
            "https://"
        )
        assert card["approved"] is False
    assert {card["group"] for card in cards} == {
        "power", "analog", "pwm", "ui"
    }


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("P01-LEFT", "PASS"),
        ("P02-RIGHT", "PASS"),
        ("P03-TOP-FIXED", "BLOCKED"),
        ("P04-BOTTOM-FIXED", "BLOCKED"),
        ("P05-WHOLE-ORIENTATION", "PASS"),
        ("P07-SEPARATE-CONTOUR", "PASS"),
        ("P08-SPLIT-ONE-UNIT", "PASS"),
        ("P09-TEXT-FREE-FIELD", "PASS"),
    ],
)
def test_exact_eight_power_placement_cases(name, status):
    card = _cards()[name]
    assert card["status"] == status
    assert card["mandatory"] and card["editorial"]


def test_fig6_a_b_c_and_document_set_policy_not_arbitrary():
    cards = _cards()
    assert cards["P06-COMMON-CONTROL"]["status"] == "PASS"
    assert cards["P10-FIG6-MIX-UNRESTRICTED"]["status"] == "FAIL"
    assert "6а+6б" in cards["P08-SPLIT-ONE-UNIT"]["mandatory"][0]
    assert "6a+6v" in cards["P07-SEPARATE-CONTOUR"]["mandatory"][0]
    assert "6б" in cards["P10-FIG6-MIX-UNRESTRICTED"][
        "negative_example"
    ]
    assert "6в" in cards["P10-FIG6-MIX-UNRESTRICTED"][
        "negative_example"
    ]


def test_power_right_is_explicit_nonlogical_not_mistaken_for_output():
    card = _cards()["P02-RIGHT"]
    assert "§2.1.4" in card["clause"]
    assert card["status"] == "PASS"
    assert "right" in card["editorial"][0].lower()


def test_analog_u_ov_not_zero_volts_and_pin_identity_is_explicit():
    d = _matrix()
    card = _cards()["P12-ANALOG-U-OV"]
    assert card["status"] == "PASS"
    assert card["standard"] == "ГОСТ 2.759-82"
    assert "OV" in card["positive_example"]
    assert "0V" in card["negative_example"]
    assert "#page=2" in d["sources"]["analog"]["table2"]
    assert _cards()["P13-PHYSICAL-PIN-NUMBERS"]["status"] == "PASS"


@pytest.mark.parametrize(
    ("angle", "status"),
    [(0, "PASS"), (90, "BLOCKED"), (270, "BLOCKED")],
)
def test_pwm_fixed_body_independent_function_orientation(angle, status):
    case = _cards()[f"PWM-{angle}"]
    assert case["status"] == status
    assert "§2.1" in case["clause"]
    assert case["approved"] is False


def test_origin_figures_exact_pages_and_separate_editorial_redraw():
    sources = _matrix()["sources"]
    digital = sources["digital"]
    assert digital["figure6"].endswith("#page=15")
    assert digital["orientation"].endswith("#page=4")
    assert digital["table5"].endswith("#page=13")
    assert digital["table5continued"].endswith("#page=14")
    drawing = ET.fromstring(
        (EXAMPLES / "issue91-fig6-editorial-interpretation.svg").read_text(
            encoding="utf-8"
        )
    )
    assert drawing.get("data-status") == "DRAFT_EDITORIAL_RECONSTRUCTION"
    assert drawing.get("data-primary-source") == digital["figure6"]


def test_clean_and_editor_examples_keep_identical_real_ink_and_pinrefs():
    clean, diagnostic = _svg("clean"), _svg("diagnostic")
    find = lambda root: next(
        x for x in root.findall(".//" + SVG + "g")
        if x.get("data-layer") == "physical-symbol-and-wires"
    )
    original_ink = ET.tostring(find(clean), encoding="unicode")
    reviewed_ink = ET.tostring(find(diagnostic), encoding="unicode")
    assert original_ink == reviewed_ink
    for root in (clean, diagnostic):
        assert root.get("data-physical-pinrefs") == "DD1.14 DD1.7"
        wires = root.findall(".//" + SVG + "path")
        assert len(wires) == 2
        assert {x.get("data-pin-ref") for x in wires} == {
            "DD1.14", "DD1.7"
        }


def test_editor_layer_only_opt_in_and_no_extra_physical_terminals():
    clean, diagnostic = _svg("clean"), _svg("diagnostic")
    clean_text = ET.tostring(clean, encoding="unicode")
    assert "editor-connection-targets" not in clean_text
    assert "#40a955" not in clean_text
    debug_layer = next(
        x for x in diagnostic.findall(".//" + SVG + "g")
        if x.get("data-layer") == "editor-connection-targets"
    )
    assert debug_layer.get("data-editor-only") == "true"
    assert debug_layer.get("data-connectivity-authoritative") == "false"
    items = debug_layer.findall(SVG + "rect")
    assert len(items) == 2
    assert {x.get("data-pin-ref") for x in items} == {
        "DD1.14", "DD1.7"
    }
    assert {x.get("data-actual-anchor-mm") for x in items} == {
        "12,14", "12,26"
    }


def test_report_explicit_source_not_fictional_dimensions():
    report = REPORT.read_text(encoding="utf-8")
    for marker in (
        "2.3.11", "чертёж 6", "2.1.4", "2.1.6",
        "2.759-82", "OV", "0V", "PWM", "270°",
        "GND", "NC", "DRAFT", "BLOCKED",
        "editor-connection-targets",
        "1cdd11a3e72e467573d5d660db923b201be21df9",
    ):
        assert marker in report
    assert "M=2500µm" in report
    assert "данные ГОСТ" not in report or "BLOCKED" in report
