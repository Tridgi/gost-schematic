# Issue #107 / #74 — source-bound catalog choice and *partial* print preflight

**Status:** read-only implementation / DRAFT independent review required.
**Parent:** integrated P1.1 ProjectService and five original saved-project MCP tools.
**Separate** PR #103 is the model-based physical endpoint editor; PR #102
is a **DOCS-ONLY** future CAS/write RFC. Neither creates/saves a TL494 E3.
**No main changes, no merge, no arbitrary SVG patch, no new connectivity.**

## Why this interface exists

A large language model cannot safely guess a circuit by selecting the first
"capacitor" or "coil" it sees. It needs exact, **catalog-sourced candidate
cards** with physical PinRef numbers, catalog SHA, dimensions, body keepout,
real print-stroke dimensions, GOST document refs and actual preview images.
A photoreconstruction also needs a **pinned BOM-to-UGO profile** independent
of general language synonyms. Geometric transform support does NOT mean
that all rotations/mirrors or absolute dimensions have received ESKD
normative approval. All 36 variants are **DRAFT** at the reviewed base.

### Read-only MCP functions implemented in this isolated branch

| Tool | Actual engineering result | Trust boundary |
| --- | --- | --- |
| \`schematic_catalog_search(semantic_query)\` | Exact installed candidates (e.g. generic \`конденсатор\` => fixed, polarized, electrolytic, no implicit choice); part/symbol catalog SHA, 8 D4 *engine* poses, pin numbers/anchor µm/role/polarity, keepout and stroked dimensions, real standard_ref, draft status | No filesystem path, no catalog mutation |
| \`schematic_catalog_preview(part_id)\` | **ImageContent PNG + TextContent full SVG + metadata** rendered with \`render_symbol_svg\` from actual installed symbol, cryptographic image SHA and exact physical pin map | Not an invented SVG or manually painted image; clean sample, not completed sheet |
| \`schematic_tl494_selection_profile()\` | Exact source-specific 12-ref matrix, explicit 36-DRAFT status and **missing real TL494CN IC adapter** gate | Editorial requirement, not full vendor pinout |
| \`schematic_tl494_pin_alias(full_name)\` | Only dictionary-confirmed \`FEEDBACK→FB\` and \`OUTPUT CTRL→OC\` display labels. Returns true full original name + declared physical numbers 3 and 13. Unknown full name => \`ALIAS_UNVERIFIED\` | Editor text only; never changes a physical \`PinRef\` |
| \`schematic_preflight_project(project_id,revision,profile)\` | Reopens **actual stored E3** through ProjectService, verifies SHA/catalog lock, enumerates original physical \`Circuit.Net\` and PinRefs, components, symbol transforms/keepouts, group bboxes, authored wire route and independent **subset** of print DRC | Same P1.1 explicit host-enabled workspace and UUID allowlist. Never exports/writes file or connects nets |

The first four access only installed package/catalog and the frozen editorial
dictionary, no personal project data. The last tool uses the original
default-denied, host-scoped \`ReadOnlyProjectAccess\`: 
\`GSE_P11_READONLY_ENABLED=1\`, absolute pre-existing trusted
\`GSE_P11_WORKSPACE\`, exact \`GSE_P11_ALLOWED_PROJECT_IDS\` canonical
UUID allowlist. No caller-supplied paths, project traversal or write tool.

**Exact response meanings:**

- \`symbol_status=draft\`: actual catalog declaration; NOT an ESKD approval.
- \`allowed_by_geometry_engine\`: 0/90/180/270 × mirror_X for the existing
  \`Transform\` primitive. Each is \`normative_transform_approval=NOT_VERIFIED_PER_POSE\`
  until ESKD/PAINT comparative review. This prevents declaring a flipped
  Schottky barb acceptable merely because the canvas renders it.
- \`symbol_sha256\`, \`part_sha256\` are computed from the actually installed
  source definitions, not human-authored text or estimated dimensions.
- \`body_keepout_um\` and \`stroked_graphic_bounds_um\` are integer µm.
  The graphics and physical pins remain separate objects.
- \`preview_tool\` directs the client to retrieve a **real SVG/PNG** if a
  visual example is needed. Preview cannot certify pin-net connectivity.
- \`selection_required=true\` even on a single exact match. The agent
  must select explicit \`part_id\`, not a generic fallback.

## Exact TL494 user/reference matrix

| Reference | Required installed part_id | Why it cannot fall back |
| --- | --- | --- |
| C1, C2, C3, C5, C6 | \`capacitor.polarized\` | Thin plates and actual + electrode; not thick \`capacitor.electrolytic\` |
| C4, C7 | \`capacitor.fixed\` | Nonpolarized symbol |
| L1, L2 | \`inductor.ferromagnetic\` | Actual ferromagnetic core, not air-core or generically ferrite |
| VT1 | \`transistor.mosfet_n_enh\` | G/D/S physical pin numbers, source-review arrow and internal dot pending ESKD |
| VD1 | \`diode.schottky\` | True A/K and Schottky cathode; preserve 90° orientation and original source, validate D4 separately |
| FU1 | \`fuse.general\` | Fuse, not resistor/block |
  
R5 is a variable resistor in the source, but **not added as a default**
to the 12-item user matrix. All other original parts (X1/X2, DA1,
R1–R8) require independently verified exact source-specific selection.

The full TL494CN is **NOT** installed as an approved \`PartDefinition\`
for P1.1 persistence. The standalone reference
\`reference/tl494-native-rework-20261114\` builds a physical 23-part,
15-Net, 91-wire DRAFT through additional experimental code and is
**NOT** a persisted v1 project proven by this read-only MCP. Do not
claim its two photos and true 16-pin vendor passport have been adopted
by integration. No silent \`DD1.1\`/DD1.2 split into separate physical
components.

### TL494 display-alias dictionary

Only these two exact editorial keys are allowed by this stage:

| Full trusted label | Display alias | Physical number | Provenance |
| --- | --- | --- | --- |
| FEEDBACK | FB | 3 | Issue #107 editorial rule, pending full manufacturer library lock |
| OUTPUT CTRL | OC | 13 | Issue #107 editorial rule, pending full manufacturer library lock |

Display aliases do **not** change actual physical pin numbers, full
manufacturer labels or \`Circuit.Net\` membership. Unknown strings
return \`ALIAS_UNVERIFIED\`; no opportunistic truncation to six chars.
A future locked 16-pin TL494 adapter must prove all 16 names/numbers
against a fixed manufacturer data sheet and check per-device alias
uniqueness and typography. UI font rotation PWM 90° is a separate
view transform and must not alter the physical Circuit.

## Print preflight: correct scope of evidence

\`schematic_preflight_project\` is run **before** calling
\`schematic_render_project\` so the agent can reject source-wrong
symbol selection or deficient routes without relying on a prettier
image. Its \`print_ready=false\` and
\`print_drc=PARTIAL_ONLY_NOT_CERTIFIED\` are unconditional until
independent PAINT/ESKD/QA release gates exist.

**Actually executable checks in this branch:**

1. Original immutable revision SHA and catalog lock through ProjectService,
   exact \`Circuit\` physical component part IDs, real physical pin positions
   and each \`Net\` ID/members — no raster reverse engineering.
   The service also includes the full original `electrical_erc` (independent
   `validate_circuit` and `validate_external_wires`) at that exact revision.
   A clean ERC never implies that all print-layout checks have passed.
2. Source-pinned TL494 12-reference matrix compared with the **actual**
   saved component \`part_id\`, reporting
   \`TL494_REQUIRED_COMPONENT_MISSING\` or
   \`TL494_UGO_VARIANT_MISMATCH\`; no silent symbol replacement.
3. \`check_verified_dimensions\` from the existing dimensional subset
   with exact diagnostic codes; it does NOT approve untested UGO shapes.
4. \`validate_sheet_wire_rules\`, already integrated and source-backed,
   for wire line widths 0.2–1.0mm, **edge-to-edge** parallel H/V
   overlapping conductor clearance >=3mm and duplicate centerlines,
   warnings for diagonal exceptions. The wrapper supplies real stable
   wire segment UUIDs, Net name, actual stroke µm, independent exact
   clearance measurement and known physical \`PinRef\` endpoints.
   Example: two 0.3mm lines 0.5mm apart have a **0.2mm printed edge gap**,
   violating the 3mm rule. Return \`ESKD_PARALLEL_WIRE_CLEARANCE\`,
   both actual wire IDs, actual Net owners and source-attached R5/R6
   pins only **if the stored physical endpoints match those PinRefs**.
5. Conservative **body keepout AABB** neighbor review for <2mm;
   advisory only — full ink-to-ink clearance for every symbol, pin
   number and label has not been implemented. No false exact 2mm PASS.
6. Measured used-content bbox, count of authored segments and exact
   explicit junction count. This does not prove A3 sheet fits because
   an exact chosen paper \`sheet_format\` and frame/title-block contract
   are not yet stored in the P1.1 schema.
7. Optional explicit TL494 functional group report: X1/L1 input,
   R1–R7/C3/C4/C7 feedback, DA1, R8/VT1/VD1 driver, output
   C1/C2/L2/C5/C6/FU1/X2. Presence and bbox are measured, but
   order/spacing relative to the source picture are still
   \`MANUAL_SOURCE_PHOTO_REQUIRED\`, NOT automatically passed.

**Not implemented and never silently passed:** true all-stroke
wire-to-symbol and wire-to-text ink DRC; pixel-verified print font;
all crossing and junction visibility; complete A3/A4 frame/title
block and scale; global placement optimization or multi-Net route
planner; 1:1 photo matching; verified 16-pin TL494 package/pinout;
physical earth/common vs PE. Existing \`validate_external_wires\`
checks connectivity but cannot be substituted for print clearance.

A 16-conductor six-part saved E3 is used for reproducible
\`ProjectService\`/MCP acceptance. Asking it to conform to TL494 profile
must **FAIL** with explicit wrong/missing UGO reasons. It must never be
advertised as a source-faithful TL494 diagram.

## Future safe P1.2 transactions are still BLOCKED

Desired loop: catalog search → choose exact catalog ID, pin SHA,
symbol status → frozen source BOM/Net → prospective type/geometry
routing plan → non-mutating preflight → manually reviewed source
picture and source-backed standards QA → eventually
\`ValidateTransaction\` → **only approved** \`CommitTransaction\`.

A later write requires exact \`expected_revision\` +
\`expected_generation\` CAS, durable idempotency, physical contact
and Net-inventory delta, independent electrical/visual ERC, no
hidden shorts or arbitrary unlabeled T/X inference, atomic file
publication and crash rollback. None of these existing-HEAD write
commands is registered through MCP here. No SVG arbitrary
patches and no "move until it looks nice" loop without Net safety.

## Reproduction and proof

~~~powershell
python -m pip install -e ".[dev,mcp]"
python -m pytest -q tests/agent_project/test_tl494_catalog_preflight.py tests/agent_project/test_tl494_catalog_preflight_stdio.py
python -m examples.agent_tl494_catalog_preflight_mcp --workspace output/tl494-catalog-readonly
~~~

The executable script uses trusted **Python API** to create the
fixed six-part engineering specimen (NOT TL494) and **real stdio
MCP ClientSession** for all search/preview/alias/preflight/render
tool calls. It archives actual catalog SVG/PNG images, the native
saved-project C3 diagnostic image and exact SHA/diagnostics as
client-side evidence. No fresh autonomous Codex CLI model run
is claimed. The catalog tool never writes files.

Independent GitHub CI tests Python 3.12/3.13, Ruff, wheel and
full background repository tests; hold Draft PR until MAIN 2,
ESKD, YGO/PAINT and independent QA have reviewed the changes.
