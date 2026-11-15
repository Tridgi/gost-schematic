# CYCLE 14 — QA2 independently executed original TL494 native b SVG + A3 PNG300

**Decision: PARTIAL NATIVE ART VERIFIED, FULL TL494 PRINT NO-GO.**
2026-11-15, existing Draft PR #99 `parallel/qa-electronic-cycle7`.

## What was actually run, not inferred

- Exact frozen original **E695**
  `e695c415fdced164b0e0c39c5249d030795a0aa6`.
- Genuine source assembly / RECON #115
  `e4eb565820e54889456f64d36598b608597ca2c2`.
- Actual manufacturer IC #97
  `bc03a31c5d15c9e962f9b26a209aab373e39bee6`.
- **Actually executed corrected PAINT #93**
  `910e6c7382137f0878a68097d40dd565be5bedbc`.
- NET #114 `a370d637fe67ec44870899d503f53c0a6f8ee3af`.
- YGO #113 `3e47cdf32ccf211ded97e3be1ad874035653e090`.
- Actual authenticated OpenGOST Type A TTF SHA256
  `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`;
  font bytes are never committed or uploaded.

Each source was checked out at its actual immutable Git SHA into a
**new isolated temporary directory**, with frozen E695 owner files
copied to a disposable RECON tree exactly as in the GitHub workflow.
No user or other-agent Git worktree was switched; no source graphic
was drawn manually or modified.

The original paired b-source marker generator ran successfully. The
original graph includes **23 parts / 15 named electrical Nets /
62 unique physical PinRefs / 16 real TI TL494 DA1 leads**.
The sole `b_NEGATIVE_OUTPUT` physical Net retains exactly
`FU1.2`, `X2.1`, `R5.2`. Its two *non-electrical*
local continuation strokes, in **integer µm**:

| Non-electrical label | True physical pin start | Signed label endpoint | Typed geometric vector |
| --- | --- | --- | --- |
| `b-X2` | `X2.1=(389000,35000)` | `(374000,35000)` | `(-15000,0)` |
| `b-R5` | `R5.2=(25000,224000)` | `(25000,236000)` | `(0,+12000)` |

No added Circuit Net, PinRef, Junction or electrical wire was
permitted for these two printed graphics.

## Reproduced and reported cross-owner code defect

Earlier true PAINT `d74300580dfd28cc3400a512828dac6b49d529f0`
render crashed with `FULL_NATIVE_TYPE_A_OWNER_SELECTOR_NOT_LITERAL`:
`_declared_type_a_family` rejected any positional argument, even the
**required** `font_file` argument of genuine RECON
`inspect_type_a_font(font_file,h_um=3500,
family="OpenGOST type A",require_family_match=True)`.
Full reproduction and strict fix requirements were sent to
[PAINT PR #93, QA comment 6895032656](https://github.com/Tridgi/gost-schematic/pull/93#issuecomment-6895032656).
New PAINT `910e6c...` fixed the validated single real positional
font path without relaxing exact family, cap height or SHA checks.

QA's own source oracle was separately fixed so it checks genuine
frozen source data and modern RECON signed builder **without
calling PAINT's font adapter**:
`scripts/qa_tl494_cycle11_b_binding_gate.py`.
In this independent source gate **3 real producer-side negative
cases** and **12 source-report mutations** all rejected, on
Python 3.12 and/or 3.13. Historical E695 old **91
wires / 37 nodes / 9 DRC errors / 32 warnings** remain negative.

## Genuine owner output, not screenshots or fake SVG

Original Python modules
`examples.render_tl494_compact_new_router_cycle10` and
`render_routed_native_sheet` genuinely executed with verified
font and **node cap 5000** after the PAINT production fix.
Result:

- **15/15 source Net trees evaluated, 6/15 routed**
  on this specific bounded trial; **37 routed physical wire
  segments**, actual 23/15/62/16 preserved.
- Four explicit blocker families from true owner print manifest:
  `ELECTRICAL:WIRE_NET_DISCONNECTED`,
  `ELECTRICAL:WIRE_PIN_UNWIRED`,
  `NET114_ORIGINAL_ROUTE_PREVIEW_NOT_PRINT_PASS`,
  `ROUTER_INCOMPLETE_OR_UNVERIFIED_15_NETS`.
- Correct actual **A3 420 × 297 mm** clean and diagnostic SVG,
  both `BLOCKED_INCOMPLETE_OR_PRINT_DRC`. Exact SVG source SHA256:
  - clean: `8862023f6d1497d09ae32cf80c1c1f79134617193602bf36fe79251d0fa475d4`
  - diagnostic: `75473463775952a72d87187cb0917d04f80cd91282644bd94cd7195e4008a3d7`
- Independent `scripts/qa_tl494_cycle14_b_xml_gate.py`
  parsed BOTH genuine SVG files: exactly TWO printed black
  0.3 mm non-electrical `<line>` stubs **per SVG** with original
  1µm-exact source/stub IDs, two real glyphs, no phantom conductive
  `wires`, no false X/T/junction or green continuation pad.
  Clean has 0 real IC editor green targets; diagnostic has 16.
  **All 24 in-memory hostile mutations against actual owner SVG
  were rejected** (1µm displacements, duplicate/absent/foreign
  strokes, fake PE/pinrefs/junctions, invisible strokes, wrong
  OpenGOST family/hash, etc.). Neither actual source SVG changed.
- Local Windows CairoSVG attempt **BLOCKED BY ENVIRONMENT ONLY**
  because native `libcairo-2.dll` is missing. This is not an
  E3/print failure. The main real Cairo 300 DPI verifier remains
  mandatory in its separate GitHub CI step; no skipped negative.

## Independently produced physical 300DPI raster

Second actual native SVG rasterizer `resvg_py.svg_to_bytes`
was used via `scripts/qa_tl494_cycle14_resvg_png.py`
with **only genuine verified OpenGOST Type A** loaded as an explicit
font asset and 300 DPI metadata. Genuine source XML was unchanged.

| Actual Resvg PNG | Physical page | Pixel dimensions | PNG SHA256 |
| --- | --- | --- | --- |
| clean | A3 420×297 mm | 4961×3508 | `ec42363d555fb4e30e818300ec838291d4013ed2bc292db1d56fed59eb3d62c7` |
| diagnostic | A3 420×297 mm | 4961×3508 | `37af65fb5aeab64c61fe7cf661036d5650d14f994557778ad3e8d284b29a2f77` |

PNG 300-DPI physical pixel dimensions and metadata passed;
clean bitmap grayscale check passed. **All 16** distinct physical
`DA1.1..DA1.16` green terminal hitboxes are actually visible
at signed µm-to-pixel anchors in the diagnostic 300DPI PNG.

QA Resvg report hash:
`27867040d22de134ad956b804ad9cf5af0966a3dc7c0f9b00867939eddb2ff62`.
SVG-only evidence hash:
`07a802fd74b33b3590a69efbc1a31ca0e8f5dda80a5b5b87a13e8c326c1c28ae`.
All these are **locally executed true owner artifacts** in the
isolated test folder, not asserted GH-hosted downloadable artifacts.

## Current QA engineering changes / CI topology

- `scripts/qa_tl494_cycle11_b_binding_gate.py`: source oracle
  independent of PAINT's Type A helper; strict authentic verified font.
- `scripts/qa_tl494_cycle11_native_300dpi.py`:
  Cairo loaded lazily **only** for mandatory raster stage; parsing
  original real SVG/24 negatives does not depend on Windows libcairo.
- `scripts/qa_tl494_cycle14_b_xml_gate.py`:
  new independent real-SVG-only source/geometry/24-adversarial gate.
- `scripts/qa_tl494_cycle14_resvg_png.py`:
  new independent physical A3 PNG300 raster + 16 visible green
  manufacturer contacts; no false full-print acceptance.
- `.github/workflows/qa92-cycle11-live-b-and-native.yml`:
  source-pin independently executed PAINT `910e6c...`;
  add real-SVG and Resvg independently run steps on Python
  **3.12/3.13** while preserving original Cairo-based raster
  gate and always-upload original native evidence.

The previous Cycle13 full QA baseline is **1919 PASS, 6 SKIP,
1 non-gating performance warning on each Python 3.12 and 3.13**
and Ruff PASS. The Cycle14 *new source-locked* gates and Resvg
also independently passed on local Python 3.12 and 3.13,
and the expanded `ruff check .` passed at the verified
new Cycle14 code SHA. Current GitHub Actions state must be checked
by actual exact new HEAD, not inferred from previous queued runs.

## Outstanding user acceptance blockers

This is the first **independently verified actual source-correct
b graphical ink + physical A3 300 DPI** from the genuine owner.
It does **NOT** prove full product success.

- Route **6/15 for node cap 5000**, versus old x16 10/15
  independently confirmed using a different search setup and
  x17 newer 8/15 at node cap 25000. They are **not comparable
  algorithm benchmarks** without identical placement, time/cell
  budget, priority, no relaxed 3/2/1 clearance and same global DRC.
- Need **all 15 Net trees genuinely complete**, full-graph ERC,
  independent global source/wire/ink/annotation 3/2/1 mm DRC
  with **zero disallowed errors**. 0 errors on the accepted
  partial graph is never sufficient.
- All source catalogue UGO remain **DRAFT/NOT APPROVED** without
  precise normative 1:1 evidence; original user photo bitmap is
  not available for pixel-exact visual comparison.
- Main, integration and frozen E695 were not modified; no
  early merge or fabricated full-sheet PASS.

**NEXT:** route owner NET/RECON get physical 15/15 candidate with
strict blocker diagnostics; PAINT provide same actual signed true
ink; QA repeat both independent b SVG/24 hostile, Resvg and Cairo
real 300DPI, signed IC 16/62 and global release gate.
