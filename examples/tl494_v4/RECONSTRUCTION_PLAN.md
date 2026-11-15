# TL494CN v4 — source-pinned reconstruction plan (Issue #107)

**State: PLAN → MODEL → SELECTION → LAYOUT/DRC → PRINT EXPORT; never the reverse.**  
Owner: independent reference builder. This plan does not approve any experimental UGO.
Original untouched branch: `reference/tl494-native-rework-20261114`, SHA `e695c415fdced164b0e0c39c5249d030795a0aa6`.

## Immutable source baselines

| Source | Identity | Status |
|---|---|---|
| Source 640×290 schematic photograph | SHA-256 `e06e845fa3d269bf71880a8cb1ad2e59c8aa844a0486351228e9da936ac4100c` | Original user upload, preserved in the current conversation; not yet a repository file |
| Source 640×702 component list photograph | SHA-256 `d54469d016eb80fe2a7b3e5aa2526da2494c20d3c18b7a1bcc8af624157fecb0` | Original user upload, preserved in the current conversation; not yet a repository file |
| Type source | `examples/tl494_full_native_model.py` blob `049c32ff6e3bf2c839641d0102e3a63fcb86caaf` | 23 references, 15 named Net identities; immutable for diff |
| Authoring source | `examples/tl494_named_photo_sheet.py` blob `990a1aca651f34dcae991575dddfa28b2acae813` | 91 wires with 2 typed-b continuation diagnostics; old implementation remains for before picture |
| Old SVG/PNG | `examples/tl494_named_truth_output/` at baseline SHA | Before image, 679.3 mm wide; preserve read-only |

**Do not use success from `validate_circuit` as normative, optical or physical proof.** The original model is a regression hypothesis, not the ground truth when it conflicts with photographs, GOST or the manufacturer datasheet. Any corrected source Net requires explicitly reviewed change log.

## Gates and acceptance (ordered, fail-closed)

| ID | Stage | Concrete requirement | Objective proof |
|---|---|---|---|
| P0 | Freeze | All 23 reference designators and actual source values including voltage, variant and count; preserve exact 15 Net + PinRef membership | BOM/manufacturer inventory diff, source hashes, regressions |
| P1 | Exact UGO | Map C1/C2/C3/C5/C6 to thin `capacitor.polarized`, C4/C7 to `capacitor.fixed`, L1/L2 to `inductor.ferromagnetic`, R5 to `resistor.variable`, VD1 to `diode.schottky`, VT1 to real 3-pin `transistor.mosfet_n_enh`, FU1 fuse, X1/X2 true terminals | Symbol-manifest plus part/symbol identifiers and actual PinRef |
| P2 | IC model | TI TL494CN physical pins 1..16 exact; pin 3 is `INPUT`, not `OUTPUT`; display FB / OC, full TI function names metadata | Programmatic tests and physical pin audit |
| P3 | Typography | Portrait PWM reads bottom→top; only the function text rotates; 16 real pin anchors invariant, OpenGost Type A measured | Marker axis/transform D4 tests and actual PNG |
| P4 | Normative symbol | VD1 Schottky original table/position comparison for barb at all 4 rotations/mirrors; MOSFET arrow/dot and optional enclosure as normative DRAFT | Source screenshots and ESKD signoff; otherwise BLOCKED |
| P5 | Circuit/common | COMMON 0V, chassis and PE must have distinct typed semantics, no inferred phantom Net or fabricated earth | Role/Net tests, source-bound 0V view marker only |
| P6 | Geometry | Move components into functional lanes preserving pin sides and nominal sizes; replace width 679.3mm with rational A3/sheet-based fit | Actual min/max occupied bounds and scale report |
| P7 | DRC | Check exact stroke-aware distances for parallel distinct-net wires ≥3mm; 2mm UGO–UGO, 1mm UGO-ink, label/lead guard; unknown intersections diagnostic | Independent numeric report + negative 1µm/2.99/3.0 mm tests |
| P8 | Router | Route around symbol obstacles and 3mm keepouts; reduce unnecessary bends/length/crossings; preserve all terminal Net identities | Measure length, bends, crossings and before/after |
| P9 | Readability | 0.3–0.4mm strokes, Type A 3.5mm chosen, readable a/b, R5/R6 lanes distinct at A3 print | PNG 300dpi, full-size paper metrics, clean and diagnostic |
| P10 | Print | Clean SVG contains no green/blue editor controls and no bogus drawn PE; valid SVG strict XML, PNG 300DPI; optional PDF only if implemented | Strict regex/DOM assertions, test render |
| P11 | Confidence | Preserve DRAFT for all unapproved UGO, 1N5822 polarity uncertainty and 680kΩ×1nF frequency inconsistency | Release manifest and clearly marked BLOCKED |
| P12 | Regression | pytest Python 3.12/3.13, Ruff, D4, physical Net/PinRef inventory, numeric DRC, mandatory before/after images | CI job and exact commit SHA |
| P13 | Integration | Changes confined to `reference/tl494-audit-v4-20261114`; no edits to main/integration or prior reference | GitHub compare, no merge |

## Ownership when engine lacks capability

- **#108 ELEKTRIK NET / QA:** `validate_external_wires` is not a stroke-aware DRC or automatic router. Request proper model-layer DRC/router; do NOT claim successful global routing from 0 ERC.
- **#109 YGO / ESKD:** common/ground/chassis/PE marker normative geometry and typed roles unresolved. A text `0V` may be review-only until owner signs off.
- **#110 ELEKTRIK IC / PAINT:** FB/OC alias in actual IC model, pin 3 INPUT, true bottom-to-top reading and D4. Do not turn source pin numbers into aliases.
- **#107 YGO / ESKD:** Schottky and MOSFET literal GOST source comparison. Report unknown features BLOCKED rather than hand-drawing an approved UGO.

## Mandatory release evidence

The new branch must include source manifest, complete Net inventory, actual before/after links, numeric paper-space distances, exact test logs, coordinate-aware error examples, full source SHA and explicit blocker list. **No SVG editing to mask incorrect source models, no merges.**
