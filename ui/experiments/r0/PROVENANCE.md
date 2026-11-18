# Visual CAD R0 standalone source — verified import

**Owner:** MASTER #125. **Purpose:** runnable experimental baseline for manual CAD interactions, not the selected React/Tauri release implementation.

- Original CHAT9 archive SHA256: `72d67151168dc9c9af9b596366b312cb54c3ac28aab3cc2f733681d583327d6b`.
- Hardened browser-tested archive SHA256: `78e4119c2af658e4f6f19511dfc7a89fa0e06218144a1965df66cc76a5fd1dbb`. Its text source files are imported here. Standalone sample PNG/SVG binaries and redundant R0 ADR are intentionally omitted.
- License: MIT, no redistributed external fonts, no runtime npm dependencies.
- Local Node v22.16: `node --check app.mjs; node --check core.mjs; node --test tests/core.test.mjs` => **26/26 PASS**.
- Restricted Linux Chromium Playwright `python tests/browser_smoke.py`: mouse R1.2→C1.1 connection, Undo/Redo, +3mm inner segment drag, exact endpoint IDs, JSON save/load, clean mm SVG, PNG A3 4961x3508 @300DPI, theme and independent grid/snap => **PASS**. The harness embeds local assets in inert `about:blank` because sandbox navigation is blocked. This is NOT localhost/Vite/Windows E2E. The fixture uses synthetic TL494 graphics.
- Browser screenshot contrast review corrected R0 canvas `currentColor` to dark ink on white paper in dark theme.
- Critical limit: `gscad-spike` v1 is **not** authoritative `gscad-project` v2. It is prohibited to import files into final engineering model or claim E695 23/15/62/16+2 without validated #122 adapter and #123 graph. Historical TL494 negative route remains invalid.
- Approved architecture: [ADR-0010](../../../docs/decisions/0010-visual-cad-mvp.md). Future React/Mantine app will live separately in `ui/editor/`.
- Run: `cd ui/experiments/r0; python -m http.server 8000 --bind 127.0.0.1`, then open http://127.0.0.1:8000/ in browser. `node --test tests/core.test.mjs` verifies model. This experiment does NOT satisfy R2/R3 acceptance.
