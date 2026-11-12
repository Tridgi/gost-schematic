"""Canonical physical values; rendered nominal labels are NOT data storage.

All values use Decimal and SI base units so changing the drawing's text profile
never changes the actual component value, the netlist, or the eventual BOM.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class QuantityKind(str, Enum):
    RESISTANCE = "resistance"
    CAPACITANCE = "capacitance"
    INDUCTANCE = "inductance"


class Unit(str, Enum):
    OHM = "ohm"
    KOHM = "kohm"
    MOHM = "Mohm"
    GOHM = "Gohm"
    FARAD = "F"
    MILLIFARAD = "mF"
    MICROFARAD = "uF"
    NANOFARAD = "nF"
    PICOFARAD = "pF"
    HENRY = "H"
    MILLIHENRY = "mH"
    MICROHENRY = "uH"
    NANOHENRY = "nH"


UNIT_DEFINITIONS: dict[Unit, tuple[QuantityKind, Decimal]] = {
    Unit.OHM: (QuantityKind.RESISTANCE, Decimal(1)),
    Unit.KOHM: (QuantityKind.RESISTANCE, Decimal(1000)),
    Unit.MOHM: (QuantityKind.RESISTANCE, Decimal(1000000)),
    Unit.GOHM: (QuantityKind.RESISTANCE, Decimal(1000000000)),
    Unit.FARAD: (QuantityKind.CAPACITANCE, Decimal(1)),
    Unit.MILLIFARAD: (QuantityKind.CAPACITANCE, Decimal("1e-3")),
    Unit.MICROFARAD: (QuantityKind.CAPACITANCE, Decimal("1e-6")),
    Unit.NANOFARAD: (QuantityKind.CAPACITANCE, Decimal("1e-9")),
    Unit.PICOFARAD: (QuantityKind.CAPACITANCE, Decimal("1e-12")),
    Unit.HENRY: (QuantityKind.INDUCTANCE, Decimal(1)),
    Unit.MILLIHENRY: (QuantityKind.INDUCTANCE, Decimal("1e-3")),
    Unit.MICROHENRY: (QuantityKind.INDUCTANCE, Decimal("1e-6")),
    Unit.NANOHENRY: (QuantityKind.INDUCTANCE, Decimal("1e-9")),
}


def parse_decimal(value: str | int | Decimal) -> Decimal:
    """Accept decimal strings (also Russian comma); reject binary floats."""
    if isinstance(value, (bool, float)):
        raise TypeError("Use a string, integer or Decimal, not a binary float/boolean")
    if not isinstance(value, (str, int, Decimal)):
        raise TypeError("Unsupported quantity value type")
    if isinstance(value, str):
        value = value.strip()
        if "." in value and "," in value:
            raise ValueError("Mixed decimal separators are not allowed")
        value = value.replace(",", ".")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Not a valid decimal quantity: {value!r}") from error
    if not result.is_finite():
        raise ValueError("A quantity must be finite")
    if result < 0:
        raise ValueError("Passive component nominal cannot be negative")
    return result


@dataclass(frozen=True, slots=True)
class Quantity:
    """Exact physical quantity in its SI base unit: ohm, farad or henry."""

    kind: QuantityKind
    si_value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.kind, QuantityKind):
            raise TypeError("kind must be a QuantityKind")
        if not isinstance(self.si_value, Decimal):
            raise TypeError("SI value must be a Decimal")
        if not self.si_value.is_finite() or self.si_value < 0:
            raise ValueError("SI value must be finite and non-negative")

    @classmethod
    def from_unit(cls, value: str | int | Decimal, unit: Unit | str) -> "Quantity":
        resolved = Unit(unit)
        kind, factor = UNIT_DEFINITIONS[resolved]
        return cls(kind, parse_decimal(value) * factor)

    def to_record(self) -> dict[str, str | int]:
        """Persistence uses strings to avoid JSON floating-point rounding."""
        return {
            "schema_version": 1,
            "kind": self.kind.value,
            "si_value": str(self.si_value),
        }

    @classmethod
    def from_record(cls, record: dict[str, str | int]) -> "Quantity":
        if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
            raise ValueError("Unsupported quantity schema version")
        if not isinstance(record.get("si_value"), str):
            raise TypeError("Persisted SI value must be a decimal string")
        return cls(
            QuantityKind(record["kind"]),
            parse_decimal(record["si_value"]),
        )
