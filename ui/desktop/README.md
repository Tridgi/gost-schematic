# Desktop IPC shell — CHAT 2 isolated Draft PR

Owner #118; integrator #125. This directory is an independent **Tauri 2 + Rust/Python IPC smoke shell**, **not a CAD editor**. It is based on ui/visual-cad-mvp at 030ec942fd9f2b2e37fc2ad62ca8c85a1b96fc7a and must not be merged without project-owner approval. No changes to main, integration, E695, or legacy PRs.

## API and security contract

- Frontend may invoke only Rust commands engine_request and cancel_engine_request. No frontend shell or broad filesystem permissions. The native Rust host executes only packaged sidecar engine-bridge, never a user-provided executable or shell command.
- Each v1 request uses keys v,id,op,args. Only hello, unit_roundtrip, check_symbol, render_symbol are active. Five future CAD commands (source_snapshot, position_edit, verify_net, render_svg, export_png) intentionally return NOT_WIRED pending #122/#124 and source CAS adoption. This is a smoke prototype, not a false R3 PASS.
- Python consumes up to 1 MiB UTF-8 NDJSON line and emits at most 4 MiB protocol response; stdout contains only protocol lines, stderr diagnostics. It rejects duplicate JSON keys, non-finite numbers, raw paths and unknown operations; verifies correlation ID. IPC v1 encodes int64 micrometres as decimal strings for exact transport; gscad-project v2 is a separate schema with bounded JSON integers (<= 1e9) — convert explicitly at the adapter.
- Rust starts a separate worker per request and terminates it on reply, 15-second timeout, or cancellation. This **is not yet a persistent sidecar supervisor**; benchmarked startup and restarts are pending. Its CommandEvent::Stdout parses line-oriented frames without waiting for a newline. CSP allows ipc: and http://ipc.localhost, offline WebView2 NSIS is configured but not verified by building.
- Rust must own native file picker, safe opaque document handles and atomic save once #122 provides a validated snapshot serializer. The current preview does **not** save documents. Source-lock CAS has an independent Python preflight helper and tests, but is deliberately not exposed as a fake write API.

## Verified independent checks

From repository root, with Python 3.12+ and Node 20+:

    python -m unittest discover -s ui/bridge/transport/tests -v
    node --check ui/bridge/transport/smoke.mjs
    node ui/bridge/transport/smoke.mjs

These tests do not need npm packages or an installed editor. To run optional real engine symbol check, install core as editable package:

    python -m pip install -e ".[dev]"
    node ui/bridge/transport/smoke.mjs

### Windows native build (NOT verified in current Linux sandbox)

Install Rust stable MSVC / Windows C++ Build Tools / WebView2 / Python 3.12. Then:

    py -3.12 -m venv .venv
    .\ui\desktop\build-sidecar.ps1
    cargo install tauri-cli --locked
    cd ui\desktop\src-tauri
    cargo tauri dev
    cargo tauri build

This produces a source-level smoke shell if toolchain and packaging are correct, **not** proof of a working CAD application. A real build must record native logs, lock Cargo dependencies, audit sidecar/font licences and test a fresh offline Windows 11 install. Separate MASTER R2 browser UI may replace the static dev-preview after integration.

## Required dependency contracts

- #122 (gscad-project v2) must publish exact model serializer/transaction command at a code SHA: project revision and immutable source topology SHA, PinRef physical identity, signed um conversion, atomic failure on invalid edit. No schema guessed here.
- #124 must publish canonical scene SVG/PNG300 adapter at exact SHA (Rust would only manage approved output paths, not render a WebView screenshot).
- #125 supplies main React/Vite app, lockfiles, native E2E and integration approval. #118 owns only ui/desktop/** and ui/bridge/transport/**; this PR targets ui/visual-cad-mvp without modifying the branch itself.

## Release safety: not yet verified

Native Rust/Tauri compile, Windows NSIS signing, actual browser invoke, timeout/cancel/restart E2E, project open/save recovery, source import fixture 23/15/62/16+2b and PNG300 are **BLOCKED or untested**. CI on docs-only PR #126 is not evidence of these gates.
