"""ГОСТ 2.702-2011 §5.3.20 compact labels and precise SI source values."""

from dataclasses import replace
from decimal import Decimal

import pytest

from gost_schematic.model.nominal_display import (
    ComponentNominalOverride,
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit, parse_decimal
from gost_schematic.standards.nominals import NominalRangeError, format_nominal


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("0", Unit.OHM, "0"),
        ("0,5", Unit.OHM, "0,5"),
        ("470", Unit.OHM, "470"),
        ("999", Unit.OHM, "999"),
        ("1000", Unit.OHM, "1к"),
        ("2300", Unit.OHM, "2,3к"),
        ("999000", Unit.OHM, "999к"),
        ("1", Unit.MOHM, "1М"),
        ("4.7", Unit.MOHM, "4,7М"),
        ("999", Unit.MOHM, "999М"),
        ("1000000000", Unit.OHM, "1Г"),
        ("2.2", Unit.GOHM, "2,2Г"),
        ("0", Unit.PICOFARAD, "0"),
        ("47", Unit.PICOFARAD, "47"),
        ("9999", Unit.PICOFARAD, "9999"),
        ("10", Unit.NANOFARAD, "0,01мк"),
        ("100", Unit.NANOFARAD, "0,1мк"),
        ("1", Unit.MICROFARAD, "1мк"),
        ("470", Unit.MICROFARAD, "470мк"),
        ("9999", Unit.MICROFARAD, "9999мк"),
    ],
)
def test_compact_nominals(value, unit, expected):
    result = format_nominal(Quantity.from_unit(value, unit))
    assert result.text == expected
    assert result.effective_mode == NominalDisplayMode.ESKD_COMPACT
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("470", Unit.OHM, "470 Ом"),
        ("2300", Unit.OHM, "2,3 кОм"),
        ("2.3", Unit.KOHM, "2,3 кОм"),
        ("4.7", Unit.MOHM, "4,7 МОм"),
        ("100", Unit.NANOFARAD, "100 нФ"),
        ("47", Unit.PICOFARAD, "47 пФ"),
        ("1", Unit.MICROFARAD, "1 мкФ"),
        ("10", Unit.MILLIFARAD, "10 мФ"),
        ("33", Unit.MICROHENRY, "33 мкГн"),
    ],
)
def test_full_units(value, unit, expected):
    policy = NominalDisplaySettings(mode=NominalDisplayMode.FULL_UNITS)
    result = format_nominal(Quantity.from_unit(value, unit), policy)
    assert result.text == expected
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        ("999.5", Unit.OHM),  # Between literal ГОСТ ranges 0..999 and >=1000.
        ("999500", Unit.OHM),
        ("999500000", Unit.OHM),
        ("9999.5", Unit.PICOFARAD),
        ("10000", Unit.MICROFARAD),
        ("33", Unit.MICROHENRY),  # No compact inductance rule in cited clause.
    ],
)
def test_undefined_compact_ranges_warn_and_fallback(value, unit):
    quantity = Quantity.from_unit(value, unit)
    result = format_nominal(quantity)
    assert result.effective_mode == NominalDisplayMode.FULL_UNITS
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "NOMINAL_COMPACT_UNSUPPORTED"
    assert result.text is not None
    with pytest.raises(NominalRangeError, match="5.3.20"):
        format_nominal(quantity, NominalDisplaySettings(strict_compact=True))


def test_decimal_output_customization_and_zero():
    settings = NominalDisplaySettings(decimal_separator=".")
    assert format_nominal(Quantity.from_unit("2,3", Unit.KOHM), settings).text == "2.3к"
    assert format_nominal(Quantity.from_unit("0", Unit.PICOFARAD)).text == "0"


def test_hidden_nominal_not_rendered_or_warned():
    quantity = Quantity.from_unit("10000", Unit.MICROFARAD)
    result = format_nominal(quantity, NominalDisplaySettings(show_nominal=False))
    assert result.text is None
    assert not result.diagnostics


def test_quantity_is_exact_and_serializes_without_binary_float():
    quantity = Quantity.from_unit("2,3", Unit.KOHM)
    assert quantity.kind == QuantityKind.RESISTANCE
    assert quantity.si_value == Decimal("2300")
    assert Quantity.from_record(quantity.to_record()) == quantity
    assert quantity.to_record()["si_value"] == "2300"
    nano = Quantity.from_unit("0.1", Unit.NANOFARAD)
    assert nano.si_value == Decimal("1E-10")
    assert Quantity.from_record(nano.to_record()) == nano


@pytest.mark.parametrize("invalid", [True, 2.3, "NaN", "Infinity", "-1", "1,2.3", ""])
def test_invalid_numeric_input_fails_early(invalid):
    with pytest.raises((TypeError, ValueError)):
        Quantity.from_unit(invalid, Unit.OHM)


def test_invalid_persisted_record_and_invalid_settings():
    quantity = Quantity.from_unit(1, Unit.OHM)
    with pytest.raises(ValueError):
        Quantity.from_record({**quantity.to_record(), "schema_version": 3})
    with pytest.raises(ValueError):
        NominalDisplaySettings(decimal_separator=";")
    with pytest.raises(TypeError):
        NominalDisplaySettings(show_nominal=1)


def test_sheet_settings_and_instance_overrides():
    settings = NominalDisplaySettings(mode=NominalDisplayMode.ESKD_COMPACT)
    config = NominalDisplayConfiguration(settings, (
        ComponentNominalOverride("R2", mode=NominalDisplayMode.FULL_UNITS),
        ComponentNominalOverride("R3", show_nominal=False),
    ))
    assert config.for_reference("R1") == settings
    assert config.for_reference("R2").mode == NominalDisplayMode.FULL_UNITS
    assert not config.for_reference("R3").show_nominal
    assert config.default.mode == NominalDisplayMode.ESKD_COMPACT
    with pytest.raises(ValueError, match="one nominal display override"):
        replace(config, overrides=(
            ComponentNominalOverride("R2"), ComponentNominalOverride("R2"),
        ))


def test_decimal_parser_rejects_floats_and_ambiguous_separators():
    assert parse_decimal("0,0001") == Decimal("0.0001")
    with pytest.raises(TypeError):
        parse_decimal(0.1)
    with pytest.raises(ValueError):
        parse_decimal("1.2,3")
