# GOST CAD Copilot Development Handoff

## Current state

```text
GOST CAD COPILOT HANDOFF

BASE_SHA: 7ea3304a13e8e13a53a66e129ec8f66f58c367b9
HEAD_SHA: 5721894b4737df14a8d2d386705e0b5aa046346d
BRANCH: copilot/cad-deep-stabilization
PR: Tridgi/gost-schematic#142 (draft)
CURRENT_STAGE: READY_FOR_REVIEW
```

## Completed

* Refreshed `origin/main` and confirmed the requested base SHA is the current upstream `main`.
* Audited the Python engine, ProjectV2/PinRef contracts, manual wire engine, canonical export, bridge worker, native file layer, editor catalog, documentation, and visual-CAD workflows.
* Confirmed that seven visual-CAD workflows were still push-scoped to `ui/visual-cad-mvp`.
* Updated lockfile, R1, R6, R8, R9 fast diagnostic, R9 native persistence, and Windows native workflows to run on `main` pushes and scoped pull requests.
* Added `docs/audits/CAD-DEEP-AUDIT.md` with evidence, priorities, and test coverage.
* Corrected the legacy QA expectation for the non-approved fallback font: the current measured failure is the narrow `rev_change` caption, not `norm_control`.
* Added canonical-source draft diode and fuse entries to the authoring catalog, including physical pins, source geometry, and prefix-specific default values.
* Added the draft variable-resistor entry with three distinct physical pins, including the canonical wiper geometry.
* Added draft polarized and electrolytic capacitor entries with explicit PLUS/MINUS physical pins and distinct default values.
* Added draft zener and Schottky diode entries with two physical pins and distinct default values.
* Added draft LED and photodiode entries, preserving optical arrows as non-electrical graphics.

## Verification

```text
VERIFIED_TESTS:
- git fetch origin main; origin/main == 7ea3304a13e8e13a53a66e129ec8f66f58c367b9
- clean worktree before edits
- workflow source review confirms old branch-only triggers and new main/PR paths
- `python -m ruff check .` passes
- frontend typecheck, 53 unit tests, and production Vite build pass
- ProjectV2/export/bridge Python slice: 102 passed, 37 deselected, 33 subtests passed
- full Python suite after QA correction: 2361 passed, 8 skipped, 3 warnings
- frontend typecheck, 54 unit tests, and production Vite build pass after catalog extension

FAILED_TESTS:
- Chromium installation was attempted twice but the Playwright downloader looped after archive download; browser E2E remains environment-blocked
- `cargo test --manifest-path ui/desktop/src-tauri/Cargo.toml`: blocked by missing Linux `glib-2.0` system development package
```

## Risks and blockers

```text
CONFIRMED_BUGS:
- Visual-CAD gates did not run for main pushes because of stale branch filters.

OPEN_RISKS:
- Windows NSIS/native acceptance cannot be executed on this Linux host.
- Chromium binaries could not be installed locally because the downloader did not complete extraction.
- Full Python validation requires an isolated virtual environment because the host Python is externally managed.

BLOCKERS:
- None for the trigger/documentation stage.
```

## Next priority

```text
NEXT_PRIORITY: READY_FOR_REVIEW
NEXT_FILES: .github/workflows/visual-cad-*.yml
NEXT_TESTS: GitHub Actions on the exact commit; Windows native current-SHA acceptance
NEXT_IMPLEMENTATION_STEP: commit the trigger correction and open one focused draft PR; use GitHub Actions for Windows/native acceptance on the exact commit
```

## Architectural decisions

* Keep `ui/editor/src/model/contract.py` and the validated ProjectV2 document as the source-of-truth boundary; do not infer electrical identity from canvas coordinates or SVG paths.
* Treat `ManualWireEngine` as the explicit conductor graph and preserve `PinRef` through transforms.
* Keep canonical export sourced from the validated electrical model, separate from UI grid/selection state.
* Do not claim ГОСТ/ЕСКД approval for draft catalog symbols or unverified typography.

## Do not repeat

* Do not base new work on `ui/visual-cad-mvp`; it is not the current integration base.
* Do not weaken required checks or use `pull_request_target` for untrusted PR code.
* Do not mark native Windows acceptance PASS based only on Linux, Node, or Chromium tests.
* Do not mark an unrouted or `needs_routing_review` Net as `verified`.
