# CHAT 5 — Visual CAD controlled Mantine shell (R1 specialist branch)

Owner CHAT 5 / Issue #121. Integration owner MASTER / Issue #125. Baseline ui/visual-cad-mvp at 030ec942fd9f2b2e37fc2ad62ca8c85a1b96fc7a. Status READY_FOR_REVIEW, **not running CAD app**.

This subtree adds controlled React UI shell, semantic theme CSS, strict mm->µm parser, dock layout persistence and Node-only tests. The specialist does NOT own ui/editor app entrypoint, package.json, lockfile, Vite config, actual canvas, wire engine, Python bridge, source UGO renderer or true export. MASTER must integrate these after R1 review.

## Candidate dependencies (NOT installed or lockfile-verified)

- @mantine/core and @mantine/hooks 9.8.1 — MIT
- lucide-react 1.73.0 — ISC
- React and TypeScript pinned by MASTER.
- Root app must import @mantine/core/styles.css once before rendering EditorShell.
- Official resizable AppShell hook: https://mantine.dev/core/app-shell/ . Its resize CSS vars live at AppShell root, not Modal portal. Our semantic colors are declared on document root's Mantine color scheme to prevent modal theme mismatches.

## Strict integration boundaries

- EditorShell receives snapshots, a real canvas ReactNode slot, and callbacks only.
- Trusted catalogue thumbnails must arrive as ReactNode rendered from versioned Python GOST UGO symbols, not fabricated Lucide electrical symbols. Never insert untrusted SVG strings into innerHTML.
- onInspectorProposal is a proposal, not a mutation. It contains instanceId, baseRevision, exact integer µm and only validated host command may commit. The UI reverts the draft display to canonical snapshot after proposal to avoid false optimistic values. The host must map to source v2 revision/CAS transaction with PinRef unchanged.
- The Grid toggle and Snap toggle are fully independent. Neither visually connects or changes a Net.
- All physical pin numbers and Net names shown in inspector are read-only; no pixel-driven source rewrites.
- Export button is disabled unless exportReady AND a real #124 renderer onExport handler exist. Never screenshot the editor and call it canonical SVG.
- Persistent keys gscad:ui:theme:v1 and gscad:ui:dock-layout:v1 belong to USER preferences, never serialized into engineering Net/PinRef hash.
- Outer left/right docks use Mantine useAppShellResize; lower right splitter is touch/pointer/keyboard. Reset calls resize.resetAll AND clears saved values.

## Repeatable isolated Node tests

Node.js >=22, experimental TS stripping:

    node --experimental-strip-types --test ui/editor/src/theme/layout.test.ts ui/editor/src/theme/tokens.test.ts ui/editor/src/components/inspector-units.test.ts

Do not claim these tests compile React/Mantine, prove browser events, validate physically correct pin-and-wire model or pass R2. Need npm ci, tsc --noEmit, Vite, Playwright and Windows WebView2 smoke once MASTER owns actual app package/lockfile. Current unavailable npm/Chromium prevents that.

## Acceptance requests

- #117 review keyboard, dialog focus, Tauri 125% and 200% scaling, 1280/1440/1920 widths and high-contrast/reduced-motion.
- #118 validate WebView2 focus, resize pointer capture, CSS portal theme consistency.
- #120 connect custom SVG canvas to canvas slot via typed commands, preserving accurate physical PinRef and snap/grid state.
- #122 provide authoritative SelectedInstance selection fields, CAS transaction adapter and error feedback for inspector proposals.
- #124 deliver canonical SVG/PNG300 output and gate exportReady only when verified.
- MASTER #125 run full integration tests, pin dependencies/lockfile, review/merge only upon user approval.

Source fixture 23 parts / 15 original source Nets / 62 PinRef memberships / 16 TL494 physical pins / 2 non-electrical b is not imported by this shell. Historical 91 wires / 37 junctions / 9ERROR+32WARN are intentionally invalid, not release-pass.