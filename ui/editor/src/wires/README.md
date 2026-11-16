# CHAT 7 — Manual Wire Engine + source-locked ProjectV2 adapter

**Owner:** Issue #123. **Branch:** `ui/chat7-manual-wires-v2`. **Draft:** PR #129, target `ui/visual-cad-mvp` — no merge without user authorization. **License:** MIT, original code; no KiCad/QET GPL imports.

## Built and reproducible

- `manual-wire.ts`: signed integer-µm `ManualWireEngine`; physical PinRef identity, orthogonal H/V geometry, port-normal validation, explicit junction vs unmarked X, hidden conductive splice, globally unique stable free IDs, split/merge, segment/vertex drag, rotation guard, Net highlight, undo/redo with monotonic CAS revision. A route may remain `partial`; no TL494 auto 15/15 claim.
- `project-v2-adapter.ts`: fail-closed single-sheet `ProjectFileV2` projection to `WiringSnapshot`; checked symbol↔manufacturer physical-pin mapping; `Net.name`→`literal_source_name`, `rotation_deg`→`rotation`, `top/bottom`→`up/down`, route roundtrip; source Nets, part definitions, UGO, provenance and **non-electrical b continuations** unchanged. Reject stale input with local CAS guard. Canonical Python document SHA/generation validation is **still required** at IPC. Multi-sheet/multi-unit explicitly rejected, not guessed.
- Tests: `tests/manual-wire.test.mjs` covers graph/geometry; `tests/project-v2-adapter.test.mjs` covers actual frozen E695 23 parts/15 Nets/62 memberships/16 DA1 physical pins/2 b strokes, synthetic X, 1µm mismatches, wrong pin normals and stale source.
- `.github/workflows/chat7-wire-v2.yml` (own isolated branch only) executes Node 22 + pinned TypeScript 5.8.3 against **immutable dependency SHA `44dc17d9ea756eadb1656c83cd369ef2b2a3b828`** from MASTER integration, without merging/updating its branch. GitHub Actions run is the source of pass/fail counts; README does not substitute for that evidence.

### Commands

From `ui/editor/src/wires`, after `npm install --ignore-scripts --no-save typescript@5.8.3`:

```bash
npm run typecheck
npm run build
npm test
```

The adapter test reads `ui/fixtures/{tl494-source-e695-v2,toy-v2}.gscad.json` from the **exact pinned integration source**. On an isolated checkout of CHAT7 (without shared fixtures), use the GitHub Actions workflow (or provide those source files explicitly) rather than claiming standalone E695 tests have run. Normal running project must be fully validated by #122 Python `contract.validate()` before import and after materialization.

### API

```ts
const binding = loadProjectWires(projectFileV2, {
  sheet_id: projectFileV2.workspace.active_sheet_id,
  revision: generation,
  source_topology_hash: canonicalSourceTopologyHash
});
binding.engine.commitWire(binding.engine.newTransaction('add:wire-1'), wire);
const proposedFileV2 = binding.materialize(originalFile);
 // caller: canonical schema/semantic/E3 DRC/sha-generation CAS → atomic save
```

**Do not** apply `proposedFileV2` to disk or advertise `route_status=verified` until canonical validator and DRC have accepted that generation. The adapter's guard is local state comparison; it is **not** a cryptographic or cross-process CAS substitute.

### Cross-owner gates

- **#122:** fix canonical `toy-v2` inward physical pin exit (R2.2 world [60000,10000] goes left into body); add source-route validator for pin normal and dangling `verified` branches. See PR #134 review.
- **#120:** actual pointer ↔ `ManualWireEngine` command dispatch, true on-screen segment handle drag, T/X, click-to-wire; source canvas geometry alone isn't a runnable editor.
- **#119:** independent on real canvas+service E2E zoom/pan, T/X, PinRef and 1µm negative.
- **#124/#118:** validate canonical source scene SVG/PNG300 + protected Tauri/Python IPC, beyond this adapter's scope.
- **#125:** integrate own directory only after PR review, run full source→wire→canvas→export tests at exact integrated SHA. Historical E695 9 ERR/32 WARN are not waived.
