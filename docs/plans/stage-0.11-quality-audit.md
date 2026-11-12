# Stage 0.11 — geometry and catalogue integrity audit

**Plan established before implementation:** 2026-11-12.
**Scope:** exact geometry, physical graphical contacts, collision protection, repeatable catalogue checks, and project reporting. This is an internal reliability milestone, **not** a claim of normative certification.

**Baseline:** draft PR #7, commit `12404cf`, 286 passing tests on Python 3.12 and 3.13, Ruff passing. All existing resistor, capacitor, inductor/choke symbols are DRAFT.

## Priority and implementation order

1. **P0 — Graphic-terminal continuity.** A pin must not be registered merely because a free-floating coordinate exists. Check that a drawable line endpoint or supported arc endpoint coincides with the connector and that the lead goes toward the device rather than projecting outward. Provide explicit diagnostic codes, regression fixtures, and preserve compatibility with existing symbols. Circuit connectivity remains governed by `PinRef` + nets; this is a visual integrity check, not a netlist inference.
2. **P0 — Stroke-aware geometry.** Make symbol rendering bounds and sheet-level component-overlap checks account for the actual strokes, especially `StyledLine` ferrite cores and half-circular winding arcs. Avoid double-counting stroke where already included. Ensure transforms preserve safety and deterministic output.
3. **P1 — Catalogue-wide audit.** Review all 15 inductors plus resistor and capacitor drafts automatically, distinguishing hard validation errors from expected `UNAPPROVED_SYMBOL` warnings. Emit machine-readable JSON summaries and run in GitHub Actions.
4. **P1 — QA regression suite.** Add both negative examples and positive controls for P0 defects, rotations/mirrors, and monotonic obstacle expansion. Keep existing tests passing.
5. **P1 — Project governance.** Maintain an append-only dated `docs/project-log.md` summarizing plan, commits, CI, limitations and next decisions. Update the roadmap and PR body. Publish CI links and review artifacts.
6. **Review gate.** Keep PR #8 stacked over #7 in DRAFT state and do not merge/approve UGO geometry without user visual sign-off against KOMPAS/GOST originals.

## Acceptance criteria

- No floating pin, backwards terminal line, or missing graphics endpoints can pass symbol validation silently.
- Changing the width of a stroked core changes collision/view extents appropriately.
- All current draft symbols have traceable catalogue audit records with zero hard validation errors.
- Python 3.12 and 3.13 pass pytest, Ruff passes; CI emits JSON audit artifacts.
- Baseline and remaining known limitations documented clearly; no false claim that auto-routing, certified fonts, full ESKD review, or full ERC are finished.

## Out of scope

- Formal geometrical certification against proprietary KOMPAS symbol libraries or standard diagrams without user-provided reference fixtures;
- true orthogonal autorouting and electrical net extraction from rendered SVG;
- transformers, variometers, multi-phase devices, multi-unit ICs and production PDF.

Sources: [ГОСТ 2.723-68 (Росстандарт)](https://protect.gost.ru/gost/details/69e5c69a-bbb9-4a6a-a8d1-2cf54c2a2164) and ГОСТ 2.702-2011; standard applicability does not itself validate a draft symbol.
