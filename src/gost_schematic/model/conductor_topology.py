"""Explicit conducting-ink topology for a single drawn UGO.

This model represents continuity of *selected drawn conductor strokes*, not
electrical netlist connectivity or a zero-ohm equivalence of element terminals.
A resistor and a capacitor have separate conductor groups even if their
electrical behavior connects their physical pins in some operating conditions.
"""

from dataclasses import dataclass

from gost_schematic.core.geometry import Point


@dataclass(frozen=True, slots=True)
class ConductorTopology:
    """Authored graph layer by indices in SymbolDefinition.graphics.

    - conductor_indices refer only to lines and true semicircular arcs.
    - junctions explicitly join strokes at their interior points.
    - pin_groups enumerate all *graphical conductor islands* expected at pins.
    Identical coordinates of two stroke endpoints join, but an unmarked
    crossing or T-contact in a stroke interior is never inferred as connected.
    """

    conductor_indices: tuple[int, ...]
    junctions: tuple[Point, ...]
    pin_groups: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.conductor_indices or not self.pin_groups:
            raise ValueError("Conductive topology needs strokes and pin groups")
        if any(type(i) is not int or i < 0 for i in self.conductor_indices):
            raise ValueError("Primitive indices must be non-negative integers")
        if len(self.conductor_indices) != len(set(self.conductor_indices)):
            raise ValueError("Duplicate conductive primitive index")
        if len(self.junctions) != len(set(self.junctions)):
            raise ValueError("Duplicate explicit junction coordinate")
        groups = [pin for group in self.pin_groups for pin in group]
        if any(not group for group in self.pin_groups):
            raise ValueError("Empty conductor pin group")
        if not all(isinstance(pin, str) and pin.strip() for pin in groups):
            raise ValueError("Pin group members must be non-empty physical numbers")
        if len(groups) != len(set(groups)):
            raise ValueError("Physical pin occurs in more than one conductor group")
