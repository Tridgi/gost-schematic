# CHAT 3 — independent canvas geometry QA oracle (R1)

**Role:** #119, review of the CUSTOM SVG canvas chosen in ADR-0010 (not a request to install React Flow).
**Baseline:** `ui/visual-cad-mvp` at `030ec942fd9f2b2e37fc2ad62ca8c85a1b96fc7a`.
**Contract:** `ui/contracts/manual-wire-v2.md` blob `1826bddc5fc9ed1ec3eeafb9c0d7bf7feee9a229`.

## Run

```sh
node --version            # Node >=20, tested 22.16.0
node --test canvas-contract.test.mjs
```

No `npm install`, third-party license, browser, network, or build step. No file in this directory belongs to the existing Python engine or production UI canvas.

## What the independent oracle covers

* exact signed-µm boundaries, local mirror then clockwise y-down transforms; four quarter turns;
* CSS client → local SVG/world projection with nonzero bounding rect/pan at zoom 0.5/1/2;
* viewport-independent visual hit radius for physical pins and orthogonal wire segments, overlap ambiguity rather than guessed electrical attachment;
* source PinRef identity distinct from mutable refdes and view handles;
* manual wire middle-segment normal move by +3 mm and exact inverse;
* geometric X as two independent wires for same or different Nets; explicit T junction, hidden Splice, isolated Free;
* wrong-Net terminal, anchored contact displaced 1 µm, unknown pin, false dot across foreign Net, zero/diagonal/fragmented segment rejection;
* read-only validation (negative fixtures must not mutate caller snapshot).

**Not tested / not a production implementation:** browser pointer captures, actual SVG DOM, Playwright gestures, production renderer (#120), actual wire service (#123), data schema (#122), E695 source file import, 1000-symbol FPS, SVG/PNG export, Windows Tauri. These remain `BLOCKED` until actual source code and runnable editor land at identifiable Git SHAs. Passing tests are only `PASS_AT_SHA` for this QA oracle, never R2/R3 acceptance.

## How to cross-check the production canvas later

1. Owner #120 exports actual `clientToWorld`, `worldPin`, `hitPin`, `hitSegment` and pointer handlers or supplies a thin adapter with equivalent interface. Replace *oracle* imports with adapter imports; use the same numeric fixtures and expected outcomes. Do not copy the oracle into production as an alternate Net engine.
2. Replay E2E gestures in Playwright: place R/C; zoom 50/200%; snap OFF; select physical pin with 6.99 CSS px vs miss at 7.01; select a vertical segment with 4.99 vs 5.01; move interior segment +3000 µm; undo/redo; pan; rotate 90; save/reopen.
3. Confirm source `Net.members` and `PinRef` remain unchanged by selection/crossing, X same/different Net has no junction dot, explicit T is validated via #123 wire command, invalid pin/net/1 µm changes roll back atomically.
4. Record test SHA and environment, never infer browser success from this no-browser suite.

`oracle.mjs` deliberately separates *view-space hit tests* from *electrical graph connectivity*. An unmarked X is not a T. Pixel distance is never an electrical equivalence relation. No dependency on `@xyflow/react` is required.

## Handoff

- #120: supply a pointer/world conversion adapter and physical pin hit-test API for actual production suite.
- #122: supply a canonical fixture loader/PinRef resolver, with exact integer validation.
- #123: supply command adapter for T/X/junction/splice/free, moveSegment and rollback.
- #125: integrate these tests in UI CI only after source adapters are wired and actual browser gestures exist.