"""Explicit operating-point potentials; net names never imply voltage values.

A single scenario is only a static operating point, not proof of correct wiring
across all supply conditions, start-up transitions, AC ripple or fault cases.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def parse_voltage(value: str | int | Decimal) -> Decimal:
    """Signed finite voltage, preserving decimals exactly and rejecting floats."""
    if isinstance(value, (float, bool)) or not isinstance(value, (str, int, Decimal)):
        raise TypeError("Voltage must be an exact decimal string, integer, or Decimal")
    if isinstance(value, str):
        source = value.strip()
        if "." in source and "," in source:
            raise ValueError("Mixed decimal separators are not allowed")
        source = source.replace(",", ".")
    else:
        source = value
    try:
        result = Decimal(source)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Not a valid voltage: {value!r}") from error
    if not result.is_finite():
        raise ValueError("Voltage must be finite")
    return result


@dataclass(frozen=True, slots=True)
class NetPotential:
    """Potential on one named net, in volts relative to a named common reference."""

    net_name: str
    volts: Decimal
    reference_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.net_name, str) or not self.net_name.strip():
            raise ValueError("Potential must name a net")
        if not isinstance(self.reference_id, str) or not self.reference_id.strip():
            raise ValueError("Potential must declare a reference coordinate system")
        if not isinstance(self.volts, Decimal) or not self.volts.is_finite():
            raise ValueError("Potential volts must be a finite Decimal")

    @classmethod
    def from_volts(
        cls,
        net_name: str,
        volts: str | int | Decimal,
        *,
        reference_id: str,
    ) -> "NetPotential":
        return cls(net_name, parse_voltage(volts), reference_id)


@dataclass(frozen=True, slots=True)
class PotentialScenario:
    """Named operating case; potentials are asserted by caller, not solved."""

    name: str
    potentials: tuple[NetPotential, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Potential scenario requires a name")
        net_names = [item.net_name for item in self.potentials]
        if len(net_names) != len(set(net_names)):
            raise ValueError("Duplicate potential entry for a net")

    def by_net(self) -> dict[str, NetPotential]:
        return {item.net_name: item for item in self.potentials}
