# TL494CN — MAIN 3, next integration sprint 2026-11-15

Continue **existing Draft PR #115** and branch \`reference/tl494-audit-v4-20261114\`; base original reference; **no merge/main/integration changes**. [Coordinator task](https://github.com/Tridgi/gost-schematic/pull/115#issuecomment-6885031936) and [audit #107](https://github.com/Tridgi/gost-schematic/issues/107#issuecomment-6885041804). Original immutable source \`e695c415fdced164b0e0c39c5249d030795a0aa6\`. Historical 91 wires /37 junctions with **9 ERROR +32 WARNING** remain an expected negative fixture.

## New code in this existing PR (no manual SVG)

- [route_candidate_driver.py](route_candidate_driver.py): builds the true typed 23-component /15 **originally named** Net /62 unique PinRef model by comparing the original frozen ELEKTRIK IC fixture Git blob \`a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65\` with the existing compact-A3 ComponentInstance poses; explicitly restores \`a_INPUT_PLUS\`, \`TRANSFER\` and \`b_NEGATIVE_OUTPUT\`, not silently replacing them with aliases. Validates each physical contact, all 16 DA1 pins, source BOM and Decimal nominals, prevents imaginary PE. Uses real YGO DRAFT UGO with \`allow_relayout=True\` only for the **new** A3, genuine PAINT DA1 leads and Type A text keepouts, routes **all 15** via owner #114 with \`stop_on_first_failure=False\`. Stores every complete/failed Net and its real graph, no fake dots or missing wire substitution.
- Deterministic route order \`source\`, \`short-first\`, \`control-first\`. CLI allows read-only position-only variants \`--move DA1:-10:0\` and **actual** decimal 2.5mm grid \`--move DA1:2.5:-2.5\`: exact Decimal-to-integer-µm coordinates, <=30mm, no changes to Net, PinRef, orientation, nominal or symbol size.
- [routed_graph_contract.py](routed_graph_contract.py): serializes only accepted owner lines and junctions into a **typed ExternalWireGraph** for PAINT's real routed renderer; refuses forged Net, PE, zero/diagonal stroke, fake T/X dot, wrong 62 PinRef, inconsistent length/count, and claims of print release.
- [test_route_candidate_driver.py](test_route_candidate_driver.py) and [test_routed_graph_contract.py](test_routed_graph_contract.py): positive/negative/regression and real all-15-Net integration checks; together with native+compact suites **32 local PASS** on pinned actual owner overlay (Windows Python3.14). Dedicated [current-owner CI](../../.github/workflows/tl494-v5-current-owner-candidates.yml) installs source files pinned by immutable Git SHA, runs python3.12+3.13 Ruff/pytest and two real route-order variants, uploads JSON BOM/netlist/graph/current-owner SHA & hashes.
- Prior completed PR #115 43 Ruff source-style fixes \`cbb4303281ddb97559fcb7273f2326063e8b854a\` and original tests not repeated; last *older* full Linux Python3.12/3.13 success [#43644800966](https://github.com/Tridgi/gost-schematic/actions/runs/43644800966). Latest branch's GitHub Actions may still be **QUEUED**; do not call this HEAD CI PASS before completion.

## Exact tested owner snapshot (unmerged, not cherry-picked)

| Owner | SHA |
| --- | --- |
| ELEKTRIK IC #97 | \`19d14c4b660c9ad490a65cd1eab644f1637bc334\` |
| PAINT #93 | \`32f2efb2cdcb561cb2567a54448381de3cb87832\` |
| YGO2 #113 | \`eb16121e07efec71de77dfc7b8123bc09f66ddd6\` |
| ELEKTRIK NET #114 | \`5033659747f01fdc03adc084b846f47b05001963\` |

Latest source compact footprint (actual stroke bounds, UGO unscaled): **615.301×178.351mm before → 395.300×228.351mm after**, width saved **220.001mm**; A3 landscape 420×297mm with 10mm margin **for components**. Wires, text/continuations and full print page still need independent fit.

Real **new #114** compact-A3 routing at 5000 nodes per attempted Net: **6/15 networks complete, 30 accepted new segments, 919.502mm Manhattan wire length, accepted PARTIAL graph DRC 0 errors**. Complete: \`a_INPUT_PLUS\` (all 5 contacts including formerly blocked DA1.12), \`ADJUSTED_DIVIDER\`, \`FEEDBACK\`, \`RC_CORRECTION\`, \`SWITCH\`, \`TRANSFER\`. **Nine others incomplete** (COMMON, CONTROL_REFERENCE, ERROR_INPUT, GATE_DRIVE, OSCILLATOR_CT, OSCILLATOR_RT, OUT_BEFORE_FUSE, SOFT_START, b_NEGATIVE_OUTPUT). Current #114 gives exact \`INK_VETO\` reference/primitive/physical stroke coordinates and search-limit diagnostics; no error waived. Short-first at prior owner SHA \`2833e0a\` had 6/15 but a distinct successful network set and 27 accepted segments, proving order matters.

## Release acceptance BLOCKED

1. NET #114 must prove full 15/15, all 62 source physical contacts joined without false X/T and original \`b\` continuation, 0 actual whole-sheet 3/2/1mm + measured text/UGO/wire DRC errors. A partial graph's DRC=0 does **not** prove a complete E3.
2. PAINT #93 must render **actual NEW** fully verified ExternalWireGraph (not old frozen 91 wires) into clean/debug E3 SVG and true 300DPI PNG, real 16 DA1 pin marker and correct PWM rotation; no manual retouch.
3. Independent QA #99 must verify exact participating Git SHAs, frozen source photo/topology/electrical net identity, negative tampering, DRC, Source/AFTER metrics; ESKD normative figure and legal source comparison still **DRAFT**. True original bitmap calibrated parity is unavailable; cannot claim photography matches 1:1.
4. Coordinator MAIN 3 alone reviews a later narrow integration; this Draft PR never self-merges or changes main.

**Overall: 23/15/62 typed source and 32 local tests PASS; all-15 routing / print / independent QA BLOCKED.** A separate Windows full-repo Python3.14 attempt yielded 2166 pass, 9 skip, 4 fail and 191 fixture/setup errors due \`core.autocrlf=true\` changing byte-locked QA fixture blobs on checkout. It is NOT authoritative Linux Python3.12/3.13 CI; do not modify those fixtures or call them a fixed upstream defect.
