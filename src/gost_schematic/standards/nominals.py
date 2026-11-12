"""Nominal value formatter for ГОСТ 2.702-2011 § 5.3.20.

The clause *permits* shortened resistor/capacitor units. It does not define a
compact syntax for inductors, nor all possible extreme/intermediate values.
Undefined ranges are explicitly reported; we never invent a compact notation.
"""

from dataclasses import dataclass
from decimal import Decimal

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.model.nominal_display import NominalDisplayMode, NominalDisplaySettings
from gost_schematic.model.quantities import Quantity, QuantityKind


class NominalRangeError(ValueError):
    """Strict compact formatting has no verified rule for this nominal value."""


@dataclass(frozen=True, slots=True)
class FormattedNominal:
    text: str | None
    effective_mode: NominalDisplayMode
    diagnostics: tuple[Diagnostic, ...] = ()


def _decimal(value: Decimal, separator: str) -> str:
    if value == 0:
        return "0"
    # Decimal's fixed format never silently rounds a fractional nominal.
    representation = format(value, "f")
    if "." in representation:
        representation = representation.rstrip("0").rstrip(".")
    return representation.replace(".", separator)


def _full(quantity: Quantity, settings: NominalDisplaySettings) -> str:
    value = quantity.si_value
    if quantity.kind == QuantityKind.RESISTANCE:
        ranges = (
            (Decimal("1e9"), "ГОм"),
            (Decimal("1e6"), "МОм"),
            (Decimal("1e3"), "кОм"),
            (Decimal("0"), "Ом"),
        )
    elif quantity.kind == QuantityKind.CAPACITANCE:
        ranges = (
            (Decimal("1"), "Ф"),
            (Decimal("1e-3"), "мФ"),
            (Decimal("1e-6"), "мкФ"),
            (Decimal("1e-9"), "нФ"),
            (Decimal("0"), "пФ"),
        )
    else:
        ranges = (
            (Decimal("1"), "Гн"),
            (Decimal("1e-3"), "мГн"),
            (Decimal("1e-6"), "мкГн"),
            (Decimal("0"), "нГн"),
        )
    factors = {
        "ГОм": Decimal("1e9"), "МОм": Decimal("1e6"), "кОм": Decimal("1e3"),
        "Ом": Decimal("1"), "Ф": Decimal("1"), "мФ": Decimal("1e-3"),
        "мкФ": Decimal("1e-6"), "нФ": Decimal("1e-9"), "пФ": Decimal("1e-12"),
        "Гн": Decimal("1"), "мГн": Decimal("1e-3"),
        "мкГн": Decimal("1e-6"), "нГн": Decimal("1e-9"),
    }
    for threshold, symbol in ranges:
        if value >= threshold:
            return f"{_decimal(value / factors[symbol], settings.decimal_separator)} {symbol}"
    raise AssertionError("At least one full-unit range must match")


def _compact(quantity: Quantity, settings: NominalDisplaySettings) -> str | None:
    value = quantity.si_value
    separator = settings.decimal_separator
    if quantity.kind == QuantityKind.RESISTANCE:
        if value <= Decimal("999"):
            return _decimal(value, separator)
        if Decimal("1e3") <= value <= Decimal("999e3"):
            return f"{_decimal(value / Decimal('1e3'), separator)}к"
        if Decimal("1e6") <= value <= Decimal("999e6"):
            return f"{_decimal(value / Decimal('1e6'), separator)}М"
        # The source says "above 1e9" but omits the exact 1e9 boundary;
        # using 1Г at exactly 1 ГОм is an explicit, conventional boundary policy.
        if value >= Decimal("1e9"):
            return f"{_decimal(value / Decimal('1e9'), separator)}Г"
        return None

    if quantity.kind == QuantityKind.CAPACITANCE:
        if value <= Decimal("9999e-12"):
            return _decimal(value / Decimal("1e-12"), separator)
        if Decimal("1e-8") <= value <= Decimal("9999e-6"):
            return f"{_decimal(value / Decimal('1e-6'), separator)}мк"
        return None

    return None


def format_nominal(
    quantity: Quantity,
    settings: NominalDisplaySettings | None = None,
) -> FormattedNominal:
    """Format one physical nominal without changing stored SI data.

    Optional compact mode defaults to ГОСТ 2.702-2011 §5.3.20 for resistors
    and capacitors. Unsupported values produce a warning and FULL_UNITS,
    unless strict_compact=True, when the formatter rejects the label.
    """
    policy = settings or NominalDisplaySettings()
    if not policy.show_nominal:
        return FormattedNominal(None, policy.mode)
    if policy.mode == NominalDisplayMode.FULL_UNITS:
        return FormattedNominal(_full(quantity, policy), NominalDisplayMode.FULL_UNITS)

    compact = _compact(quantity, policy)
    if compact is not None:
        return FormattedNominal(compact, NominalDisplayMode.ESKD_COMPACT)

    reason = (
        f"ГОСТ 2.702-2011 §5.3.20 has no defined shortened format for "
        f"{quantity.kind.value}={quantity.si_value} (SI units)"
    )
    if policy.strict_compact:
        raise NominalRangeError(reason)
    issue = Diagnostic(
        "NOMINAL_COMPACT_UNSUPPORTED", Severity.WARNING, reason,
        quantity.kind.value,
    )
    return FormattedNominal(
        _full(quantity, policy),
        NominalDisplayMode.FULL_UNITS,
        (issue,),
    )
