"""Physical component model independent of its graphical representation."""
from dataclasses import dataclass

from gost_schematic.model.pins import PhysicalPin
from gost_schematic.model.quantities import QuantityKind


@dataclass(frozen=True, slots=True)
class PartDefinition:
    identifier: str
    reference_prefix: str
    symbol_id: str
    pins: tuple[PhysicalPin, ...]
    nominal_kind: QuantityKind | None = None

    def __post_init__(self) -> None:
        if not self.identifier or not self.reference_prefix or not self.symbol_id:
            raise ValueError("Part identifier, reference prefix and symbol ID are required")
        if self.nominal_kind is not None and not isinstance(self.nominal_kind, QuantityKind):
            raise TypeError("nominal_kind must be a QuantityKind or None")
        numbers = [pin.number for pin in self.pins]
        if not numbers or len(numbers) != len(set(numbers)):
            raise ValueError("Physical pins must be present and uniquely numbered")
