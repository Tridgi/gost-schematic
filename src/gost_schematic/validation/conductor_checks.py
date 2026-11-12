"""Exact authored conductor graph for UGO primitives.

Only explicitly selected Line/StyledLine/Semicircle objects are conducting.
Geometric crossings never create implicit joins. All arithmetic uses integral
micrometres: no floating-point tolerance and no assumptions from net names.
"""

from dataclasses import dataclass

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Line, Point, Semicircle, Side, StyledLine
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class ConductorInspection:
    """Report pin islands without implying any external Circuit.net ownership."""

    pin_islands: tuple[tuple[str, ...], ...]
    visited_primitives: int
    explicit_junctions: int
    diagnostics: tuple[Diagnostic, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == Severity.ERROR for issue in self.diagnostics)


def _ends(shape: Line | StyledLine | Semicircle) -> tuple[Point, Point]:
    if isinstance(shape, (Line, StyledLine)):
        return shape.start, shape.end
    x, y, r = shape.center.x, shape.center.y, shape.radius
    if shape.bulge in (Side.TOP, Side.BOTTOM):
        return Point(x - r, y), Point(x + r, y)
    return Point(x, y - r), Point(x, y + r)


def _on_shape(point: Point, shape: Line | StyledLine | Semicircle) -> bool:
    if isinstance(shape, (Line, StyledLine)):
        a, b = shape.start, shape.end
        dx, dy = b.x - a.x, b.y - a.y
        px, py = point.x - a.x, point.y - a.y
        return (
            px * dy == py * dx
            and min(a.x, b.x) <= point.x <= max(a.x, b.x)
            and min(a.y, b.y) <= point.y <= max(a.y, b.y)
        )
    dx, dy = point.x - shape.center.x, point.y - shape.center.y
    if dx * dx + dy * dy != shape.radius * shape.radius:
        return False
    return {
        Side.TOP: dy <= 0,
        Side.BOTTOM: dy >= 0,
        Side.LEFT: dx <= 0,
        Side.RIGHT: dx >= 0,
    }[shape.bulge]


class _DisjointSets:
    def __init__(self) -> None:
        self._parent: dict[Point, Point] = {}

    def add(self, point: Point) -> None:
        self._parent.setdefault(point, point)

    def find(self, point: Point) -> Point:
        # Iterative path compression: long user-authored chains must not
        # overflow Python's recursion limit before topology can be checked.
        root = point
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[point] != root:
            previous = self._parent[point]
            self._parent[point] = root
            point = previous
        return root

    def union(self, a: Point, b: Point) -> None:
        self.add(a)
        self.add(b)
        first, second = self.find(a), self.find(b)
        if first != second:
            # Canonical parent makes diagnostics reproducible across runs.
            self._parent[max(first, second, key=lambda p: (p.x, p.y))] = min(
                first, second, key=lambda p: (p.x, p.y)
            )

    def __contains__(self, point: Point) -> bool:
        return point in self._parent

    def nodes(self) -> tuple[Point, ...]:
        return tuple(self._parent)


def inspect_conductor_topology(symbol: SymbolDefinition) -> ConductorInspection:
    """Check conductor continuity only where the symbol explicitly declares it.

    Expected groups are *painted conductor islands*, not a SPICE model of the
    electrical component. Resistive and capacitive two-terminal symbols have
    two independent stroke groups; an inductor may have one winding group
    with many taps.
    """
    topology = symbol.conductor_topology
    if topology is None:
        return ConductorInspection((), 0, 0, (
            Diagnostic(
                "TOPOLOGY_UNDECLARED", Severity.WARNING,
                "Internal conductor layer not declared (cannot verify continuity)",
                symbol.identifier,
            ),
        ))

    issues: list[Diagnostic] = []
    selected: list[Line | StyledLine | Semicircle] = []
    for index in topology.conductor_indices:
        if index >= len(symbol.graphics):
            issues.append(Diagnostic(
                "TOPOLOGY_PRIMITIVE_INVALID", Severity.ERROR,
                f"Conductor index {index} outside the symbol graphics",
                symbol.identifier,
            ))
            continue
        shape = symbol.graphics[index]
        if not isinstance(shape, (Line, StyledLine, Semicircle)):
            issues.append(Diagnostic(
                "TOPOLOGY_PRIMITIVE_INVALID", Severity.ERROR,
                f"Conductor index {index} is not a supported conductive stroke",
                symbol.identifier,
            ))
            continue
        selected.append(shape)

    graph = _DisjointSets()
    valid_junctions: list[Point] = []
    for junction in topology.junctions:
        count = sum(_on_shape(junction, item) for item in selected)
        if count < 2:
            issues.append(Diagnostic(
                "TOPOLOGY_JUNCTION_DANGLING", Severity.ERROR,
                f"Junction {junction} must be on at least two authored strokes",
                symbol.identifier,
            ))
        else:
            valid_junctions.append(junction)

    for shape in selected:
        first, second = _ends(shape)
        nodes = (first, second, *(
            joint for joint in valid_junctions if _on_shape(joint, shape)
        ))
        for node in nodes:
            graph.union(first, node)

    pin_by_number = {pin.number: pin.at for pin in symbol.pins}
    declared = {number for group in topology.pin_groups for number in group}
    if declared != set(pin_by_number):
        issues.append(Diagnostic(
            "TOPOLOGY_PIN_GROUP_MISMATCH", Severity.ERROR,
            "Conductive groups must partition the complete graphical pin set",
            symbol.identifier,
        ))

    for name, at in pin_by_number.items():
        if at not in graph:
            issues.append(Diagnostic(
                "TOPOLOGY_PIN_UNATTACHED", Severity.ERROR,
                f"Graphical pin {name} is not attached to an authored conductive stroke",
                symbol.identifier,
            ))

    islands: dict[Point, list[str]] = {}
    for name, at in pin_by_number.items():
        if at in graph:
            islands.setdefault(graph.find(at), []).append(name)

    for group in topology.pin_groups:
        roots = {graph.find(pin_by_number[name])
                 for name in group if name in pin_by_number and pin_by_number[name] in graph}
        if len(roots) > 1:
            issues.append(Diagnostic(
                "TOPOLOGY_GROUP_DISCONNECTED", Severity.ERROR,
                f"Expected joined conducting pins {group} lie on different strokes",
                symbol.identifier,
            ))

    for i, first in enumerate(topology.pin_groups):
        for second in topology.pin_groups[i + 1:]:
            roots_first = {
                graph.find(pin_by_number[name])
                for name in first if name in pin_by_number and pin_by_number[name] in graph
            }
            roots_second = {
                graph.find(pin_by_number[name])
                for name in second if name in pin_by_number and pin_by_number[name] in graph
            }
            if roots_first & roots_second:
                issues.append(Diagnostic(
                    "TOPOLOGY_UNEXPECTED_BRIDGE", Severity.ERROR,
                    f"Separate conductor groups {first} and {second} accidentally join",
                    symbol.identifier,
                ))

    occupied_roots = set(islands)
    for node in graph.nodes():
        if graph.find(node) not in occupied_roots:
            issues.append(Diagnostic(
                "TOPOLOGY_ORPHAN_CONDUCTOR", Severity.ERROR,
                f"Conductive stroke at {node} has no attached physical pin",
                symbol.identifier,
            ))
            occupied_roots.add(graph.find(node))

    groups = tuple(sorted(
        (tuple(sorted(names)) for names in islands.values()),
        key=lambda group: group[0],
    ))
    return ConductorInspection(
        pin_islands=groups,
        visited_primitives=len(selected),
        explicit_junctions=len(valid_junctions),
        diagnostics=tuple(issues),
    )
