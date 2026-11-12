# Capacitor symbolic geometry — Stage 0.8

Status: draft; user visual review pending.

## Normative references and implemented templates

ГОСТ 2.728-74 is active (Rosstandart), and table 6 on p. 21
shows the fixed capacitor plates as **8 mm** long, separated by **1.5 mm**.

- `capacitor.fixed`: plates at x=-0.75/+0.75 mm, y=-4..4 mm;
  local contact pins 1 and 2 at x=-8/+8 mm, along the horizontal axis.
- `capacitor.polarized`: shares the same base plates with an explicit
  vector `+` mark on the left (physical pin 1); this uses the *polarized
  fixed capacitor* designation of table 4, not a certified electrolytic
  body rendering. Users must approve the location/size of the + mark.
- Two symbol definitions live in independent versioned JSON files under
  `catalog/symbols/capacitors/`; they do not inherit from resistor symbols
  or share mutable globals.

The line thickness is 0.3 mm as a **draft document profile**. ГОСТ 2.728-74
§7 states that the UGO lines should have the same thickness as electrical
connection lines; a future document style enforces this consistency.

## Behavioral contracts

- Pins have stable physical numbers, directions and transformed coordinates.
- Dedicated component body keepouts and port escape corridors remain independent.
- Every rendered graphic primitive, including the complete connector lead from
  plate to pin contact, is a text obstacle with stroke-width clearance.
  This prevents vertical C3 labels crossing their own leads (regression test).
- Refdes/nominal annotation slots are separate; sheet-wide placement policy
  automatically avoids protected leads and text hitboxes.
- In `eskd_compact` mode: 100 nF → `0,1мк`, 470 µF → `470мк`.
- Switching to `full_units` recalculates labels and collision geometry.
- Each draft export can show clean vs collision-overlay SVG.

## Important distinctions

A polar capacitor symbol is **not** an electronic model of its breakdown
voltage or electrical characteristics. The '+' mark is a local graphical
primitive, anchored to the intended positive physical pin. The library's
geometry check proves symmetry, plate distance and deterministic transforms,
but does not prove complete ГОСТ conformity or correct KOMPAS import.
Do not approve or merge the UGO until user visual comparison.
