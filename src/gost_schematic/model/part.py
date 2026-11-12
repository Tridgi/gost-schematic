"""Physical component model independent of its graphical representation."""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.model.pins import PhysicalPin, TerminalPolarity
from gost_schematic.model.quantities import QuantityKind


class VoltageOrientationRule(str, Enum):
    """Opt-in passive voltage rule; not automatically applied to every + / - pin."""

    NONE = "none"
    POSITIVE_NOT_BELOW_NEGATIVE = "positive_not_below_negative"


@dataclass(frozen=True, slots=True)
class PartDefinition:
    identifier: str
    reference_prefix: str
    symbol_id: str
    pins: tuple[PhysicalPin, ...]
    nominal_kind: QuantityKind | None = None
    voltage_orientation_rule: VoltageOrientationRule = VoltageOrientationRule.NONE

    def __post_init__(self) -> None:
        if not self.identifier or not self.reference_prefix or not self.symbol_id:
            raise ValueError("Part identifier, reference prefix and symbol ID are required")
        if self.nominal_kind is not None and not isinstance(self.nominal_kind, QuantityKind):
            raise TypeError("nominal_kind must be a QuantityKind or None")
        if not isinstance(self.voltage_orientation_rule, VoltageOrientationRule):
            raise TypeError("voltage_orientation_rule must be a VoltageOrientationRule")
        if self.voltage_orientation_rule != VoltageOrientationRule.NONE:
            roles = [pin.polarity for pin in self.pins]
            if (
                roles.count(TerminalPolarity.POSITIVE) != 1
                or roles.count(TerminalPolarity.NEGATIVE) != 1
            ):
                raise ValueError(
                    "Voltage orientation requires exactly one positive and one negative pin"
                )
        numbers = [pin.number for pin in self.pins]
        if not numbers or len(numbers) != len(set(numbers)):
            raise ValueError("Physical pins must be present and uniquely numbered")
