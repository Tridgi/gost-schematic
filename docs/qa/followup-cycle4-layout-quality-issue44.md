# Issue #44 — measurable, placement-aware schematic layout quality

**Purpose:** prevent visually pointless conductor doglegs by coordinating **component placement** and **external orthogonal routing**, while leaving immutable physical pin numbers, circuit netlist, explicit junction semantics and the existing public API unchanged. This is a QA measurement proposal, not a placer, normative standard or automatically applied repair.

**Reproduced from**: `examples/review_end_to_end_circuit.py::authored_specimen()` on `integration/stage0-12` @ `73bc6f88a814d7b92267326fc1dab8f127e92e77`; user report [Issue #44](https://github.com/Tridgi/gost-schematic/issues/44). New tests: `tests/test_qa_followup_layout.py`, metrics reference: `scripts/qa_followup_layout_quality.py`.

## 1. Real C3 specimen: length ALONE cannot detect poor geometry

The current C3 origin is (100,75) mm, physical pins C3.1=(91,75), C3.2=(109,75). Branch TOP from (40,40) to C3.1:

```
(40,40) → (40,80) → (84,80) → (84,75) → (91,75)   # mm
```

The documented candidate moves *only C3* 5 mm down: C3 origin=(100,80) and pins C3.1=(91,80), C3.2=(109,80):

```
TOP:   (40,40) → (40,80) → (91,80)
RIGHT: (120,40) → (120,80) → (109,80)
```

All other six-device specimen component placements, **five semantic nets** and **three explicit junction points** remain unchanged; the original last six authored wire segments are replaced by four segments. Both candidate and original pass `validate_external_wires`, and independent tests check the changed wires against every real component body expanded by 0.55 mm. This **does not** check annotation/text hitboxes or formally certify DRC/ГОСТ.

| Metric | Original branches (TOP+RIGHT) | Moved C3 candidate | Delta |
|---|---:|---:|---:|
| Total wire length | **142 mm** (96 TOP, 46 RIGHT) | **142 mm** (91 TOP, 51 RIGHT) | **0 mm** |
| Total 90° bends | **4** (3 TOP, 1 RIGHT) | **2** (1 TOP, 1 RIGHT) | **−2** |
| TOP non-Manhattan excess | **10 mm** | **0 mm** | **−10 mm** |
| TOP physical backtrack | **5 mm** | **0 mm** | **−5 mm** |
| TOP same-axis direction reversals | **1** | **0** | **−1** |
| TOP legs shorter than 8 mm | **2** (5 mm, 7 mm) | **0** | **−2** |
| Placement displacement | 0 | 5 mm | +5 mm |

**Important distinction:** when endpoints move with the component, their Manhattan lower bound changes. Do **not** compare raw detour ratio across different endpoint positions without preserving the pin-to-net semantics.

A demonstrative cost in units of mm-equivalent is:

```text
J = Σ length
  + (5 mm) × Σ 90° bends
  + 2 × Σ (length − Manhattan(endpoint1, endpoint2))
  + (5 mm) × Σ same-axis reversals
  + 1 × total absolute component displacement
```

This yields **J(old)=187 mm-eq** and **J(candidate)=157 mm-eq** (−30 mm-eq), even though raw total conductor length did not change. Weights are illustrative and must be calibrated on accepted human-reviewed layouts before being used as a policy.

## 2. Hard constraints come before aesthetics (lexicographic safety)

**Reject immediately** any candidate that fails *any* of these mandatory checks, regardless of its score:

1. Same component/part identities, physical pin numbers, polarities and net memberships. No silent net changes; all 5 nets / 6 components retained in the C3 example.
2. Declared junction semantics preserved or explicitly revalidated; no accidental T/X join, overlapping different-net wires, incorrect wire labels, dangling endpoints, unknown pins, displaced physical connector contacts or new contact with **any unassigned terminal**. The existing validator #40 is insufficient alone: perform an independent all-pin geometric contact check before scoring.
3. Orthogonal nonzero external wires, valid on-grid endpoints, no wires inside forbidden UGO ink/keepout or reserved pin exit corridors; stroke-edge clearance, including different existing wire widths (#52), and text/annotation reservations satisfied.
4. Full-route feasibility: source and destination physically connected, no `ROUTE_NO_PATH`, `ROUTE_PORT_BLOCKED`, or cap/validation errors; finite time/memory budgets, deterministic failure.
5. Symbol/label boxes and page/format/title block constraints pass the relevant separate validation. Until they do, the score is a **preview** rather than a ГОСТ/ЕСКД-compliance claim.

A strictly feasible, human-legible route may still have a higher raw length when this reduces overlap/crossing ambiguity. Never trade electrical safety for a cheaper visual score.

## 3. Suggested objective metrics (soft constraints)

**Length and detours.** Sum segment Manhattan lengths in µm. Per ordered terminal-to-terminal branch, compute `D=L−(|dx|+|dy|)` and `backtrack=D/2`. A U-dogleg necessarily introduces positive backtrack and reversal. Aggregate per branch, not across an unordered net with forks.

**Bend count and redundant vertices.** Count each change of external conductor direction at 90°. Flag consecutive collinear fragments separately for merge without changing physical/electrical semantics. Detect 180° immediate reversals and non-adjacent axis sign changes (e.g. vertical down then up after a long horizontal segment).

**Short legs and visual jitter.** Flag stub/zigzag segments shorter than a configurable min-leg threshold (example 8 mm) **only as soft penalties**. Short connections may be required for crowded or standard-layout junctions; never delete legal geometry purely due length.

**Crossings and proximity.** Count cross-net X crossings without junction as visual ambiguity (not an electrical short without a node), count crowded multi-wire nodes, and penalize near-misses against **stroke-edge** clearance targets. Strongly penalize route lines close to unrelated connector tips and PIN ESCAPE corridors; mark actual collisions as hard failures.

**Alignment and placement.** Reward aligned pin rows, consistent branch directions and short candidate displacement; penalize large component displacement, body/label whitespace fragmentation and disconnected visual islands. Components should move/rotate only as constrained by part rules, readability and polarities.

**Complexity and determinism.** Record grid vertices searched, wall time and resource-limit failures for each candidate. Freeze seed, tie-break and symbol revision. Compare candidate vs baseline using a Pareto panel: electrical/DRC hard gates first, then bends, backtrack, excess and displacement; a weighted sum is only a final tie-breaker.

## 4. Testable acceptance criteria for automated improvement

1. **Correctness gate:** real C3 sample preserves 6 devices, 5 nets, known three node locations; both before and after diagrams must pass independent wire/ERC, symbol body, pin collision and text-layout checks when available.
2. **Dogleg gate:** for Issue #44 exemplar, the optimizer proposes a legal candidate with `backtrack_TOP == 0`, `axial_reversals_TOP == 0`, `bends_total <= 2`, `length_total <= 142 mm` and identical net memberships.
3. **No-regression gate:** a layout revision may not introduce any extra short, wrong pin, unmarked T-contact, blocked pin exit, illegal clearance or new annotation overlap; failures are explicit.
4. **Bounded algorithm:** candidate search has deterministic vertex count/iteration cap; respects fixed-layout constraints and returns the best **known feasible** layout or explicit inability to improve, never mutates the original circuit.
5. **Score calibration:** evaluate at least a small diverse library of accepted human layouts rather than tuning weights only to this single C3 example. Report both raw metrics and candidate score to avoid hiding trade-offs. Retain original geometry if score does not improve under chosen weighted objectives.

## 5. Implementation boundary

- **QA:** reference metrics and actual six-device test added without editing routing or rendering.
- **ELEKTRIK:** proposed placement-aware optimization under a new RFC with explicit constraints; PR39 remains a two-pin fixed-endpoint proof of concept.
- **PAINT:** annotation collision/ink and visible cross-node review.
- **ESKD:** standards-based widths/clearances/page rules and approval of real UGO; this document **does not** establish certification.
- **Coordinator:** approve the hard/soft objective contract before changing shared APIs or exposing end-user auto layout.

**Bottom line:** plain shortest-path routing for fixed endpoints cannot solve Issue #44 because C3 is misaligned with existing branches; moving C3 produces the same total length but 2 fewer bends and removes the 5-mm backtrack. A per-branch and placement-aware quality function can detect and prefer that improvement.
