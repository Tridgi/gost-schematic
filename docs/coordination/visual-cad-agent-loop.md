# Visual CAD — multi-agent coordination and review relay v1

**Status:** active R1 coordination protocol; **not** a claim of background-running ChatGPT agents.
**Owners:** MAIN coordinator, [MASTER #125](https://github.com/Tridgi/gost-schematic/issues/125) sole shared UI branch integrator.
**Epic:** [#116](https://github.com/Tridgi/gost-schematic/issues/116). **Integration branch:** `ui/visual-cad-mvp`. **Draft PR:** [#126](https://github.com/Tridgi/gost-schematic/pull/126). **Decision:** [ADR-0010](../decisions/0010-visual-cad-mvp.md), **contract:** [manual-wire-v2](../../ui/contracts/manual-wire-v2.md).

## Reality of the loop

A ChatGPT chat only works while explicitly activated. Issue comments, GitHub commits and CI runs **do not wake or autonomously resume** a prior chat. Never write "I'll keep running in the background" or loop indefinitely on repeated API polling. The reliable cycle is **event-triggered CI** + **documented issue handoffs** + **a fresh user-triggered session that reads the latest GitHub state and continues**.

At the start of *every active session*: fetch current HEAD of the integration branch and its base, PR #126 diff & CI, [#116](https://github.com/Tridgi/gost-schematic/issues/116), your own Issue, [#125](https://github.com/Tridgi/gost-schematic/issues/125), upstream/downstream Issue comments and any owner Draft PR. Use concrete actual commit SHA, not the historical `e258b712...` from first R1 setup.

Work during an active session: evaluate latest dependency artifact → implement or cross-review → run tests → publish SHA/patch/PR → reread relevant owner work and exact CI → fix concrete discrepancies → publish one final handoff. Repeat where productive new commits arrive. If nothing new is available, **do independent test/code tasks** rather than sleeping/waiting. Finally publish `BLOCKED WAITING_FOR` with a precise prerequisite and stop; next session resumes from GitHub.

## Required status vocabulary (never infer completion)

- `NOT_STARTED`: no code artifact;
- `IN_PROGRESS`: implementation underway without verified acceptance;
- `READY_FOR_REVIEW`: committed to exact SHA and owner tests reported; independent review still outstanding;
- `REVIEW_REQUIRED`: dependency changed; consumer must rerun tests at exact SHA;
- `BLOCKED`: cannot proceed; specify dependency Issue, needed API/commit and available independent work;
- `FAIL`: reproducible negative test/diff breaks acceptance; issue must contain expected/actual, trace and SHA;
- `PASS_AT_SHA`: tested and accepted **only on that SHA**, with commands, environment and coverage;
- `ACCEPTED_R2/R3/R4`: MASTER declares phase acceptance only after mandatory independently checked tests.

## Structured GitHub handoff comment

```text
CAD HANDOFF | ROLE=<1..9> | STAGE=<R1/R2/R3/R4>
STATUS=<NOT_STARTED|IN_PROGRESS|READY_FOR_REVIEW|REVIEW_REQUIRED|BLOCKED|FAIL|PASS_AT_SHA>
BASE_SHA=<40 hex> | HEAD_SHA=<40 hex> | SOURCE_SHA=<source fixture if relevant>
FILES_CHANGED=<specific paths>
CONTRACT=<JSON v2 / IPC v1 / canvas-commands etc and semantic version>
TESTS=<actual commands, platform, pass/fail/skip, artifact links>
DEPENDENCIES=<#N at SHA, expected interface and current gate>
REVIEW_REQUEST=<role number, change path, concrete case>
NEXT_ACTION=<one to three actionable steps>
```

Do not post superficial heartbeat comments that contain no code/CI/review facts. If a dependency changes after PASS, that old PASS remains historical; the changed consumer contract returns to `REVIEW_REQUIRED` until retested.

## Cross-review dependency matrix

| Role | Owns | First dependencies | Required cross-review |
|---|---|---|---|
| #117 CHAT1 UX/E2E | UX acceptance docs, Playwright cases | #120/#121/#123/#125 app flow | Retest #120 canvas + #121 UI + #123 wires on real browser |
| #118 CHAT2 desktop | `ui/desktop`, `ui/bridge/transport` | #122 v2, #124 export, #125 Vite app | Native Windows IPC, safe save/open, Rust/Tauri E2E |
| #119 CHAT3 canvas QA | independent geometry/interaction tests | #120 canvas, #123 wires, #122 pins | False-X/T, zoom, pointer hitbox, 1000-component measurements |
| #120 CHAT4 SVG canvas | `ui/editor/src/canvas` | #122 model, #123 commands, #121 shell | #117 gestures + #119 independent geometry QA |
| #121 CHAT5 design | `ui/editor/src/components`, `ui/editor/src/theme` | #125 root, #120 canvas, #122 selection | #117 UX + #118 WebView2 focus/panels |
| #122 CHAT6 model | `ui/editor/src/model`, `ui/contracts`, `ui/fixtures` | #123 splice/free agreement | #123 wires + #118 IPC + #124 export source graph |
| #123 CHAT7 wires | `ui/editor/src/wires` | #122 typed anchors/transaction | #120 pointer operation + #119 topology negative tests |
| #124 CHAT8 export | `ui/editor/src/export`, `ui/bridge/export` | #122 scene, #123 wires, #118 bridge | canonical mm SVG/PNG pHYs/font, native output |
| #125 CHAT9 MASTER | one shared UI app root, locks, PR/CI/E2E | all 8 owner outputs | integrate and rerun all gates; request fix ownership |

**File ownership:** specialists use separate Git worktrees or own branches; only MASTER coordinates shared project entrypoint/integration. Avoid writing into the same worktree concurrently. Specialists may submit Draft PRs targeting UI integration branch, but **no PR merges without explicit user permission**. Main, `integration/stage0-12`, frozen E695 source and original eight engine owner branches remain untouched without permission.

## Exact engineering invariants

Immutable [E695 source](https://github.com/Tridgi/gost-schematic/tree/e695c415fdced164b0e0c39c5249d030795a0aa6): 23 components, 15 literal original Net names, 62 physical PinRef memberships, all 16 TL494 DA1 physical pins, two graphical NON-electrical b continuations. Historical 91 authored wires/37 dots with 9 ERR/32 WARN are negative, **never** marked fully routed. Manual CAD R2/R3 does not require auto-router 15/15.

`gscad-project` v2 uses signed integer µm, independent `PartDefinition` and `SymbolDefinition`, stable `PinRef=(component_id,physical_pin_number)`, source-declared Nets separate from realized wire graph, `pin|junction|splice|free` anchors (only Junction visible dot, Splice invisible continuous degree-2, Free uniquely isolated), exact 1µm transforms, explicit T vs unmarked X, independent gridVisible/snapEnabled, atomic Undo/Redo/CAS, strict serialization, true clean mm SVG and raster PNG from the same clean scene with actual 300-DPI metadata. No screenshot is a canonical SVG.

## Phase gates — enforce them sequentially

- **R1:** ADR/branch/contracts and verified archive transfer from original agent chats. ZIP attachment names alone are not repo source. For every imported file record sha256/license/owner and exact commit.
- **R2:** actual Windows browser `npm ci`, TS typecheck/lint/unit, Vite launch, genuine R/C UGO placement/move/rotate, UI shell, pin selection, theme/grid/snap, actual pointer E2E. UI source must be integrated; docs-only PR is not a build.
- **R3:** real manual pin-to-pin wire, orthogonal bend+interior segment move, T/X/splice/free semantics, wrong-Net rollback, Undo/Redo, save/reopen electrical identity, canonical SVG + PNG300, Playwright gesture report, source fixture integrity.
- **R4:** genuine frozen 23/15/62/16+2b import (route may honestly remain partial), Windows Tauri installed/launch smoke, protected Python worker, font/print check, 23/1000 object benchmark measured. 60 FPS requires measured evidence.

## GitHub Actions guidance

Run checks on `push`, `pull_request`, `workflow_dispatch` on approved scopes; attach results to exact SHA. If a future `schedule` review is wanted, note GitHub's scheduled workflows execute on the repository default branch, **not merely because a file exists in an unmerged feature branch**. Do not introduce untrusted comment-triggered code execution, unsafe forks/secrets, infinite self-triggering commits or automatic merges. Prefer deterministic CI gates and human-reviewed issue notifications.

## Next actions for MASTER

1. Recover SHA-verified R0 archive from its originating CHAT9 session; source is **not yet on GitHub**.
2. Get #122+#123 to validate/implement the wire v2 schema **before** integrating UI code; source fixtures must preserve E695 truth and never invent completion.
3. Integrate #120/#121/#124 and #118 by directory ownership, run actual browser/Windows acceptance, publish exact SHA and real PASS/FAIL/BLOCKED.

**Finish each session with a factual GitHub handoff; never claim work continues between sessions.**
