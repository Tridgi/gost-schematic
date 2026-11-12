"""Data-driven, narrowly scoped dimensional checks of verified GOST figures.

These checks prove only selected figures/dimensions. They do not certify full
line style, placement, font rendering, or every alternative symbol variant.
"""

import json
from dataclasses import dataclass
from importlib.resources import files

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Line, Rectangle
from gost_schematic.model.symbol import SymbolDefinition


def load_requirements() -> dict[str, object]:
    source = files("gost_schematic").joinpath(
        "standards/requirements_2026_ru.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    if (
        data.get("schema_version") != 1
        or data.get("profile_id") != "eskd-ru-2026-11"
        or data.get("jurisdiction") != "RU"
    ):
        raise ValueError("Unknown ESKD RU standards profile")
    if any(
        not item.get("id") or not item.get("source")
        for item in data.get("dimensional_rules", [])
    ):
        raise ValueError("Every dimensional rule needs an ID and source")
    identifiers = [item["id"] for item in data["dimensional_rules"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate normative rule identifier")
    return data


@dataclass(frozen=True, slots=True)
class DimensionalAssessment:
    """Machine-verified dimensions, never an overall GOST approval state."""

    applicable_rules: tuple[str, ...]
    passed_rules: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(item.severity == Severity.ERROR for item in self.diagnostics)


def _check_fixed_resistor(
    symbol: SymbolDefinition, width: int, height: int,
) -> bool:
    return any(
        isinstance(item, Rectangle)
        and item.box.max_x - item.box.min_x == width
        and item.box.max_y - item.box.min_y == height
        for item in symbol.graphics
    )


def _check_plate_pair(
    symbol: SymbolDefinition, length: int, separation: int,
) -> bool:
    vertical: set[int] = set()
    horizontal: set[int] = set()
    for item in symbol.graphics:
        if not isinstance(item, Line):
            continue
        if item.start.x == item.end.x and abs(item.start.y - item.end.y) == length:
            vertical.add(item.start.x)
        if item.start.y == item.end.y and abs(item.start.x - item.end.x) == length:
            horizontal.add(item.start.y)
    return (
        len(vertical) == 2 and abs(max(vertical) - min(vertical)) == separation
    ) or (
        len(horizontal) == 2 and abs(max(horizontal) - min(horizontal)) == separation
    )


def check_verified_dimensions(
    symbol: SymbolDefinition,
    *,
    requirements: dict[str, object] | None = None,
) -> DimensionalAssessment:
    """Apply only dimensions verified against applicable normative figures."""
    requirements = requirements if requirements is not None else load_requirements()
    applicable: list[str] = []
    passed: list[str] = []
    issues: list[Diagnostic] = []
    for rule in requirements["dimensional_rules"]:
        if symbol.identifier not in rule["targets"]:
            continue
        name = rule["id"]
        applicable.append(name)
        if rule["kind"] == "rectangular_body":
            okay = _check_fixed_resistor(
                symbol, rule["width_um"], rule["height_um"]
            )
        elif rule["kind"] == "parallel_plate_body":
            okay = _check_plate_pair(
                symbol, rule["plate_length_um"], rule["plate_spacing_um"]
            )
        else:
            issues.append(Diagnostic(
                "NORMATIVE_RULE_UNSUPPORTED", Severity.ERROR,
                f"{name}: unsupported rule kind", symbol.identifier,
            ))
            continue
        if okay:
            passed.append(name)
        else:
            issues.append(Diagnostic(
                "NORMATIVE_DIMENSION_MISMATCH", Severity.ERROR,
                f"{symbol.identifier}: violates {name} ({rule['reference']})",
                symbol.identifier,
            ))
    return DimensionalAssessment(tuple(applicable), tuple(passed), tuple(issues))
