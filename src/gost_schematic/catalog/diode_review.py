"""Strict review guards for the first two experimental diode catalog profiles.

These guards validate our exact authored *draft fixtures*, NOT all permissible
GOST depictions of a diode. Electrical A/K labels are functional roles, not
absolute +/- polarity or manufacturer package numbers. Used by CI and SVG
sample generation without extending public model/loader/renderer APIs.
"""

from gost_schematic.core.geometry import Line, Point, Side
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import ElectricalType, TerminalFunction, TerminalPolarity
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

_DRAFT_LEADS = (
    Line(Point(-10000, 0), Point(-2500, 0)),
    Line(Point(2500, 0), Point(10000, 0)),
)
_DRAFT_BODY = (
    Line(Point(-2500, -3000), Point(2500, 0)),
    Line(Point(2500, 0), Point(-2500, 3000)),
    Line(Point(-2500, 3000), Point(-2500, -3000)),
)
_GENERAL_CATHODE = (Line(Point(2500, -3300), Point(2500, 3300)),)
_ZENER_CATHODE = (
    *_GENERAL_CATHODE,
    Line(Point(2500, -3300), Point(1300, -3300)),
    Line(Point(2500, 3300), Point(3700, 3300)),
)
_PROFILES = {
    "diode.general": _DRAFT_LEADS + _DRAFT_BODY + _GENERAL_CATHODE,
    "diode.zener": _DRAFT_LEADS + _DRAFT_BODY + _ZENER_CATHODE,
}


def verify_draft_diode(symbol: SymbolDefinition, part: PartDefinition) -> None:
    """Fail closed on A/K reversal, missing Zener kink or unintended bridge.

    These numeric coordinates are strictly an editorial regression profile;
    GOST 2.730-73 appendix 2 supplies a *reference module grid*, not fixed
    mandatory millimetre dimensions.
    """
    expected = _PROFILES.get(symbol.identifier)
    if expected is None:
        raise ValueError(f"Unknown cycle-4 diode profile: {symbol.identifier}")
    if (
        part.identifier != symbol.identifier
        or part.symbol_id != symbol.identifier
        or part.reference_prefix != "VD"
        or part.nominal_kind is not None
        or part.voltage_orientation_rule != VoltageOrientationRule.NONE
    ):
        raise ValueError("Diode part/profile identity or unsupported electrical rule")
    if symbol.revision != 1 or symbol.status != SymbolStatus.DRAFT:
        raise ValueError("Unreviewed diode must remain revision-one DRAFT")
    if len(symbol.standard_refs) < 2 or not any(
        "EDITORIAL_ASSUMPTION" in reference for reference in symbol.standard_refs
    ):
        raise ValueError("Missing explicit draft geometry assumptions")
    if [(pin.number, pin.name, pin.electrical_type, pin.polarity, pin.function)
        for pin in part.pins] != [
            ("1", "A", ElectricalType.PASSIVE, TerminalPolarity.NONE,
             TerminalFunction.GENERAL),
            ("2", "K", ElectricalType.PASSIVE, TerminalPolarity.NONE,
             TerminalFunction.GENERAL),
    ]:
        raise ValueError("Diode A/K physical terminals are swapped or misclassified")
    if [(pin.number, pin.label, pin.at, pin.side) for pin in symbol.pins] != [
        ("1", "A", Point(-10000, 0), Side.LEFT),
        ("2", "K", Point(10000, 0), Side.RIGHT),
    ]:
        raise ValueError("Diode graphic A/K pins no longer map to physical terminals")
    if symbol.graphics != expected:
        raise ValueError("Draft diode geometry lost triangle, cathode or Zener kink")
    topology = symbol.conductor_topology
    if topology is None or (
        topology.conductor_indices != (0, 1)
        or topology.junctions
        or topology.pin_groups != (("1",), ("2",))
    ):
        raise ValueError("Diode body/marker must not short A and K")
    if not inspect_conductor_topology(symbol).valid:
        raise ValueError("Diode conductor graph is malformed")
    if any(item.severity.value == "error" for item in validate_symbol(symbol)):
        raise ValueError("Diode has a structural graphic error")
