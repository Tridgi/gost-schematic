"""Documentation evidence guards for issue #11 (non-certifying).

These checks catch missing traceability, source-mixups and silently dropped
profiles; they do not assert that the SVG geometry complies with GOST.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "standards"
INDUCTORS = DOCS / "issue-11-inductor-matrix.md"
ELECTROLYTIC = DOCS / "issue-11-electrolytic.md"
PROTOCOL = DOCS / "issue-11-review-protocol.md"

EXPECTED = {
    "inductor.air_core",
    "inductor.ferromagnetic",
    "inductor.gapped_core",
    "inductor.ferrite",
    "inductor.magnetodielectric",
    "inductor.trim_magnetodielectric",
    "inductor.trim_copper",
    "inductor.tapped",
    "inductor.double_tapped",
    "inductor.sliding_contact",
    "inductor.double_sliding",
    "inductor.variable",
    "choke.air_core",
    "choke.ferromagnetic",
    "choke.ferrite",
}
ROW_RE = re.compile(r"^\| `((?:inductor|choke)\.[a-z_]+)` \|")


def _matrix():
    rows = {}
    for line in INDUCTORS.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if match:
            name = match.group(1)
            assert name not in rows, f"Duplicate normative row: {name}"
            rows[name] = [item.strip() for item in line.strip("|").split("|")]
    return rows


def test_all_fifteen_profiles_have_distinct_evidence_rows():
    rows = _matrix()
    assert set(rows) == EXPECTED
    assert len(rows) == 15
    for name, columns in rows.items():
        assert len(columns) == 5, name
        assert "табл." in columns[2], name
        assert columns[1] in ("**P0**", "**P1**", "**P2**"), name
        assert columns[3] in ("**D**", "**C**", "**A**", "**U**"), name
        assert len(columns[4]) > 40, name


@pytest.mark.parametrize(
    ("name", "relation"),
    [
        ("inductor.double_tapped", "**A**"),
        ("inductor.sliding_contact", "**A**"),
        ("inductor.variable", "**U**"),
        ("inductor.double_sliding", "**D**"),
        ("inductor.trim_copper", "**D**"),
        ("choke.ferrite", "**C**"),
    ],
)
def test_high_risk_normative_classification_stays_conservative(name, relation):
    assert _matrix()[name][3] == relation


def test_matrix_totals_are_consistent():
    values = [cells[3] for cells in _matrix().values()]
    assert {kind: values.count(kind) for kind in ("**D**", "**C**", "**A**", "**U**")} == {
        "**D**": 8,
        "**C**": 4,
        "**A**": 2,
        "**U**": 1,
    }


def test_electrolytic_is_not_the_generic_polarized_symbol():
    content = ELECTROLYTIC.read_text(encoding="utf-8")
    for name in (
        "ГОСТ 2.728-74",
        "табл. 4",
        "табл. 6",
        "C-GEN",
        "C-EL-P",
        "C-EL-N",
        "C-PRINT",
        "C-DIM-EL",
        "capacitor.polarized",
        "BLOCKED",
    ):
        assert name in content
    dimension_row = next(line for line in content.splitlines() if line.startswith("| C-DIM-EL |"))
    assert "1,5" in dimension_row
    assert "8 мм" not in dimension_row


def test_review_protocol_requires_human_gates_and_official_sources():
    content = PROTOCOL.read_text(encoding="utf-8")
    for phrase in (
        "PASS_MANUAL",
        "REJECT",
        "BLOCKED",
        "КОМПАС",
        "source_sha256",
        "ГОСТ 2.304-81",
        "d=h/14",
        "01.10.2027",
        "ГОСТ 2.701-2008",
    ):
        assert phrase in content
    assert "не акт принятия" in content


def test_documentation_keeps_critical_symbols_unapproved():
    for path in (INDUCTORS, ELECTROLYTIC, PROTOCOL):
        text = path.read_text(encoding="utf-8")
        assert "DRAFT" in text, path
    assert "0** утверждены" in INDUCTORS.read_text(encoding="utf-8")
