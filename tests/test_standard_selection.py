"""Future-effective editions never silently activate on historical plans."""

from datetime import date

import pytest

from gost_schematic.standards.selection import resolve_standard_selection


def test_default_november_2026_keeps_active_font_and_line_standards():
    chosen = resolve_standard_selection(date(2026, 11, 12))
    assert chosen.profile_id == "eskd-ru-2026-11"
    assert chosen.jurisdiction == "RU"
    assert "ГОСТ 2.304-81" in chosen.applied
    assert "ГОСТ 2.303-68" in chosen.applied
    assert "ГОСТ Р 2.304-2026" not in chosen.applied
    assert len(chosen.future_pending) == 4
    assert chosen.early_applied == ()


def test_one_explicit_early_standard_replaces_only_its_predecessor():
    chosen = resolve_standard_selection(
        date(2026, 11, 12),
        early_adopt=("ГОСТ Р 2.304-2026",),
    )
    assert "ГОСТ Р 2.304-2026" in chosen.applied
    assert "ГОСТ 2.304-81" not in chosen.applied
    assert "ГОСТ 2.303-68" in chosen.applied
    assert chosen.early_applied == ("ГОСТ Р 2.304-2026",)
    assert len(chosen.future_pending) == 3


def test_effective_date_automatically_uses_new_editions_for_new_document():
    chosen = resolve_standard_selection(date(2027, 10, 1))
    assert len(chosen.future_pending) == 0
    assert chosen.early_applied == ()
    assert "ГОСТ Р 2.304-2026" in chosen.applied
    assert "ГОСТ Р 2.301-2026" in chosen.applied
    assert "ГОСТ Р 2.303-2026" in chosen.applied
    assert "ГОСТ Р 2.105-2026" in chosen.applied
    assert "ГОСТ 2.304-81" not in chosen.applied


def test_old_existing_document_retains_historical_profile():
    historic = resolve_standard_selection(date(2026, 11, 12))
    current = resolve_standard_selection(date(2027, 10, 1))
    assert "ГОСТ 2.304-81" in historic.applied
    assert "ГОСТ 2.304-81" not in current.applied


def test_invalid_explicit_standard_and_duplicate_selection_rejected():
    with pytest.raises(ValueError):
        resolve_standard_selection(
            date(2026, 11, 12), early_adopt=("неизвестный ГОСТ",)
        )
    with pytest.raises(ValueError):
        resolve_standard_selection(
            date(2026, 11, 12),
            early_adopt=("ГОСТ Р 2.304-2026", "ГОСТ Р 2.304-2026"),
        )


def test_date_type_required():
    with pytest.raises(TypeError):
        resolve_standard_selection("2026-11-12")
