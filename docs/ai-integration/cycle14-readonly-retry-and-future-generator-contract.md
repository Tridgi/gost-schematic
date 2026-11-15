# Cycle 14 — typed AI generator boundary and safe retry contract

**Status:** the present implementation is a **read-only inspection contract**.
The *future* seven-stage generator and any transactional writer are
**NOT IMPLEMENTED / NOT APPROVED**. This document does not register an MCP
writer, allow source rewrites, or upgrade DRAFT UGO to APPROVED.

## Evidence and identity carried through every stage

Immutable root authority is the frozen user-source commit
`e695c415fdced164b0e0c39c5249d030795a0aa6` and the packaged IC97
Git blob `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`.
Every candidate must preserve **23** source BOM references with literal
`source_part_id` and `nominal_si`, exactly **15** original named physical
Nets with **62** source `PinRef` memberships, all **16** real DA1 physical
pins, and the two signed **non-electrical** `b-X2`/`b-R5` continuations.
The old 91 segments / 37 junctions are historical negative input
(9 print DRC errors, 32 warnings), never print-ready output.

The candidate identity must include:
- `source_git_commit`, `source_git_blob_sha1`, immutable source manifest SHA256;
- catalogue `part_sha256` and `symbol_sha256` for each exact selected UGO;
- manufacturer `reference.tl494cn` ↔ `ti.tl494cn.pdip16` signed owner bridge;
- canonical physical Part ID, actual `PinRef` and exactly named `Net`;
- each owner's exact reviewed code SHA and any explicitly approved API version.

Unrecognised/missing identity, ambiguous UGO, edited nominal, generated
`PinRef`, renamed physical Net, lost pin membership, forged b marker
or SVG-pixel-inferred connection is **REJECTED** before placement.

## Required future pipeline stages

| Stage | Input → output evidence | Blocking gate |
| --- | --- | --- |
| `SOURCE_MODEL` | Signed immutable source → trusted manufacturer-typed physical Circuit and exact member SHA | 23/15/62/16 and non-electrical b correspondence must match; no native P1.1 import yet |
| `UGO_SELECTION` | Source references → exact catalog variant, actual pin templates and two SHA locks | No implicit family/default fallback, 13 source-selected variants stay DRAFT until QA |
| `PLACEMENT` | True physical anchors → bounded page/layout candidate in integer µm | Preserve all pin identity; check body/ink/labels, usable page and manufacturer geometry |
| `ROUTING` | Identical original physical Net membership → connected `ExternalWireGraph` | Real 15/15 independently confirmed, no crossing false joins, 3/2/1mm constraints respected |
| `ERC_DRC` | Native candidate graph + UGO/text/sheet → globally measured typed ERC and print DRC | No waived rule, zero print errors, no invalid NC/power contacts; require independent reviewer |
| `RENDER` | Signed accepted graph only → true full-page clean/diagnostic SVG and PNG at 300 DPI | Measured sheet size, Type A font and native physical tips verified; glyph gallery does not count |
| `REPORT` | Hash-linked full artifacts → BOM, 15-Net listing, diagnostics, provenance and report | User/source approval and ESKD/QA gates, no fabricated `print_ready=true` |

A later `COMMIT_GATE` is **not one of the seven drawing stages**.
It is a separately authorized P1.2 transaction boundary, blocked until
the independent acceptance of Draft RFC PR #102.

## Executable source-verified handoff (no generator)

The actual Cycle13 user quickstart now emits
`source-generation-handoff.json`, built from its original, freshly
revalidated typed CLI request and real native MCP catalogue result.
`build_readonly_tl494_handoff` (in
`gost_schematic.agent_project.generation_handoff`) recomputes the
immutable source validator and compares the entire CLI report, checks
seven exact part+symbol SHA locks and refuses forged DRAFT approval.
The JSON includes the source request SHA256, canonical sorted physical
Net-member SHA256, 15 literal original names, 13 exact source-selected
UGO references, stage state and required six outputs. All seven
`stages[].verified_complete` remain false; no actual routing, printed
DRC, file writer or authenticated model session is implied.
Future NET/RECON/IC/PAINT/QA adapters must independently prove their
native physical results and corresponding artifact SHA before any
generator-ready status can exist. This preflight envelope itself cannot
approve a user-supplied candidate or a fake final SVG/PNG.

## Machine-readable response

The existing strict stdin CLI already returns `status`, `code` for
rejects, and `reasons` for the correct `BLOCKED_SOURCE_NOT_IMPORTABLE`
source. Cycle14 adds additive diagnostic fields, without changing the
readiness API version or its read-only exit codes:

- `diagnostic` on a `REJECTED` result;
- `diagnostics` on the blocked TL494 result, preserving original `reasons`.

Each diagnostic has `code`, `stage`, `severity`,
`retryable_read_only`, `retry_mode`, `max_retry_attempts`,
`source_model_mutation_allowed`, `net_or_pinref_mutation_allowed`,
`mcp_write_allowed`. Unknown codes **default to NO_RETRY**.

Example of a future-facing *current* blocked diagnostic, not a generator
success:

```json
{
  "code": "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED",
  "stage": "ROUTING",
  "severity": "BLOCKED",
  "retryable_read_only": false,
  "retry_mode": "AWAIT_INDEPENDENT_ACCEPTANCE",
  "max_retry_attempts": 0,
  "source_model_mutation_allowed": false,
  "net_or_pinref_mutation_allowed": false,
  "mcp_write_allowed": false
}
```

## Safe retries — implement strictly, never opportunistically

**Implemented in the strict CLI:** `REQUEST_STALE_REVISION` is the
**only** code advising a bounded read-only fresh snapshot recheck
(`REFETCH_AUTHORIZED_SNAPSHOT`, at most **one**). The trusted host must
reauthorize the canonical UUID, obtain exact revision/generation,
recompute all source/part/PinRef/Net locks, and resubmit a new validated
read request. Reusing stale bytes is not a successful retry. No source
or Net modification is permitted.

**No automatic retry:** missing manufacturer, unresolved 15/15 route,
invalid source UGO, changed BOM nominal, unknown/missing part,
stale catalog SHA, unsafe tool intent, unauthorized project, malformed
JSON, foreign PinRef, crossed Net membership, and failed printed DRC.
The agent must return typed blocker details to MAIN/QA/owner; it cannot
auto-edit source evidence, increase retry budget, or forge approval.

**Future-only optimizer:** at most three independent, bounded candidate
placement/routing attempts from the SAME verified immutable source and
physical Net identities. Each failed candidate is discarded, not
promoted to an edited circuit; every attempt must use authentic owner
routing, no waived clearance, no invented junction or Net merge.
Only a fully accepted 15/15 graph proceeds to render. Present read-only
CLI does not execute any such attempts.

## Deferred transactional write contract

Before any future `AddComponent`, `MoveComponent`,
`ConnectPins`, `RemoveWire`, `UndoTransaction` becomes callable:
trusted host authorization + existing project UUID, exact
`expected_revision` **and** `expected_generation` CAS,
bounded typed delta, immutable source/UGO/manufacturer locks,
full pre/post ERC/DRC, idempotency UUID, one atomic all-or-nothing
commit, crash-safe rollback, and durable idempotency receipt must
pass independently. A stale retry must never become a second edit;
an undo is a separately validated forward transaction. No arbitrary
MCP `create`, `route`, `write` or `commit` command is enabled.

## Verification gates

- Both Python **3.12 and 3.13**, full Ruff/pytest/wheel.
- True **non-editable installed wheel** in separate venv outside checkout,
  native `mcp.ClientSession`, seven real catalogue SVG+PNG pairs,
  all eleven historical refusal tests and matching SHA256.
- New typed negative tests: `REQUEST_STALE_REVISION` permits only
  read-only refresh; all unrecognized, changed-source and malicious
  codes reject automatic retry and all mutation.
- Future independent acceptance: full 23/15/62/16 physical source,
  15/15 authentic connected routing, printed 3/2/1mm, true native
  final sheet, original user photo review if available, and ESKD/QA
  source-signed approval.

A passing software test is **not** an approved full TL494 print. All
MCP tools in this PR remain read-only; `main`, integration and the
original frozen source are not modified.
