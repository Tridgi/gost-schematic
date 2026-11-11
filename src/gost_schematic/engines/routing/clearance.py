"""Read-only clearance checks: wires, body keepouts, protected text and pins."""

from collections.abc import Iterable

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.collision import (
    BoxObstacle,
    WireObstacle,
    wire_intersects_box,
)
from gost_schematic.model.circuit import Circuit, PinRef

from .ports import PinEscapeCorridor


def _pin_to_net(circuit: Circuit) -> dict[PinRef, set[str]]:
    membership: dict[PinRef, set[str]] = {}
    for net in circuit.nets:
        for pin in net.members:
            membership.setdefault(pin, set()).add(net.name)
    return membership


def validate_wire_clearance(
    wires: Iterable[WireObstacle],
    *,
    blocked: Iterable[BoxObstacle] = (),
    corridors: Iterable[PinEscapeCorridor] = (),
    circuit: Circuit | None = None,
) -> tuple[Diagnostic, ...]:
    """Validate route geometry and optional schematic-net association.

    Blocked rectangles can include annotation_obstacles(), which returns
    separate collision rectangles for every label and reserved text region.
    Only exact pin identity + real outward geometry permits using a corridor.
    This function does NOT yet design routes or establish netlist connectivity.
    """
    blocked = tuple(blocked)
    corridors = tuple(corridors)
    memberships = _pin_to_net(circuit) if circuit is not None else None
    problems: list[Diagnostic] = []
    for wire in wires:
        if wire.attached_pin is not None and memberships is not None:
            expected = memberships.get(wire.attached_pin, set())
            if wire.net_name not in expected:
                problems.append(Diagnostic(
                    "ROUTE_NET_MISMATCH", Severity.ERROR,
                    f"{wire.identifier} declares {wire.attached_pin} on "
                    f"{wire.net_name!r}, but netlist membership is {sorted(expected)}",
                    wire.identifier,
                ))
        for item in blocked:
            if wire_intersects_box(wire, item.box):
                problems.append(Diagnostic(
                    "ROUTE_OBSTACLE_OVERLAP", Severity.ERROR,
                    f"{wire.identifier} intersects {item.kind}:{item.identifier}",
                    wire.identifier,
                ))
        for port in corridors:
            if not wire_intersects_box(wire, port.box):
                continue
            if not port.admits(wire.line.start, wire.line.end, wire.attached_pin):
                problems.append(Diagnostic(
                    "ROUTE_PIN_ESCAPE_BLOCKED", Severity.ERROR,
                    f"{wire.identifier} crosses reserved corridor {port.identifier}",
                    wire.identifier,
                ))
    return tuple(problems)


def validate_port_reservations(
    corridors: Iterable[PinEscapeCorridor],
    *,
    blocked: Iterable[BoxObstacle] = (),
) -> tuple[Diagnostic, ...]:
    """Detect a symbol or annotation that steals another pin's exit space."""
    corridors = tuple(corridors)
    blocked = tuple(blocked)
    errors: list[Diagnostic] = []
    for port in corridors:
        for obstacle in blocked:
            if port.box.overlaps(obstacle.box):
                errors.append(Diagnostic(
                    "PIN_CORRIDOR_OBSTRUCTED", Severity.ERROR,
                    f"{port.identifier} overlaps {obstacle.kind}:{obstacle.identifier}",
                    port.identifier,
                ))
    for i, left in enumerate(corridors):
        for right in corridors[i + 1:]:
            if left.box.overlaps(right.box):
                errors.append(Diagnostic(
                    "PIN_CORRIDOR_OVERLAP", Severity.ERROR,
                    f"{left.identifier} overlaps {right.identifier}",
                    left.identifier,
                ))
    return tuple(errors)
