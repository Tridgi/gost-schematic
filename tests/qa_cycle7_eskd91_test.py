"""QA #92 independent verification of real ESKD #91 *source-card metadata*.

A source citation and an SVG comparison sheet are NOT a normative signoff.
These tests prove status/provenance/coverage correctness on an immutable
real owner document; independent 1:1 UGO approval remains BLOCKED.
"""
import json
from hashlib import sha1
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent / "fixtures/qa_cycle7_eskd91"
EXPECTED_BLOBS = {
    "cards.json": "4f31d9e24cb097c6c9e38263c0bea1d793acaae7",
    "discrete-editorial.svg": "02434949edac92d8cccefdbfd2fe8ae68949c53f",
    "ic-synthetic-4-14-40.svg": "67b94ce65de9b79aab45381a9a0d4aafb37a4ffc",
}


def test_eskd91_cards_are_actual_sha_pinned_source_with_zero_false_approvals():
    for name, digest in EXPECTED_BLOBS.items():
        content = (ROOT / name).read_bytes()
        blob = sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content
        ).hexdigest()
        assert blob == digest
    data = json.loads((ROOT / "cards.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert (data["issue"], data["epic"]) == (91, 86)
    cards = data["cards"]
    assert len(cards) == data["stats"]["new_cards"] == 107
    assert len({c["id"] for c in cards}) == len(cards)
    assert data["stats"]["approved_ugos"] == 0
    assert data["stats"]["per_variant_acceptance_blocked"] == 107
    assert sum(data["stats"]["by_family"].values()) == 107
    assert len(data["preexisting_reused"]["ids"]) == 12
    assert not set(data["preexisting_reused"]["ids"]) & {
        c["id"] for c in cards
    }
    assert all(c["approval"] == "DRAFT" for c in cards)
    assert all(c["acceptance"] == "BLOCKED" for c in cards)
    # 107 PASS means the **source rule identified**, not that 107 new
    # symbols were rendered or vetted. This is essential for release safety.
    assert all(c["normative_rule_status"] == "PASS" for c in cards)
    assert all(c["blocking_evidence"] for c in cards)
    assert all("protect.gost.ru" in c["source_official"] for c in cards)
    assert all(c["clause_and_figure"] for c in cards)
    guardrails = {c["id"] for c in data["critical_fail_guardrails"]}
    assert {
        "F91-IC-NUMBERS",
        "F91-FUSE-TABLE",
        "F91-NPN-SCREEN",
        "F91-CHAR-LIMIT",
        "F91-PLUG-OFFPAGE",
    } <= guardrails


def test_eskd91_comparison_drawings_are_real_svg_but_not_approved_catalog():
    for name in ("discrete-editorial.svg", "ic-synthetic-4-14-40.svg"):
        root = ET.fromstring((ROOT / name).read_text(encoding="utf-8"))
        assert root.tag.endswith("svg")
        assert root.findall(".//{http://www.w3.org/2000/svg}text")
        assert not root.findall(".//{http://www.w3.org/2000/svg}image")
    # Source sketches are evidence only, NOT production SVG/PNG of real ICs.
