"""Example is deterministic and demonstrates unknown vs reversed polarity clearly."""

import json

from examples.review_polarity_erc import build_report, main


def test_erc_review_shows_four_distinct_cases():
    report = build_report()
    assert report["physical_terminal_roles"] == {"1": "positive", "2": "negative"}
    cases = {item["case"]: item for item in report["cases"]}
    assert cases["forward"]["status"] == "forward"
    assert cases["forward"]["differential_volts"] == "12"
    assert cases["reversed"]["status"] == "reversed"
    assert cases["reversed"]["differential_volts"] == "-12"
    assert cases["reversed"]["diagnostics"] == [
        {"code": "POLARITY_REVERSED", "severity": "error"}
    ]
    assert cases["unknown"]["status"] == "unknown"
    assert cases["unknown"]["differential_volts"] is None
    assert cases["no_operating_point"]["status"] == "unknown"
    assert "startup" in report["warning"]


def test_example_writes_reviewable_json(tmp_path):
    output = tmp_path / "review.json"
    assert main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == build_report()
