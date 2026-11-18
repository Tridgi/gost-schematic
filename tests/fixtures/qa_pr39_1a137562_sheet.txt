"""EXPERIMENTAL ROUTING: conservative physical-pin-aware sheet adapter.

Resolves real catalog physical terminals after rotation/mirroring, supplies
every non-endpoint contact and its escape corridor as a forbidden region, and
validates the result with the existing external-wire electrical checker.
No inference of nets or junctions from ink; no changes to shared APIs.
"""

from collections.abc import Mapping

from gost_schematic.core.geometry import Box, Point
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.routing.two_pin_orthogonal import (
    TwoPinRoute,
    _fail,
    route_two_pins,
)
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.external_wire_checks import validate_external_wires


def route_circuit_two_pins(
    circuit: Circuit,
    parts: Mapping[str, PartDefinition],
    symbols: Mapping[str, SymbolDefinition],
    source: PinRef,
    target: PinRef,
    *,
    net_name: str,
    foreign_wires: tuple[WireObstacle, ...] = (),
    keepouts: tuple[Box, ...] = (),
    grid_um: int = 1000,
    clearance_um: int = 400,
    stroke_um: int = 300,
    bounds: Box | None = None,
    max_cells: int = 50000,
) -> TwoPinRoute:
    """Safely route a declared *two-member* net between exact real physical pins.

    All non-endpoint real physical pins are forbidden even if not assigned to
    any net. This prototype deliberately forbids *all* other contacts,
    including same-net branches: graph junction authoring is not implemented.

    Reserves the full foreign pin's outward 1.8mm escape corridor in addition
    to its exact physical contact and the body's catalog keepout. Caller must
    provide any text/annotation obstacles and all existing drawn wires with
    their actual printed `WireObstacle.stroke_um` as `foreign_wires`.
    This adapter is conservative; failure never leaves a partial connection.
    """
    if not isinstance(circuit, Circuit):
        return _fail("ROUTE_CIRCUIT_INVALID", "Expected immutable Circuit")
    if not isinstance(source, PinRef) or not isinstance(target, PinRef):
        return _fail("ROUTE_PIN_INVALID", "Expected exact physical PinRef values")
    if source == target or type(net_name) is not str or not net_name.strip():
        return _fail("ROUTE_NET_INVALID", "Two distinct pins and a net name required")
    matching = [net for net in circuit.nets if net.name == net_name]
    if len(matching) != 1 or len(matching[0].members) != 2:
        return _fail(
            "ROUTE_NET_INVALID",
            "Exactly one two-contact declared net is supported",
        )
    if set(matching[0].members) != {source, target}:
        return _fail("ROUTE_NET_INVALID", "The net must own exactly both requested pins")
    if (not isinstance(parts, Mapping) or not isinstance(symbols, Mapping)
            or not isinstance(keepouts, tuple)
            or any(not isinstance(box, Box) for box in keepouts)):
        return _fail("ROUTE_CATALOG_INVALID", "Invalid catalog or extra keepout input")
    if not isinstance(foreign_wires, tuple) or any(
        not isinstance(wire, WireObstacle) for wire in foreign_wires
    ):
        return _fail("ROUTE_OBSTACLE_INVALID", "Foreign wires need actual stroke metadata")

    coordinates: dict[PinRef, Point] = {}
    obstacles: list[Box] = list(keepouts)
    references: set[str] = set()
    for component in circuit.components:
        if component.reference in references:
            return _fail("ROUTE_CATALOG_INVALID", "Duplicate component reference")
        references.add(component.reference)
        part = parts.get(component.part_id)
        if part is None:
            return _fail("ROUTE_CATALOG_INVALID", "Unknown physical part")
        symbol = symbols.get(part.symbol_id)
        if symbol is None:
            return _fail("ROUTE_CATALOG_INVALID", "Unknown graphic part")
        positions = component.pin_positions(symbol)
        physical = {pin.number for pin in part.pins}
        if len(physical) != len(part.pins) or any(
            number not in positions for number in physical
        ):
            return _fail("ROUTE_CATALOG_INVALID", "Physical-to-graphic pin mismatch")
        # Exclude every catalog UGO body. Only two *physical contacts* are
        # authorized, not their entire component or any of its other pins.
        obstacles.append(
            component.transform.box(symbol.body_keepout).translated(component.origin)
        )
        corridors = {
            corridor.pin.number: corridor
            for corridor in pin_corridors_for_component(symbol, component)
        }
        for number in sorted(physical):
            ref = PinRef(component.reference, number)
            contact = positions[number]
            coordinates[ref] = contact
            if ref not in (source, target):
                # Positive-area 2µm square around an exact point. The low-level
                # router adds clearance and the NEW wire's half-ink thickness.
                obstacles.append(Box(
                    contact.x - 1, contact.y - 1,
                    contact.x + 1, contact.y + 1,
                ))
                if number in corridors:
                    obstacles.append(corridors[number].box)

    if source not in coordinates or target not in coordinates:
        return _fail("ROUTE_PIN_INVALID", "Unresolved requested physical terminal")
    result = route_two_pins(
        coordinates[source], coordinates[target],
        keepouts=tuple(obstacles), foreign_wires=foreign_wires,
        grid_um=grid_um, clearance_um=clearance_um, stroke_um=stroke_um,
        bounds=bounds, max_cells=max_cells,
    )
    if not result.ok:
        return result

    # A fail-closed independent electrical proof. Do not infer connections
    # from crossings or route ink. No junction is added by this adapter.
    diagnostics = validate_external_wires(
        circuit, result.external_graph(net_name), parts, symbols,
    )
    if diagnostics:
        codes = ", ".join(sorted({item.code for item in diagnostics}))
        return _fail(
            "ROUTE_ELECTRICAL_REJECTED",
            f"External-wire ERC rejected generated route: {codes}",
        )
    return result
