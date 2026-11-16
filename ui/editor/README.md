# Visual CAD — React/Mantine R2 engineering preview

This is the first app entrypoint on the approved ADR-0010 stack. It uses:
- CHAT5 Mantine panels and strict mm inspector (selectively transferred
  from Draft PR #132; the Draft PR itself remains open, not merged).
- CHAT4 SVG scene projection and exact physical pin positions.
- CHAT6 canonical, source-locked ProjectFileV2 fixture and Python validator.
- CHAT7 real, compiled TypeScript manual wire service.

The Python fixture preparer exports a browser-read-only E695 project and
a matching signed WireEngine snapshot; the browser does not invent source
PinRefs or create fresh Net names from pixel geometry. Source provenance
remains frozen at e695c415fdced164b0e0c39c5249d030795a0aa6.

Windows (Python >=3.12, Node >=22; no Tauri installer yet):
1. From repo root: python -m pip install -r ui/editor/src/model/requirements-dev.txt
2. cd ui/editor
3. npm install
4. npm run typecheck
5. npm run build
6. npm run dev
7. Open http://127.0.0.1:5173

Important scope limits:
- Interactive preview uses a genuine canonical ProjectFileV2-derived
  E695 snapshot and signed manual wire transaction, but has no trusted
  Python write transaction IPC in the browser. Do not claim native
  save/reopen; the File menu Save is disabled until #118 host service.
- Canonical SVG/PNG buttons stay unavailable until #124 adapter passes.
  No browser screenshot is claimed as an engineering export.
- New physical component placement, a validated MoveComponent+connected
  wire reroute command, explicit T handles and stable segment-ID move in
  the JSX are not yet R2 acceptance.
- The 23/15/62/16+2 source demo is UNROUTED initially, not 15/15 valid.
- TypeScript/Vite build + actual browser E2E + Windows Tauri are
  separate acceptance gates, not inherited from standalone tests.
