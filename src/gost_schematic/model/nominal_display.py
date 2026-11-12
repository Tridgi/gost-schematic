"""Document-wide nominal display policy with explicit per-component overrides."""

from dataclasses import dataclass, field, replace
from enum import Enum


class NominalDisplayMode(str, Enum):
    ESKD_COMPACT = "eskd_compact"
    FULL_UNITS = "full_units"


@dataclass(frozen=True, slots=True)
class NominalDisplaySettings:
    mode: NominalDisplayMode = NominalDisplayMode.ESKD_COMPACT
    show_nominal: bool = True
    decimal_separator: str = ","
    strict_compact: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mode, NominalDisplayMode):
            raise TypeError("mode must be a NominalDisplayMode")
        if type(self.show_nominal) is not bool or type(self.strict_compact) is not bool:
            raise TypeError("Visibility and strict mode must be booleans")
        if self.decimal_separator not in (",", "."):
            raise ValueError("Only comma or dot are supported decimal separators")


@dataclass(frozen=True, slots=True)
class ComponentNominalOverride:
    reference: str
    mode: NominalDisplayMode | None = None
    show_nominal: bool | None = None
    strict_compact: bool | None = None

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("An override needs a reference designator")
        if self.mode is not None and not isinstance(self.mode, NominalDisplayMode):
            raise TypeError("Override mode must be a NominalDisplayMode")
        for value in (self.show_nominal, self.strict_compact):
            if value is not None and type(value) is not bool:
                raise TypeError("Visibility/strict override must be boolean or None")


@dataclass(frozen=True, slots=True)
class NominalDisplayConfiguration:
    default: NominalDisplaySettings = field(default_factory=NominalDisplaySettings)
    overrides: tuple[ComponentNominalOverride, ...] = ()

    def __post_init__(self) -> None:
        references = [item.reference for item in self.overrides]
        if len(references) != len(set(references)):
            raise ValueError("Only one nominal display override per component is allowed")

    def for_reference(self, reference: str) -> NominalDisplaySettings:
        result = self.default
        for override in self.overrides:
            if override.reference == reference:
                return replace(
                    result,
                    mode=override.mode if override.mode is not None else result.mode,
                    show_nominal=(
                        override.show_nominal
                        if override.show_nominal is not None else result.show_nominal
                    ),
                    strict_compact=(
                        override.strict_compact
                        if override.strict_compact is not None else result.strict_compact
                    ),
                )
        return result
