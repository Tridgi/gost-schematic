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


## R30 — joint alignment of a multi-connected satellite

The layout preview now tries moving a two-terminal symbol with 2–8
incident direct physical-pin conductors, including a satellite connected
both to a multi-pin hub and another device. Candidate translations come
from signed opposing pin axes, not symbol center coordinates. Neighbor
poses, rotation, electrical membership, wire identities and terminal
vertex identities stay fixed; all incident routes are rebuilt together.
Unselected endpoints, cross-sheet membership, partial connectivity,
locked layers, annotations and junction-attached paths fail closed.
The move is rejected if it violates symbol/foreign-route clearance,
print margins, diagnostic safety or the strict Pareto gate on total
wire length and turns. No new interior crossings are permitted by the
route builder. Unrelated wire geometry and route statuses remain fixed.
At most eight candidate translations per device and three multi-device
trials per preview; the existing 12-trial overall cap remains.
Preview stays detached until the existing explicit Apply; one Undo
reverts the entire optimization. This is a bounded local heuristic,
not a globally optimal placement solver and not automatic movement of
multi-terminal hubs. New domain tests cover fixed neighbors, two-wire
straightening, preview discovery and rollback for forbidden moves.
Full CI pending.


## R31a — visible ink protection and paper extents

Live diagnostics now check straight stroke width (round-envelope distance
to a disjoint conductor centerline) in addition to exact centerline
intersection. An existing signed pin contact remains exempt under the
previous exact-contact rule. Constant symbol notes are checked separately
against their conservative upright sheet-space text boxes and reported as
DRC_WIRE_SYMBOL_TEXT warnings, without any electrical edge. The existing
layout quality gate includes this new warning. Paper overflow uses exact
cardinal curve extents and straight stroke half-width, including rotated
and mirrored instances; legacy stroke-only scenes remain supported.
Four focused regression tests cover near-miss strokes, text transforms,
and paper edges. This is not a normative GOST clearance certificate:
actual font glyph extents, wire stroke width, arc stroke contact distance,
and dynamic refdes/value labels remain outside this increment. No change
to frozen E695, catalog approval, or electrical membership.


## R31b — curved ink and physical print extents

The arc proximity warning now tests the visible cardinal semicircle
or full circle, using radial endpoint projections and cardinal extrema.
For disjoint conductor centerlines it compares minimum distance against
the symbol stroke half-width. Exact signed pin contact exemptions from
R31a remain. This is visual protection, not an electrical clearance rule.
Paper overflow also accounts for the browser print's 300 µm orthogonal
butt-capped wire stroke and 550 µm explicit junction dot radius.
The projection retains non-electrical sheet graphic stroke widths.
Invisible splice nodes remain point checks. Four tests cover thick
circle near misses, mirrored semicircles, physical print bounds and
non-electrical graphics. No dynamic refdes/value label rendering or
font metric verification is introduced here. Wire width in DRC and
non-cardinal curves are still outside this increment. Frozen E695
and catalogue approval are unchanged.


## R32a — actual TL494 routing preflight, not source editing

Initial tree routing now accepts bounded visual-only labels and sheet
line/polyline/source-b ink as conservative closed routing obstacles.
Stroke width and a 1 mm routing allowance are included; the visual label
uses the upright browser export baseline and a conservative 3.5 mm text
envelope. Free text, Net annotations, excessive counts and unsupported
geometry still fail closed. Existing geometry reconstruction is unchanged.
The new regression checks a real detour around graphical ink and exact
preservation of annotations.

A diagnostic test reads the frozen TL494 fixture, verifies that the
normal authoring session rejects its source provenance, and constructs
an isolated, explicitly synthetic test-only copy with unchanged physical
membership, poses, UGO, two b graphics and visual label. Each of the 15
declared Nets is independently attempted from the same starting copy.
Successful routes must preserve all 62 PinRefs, reach one connected group
and retain review flags; failures must preserve the entire copy.
The test emits TL494_R32A_PREFLIGHT with each Net's result and metrics
or explicit rejection reason. No minimum successful count is asserted:
this is a diagnostic baseline, not simultaneous routing acceptance.
No source unlock, saved candidate, native validation or change to the
canonical source fixture is authorized by this test.


## R32b — reserve signed lead space inside the print margin

R32a CI verified 11/15 independent TL494 routes. SWITCH, TRANSFER,
OSCILLATOR_CT and OSCILLATOR_RT each use a left-facing terminal at
x=10 mm, exactly on the 10 mm print margin. The mandatory outward
lead extends beyond the allowed routing frame. The route builder now
reports TREE_PIN_LEAD_OUTSIDE_FRAME explicitly rather than collapsing
this case into TREE_NO_SAFE_ROUTE.

An explicit preparation command for completely unrouted editable
sheets clamps transformed symbol ink bounds to margin + 3 mm, without
changing rotation, mirror, part definitions, Net membership or visual
annotations. Only the minimum integer translation is applied. Locked
layers, cross-sheet membership, occupied destinations and unsupported
annotations cause atomic refusal. No automatic movement when routing.
The user must confirm the separate preparation action; one Undo
restores the exact original document.

Three tests exercise the boundary failure, preparation and refusal,
and repeat the independent 15-Net TL494 diagnostic on the detached
synthetic copy after preparation (TL494_R32B_PREFLIGHT). No claim of
15/15 before the actual CI log, or simultaneous feasibility. The
frozen source fixture remains unchanged and is not editable.


## R32c — simultaneous initial routing feasibility

The new read-only whole-sheet preview checks up to 16 explicitly declared
untouched local Nets. Three deterministic orders are tried on independent
copies: descending pin count, ascending pin count and ascending bounding-box
Manhattan span. Duplicate orders are skipped. Each route respects previously
placed foreign wires as obstacles; a rejected Net is skipped for diagnostic
coverage only. Candidates rank by connected Net count, bends and wire length.
Only a complete candidate receives the existing revision-bound Apply token.
Partial results are not saved, even if most Nets succeed. The UI reports
failed Net names/codes and asks for explicit confirmation before full Apply.
Maximum 48 attempts, no guarantee of global routing feasibility, no ordinary
foreign X crossings in this mode. Existing 8-Net atomic operation unchanged.
Three tests verify complete and partial previews and emit TL494_R32C_MULTINET
for the prepared detached source copy with all 15 Nets. The source fixture,
annotations and electrical membership remain unchanged; no source unlocking.


## R32d — future terminal reservations and opt-in X crossings

R32c CI confirmed 6/15 simultaneous TL494 Nets (small-first, 29 bends,
2469.673 mm, zero crossings/errors/geometry warnings). Every remaining
Net was rejected TREE_BLOCKED_PIN_LEAD. This exposes an ordering issue:
an earlier route can occupy the mandatory outward lead of a later pin.

The separately confirmed controlled preview reserves conservative 1 mm
envelopes around outward leads of untouched local declared Nets.
Previously routed wires remain obstacles for the first attempt. Only if
no strict path is found may a visibility edge cross a foreign straight
wire perpendicularly, spanning its entire keepout and staying more than
1 mm from each end. No vertex, bend, branch, pin or explicit junction may
occur inside that keepout. Parallel overlap, T/endpoint contact, symbol
ink and annotations remain forbidden. Each crossing costs 20 mm in the
search score; whole-sheet ranking prefers fewer crossings before bends
and length. The quality gate permits only new strict interior crossings
between the current target Net and another Net; connectivity, hazards
and overflow protections are unchanged. Strict mode remains the default.
Bounded search/grid limits remain, and no completeness or GOST approval
is claimed. Three regression tests include TL494_R32D_CONTROLLED.
Full CI and actual controlled routing counts are pending.


## R32e — adaptive visibility-grid capacity and blocked-first retry

The controlled initial-routing mode now retains every mandatory pin-tip
coordinate and both frame boundaries, selecting optional obstacle channels
deterministically by subdivision of the widest remaining gap. The 96-axis,
6500-vertex and 3-million comparison hard limits remain. A conservative
budget accounts for the number of solid keepouts, crossable segments and
signed stubs. Every original obstacle is still checked, including those
whose optional channels were omitted; reduced grid coverage can reject
feasible routes, never authorize collisions. Strict default routing is
unchanged. Two additional deterministic orders prioritize blocked Nets
from the best initial trial; up to five orders / 80 Net attempts (75 for
TL494) on detached copies, no partial Apply. Existing controlled crossing
and topology gates remain. Regression exercises a dense coordinate grid,
straight route, deterministic replay and an impassable barrier. Updated
TL494 benchmark emits TL494_R32E_ADAPTIVE; no claim of improvement until
CI results. The original R32d report remains in its own commit's CI.


## R32f — topology-driven hub satellite pre-placement

On wholly unrouted editable sheets, a separate read-only proposal finds
two-terminal components joined by a declared two-member Net to a hub
having at least four physical terminals. It keeps the hub stationary,
tries the facing cardinal orientation and 12/20/30/40 mm pin gaps,
and accepts only a strictly lower total Manhattan bounding-box span
across local Nets. The directly associated pins must share an axis and
have a clear corridor. Candidate checks preserve all declared future
pin leads, ink/annotation clearance, print margins, locks, cross-sheet
membership, and existing diagnostics. Maximum 48 candidates. No Net
inference, no automatic placement on already wired sheets, and no
source unlock. This is a geometric proxy, not a guarantee of improved
routing; the existing controlled multinet benchmark measures actual
feasibility and quality separately. Existing revision-bound Apply
requires explicit confirmation; Undo restores the original placement.
Three tests cover rotation, fixed hub, read-only preview/Undo, refusal
on wired or locked sheets, and detached TL494 comparison
(TL494_R32F_PREPLACEMENT). CI and actual improvement are pending.


## R32g — connected route refinement

R32f passed the real TL494 test with all 15 Nets connected after moving
C7, R7 and R3: 89 bends, 48 crossings, 6026.963 mm, 79 wires,
34 straight wires, zero errors/geometry warnings/overflow.
The new explicitly confirmed refinement preview considers only connected
local 2–32-pin Nets whose wires all carry needs_routing_review.
This flag is not proof of generated provenance; users must consent to
replacing the eligible routes. It ranks Nets by existing crossings
and length, tries up to two passes / 32 rebuilds on detached copies,
and accepts only strict Pareto improvements in actual geometry.
The controlled adaptive planner retains bounded visual annotations,
physical lead reservations and foreign geometry. Each replacement
must preserve all physical pin groups and existing safety gates;
crossings, bends and length may not increase. Other Net geometry
and route statuses remain unchanged. No movement of components or
change to the frozen source. Entire accepted sequence is one
revision-bound Apply, with exact Undo. Three regressions include
staircase simplification, protection of unmarked routes, and actual
15-Net TL494 refinement benchmark TL494_R32G_REFINEMENT.
Full CI and improvement measurements pending.


## R32h — functional peer-chain placement with full routing comparison

The new explicitly confirmed combined preview prepares a wholly unrouted
sheet, then establishes the hub-only baseline and attempts an extended
functional placement on a detached copy. Up to two continuation layers
follow actual two-member Nets from previously placed two-terminal
anchors to another two-terminal component. Previously placed anchors
remain fixed; the same pose, ink, clearance, signed lead and total
Manhattan span checks from R32f apply. This detects such links as
C4–R3–DA1 without inferring circuit function from reference labels.
The controlled simultaneous router evaluates both placements (at most
two routing previews / 160 single-Net attempts). When both candidates
connect the same number of Nets, the expanded variant must strictly
Pareto-improve actual crossing count, bends and routed length to win.
Only a complete candidate may be applied, and the complete placement
and routes form one revision-bound undoable transaction. An incomplete
candidate is diagnostic only. The new benchmark TL494_R32H_FUNCTIONAL
compares real routed metrics with the hub-only baseline, not solely
the geometric span proxy. Three regression tests cover fixed peer
anchors, complete atomic Apply/Undo and the frozen TL494 test copy.
No source unlock, main merge, or claim of global functional clustering.
CI and quantitative improvement pending.


## R32i — reproducible visual comparison artifacts

The browser CI now executes scripts/tl494-visual-evidence.mjs after
installing Chromium. It bundles the production authoring and export
modules, reads the frozen E695 inventory without changing its bytes,
and builds three independent evidence stages: margin-repaired initial
routing, selected functional routing, and connected route refinement.
Every stage must connect all 15 declared Nets and preserve 23 components,
62 PinRefs, DA1's 16 physical pins, two non-electrical b graphics,
annotations and symbol definitions, with zero diagnosed geometry
warnings/errors/overflow. Refinement must not increase bends, crossings
or length. Each stage exports actual ProjectV2, SVG and browser PNG300;
the JSON manifest records dimensions, metrics, source-file SHA256 and
artifact SHA256 values. This makes the geometry inspectable rather than
relying on schematic illustrations or aggregate scores alone. The
artifact is named tl494-routing-visual-evidence. IDs are generated at
runtime; hashes identify the produced files, not a promise of identical
bytes across runs. Preview fonts remain unverified, and the current
browser exporter records refdes in metadata rather than complete visible
reference/value labels. This is not normative ESKD print acceptance,
a canonical source unlock, or native Windows acceptance.
R32g confirmed 15/15, 87 bends, 41 crossings, 5763.668 mm after refinement.
R32h main CI passed; browser result and R32i evidence CI pending.


## R32j — derived visible component labels

Canvas and browser SVG share one bounded read-only label placement
function. Upright reference designators and existing nonempty values
use 2.5 mm monospace preview text, conservative physical envelopes
and eight nearby candidate positions at four distances. Candidate
envelopes must stay inside print margins and clear every transformed
symbol envelope, conductor, junction, source graphic, sheet annotation
and previously placed label. Missing values are never invented.
Unplaced labels are explicitly counted on canvas and listed in SVG
metadata and the R32i evidence manifest. Existing Net membership and
serialized projects remain unchanged. Labels are derived after route
geometry, not yet reserved as permanent routing obstacles. The planner
is conservative, so a failed placement is not proof that no placement
exists. Preview font metrics and actual printed typography remain
unverified; canonical Python/Windows export parity is not claimed.
Two regression tests cover deterministic identity, label counts,
non-overlap, empty values, XML escaping and explicit refusal.


## R32k — complete visible reference inventory

R32j CI verified 156/156 unit tests and 52/52 browser tests.
The three-stage actual TL494 artifact reported 23, 22 and 22 placed
reference designators respectively; the refined geometry connected
15/15 Nets with 81 bends, 38 X crossings and 5340.345 mm wire length.

The shared label planner now first evaluates the original nearby slots
against immutable geometry, then retries in fewest-candidates-first
order if assignment is incomplete. Only if necessary it expands
candidate channels along the owning symbol's sides (2.5 mm offsets,
up to 20 mm normal gap), preserving 2.5 mm font height, the existing
conservative envelopes and 0.5 mm padding. Successful original
assignments are preferred; the expanded result is used only if it
places more labels. Search remains bounded by a 12-million static
geometry comparison cap; incomplete assignments are reported honestly.
One regression exercises blocked original slots, deterministic replay,
unchanged text size and obstacle clearance. Evidence now records exact
unplaced reference designators/reasons and checks the full inventory.
After publishing the evidence and running browser E2E, CI requires
23/23 visible references at every TL494 stage. A failed acceptance gate
does not erase the diagnostic artifact. This is a bounded heuristic,
not global placement completeness or normative GOST typography.
Labels remain derived, not permanent route obstacles. Main and frozen
source unchanged. R32k results pending.


## R32l — native Python label and export parity

R32k passed both CI gates: 157/157 unit tests, 52/52 Chromium tests,
23/23 visible reference labels on each of the three actual routed TL494
stages, with unchanged refined geometry (15/15 Nets, 81 bends, 38 X
crossings, 5340.345 mm). The canonical Python exporter previously did
not emit visible component reference/value labels. It now derives
upright labels from the same bounded placement contract as the browser,
preserves their non-electrical identity and reports unplaced labels in
metadata and export warnings. The canonical source SHA gate remains;
no actual nominal values are inferred. Preview text remains unverified
and strict-font export still refuses unoutlined text.

The added integration check consumes the real browser evidence for all
three stages and invokes the canonical Python SVG/PNG300 export engine.
It requires identical instance/role/text/position/font-height/anchor
records, 23/23 visible references, 15 declared Nets, 62 PinRefs, two b
graphics, preserved wire/junction inventories, correct project digest
and A3 4961 x 3508 pixels at 300 DPI. Native evidence is published as
tl494-native-export-parity. Browser and native raster bytes are not
required to match because rendering/font fallback may differ. The
independent implementations need CI parity checks to detect drift.
Actual installed Windows/WebView2, print typography, and normative
approval remain separate acceptance stages. R32l CI pending.


## R33 — full TL494 installed Windows acceptance

The R32l initial CI failed at Ruff UP035/I001 import checks; these were
fixed on the same branch without changing geometry (4c5e2dc). Its
native parity run still requires a successful final result.

The R33 branch extends the existing installed NSIS/WebView2 R9
harness, not a mocked browser-only workflow. A CI-only generator
constructs a detached complete TL494 using the production functional
routing and refinement modules and checks 15 connected Nets, 62
PinRefs, 23 labels and frozen-source invariants. After the original
three-component native regression, the same current-SHA installer
opens the complete generated project through the actual OS picker,
checks visible component/label/wire inventory and Python reachability,
saves to the existing path, saves a Unicode-path copy, and exports
SVG and PNG300 through the real native dialogs. It closes the app and
repeats the scenario with the saved copy. Both rounds require unchanged
canonical digest, 23 visible SVG references, 15 Nets, and 300 DPI PNG.
Successful round files are copied to the isolated CI artifact folder.
The original source fixture and main remain untouched. The R33 branch
push enables the existing Windows workflow; its full acceptance mode
is deliberately limited to R33 branches. No actual Windows PASS is
claimed until the installed-app job completes.


## R35 — bounded alternative tree search

R34's exact head (9e08b09ecf7d0515b567bc507dfd9da34113130b) passed
main CI, Visual CAD and installed Windows. Its measured baseline is
15 connected Nets, 23 labels, 81 bends, 38 crossings and 5340345 um.

The existing refinement command retains its default two-pass / 32
trial behavior. An explicit extended command adds at most 48 trials,
with three deterministic alternatives: crossing penalty 60000 um
instead of 20000, bend penalty 15000 um instead of 5000 with a central
root terminal, and a peripheral root selected by total Manhattan
distance. Terminal indices, signed leads, obstacle envelopes and
planner search bounds remain unchanged. The objective weights are
heuristics, not normative dimensions. For each prioritized Net,
all alternatives are evaluated on the same detached snapshot.
A candidate must pass the real geometry and connectivity Pareto gate
and preserve all already-visible label identities. Winners are ranked
by actual crossings, then bends, then length. The entire result uses
the existing revision-bound Apply/Undo; the live model does not change
during the preview. At most 80 total rebuild attempts; no claim of
global optimality, and the explicit extended command is synchronous.

Two regression tests cover alternative terminal mapping and signed
lead preservation, determinism, the actual TL494 baseline comparison,
complete physical membership, unchanged symbol positions and atomic
Undo/Redo. The browser evidence gains stage 04-extended-routing and
canonical Python checks its actual SVG label geometry and PNG300.
R35 installed Windows CI also uses the extended generated project,
asserts no baseline regression, and checks its actual persisted wire
inventory and SVG count instead of imposing a fixed 78-wire count.
Previous R33/R34 fixed baseline checks remain. No edits to main or the
frozen E695 source, and no new improvement claimed before CI.


## R36 — review-only common trunk refinement

The existing single-Net rail command remains conservative by default.
The new explicit refinement mode also handles bounded visual labels
and non-electrical graphics as hard obstacles. Foreign wire segments
are traversable only at a perpendicular strictly interior X crossing,
more than 1000 um from both segment endpoints, with all junctions,
splices, symbol envelopes and annotations protected. Each final trunk
interval is checked separately: a crossing at a newly introduced tap
cannot become a false connection. Candidate trunks prefer fewer
crossings, then bends, then length. Only strict improvements in actual
layout assessment are accepted, with identical signed connectivity,
foreign geometry and visible label identities; manual/unmarked routes
are not eligible. The 500000 comparison cap remains per search.

The new explicit preview tries at most 16 eligible local Nets with
3–32 pins, prioritized by existing crossings and pin count. The live
project stays unchanged until a revision-bound Apply, with Undo/Redo.
Two regression tests cover an artificial detour on an annotated
four-pin trunk and refusal of unmarked routes. Evidence adds stage
05-common-trunks, checks monotonic metrics, and requires native Python
export parity. R36 Windows acceptance uses the extended and trunk
refinement results, not a hardcoded wire count. Prior R35 exact head
2fa62783 passed frontend typecheck/unit and generated four evidence
stages while E2E and native acceptance were still running. No claim
of numerical R36 improvement before CI. Main/frozen fixture untouched.


## R37 — compare functional placement profiles before routing

R35 exact 2fa62783 passed main CI and Visual CAD (160 unit, 52
browser tests and four-stage Python label geometry parity).
All 60 actual TL494 refinement attempts were rejected, leaving the
81 bends / 38 crossings / 5340345 um baseline unchanged. R36
compiled, passed its domain checks and generated five-stage evidence;
final R36 and R35 Windows results were still pending when this branch
was prepared.

An explicit placement comparison command on an entirely unwired sheet
now evaluates default, compact and spacious functional placement.
The existing deterministic gap sets (12/20/30/40 mm) remain the
default; additional profiles use 8/12/16/24 and 20/30/45/60 mm.
These are heuristic pin-to-pin gaps, not normative GOST dimensions.
Each profile uses the existing signed terminal, symbol/ink clearance,
placement and whole-Net routing checks. Complete candidates receive
the same normal refinement, extended refinement and common trunk
refinement as the established R36 pipeline. Selection compares actual
complete route metrics, not estimated placement spans, and requires
strict Pareto improvement and retention of visible label identities.
Default complete layout is the fallback. No live document changes
until revision-bound Apply; Undo/Redo restores the entire operation.
Maximum three profiles, each subject to existing per-stage search
caps; up to 384 refinement attempts. This is an explicit synchronous
search and may be slower; no global-optimality guarantee.

Two domain regressions cover atomic full candidate selection and invalid
profile refusal. CI adds 06-placement-profiles to comparative SVG,
PNG300, ProjectV2 and Python parity, with non-regression against stage
05-common-trunks; installed Windows exercises the chosen project.
No claim of numeric improvement or Windows PASS before logs. Main
and frozen E695 unchanged.


## R38 — local shortcuts without moving terminals or nodes

R36 main CI and Visual CAD passed (162 unit, 52 browser tests).
All 11 TL494 common-trunk trials were rejected, leaving the R34
geometry unchanged. R37 built successfully and generated its sixth
comparison stage; its full CI and native acceptance were still
running when R38 was prepared.

R38 adds an explicit review-only local shortcut preview, independent
of whole-Net rerouting and placement. For each eligible 3–24 vertex
wire, try replacing a short subpath (up to six segments) with a
straight segment or one orthogonal corner, compacting collinear
segments and rejecting reversals. The existing physical pin lead
direction and length cannot decrease; explicit junction and splice
coordinates, endpoint identity, wire ID, all other wires and all
component poses remain unchanged. Candidate paths must remain inside
the print frame, clear symbols and annotation ink by 1 mm, avoid
foreign overlaps and endpoint contact except exact shared explicit
anchors, and allow only proper different-Net X crossings more than
1 mm from endpoints. Independent engine validation, strict real
Pareto improvement, and retention of visible label identities are
required. Maximum 12 candidates per wire and 64 trials per preview.
Revision-bound Apply and Undo/Redo remain atomic. Two regressions
cover deterministic physical-lead shortcuts and a detoured common
trunk with fixed endpoints and foreign geometry. The seventh evidence
stage and Python parity plus exact-head installed Windows acceptance
exercise the final route. No actual numerical improvement claimed
until CI. The search is a conservative bounded heuristic; 1 mm is
a chosen engineering clearance, not normative approval. Main and
frozen E695 untouched.


## R39 — crossing-channel refinement

R38 exact f2b3b65c141e5d07094cc1ce99d7122f5cfdc3c4 passed all three
workflows. The new protected measured TL494 baseline is 77 bends,
38 crossings and 5282207 um, with 15 connected Nets, 62 PinRefs,
23 labels and no geometry diagnostics. R37 compact placement and
the accepted R38 TRANSFER shortcut yielded the improvement.

R39 adds an explicit mode of the local preview. It prioritizes wires
with different-Net crossings and tries alternate L corners and
monotone Z channels. Candidates sample endpoint-relative channels
and foreign segment boundaries +/-1001 um. Local ranking requires
a reduction of unique foreign Net/position crossings without extra
length or bends. Existing physical lead direction and length are
preserved, as are wire IDs, terminal IDs, symbol poses and node
coordinates. The existing R38 geometric clearance and independent
engine validation remain active; the full assessment must confirm a
strict reduction of total crossings, no increase in bends or length,
and no lost visible label identities. Search caps: 192 scored
candidate paths per wire, 12 selected paths per wire, 96 full trials
per preview. This is a conservative heuristic, not exhaustive.
The eighth evidence stage checks the measured R38 floor and
monotonic improvement, actual Python/browser label parity and native
Windows persistence. Two regression tests exercise equal-length Z
channel improvement, signed lead retention and atomic no-op.
R39 numerical improvement and CI results pending. Main and frozen
E695 unchanged.
