# FINAL INDEPENDENT QA — updated Draft PR #39 @ 1a1375623c0f098cac14f7843c44d75982a4d749

**Subject:** [PR #39](https://github.com/Tridgi/gost-schematic/pull/39), new implementation on **exact commit** `1a1375623c0f098cac14f7843c44d75982a4d749` — NOT the old `4e86e2e` implementation or earlier PR #53 results. **Base integration:** `2052e9d3a903edea860c100e00609ceee3c9062b`, with validator fix #40, validator file blob `fbc02c8ca37f91f01c507c9a98be84009213b05f`. All tests load genuine catalog physical passports from the base integration.

**Review source integrity:** both upstream files copied *byte for byte*, as QA-only **.txt fixture payloads**, not runtime production Python. The fixture loader cryptographically checks exact Git object hashes **before importing**:

| Upstream file in PR #39 @ exact SHA | Immutable Git blob |
|---|---|
| `src/gost_schematic/engines/routing/two_pin_orthogonal.py` | `0b338b938cdd7c66a05c5cf68f02c8e6509589dc` |
| `src/gost_schematic/engines/routing/two_pin_sheet.py` | `1af14ada6e1e37c8c94d8c27b100bdba14a41a4d` |

Use `scripts/qa_final_pr39_loader.py::load_frozen_pr39()`. No `git fetch` or outside network needed during pytest. This **cannot be used to certify a later PR39 SHA** without deliberate update. No production changes; no merges into other branches.

## POST-MERGE INDEPENDENT QA — authoritative update (2026-11-13)

**Current integration HEAD** `c8a6eae741d6fcdc341ff78c0f226014c1bf5c0e`, synchronized into `parallel/qa-final-pr39-1a137562`. Owner PR #39 and validator PR #60 were merged by the **coordinator**, not QA. The catalogue is now **21 DRAFT**, including `diode.general` and `diode.zener`; the installed validator file Git blob is `c0e42d4537db224f3a9367a78f40764e2945437b`. The two installed router files have **the same exact Git blob hashes** as the frozen PR39 HEAD `1a1375623c0f098cac14f7843c44d75982a4d749`.

The follow-up runs the #50–#52/typed-route regressions against **BOTH** the actual installed modules and frozen SHA-verified sources in separate namespaces. The previously strict-xfailed #58 is now an ordinary **mandatory passing test**: real R1.1 already attached to A, foreign B wire interior at the same physical contact without junction, resulting in **ERROR `WIRE_PIN_CONTACT_UNDECLARED`** and no inferred `WIRE_NET_SHORT`. Independent tests also require `ROUTE_PORT_BLOCKED` when the typed adapter receives unsafe pre-existing foreign ink. No stale #58 xfail remains in this QA PR.

New integration-specific tests discover all **21 actual physical part/UGO definitions**, verify physical pin identity across **8 rotations/reflections**, and exercise safe routing around every family. The actual six-component source example now has **C3 at (100000,80000) µm**, with pins at **(91000,80000)** and **(109000,80000)**; its TOP/RIGHT wires must remain electrically valid, total length 142mm, with two rather than four bends. No fictional rescaling or moving C3 from the integrated example is done in QA.

The sections below were originally written **before** PR #39 and #60 integration. Historic CI figures and prior-base findings are preserved as historical evidence, not the current authoritative result. No production files or PR #39/#42/#53/#60 were edited; no merge of PR #61.

---

## 1. Independent acceptance matrix

*PASS* = independently executed assertions passed on exact reviewed SHA. *FAIL* = a required behavior still reproducibly incorrect. *BLOCKED* = current documented capability or external dependency does not permit the full intended acceptance; does not necessarily mean a new defect.

| ID / acceptance | Status | Independent evidence and limits |
|---|---|---|
| **#50** exposed unassigned real physical pin | **PASS (typed adapter)** | Three real resistors: old geometry-only line crosses R3.1 but current *safe sheet adapter* diverts it; **40 checks** cover five real UGO/part types × 8 rotations/mirrors. Exact contacts, netlist, no junction and independent `validate_external_wires` all validated. Low-level geometry-only helper **is not a safety API** and is still unsafe if caller omits pins — intentional contract, not a new #50 regression. |
| **#51** unrelated remote keepout / search budget | **PASS** | 1mm clear path plus Box around (1,000,000,000;1,000,000,000) µm now returns the exact one-edge path with `max_cells=1000`. Additional local obstacle triggers a bounded adaptive detour unaffected by distant hazard. Genuine overbudget request produces explicit `ROUTE_CELL_LIMIT`, not fabricated route. |
| **#52** mixed printed conductor widths | **PASS** | New 300µm line, 400µm clear gap, foreign strokes **101/299/300/1000/1401µm**. Every constructed path independently avoids an inflated foreign-ink AABB of **clearance + ceil(new/2) + ceil(foreign/2)**. Widthless legacy `WireSegment` now gives `ROUTE_FOREIGN_WIDTH_REQUIRED` and empty route. |
| Real catalog D4 transformations and pin identities | **PASS** | 5 real symbol families × 4 rotations × 2 mirror settings; physical pin #1 is preserved exactly and path does not touch excluded R3.1; unrelated body/escape obstacles are supplied by adapter. |
| Blocked terminal / impossible fixed window | **PASS** | Body or foreign ink on selected endpoint → `ROUTE_PORT_BLOCKED`, empty route; blocked wall across bounded window → `ROUTE_NO_PATH`; invalid net member/owner → `ROUTE_NET_INVALID`; no partial `ExternalWireGraph`. |
| Single-net postroute electrical validation | **PASS** | For every accepted route, `validate_external_wires(circuit, route.external_graph("LINK"), real_parts, real_symbols) == ()`, netlist/circuit unchanged, junctions empty. No invented join/short in the supported two-pin net. |
| **#58 compatibility**: pre-existing foreign wire across attached physical pin | **PASS, fail-closed** | Typed adapter refuses to draw a fresh route into a source/target already covered by a foreign-net ink obstacle with `ROUTE_PORT_BLOCKED` before relying on the validator. It does **not** synthesize a junction or mutate net membership. |
| **#58 existing validator correctness** on already-attached pin | **PASS after owner PR #60** | The integrated electrical validator now emits exact ERROR `WIRE_PIN_CONTACT_UNDECLARED` for real A-endpoint + B-interior crossing. The test is a mandatory ordinary PASS, never a stale `xfail`; no inferred short. Earlier failure is retained in historical QA PR #42/#53. |
| Multi-net sheet **completeness** | **BLOCKED / known scope limit** | Adapter's final ERC checks **only the generated LINK graph** against a Circuit with all declared nets. A second, separately authored and safely positioned net has no segments in that graph, causing `ROUTE_ELECTRICAL_REJECTED` even when its `foreign_wires` contains an already drawn wire. This is a **safe refusal**, but is not an end-to-end multi-net sheet verifier. Owner explicitly states this experimental prototype supports a single two-member net. An overall multi-net claim needs a combined graph and resolved #58 before approval. |
| Repeatability & bounded resources | **PASS for measured cases, no SLA** | 8 repeated hazard-permutation calls produce identical paths; deterministic frozen source. Checked a small explicit `max_cells` refusal, legitimate wall, adaptive detour and 3 repeated timing samples per case. Timing numbers below; no worst-case proof. |
| **#44** objective layout metrics | **PASS (measurement reference)** | Exact integer wire length, Manhattan excess and backtrack, orthogonal bends, direction reversals, sub-8mm legs, proper X-crossings and ink-AABB collisions defined in test-only helper. Real six-part C3 specimen: moving C3 5mm down preserves **142mm** total conductor, improves bends **4→2** and backtrack on TOP **5→0mm**. |
| #44 *automatic placement* and actual annotation collisions | **BLOCKED (out of PR39 scope)** | The metrics quantify quality but no general optimizer, text bounding-box extraction, human-reviewed weights or full-page format/ESKD ink certification exists in the router. No normative approval is asserted. |

## 2. Reproduction of previous issues on NEW SHA

### #50 — separate raw geometry helper vs physical safe adapter

Actual physical pin 1 positions (µm), three **real** fixed resistors:

```text
R1.1 = (0,-14000)   LINK source
R3.1 = (0,0)        UNUSED, physically real
R2.1 = (0,14000)    LINK destination
```

The primitive `route_two_pins(source,target,keepouts=only_real_body_boxes)` deliberately lacks catalog pin knowledge and would still draw straight through R3.1. **Do not route real sheets through this entrypoint.** The newly introduced **`route_circuit_two_pins(circuit, parts, symbols, R1.1, R2.1, net_name="LINK")`** resolves all real parts, protects both non-target physical pins and their outward 1.8mm corridors, and returns a detour that **does not** hit R3.1. The current independent validator returns no diagnostics for that safe result. This is a verified correction of **the sheet-level call contract**, not a claim that raw Dijkstra understands physical nets.

### #51 — far-away noise no longer expands the search window

```python
from gost_schematic.core.geometry import Box, Point
# route_two_pins = pinned NEW PR39 low-level function, not original PR53
route = route_two_pins(
    Point(0,0), Point(1000,0),
    keepouts=(Box(10**9,10**9,10**9+1000,10**9+1000),),
    max_cells=1000,
)
assert route.ok and route.points == (Point(0,0), Point(1000,0))
```

Nearby blocking geometry still matters; explicit bounded windows and cell caps can still fail by design.

### #52 — stroke-aware independent geometric check

```python
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.obstacles import WireObstacle
foreign = WireObstacle(
    "other", Line(Point(5000,-1000), Point(5000,1000)),
    stroke_um=1000, net_name="B",
)
route = route_two_pins(
    Point(0,0), Point(10000,0),
    foreign_wires=(foreign,), grid_um=100,
    clearance_um=400, stroke_um=300, max_cells=15000,
)
assert route.ok
for a,b in zip(route.points, route.points[1:]):
    assert not segment_intersects_box(
        Line(a,b), Box(5000,-1000,5001,1001).expanded(400+500+150)
    )
```

Same result is verified for odd stroke widths; widthless `existing_wires` are rejected rather than guessed.

### #58 — confirmed owner fix, ordinary non-xfail regression

A valid A conductor ends exactly on real R1.1=(0,0); B foreign conductor intersects R1.1 by its interior with no junction. The **pre-PR60** validator was silent. With PR #60 merged, this exact physical foreign-net intersection **does** yield `WIRE_PIN_CONTACT_UNDECLARED` without inferencing a short or changing the graph; it is a mandatory passing test. The typed adapter independently refuses to route into B ink with `ROUTE_PORT_BLOCKED`. This does **not** certify arbitrary multi-net graphs.

## 3. Runtime evidence: 3 samples per scenario, GitHub Actions

Results from [Actions run #43467423282](https://github.com/Tridgi/gost-schematic/actions/runs/43467423282), single hosted runner per Python version. **Medians in milliseconds; not performance SLA.**

| Bounded scenario | Python 3.12 median | Python 3.13 median |
|---|---:|---:|
| 1mm direct with remote 10^9 µm obstacle | 0.036 | 0.056 |
| 30mm route detouring local blocker | 21.173 | 28.589 |
| 10mm route, 0.1mm grid, 1.0mm foreign ink | 382.495 | 496.699 |
| 28mm real-three-resistor safe sheet adapter | 10.493 | 11.677 |

The fine-grid mixed-stroke route is substantially more expensive than the 1mm coarse-grid case. Route search should be profiled under realistic sheet complexity before setting interactive UI latency promises. The performance test is a bounded 3-sample reporter; it emits one non-gating warning. No fake timing threshold is used.

## 4. CI, exact scope and QA delivery

New standalone QA branch: `parallel/qa-final-pr39-1a137562`, starting from integration SHA `2052e9d3a903edea860c100e00609ceee3c9062b`. Only **test-only** files under `tests/test_qa_final_pr39*.py`, `tests/fixtures/qa_pr39_1a137562_*.txt`, `scripts/qa_final_pr39_*.py`, and `docs/qa/`.

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
pytest -q tests/test_qa_final_pr39.py tests/test_qa_final_pr39_metrics.py
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

**Last completed pre-document source run:** [#43467423282](https://github.com/Tridgi/gost-schematic/actions/runs/43467423282), Python 3.12 + 3.13 both **SUCCESS**, Ruff PASS, **1081 passed / 1 non-gating performance warning**, 19 DRAFT symbols / 0 hard catalog errors, wheel payload PASS. This is **historical pre-merge CI**. The strict #58 xfail introduced after that run has now been removed after PR #60 integration. Post-merge source and installed-module CI must be reported separately.

**Evidence boundaries:** QA did not edit PR #39, #42, #53, #60 or production files. Owner PR #60 supplied the now integrated #58 correction. PR39 remains a single-net experimental router; **21 UGO are DRAFT**. Full multi-net safety, production latency and ГОСТ/ЕСКД certification remain outside this audit. No merge of PR #61 was done.
