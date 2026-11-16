# Desktop IPC shell — CHAT 2 isolated Draft PR

Owner #118; integrator #125. This directory is an independent **Tauri 2 + Rust/Python IPC smoke shell**, **not a CAD editor**. It is based on ui/visual-cad-mvp at 030ec942fd9f2b2e37fc2ad62ca8c85a1b96fc7a and must not be merged without project-owner approval. No changes to main, integration, E695, or legacy PRs.

## API and security contract

- Frontend may invoke only Rust commands engine_request and cancel_engine_request. No frontend shell or broad filesystem permissions. The native Rust host executes only packaged sidecar engine-bridge, never a user-provided executable or shell command.
- v1 requests use exact keys v,id,op,args. Active: hello/unit_roundtrip/check_symbol/render_symbol; read-only #122 canonical gscad-project v2 operations validate_document/source_snapshot/verify_net; and #125 read-only wire_snapshot/validate_wire_candidate (candidate is only validated and returned, NEVER persisted, committed=false). ProjectV2 is validated against the single #122 JSON Schema and semantic graph; there is no transport-local copy. position_edit/render_svg/export_png deliberately return NOT_WIRED pending authoritative transaction + #124 export adapter. This is not R3 acceptance.
- Python consumes up to 1 MiB UTF-8 NDJSON line and emits at most 4 MiB protocol response; stdout contains only protocol lines, stderr diagnostics. It rejects duplicate JSON keys, non-finite numbers, raw paths and unknown operations; verifies correlation ID. IPC v1 encodes int64 micrometres as decimal strings for exact transport; gscad-project v2 is a separate schema with bounded JSON integers (<= 1e9) — convert explicitly at the adapter.
- Rust starts a separate worker per request and terminates it on reply, 15-second timeout, or cancellation. This **is not yet a persistent sidecar supervisor**; benchmarked startup and restarts are pending. Its CommandEvent::Stdout parses line-oriented frames without waiting for a newline. CSP allows ipc: and http://ipc.localhost, offline WebView2 NSIS is configured but not verified by building.
- Rust must own native file picker, safe opaque document handles and atomic save after MASTER approves a versioned document session API. The current preview does **not** save documents. ProjectFileV2 candidate checks use the real #125 ProjectWire adapter with exact source hash and stale project SHA rejection, but they remain **stateless dry-run validation**; request-provided baseline is not an OS-backed CAS. Use a Rust owned document handle before calling it a commit.

## Verified independent checks

From repository root, with Python 3.12+ and Node 20+:

    python -m unittest discover -s ui/bridge/transport/tests -v
    node --check ui/bridge/transport/smoke.mjs
    node ui/bridge/transport/smoke.mjs

Transport/Node tests have no npm dependencies. When the shared #122 model and #125 adapter/fixture files are present, five additional v2 model/Net/candidate integration tests execute rather than SKIP. Install the canonical model requirements and optional real Python core for complete coverage:

    python -m pip install -e ".[dev]"
    python -m pip install -r ui/editor/src/model/requirements-dev.txt
    python -m unittest discover -s ui/bridge/transport/tests -v
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

- #122 model code from Draft PR #134 (and its source-locked E695 fixture) is now available and called for **read-only** validation. #125 currently owns ProjectFileV2↔WireEngine bridge at ui/integration/project_wire_bridge.py; our stateless candidate validation uses it. Permanent session generation and transactional durable writes remain blocked pending #125 approved integration.
- #124 must publish canonical scene SVG/PNG300 adapter at exact SHA (Rust would only manage approved output paths, not render a WebView screenshot).
- #125 supplies main React/Vite app, lockfiles, native E2E and integration approval. #118 owns only ui/desktop/** and ui/bridge/transport/**; this PR targets ui/visual-cad-mvp without modifying the branch itself.

## Release safety: not yet verified

Native Rust/Tauri compile, Windows NSIS signing, actual browser invoke, timeout/cancel/restart E2E, protected project open/save recovery and PNG300 are **BLOCKED or untested**. Read-only E695 fixture/Net verification is integrated at source level and has targeted tests, but must be executed on the merged source tree before PASS_AT_SHA. CI on docs-only PR #126 is not evidence of these gates.


## New IPC wire adapter v1 (source-level R2 preflight)

Request to obtain current canonical WireEngine DTO (no disk mutation):

~~~json
{"v":1,"id":"snap_1","op":"wire_snapshot","args":{"document":{"format":"gscad-project","format_version":2,"project":{},"workspace":{}}}}
~~~

The payload above is a **shape example only** and intentionally fails schema validation until an actual ProjectFileV2 document is supplied. A valid result contains project_sha256, source_topology_sha256, wiring_snapshot and committed=false. Submit proposed candidate via op=validate_wire_candidate with args.document (original validated ProjectFileV2), args.candidate (canonical #125 WireEngine snapshot), args.expected_project_sha256 (64-lowercase hex). This returns validated_document, new project_sha256 and committed=false, or a strict error STALE_PROJECT_SHA / SOURCE_TOPOLOGY_CHANGED / PIN_ANCHOR_MISMATCH / BRIDGE_UNAVAILABLE.

**No arbitrary filesystem paths** are accepted through either IPC operation. Worker imports only fixed app-owned files ui/editor/src/model/contract.py, ui/contracts/project-v2.schema.json and ui/integration/project_wire_bridge.py. Windows packaging includes those data files; tauri-plugin-shell is pinned >=2.6.0 because kill_on_drop(true) and set_process_group(true) protect PyInstaller subprocess tree. Full version-locked Cargo build and Windows acceptance remain unverified.

This bridge does not infer electrical topology from SVG/pixels. It does not certify partial TL494 routing as complete; use source counts 23/15/62/16+2 b / 0 legacy wires as the negative gate.
