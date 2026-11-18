# GOST Schematic CAD Deep Audit

**Audit base:** `7ea3304a13e8e13a53a66e129ec8f66f58c367b9`  
**Audit branch:** `copilot/cad-deep-stabilization`  
**Scope:** repository state after PR #126 and the Stage 0.12 foundation. This is an engineering audit, not a ГОСТ/ЕСКД certification.

## 1. фактическая архитектура

The repository is a Python engine plus a React/TypeScript editor and a Rust/Tauri desktop shell:

* `src/gost_schematic/` contains integer-micrometre geometry, catalog Part/Symbol definitions, electrical models, validation, routing experiments, and SVG/sheet rendering.
* `ui/editor/src/model/contract.py` is the authoritative ProjectV2 validator/digest boundary. TypeScript mirrors the contract in `contract.ts`; Rust has a transport model in `contract.rs`.
* `ui/editor/src/authoring/session.ts` owns immutable authoring transactions, component transforms, and source topology preservation.
* `ui/editor/src/wires/manual-wire.ts` owns the explicit authored conductor graph. Pin anchors are `{component_id, physical_pin_number}`; free endpoints, junctions, and splices are distinct.
* `ui/bridge/export/project_v2.py` renders canonical SVG from the validated source model, not from the browser canvas. `canonical.py` provides PNG conversion.
* `ui/bridge/transport/worker.py` is the NDJSON Python sidecar boundary. `ui/desktop/src-tauri/src/native_files.rs` provides native file/CAS operations.

## 2. implemented, partial, and absent

**Implemented:** ProjectV2 validation and SHA digest; immutable transactions and CAS revisions; exact PinRef anchors; orthogonal wires with elbows, junctions, splices, split/merge, undo/redo; conservative `needs_routing_review`; source-backed SVG/PNG export; Python sidecar; Tauri native persistence; draft discrete catalog data; broad Python/TypeScript/Rust regression suites.

**Partial:** the browser editor is a working preview rather than a complete CAD command set; the authoring catalog now exposes five draft discrete types (`resistor.fixed`, `resistor.variable`, `capacitor.fixed`, `diode.general`, and `fuse.general`) but is not yet generated from the Python registry; wire editing is primarily domain/API coverage with limited UI affordances; sheet support and diagnostics are stronger in the Python/source model than in the visible editor; standards and fonts remain review-gated.

**Absent or explicitly out of scope:** production autorouting, full multiple-selection and copy/paste workflows, complete catalog-to-editor registry integration, verified multi-sheet electrical continuation semantics, circuit simulation, normative approval, and local Windows acceptance in this Linux session.

## 3. confirmed defects

1. **P0 CI trigger regression (confirmed by workflow source).** Seven visual-CAD workflows (`lockfile`, R1, R6, R8, R9 fast diagnostic, R9 native persistence, and Windows native) had push triggers restricted to `ui/visual-cad-mvp`. Consequently, relevant changes on `main` and pull requests could miss the visual-CAD gates. This branch changes the push target to `main` and adds scoped `pull_request` triggers.
2. **P0 local validation is not runnable until dependencies are installed.** Initial baseline commands failed because `pytest`, `ruff`, and frontend `tsc` were absent from the environment. This is an environment setup failure, not a code defect; the required dependency installation is being retried in an isolated virtual environment.

No additional behavior is classified as confirmed without a failing reproduction. Existing negative suites already cover the high-risk PinRef, stale-CAS, foreign-Net, X/T/junction, splice, 1 µm, rotation, and `needs_routing_review` contracts.

## 4. suspected defects requiring focused reproduction

* Native Windows acceptance may still depend on workflow-only behavior and cannot be certified from Linux.
* The editor catalog and Python catalog can drift because `ui/editor/src/authoring/catalog.ts` duplicates only two symbol definitions instead of consuming the canonical registry.
* Full UI copy/paste, rectangle selection, and group transactions are not exposed by the current editor shell.
* The canonical exporter uses conservative text envelopes and a requested font family; this is intentionally not proof of measured Type A glyph compliance.
* Multi-sheet behavior, cross-sheet net continuation, and sheet-scoped ID rules need dedicated source fixtures before implementation claims are made.

## 5. technical debt and security

The project has several contract representations (Python, TypeScript, Rust, JSON schema) and a large workflow matrix. They are valuable compatibility boundaries but require synchronized version tests. The sidecar and native file layers should continue enforcing strict operation allowlists, bounded JSON, CAS checks, and atomic replacement. No `pull_request_target` execution was found in the reviewed workflows; Windows/native workflows must remain `pull_request` or trusted `push` only.

The main remaining security review items are duplicate-key/size policy at every NDJSON boundary, SVG/XML content validation, symlink/reparse handling on Windows, and subprocess/temp-file cleanup. These are follow-up work, not declared vulnerabilities from this audit.

## 6. UI, electrical, normative, and build findings

The UI has a custom SVG canvas, Mantine shell, inspector, project tree, shortcuts, theme tokens, and browser E2E coverage. It does not yet present the full CAD workflow requested in the long-term roadmap. The electrical model is substantially safer than the UI surface: it preserves physical identity and explicitly refuses to infer connections from coordinate coincidence. Canonical export retains declared source Nets even when routes are unrouted.

Catalog symbols and standards are deliberately marked draft/review-required in source data and documentation. No symbol is promoted to ГОСТ APPROVED by passing automated tests. Linux CI covers Python 3.12/3.13, frontend checks, and source-model/browser paths; Windows NSIS/native acceptance remains a GitHub Actions responsibility.

## 7. priority matrix

| Priority | Finding / next action | Evidence |
|---|---|---|
| P0 | Restore visual-CAD checks for `main` and PRs | Seven workflow trigger files; fixed on this branch |
| P0 | Preserve PinRef/Net/CAS invariants | `ui/editor/src/wires/tests/manual-wire.test.mjs`, `ui/editor/src/model/tests/test_contract.py` |
| P0 | Keep native Save/Open/Save As acceptance on current SHA | `visual-cad-r9-native-persist.yml`; Windows-only |
| P1 | Expose complete wire editing in the UI | domain engine exists; visible editor coverage is narrower |
| P1 | Add multi-select, clipboard, and atomic group operations | no equivalent editor command surface identified |
| P1 | Generate editor catalog entries from canonical Part/Symbol data | `ui/editor/src/authoring/catalog.ts` currently contains four synchronized draft entries |
| P1 | Add sheet-scoped fixtures and continuation contract | no verified cross-sheet electrical contract |
| P2 | Expand ERC/DRC diagnostics and measured typography | existing validation/rendering is draft/review gated |
| P2 | Performance measurements at 100/500/1000 components | not measured in this audit |
| P3 | Cosmetic polish and optional animation | after correctness and persistence |

## 8. test coverage matrix

| Area | Existing coverage | Current status |
|---|---|---|
| Python engine/catalog/rendering | pytest, Ruff, catalog audit, export fixtures | available after isolated dependency setup |
| ProjectV2 | Python contract, bridge, export, strict negative fixtures | strong source-model coverage |
| Manual wires | standalone TypeScript build and extensive node tests | strong domain coverage |
| React editor | typecheck, unit tests, Vite build | available after `npm ci`; limited CAD command coverage |
| Browser | Chromium Playwright E2E | workflow-covered; browser binaries not installed locally |
| Rust/Tauri | cargo tests and Windows workflows | Linux cargo tests possible; NSIS requires Windows |
| Native persistence | R9 current-SHA workflow | not locally reproducible on Linux |

## 9. improvement plan

1. Land the trigger correction and verify all Linux gates on the exact branch SHA.
2. Add a focused editor-level regression for the most valuable missing command, starting with wire edit preview/commit and explicit `needs_routing_review`.
3. Replace duplicated editor catalog data with a versioned engine catalog adapter, preserving draft status and physical pins.
4. Add multi-select/copy transactions only after defining source-Net remapping rules and negative tests.
5. Add multi-sheet fixtures and export tests with sheet-scoped IDs before UI sheet commands.
6. Extend security and Windows filesystem tests, then use current-SHA NSIS acceptance as the release gate.

