"""Sheet/document presentation settings, separate from electrical connectivity."""

from dataclasses import dataclass, field

from gost_schematic.model.circuit import Circuit
from gost_schematic.model.nominal_display import NominalDisplayConfiguration


@dataclass(frozen=True, slots=True)
class SchematicDocument:
    circuit: Circuit
    nominal_display: NominalDisplayConfiguration = field(
        default_factory=NominalDisplayConfiguration
    )

    def __post_init__(self) -> None:
        present = {item.reference for item in self.circuit.components}
        unknown = {
            item.reference for item in self.nominal_display.overrides
            if item.reference not in present
        }
        if unknown:
            raise ValueError(
                "Nominal display overrides refer to unknown components: "
                + ", ".join(sorted(unknown))
            )
