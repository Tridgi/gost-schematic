# ADR-0007 — Electrical polarity is a property of physical pins, not УГО

Status: experimental implementation; pending user review.

## Core rule

Every physical pin has `TerminalPolarity`: `none`, `positive`, or
`negative`. This belongs to `PhysicalPin` in `PartDefinition` and
is **not** inferred from graphical `GraphicPin.label` or symbol geometry.

The capacitor's immutable physical catalog entry is in
`catalog/parts/capacitors/polarized.json`:

| Pin | Name | Electrical type | Polarity |
|---|---|---|---|
| 1 | PLUS | passive | positive |
| 2 | MINUS | passive | negative |

The graphic symbol independently uses the same stable pin numbers. The
compatibility validator reports `GRAPHIC_POLARITY_MISMATCH` if a visible
`+` or `-` label contradicts the physical mapping. Rotating or mirroring
moves coordinates but never changes `PinRef` or `TerminalPolarity`.

## Opt-in voltage rule

`PartDefinition.voltage_orientation_rule` is `none` by default.
The polarized capacitor opts into
`positive_not_below_negative`, requiring exactly one positive and one
negative physical terminal. The rule is deliberately NOT applied
automatically to diode anodes/cathodes, LEDs or unpolarized capacitors.

## Scope and uncertainty of ERC

`NetPotential` contains a **declared** signed Decimal voltage on a
named net, with a required `reference_id`. Neither `GND`, `+12V`,
nor graphical ground symbols are interpreted as measured voltages. A
`PotentialScenario` is one named static operating point.

The polarity evaluator requires:
- both physical pins connected to exactly one named net each;
- voltages explicitly supplied for both nets;
- the same `reference_id` for the two voltages.

Results:
- `forward`: V(positive) > V(negative), no error **for this scenario only**;
- `reversed`: V(positive) < V(negative), ERROR `POLARITY_REVERSED`;
- `zero_bias`: equal voltages, INFO rather than claiming verified polarity;
- `unknown`: missing, ambiguous or incomparable data, WARNING
  `POLARITY_UNVERIFIABLE` (never silently treated as correct).

The evaluator cannot prove compliance during startup, AC cycles,
transients, reversal under fault conditions, or absolute capacitor voltage
rating. Future simulation may provide multiple actual operating scenarios
and rating limits, but must not replace explicit checks with net-name
heuristics.

## Architecture

- `model/pins.py`: shared frozen physical-pin polarity field
- `model/part.py`: explicitly opted-in voltage rule
- `catalog/part_loader.py`: separate versioned physical part JSON
- `model/potentials.py`: signed exact-voltage operating points
- `validation/polarity_checks.py`: tri-state-plus-zero electrical checks
- `validation/circuit_checks.py`: existing netlist and symbol consistency,
  with optional operating-point scenario
- `examples/review_polarity_erc.py`: machine-readable forward, reversed and
  unknown cases

No drawing layout, font, nominal formatter or route generator is modified.
Only the part catalog and independent electrical validator are extended.
