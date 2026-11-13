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
7. `examples/review_ic_paint_joint_cycle7.py` produces actual split DD14 and DA8 **synthetic** SVG, strict JSON view records, physical Circuit nets and QA manifest. CI rasterizes SVG to 300 DPI PNG and produces SHA256SUMS. These are **inspection evidence**, not accepted GOST drawings.

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
