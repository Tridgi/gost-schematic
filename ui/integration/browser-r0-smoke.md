# MASTER #125 — R0 browser regression evidence (2026-11-16)

**Purpose:** translate a real browser test of the previous standalone R0 prototype into an R2/R3 acceptance target. This document is an independently executed smoke record, **NOT** a product acceptance for React/Tauri, not a test of gscad-project v2.

## Source and environment

- Original user-facing R0 archive SHA256: `72d67151168dc9c9af9b596366b312cb54c3ac28aab3cc2f733681d583327d6b` (15 files). Source is **not imported to the branch**.
- Locally hardened R0 archive (26 Node unit tests plus `tests/browser_smoke.py`): `gost-visual-cad-r0-hardened-e2e-20261116.zip` SHA256 `78e4119c2af658e4f6f19511dfc7a89fa0e06218144a1965df66cc76a5fd1dbb`. The file was delivered in this CHAT9 conversation, not committed to GitHub.
- Linux Chromium headless via Playwright. The sandbox rejects navigation to localhost, HTTPS and file: with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. To exercise **real** DOM pointer events without bypassing security policy, a trusted local test harness embeds R0 HTML/CSS/ES modules in inert `about:blank` with an ephemeral in-memory localStorage shim. **No real origin, installed Tauri, HTTP serving, persistent browser storage or Vite bundle was tested.**
- Node.js v22.16, JavaScript syntax checks PASS and `node --test tests/core.test.mjs` 26/26 PASS.

## Executed real browser smoke (PASS, R0 ONLY)

1. Open source in restricted Chromium in an inert document; 3 synthetic DRAFT instances visible, **0 JavaScript page errors**.
2. Select Wire and **mouse-click real SVG pin `r1.2`**, then **mouse-click `c1.1`**: 1 orthogonal wire created, physical endpoint IDs retained.
3. UI Undo → 0 wires; Redo → 1 wire.
4. Disable grid visibility and grid snapping independently; switch to light theme.
5. Mouse-drag interior vertical wire segment **+3000µm (within ±100µm)**; confirm endpoints byte-identical and interior geometry changed.
6. Undo/Redo segment transaction; saved project point arrays match pre/post snapshots.
7. Native browser Download of editable JSON; reopen JSON from file input, same wire count and preserved endpoint refs.
8. Native browser Download of clean SVG: physical `width="420mm"`, `data-wire-id` and `data-net-id`; no editor grid/handles.
9. Native browser Download PNG: A3 **4961×3508** with embedded `pHYs` ~300 DPI (Pillow inspected).
10. Visual screenshot caught **white-on-white symbol contrast in dark theme** caused by nested SVG `currentColor` inheritance; isolated R0 source fixed by setting `color="#202935"` on symbols' scene group and re-tested.

**Honest negative boundary:** R0 uses synthetic `gscad-spike` v1 and a demo TL494 symbol, **NOT** frozen E695 23/15/62/16+2; no true cross-Net T/X/splice graph CAS, no final #122 schema, no production Python clean SVG bridge, no Windows / Tauri smoke. This does **not** satisfy full R2/R3.

## Required re-run for accepted R2/R3

Use #117 UX acceptance and real built `ui/editor` (React/Vite) from exact commit, **no inline test transport**:
- Playwright navigate actual localhost WebView dev server, verify mouse selection/rotate/pin/wire/segment edit at 50% and 200% zoom.
- Preserve original physical `PinRef={component_id,physical_pin_number}`, test 1µm drift, unique free endpoint, invisible splice, explicit same-Net junction, unmarked X/foreign-Net rollback.
- Save/reopen canonical `gscad-project` v2, source identity hash and full frozen E695 count+name+membership fixture.
- Compare canonical Python SVG with rasterized true PNG300 and font hash, not DOM screenshot.
- Windows Tauri native worker IPC and durable atomic save; only then mark `PASS_AT_SHA`.

**Dependencies:** #122 model/schema/source fixture; #123 wire transactions; #120 canvas; #121 Mantine shell; #124 export; #118 Tauri/Python worker. All are **BLOCKED for integrated R2/R3** until source files are committed at exact SHAs.
