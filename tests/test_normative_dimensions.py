"""Evidence-scoped GOST dimensional tests; other UGO remain draft."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Box, Line, Point, Rectangle
from gost_schematic.validation.dimensional_checks import (
    check_verified_dimensions,
    load_requirements,
)
from scripts.audit_symbol_catalog import audit_catalog


def _symbol(path):
    root = files("gost_schematic").joinpath("catalog/symbols")
    return load_symbol(Path(str(root.joinpath(path))))


def test_source_registry_holds_current_and_future_effective_dates():
    rules = load_requirements()
    assert rules["profile_id"] == "eskd-ru-2026-11"
    assert rules["jurisdiction"] == "RU"
    assert all(
        item["effective_on"] == "2027-10-01"
        and item["early_application_permitted"]
        for item in rules["pending_standards"]
    )
    assert {
        item["id"] for item in rules["dimensional_rules"]
    } == {"ESKD-2728-R-FIXED-10x4", "ESKD-2728-C-PLATES-8-1.5"}
    assert all(item["source"].startswith("https://") for item in rules["dimensional_rules"])


@pytest.mark.parametrize(
    ("path", "id_rule"),
    [
        ("resistors/fixed.json", "ESKD-2728-R-FIXED-10x4"),
        ("capacitors/fixed.json", "ESKD-2728-C-PLATES-8-1.5"),
        ("capacitors/polarized.json", "ESKD-2728-C-PLATES-8-1.5"),
    ],
)
def test_three_symbols_pass_explicitly_checked_gost_dimensions(path, id_rule):
    result = check_verified_dimensions(_symbol(path))
    assert result.valid
    assert result.passed_rules == (id_rule,)


def test_resistor_body_length_change_fails_normative_dimension_rule():
    symbol = _symbol("resistors/fixed.json")
    shapes = (Rectangle(Box(-4500, -2000, 5000, 2000)), *symbol.graphics[1:])
    result = check_verified_dimensions(replace(symbol, graphics=shapes))
    assert {issue.code for issue in result.diagnostics} == {
        "NORMATIVE_DIMENSION_MISMATCH"
    }


def test_wrong_capacitor_plate_length_or_gap_fails_normative_rule():
    symbol = _symbol("capacitors/fixed.json")
    wrong_length = (*symbol.graphics[:2], Line(Point(-750, -3500), Point(-750, 4000)),
                    symbol.graphics[3])
    wrong_gap = (*symbol.graphics[:2],
                 Line(Point(-850, -4000), Point(-850, 4000)),
                 symbol.graphics[3])
    for graphics in (wrong_length, wrong_gap):
        result = check_verified_dimensions(replace(symbol, graphics=graphics))
        assert "NORMATIVE_DIMENSION_MISMATCH" in {
            issue.code for issue in result.diagnostics
        }


def test_coils_have_no_invented_fixed_dimensions():
    root = files("gost_schematic").joinpath("catalog/inductors")
    built = load_inductor(Path(str(root.joinpath("inductor.air_core.json"))))
    result = check_verified_dimensions(built.symbol)
    assert result.applicable_rules == ()
    assert result.passed_rules == ()
    assert result.valid


def test_catalog_audit_does_not_mark_all_coils_dimension_certified():
    result = audit_catalog()
    assert result["total_symbols"] == 19
    assert result["topologies_verified"] == 19
    assert result["symbols_with_checked_dimensions"] == 3
    assert result["hard_errors"] == 0
    assert len([
        e for e in result["entries"]
        if e["dimension_status"] == "not_yet_verifiable"
    ]) == 16



def test_two_correct_length_capacitor_plates_do_not_pass_when_staggered():
    symbol = _symbol("capacitors/fixed.json")
    shapes = list(symbol.graphics)
    shapes[3] = Line(Point(750, -3000), Point(750, 5000))
    result = check_verified_dimensions(replace(symbol, graphics=tuple(shapes)))
    assert "NORMATIVE_DIMENSION_MISMATCH" in {
        issue.code for issue in result.diagnostics
    }


def test_correct_plate_dimensions_do_not_hide_missing_center_lead():
    symbol = _symbol("capacitors/fixed.json")
    shapes = list(symbol.graphics)
    shapes[1] = Line(Point(750, 1000), Point(8000, 1000))
    assert "NORMATIVE_DIMENSION_MISMATCH" in {
        issue.code for issue in check_verified_dimensions(
            replace(symbol, graphics=tuple(shapes))
        ).diagnostics
    }


def test_fixed_resistor_cannot_hide_an_oversize_second_body():
    symbol = _symbol("resistors/fixed.json")
    big = Rectangle(Box(-6000, -3000, 6000, 3000))
    assert "NORMATIVE_DIMENSION_MISMATCH" in {
        issue.code for issue in check_verified_dimensions(
            replace(symbol, graphics=(big, *symbol.graphics))
        ).diagnostics
    }
