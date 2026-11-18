# RFC #74 Annex C — first P1 implementation gate: read-only persisted E3

**DESIGN ONLY — not implemented.** This is the *next separate*
implementation PR after architectural acceptance of Draft PR #81.
It excludes arbitrary creation/editing and all MoveComponent,
ConnectPins, DisconnectPins and autorouting tools.

## P1.1 objective and non-goals

Goal: take an **existing real six-part E3 Circuit and ExternalWireGraph**,
import it through a controlled ProjectService into a typed, content-addressed
SchematicProject, durably save it, cold-open it in a fresh process, project it
back into the existing real Circuit/ExternalWireGraph types, independently
validate it and render authentic SVG/PNG with matching revision metadata.

Non-goals: no user-selected Python module execution; no raw JSON patch,
generic document editing, no connected-part movement, no E1 project
creation, no Issue #82 algorithmic conversion, no branch autorouter,
no DRAFT->APPROVED promotion, no "write" MCP tool accepting arbitrary paths.

**One fixed importer** is acceptable to *bootstrap* this test, but once
stored, the new process **must not import any fixture code**. This
distinguishes genuine persistence from rebuilding a six-part scene.

## Domain and provenance checklist

The importer must obtain:

- Circuit: six authentic ComponentInstance objects, their exact
  reference designators, catalog part IDs, origins, transforms, typed
  nominals and five Net records containing physical PinRefs.
- ExternalWireGraph: **16 authored WireSegment objects** with
  unmodified coordinates, ordering, declared net names, and **3**
  explicit junction points. No inferred junction at a drawing cross.
- Catalog: real PartDefinition and SymbolDefinition for each part;
  C3 specifically uses capacitor.electrolytic revision 1, DRAFT,
  C3.1=PLUS at (91000,80000) µm and C3.2=MINUS at
  (109000,80000) µm. Preserve the catalog SHA/edition.
- Wire ink: currently the fixed renderer_wires() adapter explicitly
  wraps each segment in WireObstacle(stroke_um=300). Record that
  **source-proven 300 µm** style in the project, not an assumption
  extracted from an SVG.
- Presentation: the existing six-part example adds explicit junction
  dots, sans-serif refdes and a fixed label-offset formula. Capture
  equivalent typed presentation data and its derivation recipe and
  font-warning into the project; a cold renderer must not import
  the Python example merely to reconstruct this overlay.
- Diagnostic scenario: the fixture has an optional typed
  PotentialScenario for a nominal static operating point.
  Preserve an explicitly versioned scenario record if equivalent
  polarity/ERC evaluation is required; a missing scenario is
  NOT silently interpreted as electrically verified operation.
- Traceable import provenance: fixed source identifier, code revision,
  catalog digest, conversion recipe version, hash of source model
  fields, and warnings. Record old P0 specimen project_revision
  separately from new v1 revision_sha256.

Do not re-use the archival 18-segment fixture. Do not substitute
capacitor.polarized for the special capacitor.electrolytic symbol.
Never reconstruct physical contacts from drawn pixel endpoints.

## Proposed code boundaries (implementation PR only)

~~~text
gost_schematic/agent_project/
    contracts/             # typed v1 ProjectEnvelope + E3 payload records
    repository.py           # ProjectRepository protocol, immutable reads + CAS
    local_store.py          # safe scoped paths, blobs, journal, HEAD
    service.py              # ProjectService, security and validation
    importers/six_part.py   # one allowlisted authored Circuit/Graph adapter
    projectors/e3.py        # strict project <-> real Circuit/ExternalWireGraph
    views/e3.py             # render restored immutable model via SVG/PNG
    diagnostics.py          # independent revision-bound report envelopes
~~~

These paths are a **suggested package layout**, not existing modules
or a new public API. The implementation may consolidate modules
after review, but must retain the separation of responsibilities.
The first MCP additions are read-only: list/open/get_snapshot/validate
and project-revision-bound render/inspect. Import and initial save are
trusted service/CLI bootstrap operations, not arbitrary MCP writes.

## Reproducible eight-step acceptance flow

| Step | Test command/observation | Success evidence |
| --- | --- | --- |
| 1. Capture source | trusted test importer reads authored_specimen(), definitions(), renderer_wires() | concrete Circuit/ExternalWireGraph types, 6/5/16/3 counts |
| 2. Convert | ProjectService import_fixed_source with exact catalog/style manifests | typed E3 snapshot, unique stable IDs, no electrical simplification |
| 3. Persist | ProjectRepository commits canonical .gseproj blob and HEAD gen=1 | immutable revision SHA, valid size/hash, no path escape |
| 4. Cold reopen | launch **new Python process** and ProjectService.open_project(project_id) from allowed root | exact revision loaded without Python example module |
| 5. Electrical roundtrip | strict E3 projector rehydrates real Circuit/ExternalWireGraph | all component/PinRef/net memberships, 16 wires and 3 junctions match exactly |
| 6. Render | SVG renderer with imported presentation style and PNG resvg backend | real SVG/PNG, original symbol geometry, exact viewBox/mm, nonblank bytes |
| 7. Validate | independent electrical/geometry/ERC validators on restored model | report contains same revision SHA; no new shorts/dangling wires |
| 8. Repeat | close/reopen/render again under same pinned toolchain | exact canonical bytes and SVG SHA stable; PNG SHA stable under same pinned rasterizer/fonts |

Verification must be independently performed through source-model
comparators, not by checking only that filenames exist or counting
pixels. Canonical JSON hash and serialized byte roundtrip are exact
even across Python 3.12/3.13. PNG byte equality is required within
a pinned renderer/backend/font environment; across platforms a
deterministic SVG + image dimensions and independent view check
is the stronger portable criterion.

### Cold-process isolation

A regression shall remove the source fixture from the **new process**
import path (or run from an installed wheel without an examples/
directory), leaving only the .gseproj, catalog data and the application
renderer. If ProjectService.open_project invokes
examples.review_end_to_end_circuit or load_specimen(), the test FAILS.
The source fixture remains unchanged in the authoring checkout.

### Cross-checks for sample

Expected source snapshot signature (not a v1 SHA until implemented):

| Property | Expected |
| --- | --- |
| Component count | 6 |
| Components | R1, R2, C1, C2, C3, L1 |
| Semantic nets | 5: LEFT, TOP, BOTTOM, TAP, RIGHT |
| External wire segments | 16 |
| Explicit junction points | 3 |
| C3 origin | (100000, 80000) µm |
| C3 catalog definition | capacitor.electrolytic, revision 1 DRAFT |
| C3 pin 1 | PLUS / positive; (91000,80000) µm; TOP |
| C3 pin 2 | MINUS / negative; (109000,80000) µm; RIGHT |
| Source-defined wire stroke | 300 µm |
| P0 old six-part revision | 03c624ec68760a31b5b7f48d1cfcfffe1fb3e293fb616f2b03127cdd2ed1ddf9 |

Additional trusted values (source wire coordinates, catalog SHA) must be
recovered from source itself at test time, **not typed as arbitrary
hardcoded copy fixtures**.

## Negative and resilience scenarios

| Scenario | Expected outcome |
| --- | --- |
| Alter one byte of persisted revision blob | STORAGE_CORRUPT, no render |
| Unknown project UUID or malformed ID | PROJECT_NOT_FOUND / schema error, no path lookup |
| Parent directory "..", UNC, drive letter, symlink/reparse escape | WORKSPACE_DENIED, no external read/write |
| Catalog manifest / symbol revision differs | CATALOG_REVISION_MISMATCH, no silent repair |
| E3 physical pin number unknown | PHYSICAL_PIN_INVALID, fail-closed |
| E3 branch crossing with no explicit junction | remain unconnected, validator respects authored semantics |
| 1 µm physical gap | corresponding disconnected/dangling diagnostic, no auto snap |
| Missing junction at T | model diagnostic, never infer a new junction |
| Import same fixed source into existing project_id | conflict; do not overwrite |
| Crash after staging blob before HEAD | old head or no head remains; recover idempotently |
| Read old immutable revision after a new HEAD | exact original bytes and report |
| Missing font / label-checker unavailable | explicit warning / NOT_IMPLEMENTED, never fabricated PASS |
| Try opening E1 or ALGORITHM via E3 projector | SCHEMA_UNSUPPORTED (until dedicated kind adapters accepted) |
| 18-segment archived C3 variant | never overwritten or silently substituted |

## Runtime/CI acceptance

The independent implementation PR needs tests on Python 3.12 and
3.13, Ruff, wheel payload inspection with new project service package,
dynamic audit of **21 DRAFT electric symbols**, real SVG/PNG files,
and a cold process that does not import the example. Tests for SHA and
failed crash recovery are required. On Windows, preserved LF bytes in
archival frozen fixtures must not be normalized by Git checkout:
avoid false hash mismatches, but never rewrite the frozen expected SHA.
Linux CI success does not justify skipping Windows persistence tests.

Test artifacts (to be generated by implementation, not claimed by RFC):
initial source model fingerprint, v1 saved .gseproj,
reopened typed model summary, source/reopened SVG+PNG and their SHA,
revision-bound diagnostics JSON, and CLI/MCP read-only transcript.

## After P1.1: strictly separate implementation gates

**P1.2 isolated typed changes:** add/nominal/transform of unconnected
components. Any connected MoveComponent without safe route repair
returns ROUTE_REPAIR_REQUIRED and must preserve HEAD and old image.

**P1.3 topology-changing commands:** ConnectPins/DisconnectPins require
exact physical contacts, explicit named net, branch ownership, no
implicit net merge/split or unsupported junction. Include rollback
on any failed diagnostic.

**P1.4 C3 connected move:** only after ELEKTRIK/QA acceptance of
branch-aware multi-member TOP/RIGHT routing. Move C3 by +5000 µm y,
repair both declared branches in **one** transaction and verify net
members and explicit junctions unchanged. If there is no safe route
the service returns BLOCKED with mutated=false, old revision SHA intact.
The current two-pin safe router cannot complete this scenario.

**P1.5 Codex write MCP:** expose capability-scoped typed commands
with expected_revision/generation, idempotency, real before/after
ImageContent, independent diagnostics and cold saved-project reopening.
Never allow Python/shell execution, JSON patch or PNG pixel editing.
All write tools are disabled until their respective prior gates pass.

No PR merging is delegated to this RFC or prototype plan.