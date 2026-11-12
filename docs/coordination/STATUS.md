# Coordination status — 2026-11-12

**Scope:** experimental work only. `main` and historical PR #2–#9 remain untouched; all 18 existing symbols remain **DRAFT**, 0 approved.

## Accepted integration batch

- **#15 / Issue #11 — ESKD normative evidence:** merged to `integration/stage0-12` as `122b4caff1962841d98f43ac5e36cc3896240da2`. CI after merge: https://github.com/Tridgi/gost-schematic/actions/runs/43299843402 (success).
- **#16 / Issue #12 — external wire graph prototype:** merged as `bcfdec9b9c1101ba7ce5d3028ec624acf7c47da0`. CI after merge: https://github.com/Tridgi/gost-schematic/actions/runs/43300060566 (success).
- **#14 / Issue #13 — 18-UGO SVG review harness:** merged as `c31b16a24f967f99b780166a075d615aa73a6ce5`. **Combined CI**: https://github.com/Tridgi/gost-schematic/actions/runs/43300234625 (success, **408/408 tests** on Python 3.12 & 3.13, Ruff pass, catalog audit 18 draft / 0 hard errors, wheel verification success).
- Issues #11, #12, #13 closed as completed development tasks, **not** as normative UGO approvals.

## Active / blocked

- **Issue #10 `parallel/catalog`**: standalone polarized electrolytic capacitor DRAFT. Normative sources from #11 handed off in coordinator comment: https://github.com/Tridgi/gost-schematic/issues/10#issuecomment-6834997778 . Exact final geometry/controlled vector and full dimension authority still pending. Any experimental dimensions must be clearly named editorial and not claim ГОСТ certification. New JSON/physical part requires tests, isolated contacts, correct polarity, explicit topology.
- **Issue #17 — Rendering catalog growth**: refactor review sheet to include all current DRAFT symbols dynamically, not hard-coded 18. Coordinate with #10; no shared model/core/catalog changes. https://github.com/Tridgi/gost-schematic/issues/17
- **Normative manual review**: 15 inductor shapes remain unapproved, high-risk `double_tapped`, `sliding_contact`, `trim_copper`, `variable` need controlled KOMPAS/original comparison; not a blocker for isolated DRAFT engine evolution.

## Review decisions

- Three PRs were reviewed by coordinator and merged **only** into experimental integration, not `main`.
- No automatic promotion from DRAFT to APPROVED. Green CI checks implementation properties, not full compliance with ГОСТ.
- Current integration code baseline before this status document: `c31b16a24f967f99b780166a075d615aa73a6ce5`. Future workers must fetch current `integration/stage0-12` HEAD, not use old `67c66da` baseline.
- New work must use independent branches, clear Issue scope, and new Draft PR; preserve existing reviewed commits and avoid rewriting unrelated history.
