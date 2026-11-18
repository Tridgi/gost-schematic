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
    """The sole fixed-resistor body must match its declared keepout."""
    rectangles = [
        item for item in symbol.graphics if isinstance(item, Rectangle)
    ]
    return (
        len(rectangles) == 1
        and rectangles[0].box == symbol.body_keepout
        and rectangles[0].box.max_x - rectangles[0].box.min_x == width
        and rectangles[0].box.max_y - rectangles[0].box.min_y == height
    )


def _check_plate_pair(
    symbol: SymbolDefinition, length: int, separation: int,
) -> bool:
    """Validate a facing, aligned pair WITH leads at plate midpoints.

    Just finding any two lines of the correct length and gap can produce
    false positives: staggered plates or unconnected decorations are not
    the fixed capacitor UGO under review. This checks its canonical
    geometry only, not every GOST-permitted alternative.
    """
    strokes = [item for item in symbol.graphics if isinstance(item, Line)]
    for i, left in enumerate(strokes):
        for j, right in enumerate(strokes[i + 1:], i + 1):
            if left.start.x == left.end.x and right.start.x == right.end.x:
                y1 = sorted((left.start.y, left.end.y))
                y2 = sorted((right.start.y, right.end.y))
                if (
                    y1 == y2
                    and y1[1] - y1[0] == length
                    and abs(left.start.x - right.start.x) == separation
                ):
                    midpoint_left = (left.start.x, (y1[0] + y1[1]) // 2)
                    midpoint_right = (right.start.x, (y2[0] + y2[1]) // 2)
                else:
                    continue
            elif left.start.y == left.end.y and right.start.y == right.end.y:
                x1 = sorted((left.start.x, left.end.x))
                x2 = sorted((right.start.x, right.end.x))
                if (
                    x1 == x2
                    and x1[1] - x1[0] == length
                    and abs(left.start.y - right.start.y) == separation
                ):
                    midpoint_left = ((x1[0] + x1[1]) // 2, left.start.y)
                    midpoint_right = ((x2[0] + x2[1]) // 2, right.start.y)
                else:
                    continue
            else:
                continue
            other_strokes = (
                item for index, item in enumerate(strokes) if index not in (i, j)
            )
            endpoints = {
                (point.x, point.y)
                for item in other_strokes
                for point in (item.start, item.end)
            }
            if midpoint_left in endpoints and midpoint_right in endpoints:
                return True
    return False


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
