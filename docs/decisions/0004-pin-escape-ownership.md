# ADR-0004: Connector identity and restricted escape corridors

Status: experimental implementation — awaiting user review.

## Problem

A green rectangle outside each pin in the symbol diagnostic view is NOT the
contact's hitbox. It reserves space so other symbols, text and foreign wires
cannot obstruct the very first conductor leaving the connector.

Treating the rectangle as an ordinary immutable obstacle would also block
the *intended* connection. Treating it as wholly passable for all conductors
on a matching net would permit wires to enter sideways and defeat the purpose.

## Decision

`PinEscapeCorridor` is an immutable typed object with:
- physical identity `PinRef(component_reference, physical_pin_number)`;
- exact global connector `contact`, after rotation/mirror/translation;
- an outward `Side` normal and rectangular `box`;
- a strict admission predicate for the particular wire segment physically
  ending at that connector and leaving it along the outward axis.

`WireObstacle` adds optional `attached_pin` and `net_name`. Permission to
use a corridor requires exact physical-pin identity, connector coincidence,
and an outward-aligned segment. Membership in the same electrical net by
itself does NOT grant entry. A route through a body or text hitbox remains
forbidden even if it is attached to the correct pin.

`validate_wire_clearance` returns structured errors for:
- `ROUTE_OBSTACLE_OVERLAP` (symbol or annotation intrusion);
- `ROUTE_PIN_ESCAPE_BLOCKED` (foreign / off-axis / disconnected wire);
- `ROUTE_NET_MISMATCH` (wire's declared pin/net pair disagrees with a supplied circuit).

`validate_port_reservations` reports:
- `PIN_CORRIDOR_OBSTRUCTED` (foreign obstacle overlays reserved exit);
- `PIN_CORRIDOR_OVERLAP` (two protected connector exits overlap).

The annotation solver deliberately treats ALL corridors as hard obstacles,
including a label belonging to the same component. This has different
semantics from routing and is implemented via `obstacles_for_component`.

## Geometric convention

By default a corridor measures 1.8 mm outwards and 0.8 mm across. These are
**draft engineering parameters**, NOT normative GOST dimensions. They are
inputs to a policy and can be overridden. All calculations use integer µm.
The fixed resistor has physical contacts at -8 and +8 mm on its local X axis.

## Limits and next stages

This validates individual straight conductor segments: it does NOT yet
create orthogonal routes, optimize paths, establish finished electrical-net
connectivity, infer junctions, or handle a bend inside a protected exit.
A future multi-segment router must preserve the attached physical-pin
identity for the first leg; later legs cannot inherit unrestricted port access.

Spacing/collision validation of every object on an entire sheet remains a
future aggregate validation step. The committed tests exercise the reusable
geometry and permission contracts in isolation and with sample circuits.
