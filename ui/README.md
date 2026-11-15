# GOST Schematic — Visual CAD integration worktree

**STATUS as of 2026-11-16:** R1 architecture/contract and independent `ui/integration/` structural gate (17 Node tests). **No integrated React CAD app, signed TL494 source import, Python v2 adapter or Windows Tauri binary.** Never describe this branch as an MVP release until R2–R4 acceptance is demonstrated.

**Single integration owner:** #125 (MASTER). Direction and issue tracking: #116. Approved baseline: `integration/stage0-12` SHA `9ae2561562c2b6e41069e8343d0e682bd37ab3d4`. Architectural authority: [ADR-0010](../docs/decisions/0010-visual-cad-mvp.md). Data/wire contract: [manual-wire-v2](contracts/manual-wire-v2.md).

## R1 independently executable integration smoke

The MASTER-owned `ui/integration/source-gate.mjs` is a deliberately *non-authoritative* negative/positive screen for proposed `gscad-project` v2 values. It checks exact pin anchors, unique declared Net membership, tagged junction/splice/free behavior, orthogonality, 1µm drift and synthetic source spoofing; its 15 tests run automatically in `.github/workflows/visual-cad-r1.yml`.

```powershell
node --check ui/integration/source-gate.mjs
node --test ui/integration/source-gate.test.mjs
```

See `ui/integration/README.md` for limits and `ui/integration/browser-r0-smoke.md` for real R0 browser gestures (not an R2 acceptance claim). It does not replace #122's versioned JSON Schema, #123's write-safe wire engine, the original source E695 fixture or independent real-browser tests. Existing Python CI separately renders OpenGOST technical samples; its release metadata download uses the job-scoped GitHub API token only for `api.github.com` to avoid anonymous shared-runner 403 (no token on CDN assets).

## Expected structure (create directories only as code is transferred)

```text
ui/
  contracts/             # v2 schema/commands; #122 in consultation with #123
  fixtures/              # signed original TL494 + isolated toy projects; #122
  editor/                # React/Vite TypeScript package; #125 root owner
    src/model/           # #122
    src/wires/           # #123
    src/canvas/          # #120
    src/components/      # #121
    src/theme/           # #121
    src/export/          # #124
    src/history/         # #125 + #122
  desktop/src-tauri/     # #118
  bridge/transport/      # #118 supervised Python worker
  bridge/export/         # #124
```

# Reproducible process

1. Obtain ORIGINAL bytes from the isolated chats' ZIP attachments; GitHub issue comments are *not* downloadable source archives. Independently verify claimed SHA256 before extraction, check license/secrets, and list direct source/test inventory.
2. MASTER imports only the needed reviewed source into a dedicated working tree based on `ui/visual-cad-mvp`, keeping ownership boundaries above. Specialists use isolated worktrees/branches and report exact commit SHA and tests back to their Issues.
3. Integrate #122 typed v2 model **with** #123 splice/free semantics before using either as persistence; enforce the same exact 1µm physical PinRef values across TS and Python.
4. Integrate real Python-sourced UGO import, custom SVG editor view, wire state machine, save/open, canonical SVG+PNG300, then add Tauri shell and Windows build.
5. Until a real app exists, the commands below only verify the **existing Python baseline** and may not exercise any GUI:

```powershell
git fetch origin
git switch ui/visual-cad-mvp
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

**Future R2 app commands (not yet usable):** `cd ui/editor; npm ci; npm run typecheck; npm run lint; npm test; npm run dev` (Windows browser preview); `cd ui/desktop; npm run tauri dev` only after installed Tauri scaffold/sidecar. A native .exe requires Rust, Windows C++ toolchain and WebView2. Never claim these currently run.

First real GUI acceptance: create / select authentic R/C symbol / place / rotate / start wire at physical pin / bend and drag selected segment / explicit T vs false X / Undo+Redo / change inspector / independent grid+snap / save+reopen / clean SVG and 300DPI PNG / error panel / dark+light. Then import original 23/15/62/16+2b fixture and run source-integrity/negative gate, and finally native Windows bundle smoke.

Legacy eight PRs #93/#97/#99/#111/#112/#113/#114/#115 are **out of scope for code edits** and must remain open DRAFT until separately reviewed. Do not merge into `main` or `integration/stage0-12` without user approval.
