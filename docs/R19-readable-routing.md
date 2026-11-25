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


## R22 — quality-gated optimization preview

The optimizer works on isolated AuthoringSessions; no mutation occurs while
generating the preview. It discovers closed two-Net parallel groups and
connected direct-wire groups, invokes the existing pair/series/rail solvers,
and tries direct-wire cleanup. All accepted operations accumulate in one
candidate. Only 12 trials are attempted, with 128 components and 512 segments
maximum on the active sheet. It is a bounded greedy search, not a global optimum.

Measured quality includes length, direction changes (also across degree-2
splices), strict interior perpendicular crossing coordinates, diagnostic
hazard multiplicities, paper overflow identities and signed pin-group
connectivity. No candidate may increase length, bends or crossings, add
measured hazards/overflow or alter pin connectivity; at least one criterion
must improve. Routing-review flags are not geometry errors. Incomplete
diagnostics fail closed. Sheet-level annotations and hidden/nonprintable used
layers are currently excluded.

The modal uses the two actual detached ProjectV2 preview SVGs with an identical
physical viewBox, not a mockup. Apply consumes an opaque revision-bound token
and checks the owning session and content epoch; Cancel discards it.
One Undo restores the complete pre-optimization document. Native physical
export is still separate; the preview is not a normative approval or a complete
annotation/clearance certificate.


## R23 — multi-terminal anchors and source topology inventory

The automatic optimizer now recognizes a fixed multi-terminal anchor (at least
four signed physical pins and at least two attached wires). A selected
two-terminal satellite with exactly one attached direct wire can be aligned to
its own facing hub pin. The anchor pose is checked unchanged after each trial;
other satellites, external connections and topology are preserved. All trials
still pass the R22 quality gate. This is local alignment, not a full placement
algorithm or inference of circuit function.

The read-only Electrical Structure report enumerates actual physical pins,
literal Net names, unique neighboring devices and shared Nets (at least three
local components). Explicit power evidence comes only from catalog
power_input/power_output types, not names or coordinates.

The frozen TL494 E695 fixture has 23 placed components, 15 declared Nets,
DA1 with 16 physical pins across nine Nets; COMMON has 14 memberships across
11 distinct components. The CT and RT connections are reported from literal
source memberships. The source itself remains immutable and unrouted in
ProjectV2. Tests do not silently copy or alter it.


## R24 — individual Net trunk reconstruction

The topology report exposes an explicit common-trunk command for shared Nets
on authored sheets. The solver accepts 3–32 physical pins in one already
connected, local Net on a single unlocked electrical layer. All pin normals
must lie on the same axis, but leads may point toward the trunk from either
side. Opposite leads may share a tap; same-side coincident leads are rejected.

The feasible trunk interval is constrained by actual transformed symbol
envelopes, a 5 mm lead allowance, and the printable frame. Candidate channels
come from the interval limits, midpoint and obstacle boundaries; at most 64
are evaluated, ordered by total conductor length. All branches and the trunk
must clear unrelated wires, nodes and symbols. Explicit degree-3/4 junctions
and degree-2 invisible splices preserve signed topology. No symbol moves or
new memberships occur. Existing route IDs are replaced only with consent;
equivalent geometry is a no-op, and Undo restores the exact old geometry.

The R22 optimizer also tries these candidates within the selected scope and
trial budget. Its stricter quality gate may reject a longer trunk. No
automatic power assignment, arbitrary mixed-axis branch routing, or source
fixture mutation is implied. Text/label/graphic obstacles are still excluded
rather than guessed. Limits and clearances are draft engineering heuristics.


## R25 — mixed-axis individual Net rails

For mixed signed pin normals the single-Net rail planner tries horizontal
and vertical trunk orientations (at most 32 candidate channels per axis).
Pins facing the trunk retain straight perpendicular leads. Pins parallel to
the trunk leave their own signed terminal outward and make one right-angle
turn; up to 24 obstacle-derived tap candidates are considered for each.
Branches cannot cross or overlap one another; two opposite-side branches
may meet only at their common explicit tap. Distinct taps require at least
1 mm separation. All branch segments and the full trunk are checked against
unrelated wires, nodes, symbol bounds and print margins. Candidate geometry
is ranked by lead bends first, then Manhattan length. The search uses
500,000 geometric comparisons at most and fails closed at that limit.

The procedure is greedy, not a complete maze/Steiner solver. It may reject
a routable Net that needs two or more lead bends, moving symbols, or multiple
trunk sections. Same-axis R24 behavior, immutable signed membership,
no-new-hazard/crossing gate, route review flags and one-step Undo remain.


## R26 — obstacle-aware orthogonal Net tree

If one straight trunk cannot reach all signed pins, an explicit tree command
can reconstruct an already-connected local Net. The planner creates mandatory
outward leads, expands obstacle envelopes by 1 mm, and builds a compressed
rectilinear visibility grid from lead tips, obstacle boundaries and printable
frame limits. A multi-source shortest-path search grows an acyclic tree,
using a 5 mm equivalent bend penalty. Degree-two chains are compacted into
orthogonal polylines; only degree-three/four branch nodes become junctions.
Other Nets and symbol poses are untouched. No inferred contacts are allowed.

Limits: 3–32 pins, 96 coordinates per axis, 6,500 grid cells, 640 obstacles,
3 million geometric comparisons. No result on exhaustion or blocked leads.
The R22 optimizer may try the tree under the existing non-regression gate;
the explicit command preserves signed connectivity and adds no measured
hazards or crossings. The user must review the resulting routes. This is a
bounded heuristic, not an exact rectilinear Steiner optimum or complete
maze solver. Unrouted declared Nets and frozen source projects remain
outside the reconstruction command.


## R27 — signed terminal lead bend accounting

R26 charged 5 mm per internal visibility-grid turn but ignored the physical
lead axis at the initial root and destination. In an unobstructed three-pin
fixture this produced 98 mm / four bends rather than 90 mm / one bend.
A second fixture preserved 98 mm while reducing three bends to two.

R27 reuses the same bounded visibility graph for two deterministic greedy
tree-growth strategies. The lead-aware strategy initializes the isolated root
with its signed lead axis and includes the destination lead turn in goal
selection; a reached terminal is not expanded. Existing-tree attachments
remain free-axis junctions. Physical stub constraints are unchanged.
The baseline is retained unless the candidate has no more bends and no
greater length + 5000 um * bends cost. The visibility-grid envelope and
comparison limits remain unchanged; tree growth may run twice.

Regression tests exercise actual production planner, signed endpoint geometry,
junction, unchanged input and deterministic repeated output.
This remains a bounded heuristic for already-connected Nets; no global
optimality, automatic creation of missing source routes, or GOST approval.


## R28 — first route for an existing declared Net

In a synthetic editable ProjectV2, the topology report lists untouched local
Nets with 2–32 declared physical PinRefs and no wires, junctions or splices
on any sheet. The explicit "Развести цепь" action asks for confirmation.
It uses the bounded R27 orthogonal planner, supports two-terminal paths,
and requires exactly one visible printable unlocked electrical layer.
The pre/post connectivity comparison excludes only the target Net, whose
complete one-group connectivity is verified independently; all other Nets,
diagnostic hazard multiplicities, crossings and overflow remain gated.
Other route statuses are retained. No inferred membership, component motion,
or replacement of partially drawn manual routes is allowed. One transaction
supports Undo/Redo; generated wires retain needs_routing_review.

This does not unlock the frozen E695 source or route a full board automatically.
No geometry may be added if annotations are present or the safety/search
budget is exceeded. A failed route leaves the document and history untouched.
Unit and real-browser regression tests cover initial routing, physical
membership, foreign routes, locked layers, stale CAS and repeat refusal.
Full CI and installed native acceptance are required before declaring PASS.


## R29 — atomic initial routing batch

The topology dialog offers an explicit batch action for the first eight
eligible untouched local Nets (or all eligible Nets when there are at
most eight). A confirmation describes all-or-nothing semantics.
The domain command accepts 1–8 distinct existing Net IDs. It routes a
detached AuthoringSession in descending terminal-count order, then tries
the reversed order from the original document if the first fails. Each
R28 route treats earlier committed draft routes as foreign obstacles and
retains the diagnostic, frame, and other-Net connectivity gates.
No intermediate draft, revision or history entry is published. Only
complete success with unchanged source inventory and one connected group
per target Net can commit; one Undo reverses the entire batch.
Failure reports the last rejected Net and reason and preserves the document.
At most 16 individual route attempts; no claim of complete multi-Net
search, global optimum, crossing insertion, partial-route repair or source
E695 editing. This remains synchronous and intentionally bounded.
Three domain regressions and one Chromium acceptance scenario cover
success, rollback, stale CAS, invalid inputs and atomic Undo/Redo.
Full CI and installed native acceptance are still required.
