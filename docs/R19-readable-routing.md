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


## R20 — selected chain layout

A selected simple geometric path of 3–32 components is built from existing
direct signed pin-to-pin wire endpoints (not proximity, nor inferred circuits).
This is a geometric chain operation, not proof that components form an electrical
series circuit. Each direct connection must use opposing pin normals on a common
axis and preserve its forward order. Mixed pin heights are handled using
relative transverse physical pin offsets instead of symbol centers.

- Align: solve the offsets along the path, minimize total absolute transverse
  displacement with a median common shift; try remaining existing candidate
  axes if obstacles prevent the median. External connections and locked
  components pin the transverse axis; contradictory fixed constraints reject.
- Distribute: optionally equalize longitudinal gaps between facing physical
  pins, preserving the longitudinal positions of the two end components.
  Integer rounding differs by at most 1 µm between gaps. Nonmonotonic chains,
  fixed intermediate poses that cannot satisfy spacing, and gaps below 4 mm
  are rejected.
- Trial: do not move external conductors; check changed component envelopes
  against existing symbols, wires, explicit nodes and print margins. Remove
  internal wires only in a cloned trial, require every new route to be straight
  and crossing-free, then commit once. Undo restores the whole previous file.
  Net IDs/members, rotations, original wire IDs and signed terminal identities
  remain unchanged. Changed wires require routing review.

The search is bounded and conservative; it is not a complete global placement
solver. The 4 mm minimum gap and 1 mm obstacle envelope are draft heuristics,
not normative GOST dimensions. General parallel rail/branch layout, full
annotation collision checking and multi-net topology optimization remain open.


## R21 — closed parallel branch layout

Select 3–24 existing two-terminal components whose physical pins belong
to exactly two complete, already connected Nets. Both Nets must be wholly
within the selection and active sheet, with no free ends and one unlocked
electrical layer per Net. No membership inference from proximity or labels.

- Rail-only mode leaves all component poses untouched. Two straight rails
  run outside the selected symbol bounds, with orthogonal branch leads.
  Extreme taps have invisible degree-2 splices, intermediate taps explicit
  degree-3 junctions. Finite 5/10/15/20/30 mm rail offsets are tried.
- Symmetry mode requires equal physical pin spans and opposed normals.
  It preserves extreme lateral coordinates, distributes physical contacts
  evenly to within 1 µm, and aligns both pin rows using a median or fixed
  locked-row constraint. No external Net member may be moved.
- Unrelated wires, nodes, symbols and printable margins are checked
  conservatively. Text/label anchors are obstacles, not complete text
  outlines. Changed wire and junction IDs are intentionally regenerated
  with explicit user consent. Net IDs and physical membership never change.
  Equivalent repeated geometry is rejected as NO_CHANGE.
- The whole edit is one CAS transaction, with exact Undo/Redo and validation
  of signed connectivity. New routes require review.

This is not a general power/ground bus or arbitrary branched Net solver.
Rail offsets, minimum gap and bounding clearance are DRAFT heuristics.
