# R19 — readable schematic layout

## Basis

- GOST 2.701-2008 §5.5.2: orthogonal connections with minimum bends and crossings. https://base.garant.ru/6180373/
- Wybrow, Marriott, Stuckey, *Orthogonal Connector Routing* (2009): obstacle avoidance, length and bend cost, route nudging. https://users.monash.edu/~mwybrow/papers/wybrow-gd-2009.pdf
- KiCad schematic editor: grid and Align/Distribute commands. https://docs.kicad.org/master/en/eeschema/eeschema.html
- TU Delft, *Guidelines for Drawing Schematics*: alignment and readable signal flow. https://eee.ewi.tudelft.nl/q1-courselabs/schematics/

## Implemented, DRAFT engineering policy

1. Prefer 0, 1, 2 bends, only more for necessary detours. This is a preference, not a numerical GOST requirement.
2. For each candidate, respect signed pin direction, reject self intersections/backtracking; sort by bends, Manhattan length, balance of a Z route. Sheet smart mode prefers no crossings; proper interior X crossing is a fallback only.
3. Pin magnet proposes actual facing terminal alignment, not center alignment. Opt-in; at most 5 mm transverse adjustment, 4–80 mm forward gap; no Net is created. Ambiguous suggestions are rejected.
4. Align connected pair explicitly: one direct wire, opposed normals, one movable component with no other attached wires, safe straight route and printable margins. Preserve Net and terminal identities.
5. Simplify existing direct pin-to-pin routes: no symbol moves; no new crossings; never increase length or direction changes. Skip locked layers and branched/dangling wires. Atomic Undo/Redo.

The 1 mm conservative bounding-box clearance, 2 mm preferred lead, 5 mm magnet range and bounded search limits are project heuristics, not certified GOST dimensions. No automatic global layout, no whole-net bus/trunk optimizer, no text/label collision certificate; the existing DRC and review workflow remain required. Existing frozen source stays immutable. No third-party implementation code was copied.
