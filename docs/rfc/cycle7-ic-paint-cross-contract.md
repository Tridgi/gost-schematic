# RFC IC-C7-002 — joint physical E3 ↔ PAINT source boundary

Status: **experimental DRAFT; no manufacturer pinout / UGO / ESKD approval**.

- ELEKTRIK physical source: Issue #87, Draft PR #97, same `parallel/electrical-ic-contract-cycle7` branch; existing RFC IC-C7-001 remains authoritative.
- PAINT renderer source: Issue #88, independent Draft PR #93, **fixed snapshot `f8f9dc4c1fd8266b807dea9d6f268d971bec8d7a`**. It is not merged into the physical PR.
- ESKD source dossier: Issue #91, independent Draft PR #95, head `4445b9d916217756d2586e4257a2b59ad72f9103`; all normative candidates remain DRAFT/BLOCKED.
- Independent QA owner: Issue #92. Evidence is available from the dedicated `.github/workflows/ic-paint-cross-cycle7.yml` and the generated `draft-cycle7-real-model-paint-joint-qa` artifact if the workflow succeeds.

## Contract sequence

1. `IcDeviceDefinition` declares immutable *physical* numbers, NC, power and open-collector roles and disjoint logical units owned by one real `Circuit.ComponentInstance` (`DA1` or `DD1`). The 2/4/8/14/40/64-pin test fixtures are **all SYNTHETIC**, never a manufacturer IC.
2. `propose_ic_paint_binding(record, actual Type A style, measurer)` calls the **real** `propose_ic_dimensions` from PAINT #93. It generates a new `IcSymbolSpec` revision with measured field width, row pitch, body height, physical lead length and exact *local* outside endpoints. Existing immutable records are left unmodified.
3. For a split logical unit whose original order is not input-left/output-right, a **new view** is deliberately reflowed to PAINT's supported LEFT/RIGHT role policy. This does **not** renumber a pin, merge sections, move a circuit component or create a net. Explicit `AUX_LEFT/AUX_RIGHT` pin-field conflicts fail closed.
4. `resolve_ic_pin_positions` supplies authoritative world `PinRef(reference, number) → Point` (integer micrometres). `IcPaintBinding.verify_endpoints` compares them **exactly** with the projected `ResolvedIcPin.anchor`, without ±1 µm allowance.
5. `render_resolved_ic` checks every endpoint against its actual SVG lead geometry and emits the exact coordinates in SVG `line[x2,y2]`. The test parses real SVG and compares every line coordinate against the authoritative model `Point`; 1 µm mutation must raise `IC_PIN_ANCHOR_MISMATCH`.
6. The measured typographic source is real OpenGost Type A release v0.7, SHA-256 `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`, cap height h=3500 µm. Font is downloaded only inside CI, **never committed**.
7. `examples/review_ic_paint_joint_cycle7.py` produces actual split DD14/DD40/DD64 and DA8 **synthetic** SVG, strict JSON view records, physical Circuit nets and QA manifest. CI rasterizes SVG to 300 DPI PNG and produces SHA256SUMS. These are **inspection evidence**, not accepted GOST drawings.

## Execute

The dedicated workflow checks out **both exact source revisions** rather than treating disconnected per-branch test suites as joint evidence. It copies the single PAINT module into the runner's disposable working tree for test execution only; it does not commit PAINT code to #97 and cannot merge either branch.

```sh
# Within the CI checkout after the pinned PAINT snapshot is staged:
pytest -q -ra tests/test_ic_paint_joint_cycle7.py
python -m examples.review_ic_paint_joint_cycle7 \
  --font-file "$IC_TYPE_A_FONT_PATH" \
  --output-dir output/ic-paint-joint-cycle7
```

## Release gates and known BLOCKED cases

- **TOP-input/BOTTOM-output** true alternative UGO under ГОСТ 2.743-91 §2.1.6 / ГОСТ 2.759-82 §1.8 is **BLOCKED**, because PAINT #93's current `IC_UNSUPPORTED_VERTICAL_PORT` deliberately rejects top/bottom terminals. D4 whole-symbol rotation does not substitute for this alternative functional presentation.
- Selected M=2.5 mm, pitch ≥2M and ink guard are **editorial profile choices**, not universal mandatory ГОСТ dimensions. Full source-printed normative overlays remain BLOCKED until ESKD/QA.
- Semantic 0/1/2 auxiliary fields and `IcField.MAIN` vs actual visual label placement need final PAINT/ESKD mapping review; real per-device analog and digital functional pictograms, inversion/control arrow glyphs and aliases remain BLOCKED.
- No verified vendor part/revision/datasheet means **no real IC pinouts** and no APPROVED status. GREEN CAD attachment-zone squares are editor-only Issue #100, not printed УГО.
- No changes to E1, ordinary E3 public API, main, integration, old symbol catalog, or other owners' PRs.


## Source-verified vertical orientation review — 2026-11-14

Source checked against **printed page 6 (PDF page index 6)** of ГОСТ 2.743-91,
§2.1.4–2.1.6 and *figures 3 and 4*:
https://prikladmeh.ru/Standart/2.743-91.pdf .
The actual figure 3 contains **two non-equivalent text-orientation drawings**
with input lines at the TOP and outputs at the BOTTOM: one has upright
horizontal function/field text, the other has field inscriptions rotated.
This permits neither arbitrary rotation of the central function in isolation
nor universal rotation of every label, auxiliary field and physical number.
Figure 4 also requires information-flow arrows for reversing nominal input/
output direction (inputs right/bottom or outputs left/top), with the correct
corresponding function inscription. The text of ГОСТ 2.759-82 §1.8 independently
permits TOP analog input and BOTTOM output:
https://normadocs.ru/gost_2.759-82 .

**Explicit electrical-model readiness:** `IcPinRow.side=TOP/BOTTOM` already
stores the side and the immutable external local integer-µm `Point` on that
side's outward normal. The source tests
`test_explicit_vertical_physical_pinrefs_are_exact_model_only` cover
DA/DD 8/14/40/64 × all eight D4 transforms, DRAFT physical pitch 5000 µm,
separate logical units, stable physical PinRef and real `Circuit.Net`. They
exercise *electrical coordinate preservation only*. These source tests do
NOT claim correct rotated text or normative UGO.

**Required joint PAINT/ESKD boundary:** a future explicit view-profile ID
must specify (a) input TOP/output BOTTOM or source-approved opposite with
information arrows, (b) independent drawing pitch and x-coordinate index
for each TOP/BOTTOM pin, (c) frame extents/lead length, (d) per-field text
orientation: FIG3_HORIZONTAL_TEXT vs FIG3_ROTATED_TEXT source profile, not
global arbitrary text rotate, (e) physical pin numbers beside their own lead
consistent with §2.3.12, (f) measured real Type A transformed ink/hitboxes,
(g) separator and optional zone transforms, (h) end-to-end 1µm exact pins,
including all D4 composed transforms, 300DPI and paper zone bounds.

**Current behavior:** `propose_ic_paint_binding` deliberately raises
`IC_UNSUPPORTED_VERTICAL_PORT` for TOP/BOTTOM. `render_resolved_ic` in
independent PAINT PR #93 also raises this code. These are proper BLOCKED
gates until PAINT and ESKD agree the profile and implement the source
figures. Nothing in this PR changes the PAINT branch. The editor's green
connection squares belong to future Issue #100, not printed ESKD SVG.

## Exact joint-binding semantic validation

`IcPaintBinding.verify_endpoints` now rejects stale/misassociated views
even if their outer `Point` remains identical: wrong source unit ID, refdes,
content, transform, origin, body, physical number, label, electrical role,
side, visual row, functional row_key and pin id are all checked against the
unchanged `IcDeviceDefinition` and explicit new `IcSymbolSpec`. A 1µm
endpoint deviation is independently rejected. Cross-unit references cannot
be accidentally swapped. Any input/output side correction used for the
independent PAINT #93 left/right profile emits an explicit auditable
`IcPinSideReflow` record (unit ID, physical `PinRef`, old/new side); the old
serialized source is not mutated. Old valid declared body dimensions are
never silently reduced; only an explicit revised spec with grid-rounded
growth can be rendered. All profiles and fixture source pinouts are DRAFT.
