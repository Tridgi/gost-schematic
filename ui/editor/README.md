# Visual CAD R2 — integrated React/Mantine/SVG editor (engineering preview)

**Integration:** [MASTER Issue #125](https://github.com/Tridgi/gost-schematic/issues/125), [Epic #116](https://github.com/Tridgi/gost-schematic/issues/116), branch `ui/visual-cad-mvp`. Changes from CHAT4/#133, CHAT5/#132, CHAT6/#134, CHAT7/#129 and cross-domain negative QA are integrated selectively. Draft PRs are NOT automatically merged into `main`.

## Reproducible browser startup

Requirements: Python 3.12+, Node.js 22+, npm; internet for initial package download.

From repository root:

```powershell
python -m pip install -r ui/editor/src/model/requirements-dev.txt
cd ui/editor
npm ci
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
npm run dev
```

Vite serves the editor at `http://127.0.0.1:5173`. `predev`/`prebuild` validate and derive the E695 fixture and wire snapshot from canonical Python model. `package-lock.json` is committed, and `npm ci` is enforced in GitHub Actions; do not replace it with an unpinned `npm install` while reproducing CI.

## What the preview actually does

- Opens the **real source-traced** TL494 model pinned at `e695c415fdced164b0e0c39c5249d030795a0aa6`: **23 components, 15 declared source Nets, 62 unique physical PinRefs, 16 DA1 terminals, 2 non-electrical source-b graphics**. Initial routes: **zero**, not 15 verified.
- The mounted signed `CanvasViewport` supports zoom/pan, physical pin selection, pin-to-pin wire creation, interior segment move using stable `segment_id` plus monotonic revision/CAS, signed model-command Undo/Redo, and visible diagnostic rejections. Source Nets cannot be inferred by coincident SVG strokes.
- Symbol stroke selection, model-validated unconnected component placement, 90° rotation and inspector millimetre-coordinate changes, with rejection of movement that would detach authored physical wires. Connected component rerouting is not implemented.
- Browser file Save downloads editable `gscad-project` v2 JSON; Open restores the same frozen E695 source and editable route geometry after validating via model wire adapter. **This is deliberately source-locked**, not yet an unrestricted arbitrary third-party import. It is not atomic OS persistence or native Python IPC.
- Export downloads a **physical-mm SVG** retaining declared Net/PinRef inventory as metadata, or a **true 300-DPI PNG** derived from the same canonical project SVG and tagged with PNG `pHYs` 11811 pixels/m. Preview white paper A3 420 × 297 mm. Browser export is **NOT normative approval**: exact GOST font identity, print readiness and Windows spooler output are unverified. Certified export remains Python engine `ui/bridge/export/project_v2.py` awaiting desktop wiring.

## Validation boundaries

`npm test` exercises the inspector and browser physical exporter, including invalid project versions, XML escaping and PNG DPI; `npm run test:e2e` uses a real Playwright Chromium session for E695, wires/Undo/Redo, wrong-Net rollback, save/reopen, inspector placement, SVG/PNG download, and explicit 50/100/200% zoom. Independent `manual-wire-domain`, `project-wire-adapter`, `canvas-and-qa`, `source-v2-model`, `desktop-ipc-python`, and `canonical-v2-export` run on GitHub Actions. Check the **exact HEAD's** conclusions before claiming PASS. CI is not a Windows installer test.

Remaining before full CAD/desktop acceptance:
- New arbitrary physical part placement and editable part catalogue with source Net review.
- Explicit route handles, physical junction UI, advanced ERC/DRC and connected-symbol reanchor command.
- Unrestricted schema-validated project import, atomic host save/open.
- Production GOST typography/certified print export and safe Python/Tauri integration.
- Actual **Windows Tauri build, installation and runtime tests**, currently BLOCKED until a Windows build environment is available.

Do not count all 15 declared source Nets as wired; do not substitute rendered geometry for electrical topology.
