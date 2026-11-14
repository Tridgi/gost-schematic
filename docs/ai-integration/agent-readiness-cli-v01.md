# Agent v0.1 — honest read-only planning and future trusted generator gate

**Status:** runnable contract validator, **NOT** a full TL494
generator; no create/move/connect/undo through MCP, no new P1.2 commit,
no automatic source photo wiring, zero write permissions granted.
New source instructions: repository root [AGENTS.md](../../AGENTS.md)
and [Skill](../../skills/gost-schematic/SKILL.md).
Issues #74 / #107; existing Draft PR #111 only.

## What is independently executable

```bash
python -m pip install -e ".[dev,mcp]"
python -m examples.agent_readiness_readonly --workspace output/agent-readiness
python -m pytest -q tests/agent_project/test_agent_readiness_cli.py
python -m gost_schematic.agent_project.agent_readiness < saved-review-request.json
```

The example performs a **TRUSTED Python import of the existing six-part**
P1.1 specimen, then invokes the **separate subprocess CLI over strict
JSON stdin**. It writes a request and proof file ONLY on the trusted
**client** side in `output/agent-readiness/readiness-client-evidence/`.
The CLI itself reads stdin, writes one JSON response to stdout, never
accepts an output path or shell/python snippet, never emits an updated
E3 file and never changes source/HEAD. Stale or unauthorized projects
are denied. A source-locked 23-part TL494 is **NOT produced**.

The saved review consumes the exact saved Circuit and all true physical
Net memberships. For the actual saved specimen, it returns
`status=READ_ONLY_MODEL_MATCH` and always
`ready_to_generate=false`. A missing Net, wrong physical number, extra
Net, conflicting owner, stale project generation or stale physical
UGO SHA is an explicit **failure**, not an approximate validation.

The same CLI accepts a tagged `intent=tl494_reconstruction` envelope
for future trusted use but always returns
`BLOCKED_SOURCE_NOT_IMPORTABLE` (exit 2) even if a submitted test-shaped
manifest has 23 refs, 15 Nets and 62 PinRefs. Without direct comparison
to the authentic frozen source tuples, **matching counts alone proves
nothing**. Do not regard a synthetic 23/15/62 fixture as the user's
actual schematic.

## Exact strict schema — v1 JSON

All fields required; no aliases, extra keys, duplicate JSON keys,
NaN/Infinity, floats where integer types are required, or unknown
`intent`:

```json
{
  "schema_version": 1,
  "intent": "saved_e3_review",
  "source_sha": "saved-p11-e3",
  "project_id": "canonical-lowercase-uuid",
  "expected_revision": "64-lowercase-hex-project-SHA256",
  "expected_generation": 1,
  "components": [
    {
      "reference": "C3",
      "part_id": "capacitor.polarized",
      "part_sha256": "64-lowercase-hex-real-installed-part-SHA256",
      "symbol_sha256": "64-lowercase-hex-real-installed-symbol-SHA256"
    }
  ],
  "nets": [
    {
      "name": "TOP",
      "members": [{"reference": "C3", "number": "1"}]
    }
  ],
  "outputs": [
    "bom", "netlist", "drc",
    "svg_clean", "svg_diagnostic", "png_300dpi"
  ],
  "max_route_attempts": 0
}
```

**The JSON above is a SHAPE EXAMPLE, NOT an executable complete P1.1
request.** Do not copy placeholder UUID/SHA or omit other true components
or Net memberships. Create a real model-based request through trusted
`build_saved_review_request(snapshot,catalog)`; review it before use.
All input is capped at 128KiB, components 128, Nets 128, total physical
PinRefs 512, outputs fixed six choices, max route attempts 0..3.
The CLI currently performs **ZERO actual routing iterations**.

For `tl494_reconstruction`, use `source_sha` equal to the frozen
Git commit `e695c415fdced164b0e0c39c5249d030795a0aa6`,
and set `project_id`, `expected_revision` and
`expected_generation` to null: frozen source is **not** a persisted
P1.1 revision. The typed set requires all 23 original refdes,
13 known exact part/symbol locks and 10 explicitly unresolved parts.
The full **15 original named Net / 62 physical PinRef** declarations
are now independently compared with the verified IC #97 immutable
Git blob `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`,
embedded verbatim in the package and wheel. Matching counts alone
are **not** enough: `SOURCE_NET_MEMBERSHIP_MISMATCH` is raised on
any renamed source Net or changed physical ownership. `a_INPUT_PLUS`
and `b_NEGATIVE_OUTPUT` are literal original names, not malformed
lowercase inputs or aliases to silently merge.

The `tl494_reconstruction` intent additionally requires each
`components[]` row to carry **`source_part_id`** and **`nominal_si`**
beside its reviewed `part_id`, `part_sha256` and `symbol_sha256`.
Original `reference.tl494cn` is retained as the source physical part ID,
even though the separate manufacturer owner calls it
`ti.tl494cn.pdip16`. No automatic source ID substitution.
`nominal_si` is an exact original string (or null where no
source value exists), never rounded or formatted from UGO ink.
`SOURCE_PART_ID_MISMATCH` and `SOURCE_NOMINAL_MISMATCH` reject
same-count, wrong-BOM requests. Only the 13 approved-for-source-**choice**
UGO IDs are currently installed; the remaining 10 exact original
source part IDs are independently verified but deliberately unresolved
in the target P1.1 catalogue.

Example TL494-only component record:

```json
{
  "reference": "R5",
  "source_part_id": "resistor.variable",
  "nominal_si": "1000",
  "part_id": "resistor.variable",
  "part_sha256": "REPLACE_WITH_ACTUAL_INSTALLED_SHA",
  "symbol_sha256": "REPLACE_WITH_ACTUAL_INSTALLED_SHA"
}
```

This record illustrates a shape, NOT valid SHA input. The complete
machine-generated true original typed request is provided by
`examples.agent_tl494_cycle11_pipeline` and preserved as
`source-typed-request.json`; it contains all 23 sources, 15 Net
identities, 62 members and original nominal strings.
If the request passes source verification, it STILL returns
`BLOCKED_SOURCE_NOT_IMPORTABLE` because the complete persistent
TI device, 15/15 router, printed DRC and transactional writer have
not been accepted. Fields
`frozen_original_pinref_membership_verified=true`,
`frozen_original_bom_part_ids_verified=true` and
`frozen_original_nominals_verified=true` refer to the immutable
**external source**, whereas `source_membership_verified=false`
denotes **not imported into a complete persisted P1.1 project**.

### Failure codes and process exit contract

| Exit/status | Cause |
| --- | --- |
| 0 / `READ_ONLY_MODEL_MATCH` | Exact stored, host-authorized physical model and full Net membership matched; **not print approval** |
| 2 / `BLOCKED_SOURCE_NOT_IMPORTABLE` | Source-profile shape accepted; independent physical TL494/source/renderer/router trust gate missing |
| 3 / `REJECTED` | Invalid schema, unsupported version, source mismatch, missing/foreign Net, repeated physical PinRef, stale catalog SHA or unauthorized project |

Examples of machine-readable `REJECTED.code`:
`REQUEST_SCHEMA_INVALID`, `REQUEST_SIZE_INVALID`,
`REQUEST_DUPLICATE_KEY`, `REQUEST_OUTPUT_INVALID`,
`REQUEST_INTENT_UNSUPPORTED`, `REQUEST_STALE_REVISION`,
`REQUEST_NET_MEMBERSHIP_MISMATCH`,
`SOURCE_NET_INVENTORY_INCOMPLETE`,
`SOURCE_PIN_INVENTORY_INCOMPLETE`,
`SOURCE_NET_MEMBERSHIP_MISMATCH`, `SOURCE_PART_ID_MISMATCH`,
`SOURCE_NOMINAL_MISMATCH`, `SOURCE_UGO_VARIANT_MISMATCH`,
`CATALOG_REVISION_MISMATCH`, `REQUEST_PINREF_REUSED`,
`PROJECT_ACCESS_DENIED`.
The response never emits a traceback or host secret path.

## Real native MCP vs trusted Python vs future generator

| Stage | Working today? | Engineering authority |
| --- | --- | --- |
| Catalog semantic query / exact dual-SHA selection | YES: read-only MCP | Installed immutable catalog, 36 DRAFT |
| Source-locked real UGO preview | YES: MCP SVG+PNG | Native renderer image only |
| Saved P1.1 ProjectService model / original ERC | YES: allowlisted read-only MCP | Real full persisted `Circuit`/PinRef/Net; six-part test verified |
| Typed request parser / source-vs-saved Net comparator | YES: separate read-only CLI | Exact saved model/generation, fail closed |
| Trusted initial six-part creation | YES: explicit in-process Python only | Local controlled bootstrap, **not MCP write** |
| TI TL494 23/15/16/62 complete persisted adapter | BLOCKED | Depends on independent IC #97 and reference #115 |
| Global deterministic 15/15 multi-terminal routed graph | BLOCKED | NET #114 partial 8/15; DA1.12 ink collision |
| Zero-error complete A3 print DRC and source-faithful output | BLOCKED | PAINT/ESKD/QA; 3/2/1mm specific contexts |
| Typed authenticated create/move/connect/CAS/rollback | BLOCKED | Design-only RFC #102; NO registered MCP write |

## Trusted future generator design — separate security review

A future `gse-build-e3` **is a PROPOSED command name, NOT CURRENTLY
INSTALLED OR EXECUTABLE**. It must be deployed only as a separately
authorized local operator process, not through read-only MCP, with:

1. Fixed input from immutable source Git commit, exact photo provenance,
   verified TI SLVS074J physical 16-pin adapter and the literal 62
   `PinRef → NetIdentity` memberships. Reject any incomplete source
   manifest, missing Net owner, NC/power conflict, same-name distinct
   Net merge, unknown reference, unapproved silent glyph swap or
   wrong symbol SHA. Never auto-correct graph membership from SVG.
2. A strict versioned tagged structured JSON input (`schema_version=1`,
   one canonical `project_id`, explicit source/source-profile digest,
   bounded command array, exact catalog locks, no shell/SQL/Python,
   arbitrary path, free-form SVG, remote data download or dynamic import).
3. A host-admin-scoped workspace with no symlink/junction escapes;
   separate output and trusted source directories. Source immutable.
   Validate all input *before* touching project files or renderer.
4. Deterministic placement + multi-terminal global 15-Net routing with
   bounded 0..3 retries. Preserve 23/15/16 physical inventories and
   exactly source-locked membership; report any route member loss or
   DRC failure; never call a partial 8/15 route a passing circuit.
5. Complete native printed DRC before artifact publication: actual
   geometry, glyph, connected T and foreign X, full ink/text,
   3mm overlapping parallel conductor printed edge gap,
   appropriate 2mm UGO and 1mm graphics distance, A3 frame/labels.
   Refuse `print_ready` until independent normative signoff.
6. Only a separately reviewed write subsystem can use current-HEAD
   `expected_revision`, `expected_generation` CAS, durable
   idempotency, isolated candidate staging, fsync/atomic publication,
   crash replay + rollback. A read-only CLI schema validation must
   never be repurposed to write to a project directly.
7. On success (future only), emit real clean + debug SVG, native
   PNG300DPI, BOM, physical Netlist, complete machine-readable DRC,
   source vs print-clean differences, project+catalog+SVG/PNG SHA
   and independent QA report. No hand-made "source-perfect" image.

Original source is a **known-bad print baseline**: preserve its 9
errors/32 warnings separately. The new compact candidate with 8/15
routed Nets and DA1.12 INPUT_POS symbol-ink overlap must remain
BLOCKED until real 15/15 and ink DRC=0.

## Independent test policy

Tests include positive six-part source-equal read-only review,
intentional synthetic full-count TL494 BLOCKED, missing Net,
missing PinRef, altered source commit, bad physical UGO,
reused PinRef across Net, stale generation, wrong catalog SHA,
foreign project UUID, JSON duplicate keys, NaN/oversize payloads,
prompt injections requesting commits or shell commands and real
subprocess CLI stdout/exit semantics. Both Python 3.12/3.13 are
mandatory; do not silence negative checks to obtain a green badge.

Do **not** claim an autonomous Codex-driven original-photo reconstruction,
a real accepted 23-part saved project, or a ГОСТ-approved schema from
this planning CLI, current read-only MCP, partial DRC or a green
GitHub Actions run.
