# CHAT3 R2 — independent production-module review, not release acceptance

- **Production base under test:** `ui/visual-cad-mvp` SHA `44dc17d9ea756eadb1656c83cd369ef2b2a3b828`.
- **Authentic code blobs independently reconstructed and `git hash-object`-verified:** `precision.mjs` `389f60c1c6ee23d291a95ddf3d2d3dbe43b23203`, `scene-projection.mjs` `38c00d8e39c70709dd7546913704a3da6ccc0033`.
- **Actual ProjectV2 E695** `ui/fixtures/tl494-source-e695-v2.gscad.json` contains 23 components/15 source Nets/62 member PinRef/0 imported wires/2 `Graphic.kind='source_b_continuation'`. No claim of routed 15/15.
- **GH Actions:** PR #136 branch `ui/chat3-production-canvas-qa-r2`: `canvas-and-qa` FAILED on newly added `real-integration.test.mjs`; concurrent `source-v2-model`, `manual-wire-domain`, `r0-editor-core`, `candidate-v2` SUCCESS at first GitHub check. Follow latest SHA after further commits.

## Real failures and tested scoped patch for owner #120

`real-integration.test.mjs` executes the actual imported canvas `projectToCanvasScene`, `hitTest`, `zoom`, `pinWorld`, original toy-v2 and genuine E695 source fixtures. On the base version it is expected to expose three failures:

1. E695 `source_b_continuation` unsupported by `graphicsToStrokes` (`UNKNOWN_GRAPHIC_KIND`). Original data is not allowed to be silently downcast as a conductor/Net. Fix a **graphical-only** stroke and explicit source role.
2. `hitTest` incorrectly selects a zero-length wire as if valid orthogonal conductor geometry.
3. `zoom` accepts existing camera scale zero and divides by it, generating nonfinite view state.

Patch for #120 in `patch-for-canvas-owner-120.diff`, **not applied** to their production files. In an isolated local copy of the two exact verified GitHub blobs, three regression tests initially **0/3 PASS**, after applying patch **3/3 PASS** with Node 22.16.0 Linux. Patch has not been approved/integrated into common UI and is not enough alone to declare R2.

## Manual Wire Engine UI selection boundary

`segment-id-command-adapter.mjs` is a small QA/bridge **reference**, not authoritative graph implementation. UI stores `{wire_id,segment_id}` from a non-ambiguous `hitTest`; on commit it checks `expected_revision`, `source_topology_hash`, `project_id`, and resolves stable segment ID to current engine array index inside one synchronous CAS window; then calls `#123 ManualWireEngine.moveSegment`. It refuses endpoint leads, stale index, missing segment, zero/unsafe delta, wrong source lock. `node --test ui/qa/chat3-canvas/segment-id-command-adapter.test.mjs` -> **5/5 PASS** using a controlled engine stub. Full #123 compiled-engine integration remains a separate mandatory acceptance.

## Performance and actual browser

Using verified `precision.mjs` at Node 22.16.0 Linux: 1000 custom symbols, 2000 segments, 100 pointer misses, warmup 15 queries; three runs **107.74, 106.89, 112.14 ms / 100 calls** (algorithm scan only, no SVG DOM or React). Does not imply 60 FPS.

`browser-pointer-harness.html` + `browser-pointer-smoke.py` is a repeatable **proposed** Playwright pointer smoke at 50/100/200% with `screen()` / `hitTest()`, pan and CSS rect offsets, pin identity, X selection and snap/grid toggle. Local Linux Chromium 144.0.7559.96 starts, but browser navigation to local HTTP test server was blocked with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. **Served-URL browser smoke = BLOCKED**. A separate offline in-memory Chromium QA harness (`browser-pointer-offline.py`) uses *exact original* #120 production JS bodies (only `import`/`export` transport statements are stripped to avoid forbidden local HTTP navigation). Chromium 144.0.7559.96 performed real Playwright pointermove/mousedown events at 0.004 / 0.008 / 0.016 px/µm, checking X hover/click, physical pin number, independent snap/grid: **15/15 assertions PASS**. It is a **geometry click smoke, not the actual React/Vite/Tauri CAD app E2E**; R2/R3 app browser acceptance remains BLOCKED. It must be exercised on approved Windows/browser CI by #125/#117 with a real app when present, not treated as a shipped React editor.

## Repro / constraints

From repo checkout: `node --test ui/qa/chat3-canvas/real-integration.test.mjs ui/qa/chat3-canvas/real-source-gate.test.mjs ui/qa/chat3-canvas/segment-id-command-adapter.test.mjs`. Base integration is expected to fail known negatives. Existing `ui/editor/src/canvas/*.test.mjs` and `ui/editor/src/wires/tests/manual-wire.test.mjs` are independent positives. Do not hide FAIL by skipping these checks or claiming that old Python CI covers browser gestures. Do not merge any PR without explicit user approval.

**BLOCKED WAITING_FOR:** #120 owner applies/mutates equivalent patch and commits verified SHA; #125 integrates actual React/Vite application and runnable E2E runner; #123 exposes stable segment-id command interface or accepts this CAS adapter; #122 validates E695 fixture/PinRef across snapshot and canvas.

## Latest integration recheck (2026-11-16, subject to newer HEAD)

MASTER added graphical-only source-b projection at `ui/visual-cad-mvp` SHA `180b5c244fe33d6c2b96fc50be4bb88018fe9d55`, `scene-projection.mjs` blob `6a19a0e0521381cdadebba39c725921b95e4a47c`. The E695 source-b failure is therefore historically reproduced at 44dc, **now corrected upstream**; do not reapply the old source-b diff. The remaining #120 precision.mjs SHA `389f60c1c6ee23d291a95ddf3d2d3dbe43b23203` still accepts zero-length segments and zero/invalid prior zoom. Current `patch-for-owner-120.diff` intentionally contains only those two changes.

MASTER subsequently introduced React/Vite/Mantine app entrypoint and `App.tsx`; canvas JSX uses positional `segmentIndex` in drag command even though segment IDs are stable. Our CAS-aware selection adapter is separately validated but **not integrated into App**. At integration SHA `9e0bf031879eede55389966e81be4562832fcef9`, `ui/editor/src/App.tsx` exists, but `ui/editor/package-lock.json` is still absent; R2 reproducible `npm ci` gate remains blocked. The new `editor-entrypoint.test.mjs` uses direct filesystem existence asserts against the live PR merge tree, making later fixes visible at exact SHA.