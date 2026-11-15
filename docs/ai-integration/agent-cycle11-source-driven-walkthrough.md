# Cycle 11/12 — real TL494 source → typed AI input → native read-only MCP

Issue #74, Epic #107, existing Draft PR #111. This is a **reproducible
engineering source-inspection pipeline**, not an autonomous Codex
reconstruction or accepted new electrical scheme.

## 0. Immutable engineering authorities

- Original frozen commit `e695c415fdced164b0e0c39c5249d030795a0aa6`.
- Independently frozen IC #97 23/15/62/16 source JSON at exact Git blob
  `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`, source netlist
  Git blob `c4cfd515782bf856a7a44fbe2c2ceacd303208d6`.
- IC owner code inspected at SHA
  `585d4e645b01ba48e8f7d0574a447a5b6c33c07f`.
- RECON owner code inspected at SHA
  `32548a704420683e0cb30bf6ab80788c68f84eae`.
- PAINT owner SHA at task acceptance `ef1f817ab47bba7b3776341e7162ae54ad5c826a`;
  independently valid original-source/native PNG output is **not** a
  proof of complete new print-clean all-15-Net connectivity.

These are snapshots for the interoperability check, **not current
unversioned symbolic branch names**. Re-fetch the owner HEAD and
re-review intentionally changed contracts before updating pins.
Do not execute owner branch Python directly in the trusted MCP
process. Static AST extracts only literal `TI_DEVICE_ID`,
`SOURCE_SHA` and `NET_RENAMES`. This prevents an unmerged,
potentially untrusted code checkout from affecting the agent engine.

**Cycle12 integration lock:** the installed, machine-readable
`agent_project/data/tl494_cycle12_owner_locks.json` pins the exact
latest-reviewed owner HEADs for IC #97, RECON #115, NET #114 and PAINT
#93, and six source/API file Git-blob IDs. The native workflow
`ai-tl494-catalog-preflight.yml` fetches exactly the locked owner
commits. The trusted CLI checks **all six** blob IDs before accessing
MCP, then verifies strict source identity and AST owner interface
signatures. This protects against silently mixing a newer owner
contract with old test data. The lock is an auditable **snapshot**,
not a claim the owner branches cannot move or the joint library is
already merged.

## 1. Reproduce real source/owner compatibility

In an authorized disposable local checkout of PR #111, run:

```bash
python -m pip install -e ".[dev,mcp]"
mkdir -p output/cycle11-owner output/cycle11-original-source-proof

git fetch --no-tags --depth=1 origin \
  585d4e645b01ba48e8f7d0574a447a5b6c33c07f \
  32548a704420683e0cb30bf6ab80788c68f84eae

git show 585d4e645b01ba48e8f7d0574a447a5b6c33c07f:tests/fixtures/tl494_photo_23_frozen_cycle9.json > output/cycle11-owner/frozen-IC97-source.json
git show 585d4e645b01ba48e8f7d0574a447a5b6c33c07f:src/gost_schematic/electrical/tl494cn.py > output/cycle11-owner/IC97-tl494cn.py
git show 32548a704420683e0cb30bf6ab80788c68f84eae:examples/tl494_v5/native_circuit.py > output/cycle11-owner/RECON115-native-circuit.py
git show 585d4e645b01ba48e8f7d0574a447a5b6c33c07f:examples/tl494_cycle9_circuit_integration.py > output/cycle11-owner/IC97-typed-integration.py
git show 32548a704420683e0cb30bf6ab80788c68f84eae:examples/tl494_v5/cycle11_ti_bridge.py > output/cycle11-owner/RECON115-typed-ti-bridge.py
git show 32548a704420683e0cb30bf6ab80788c68f84eae:examples/tl494_v5/cycle11_b_continuation.py > output/cycle11-owner/RECON115-typed-b-continuation.py

git hash-object output/cycle11-owner/frozen-IC97-source.json
# Must output a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65
```

Then perform one **actual `mcp.ClientSession` stdio** read-only
catalog check and strict subprocess CLI source review:

```bash
python -m examples.agent_tl494_cycle11_pipeline \
  --owner-fixture output/cycle11-owner/frozen-IC97-source.json \
  --ic-header output/cycle11-owner/IC97-tl494cn.py \
  --recon-header output/cycle11-owner/RECON115-native-circuit.py \
  --ic-integration output/cycle11-owner/IC97-typed-integration.py \
  --recon-ti-bridge output/cycle11-owner/RECON115-typed-ti-bridge.py \
  --recon-b-continuation output/cycle11-owner/RECON115-typed-b-continuation.py \
  --out output/cycle11-original-source-proof \
  > output/cycle11-source-pipeline-report.json
```

The CLI paths above are trusted **local operator inputs to an
offline evidence command**, NOT user-selectable `schematic_*` MCP
parameters. The native MCP server receives only strict
`part_id`+SHA locks for the seven distinct needed installed UGO.
It has no write tool, no extra project allowlist and no access to
operator source paths. The Python source parser verifies original
**23 component refs, 15 named Nets, exactly 62 distinct physical
PinRef memberships, all 16 DA1 physical numbers, source nominals
as exact strings, 13 required UGO variants and real catalogue SHA**.
It compares literal unchanged source Net identities, including
`a_INPUT_PLUS` and `b_NEGATIVE_OUTPUT`, and refuses invented PE.

The RECON display translation is explicitly reversible:
`a_INPUT_PLUS → INPUT_POS`,
`b_NEGATIVE_OUTPUT → OUTPUT_NEG`,
`TRANSFER → ENERGY_TRANSFER`.
These aliases are **not new electrical Net IDs** and the original
sources of b nonphysical continuation markers are not replaced by
invented physical pins. The IC physical Part-ID bridge
`reference.tl494cn → ti.tl494cn.pdip16` remains a
**presentation/owner-boundary contract only**, not an installed P1.1
PartDefinition or permission to silently rebind saved Circuit.

The installed original source is additionally bundled as **exact
Git-blob bytes** at
`src/gost_schematic/agent_project/data/tl494_ic97_frozen_source.json`.
The wheel verifier independently checks this exact blob identity.
`agent_readiness.py` now rejects *same-count* 15-Net requests when
any original Net name, PinRef or member changes, with
`SOURCE_NET_MEMBERSHIP_MISMATCH`. A full verified-source request also carries all 23 exact original
`source_part_id` and literal `nominal_si` values. It rejects changed
resistor values or DA1 part aliases before routing. A full verified-source request
reports `frozen_original_pinref_membership_verified=true`
but remains `BLOCKED_SOURCE_NOT_IMPORTABLE`: no persisted TI
16-pin manufacturer package, no accepted router or authoring writer.
`source_membership_verified=false` explicitly means **not validated
against a persisted complete P1.1 project**.

At the MAIN3 Cycle12 audit (#107) the best independently verified
compact A3 owner route remains **10/15**, with five failed Nets
`GATE_DRIVE`, `CONTROL_REFERENCE`, `FEEDBACK`,
`OSCILLATOR_RT`, `COMMON`. Even if the accepted partial graph's DRC
is zero, **full 15/15 print release is BLOCKED**. This read-only
pipeline itself never invokes the owner router.

## 2. Output artifacts — exact meaning

| Artifact | Evidence | Not proof of |
| --- | --- | --- |
| `source-typed-request.json` | real original 23/15/62 physical design intent for stricter future generator | committed/revised E3 |
| `source-pipeline-report.json` | actual source Git SHA, full nominal/net provenance, complete current owner API blob locks, duplicate/missing Net denial, blocked code | finished printed drawing |
| `{part_id}.svg` + `.png` (7 pairs) | native installed catalogue glyph rendered by the real read-only MCP; SHA locked | correct complete sheet or approved ГОСТ |
| `output/cycle11-source-pipeline-report.json` | top-level CI-collected machine-readable report | autonomous Codex LLM tool run |

**Required actual result now:** `status=BLOCKED_15NET_NOT_ROUTED`,
`real_source_23_15_62_verified=true`,
`typed_readiness.status=BLOCKED_SOURCE_NOT_IMPORTABLE`,
`missing_net_reject_code=SOURCE_NET_INVENTORY_INCOMPLETE`,
`route_completed_nets=0`, `new_print_svg_generated=false`,
`new_print_png300dpi_generated=false`, `print_ready=false`.
This does **not** mean the owner router is 0/15: this isolated
read-only pipeline calls **no routing tool at all**. The separate
owner's independently evaluated route remains partial and BLOCKED.

## 3. Actual Codex CLI binary smoke, not model-generated source

A separate CI runner may install the **real published Codex CLI**
and run `codex --version`, `codex mcp add`,
`codex mcp list`, and `codex exec --help`, with
`CODEX_HOME` isolated to a disposable CI workspace. This checks
Codex executable/MCP **configuration integration only**.

A genuine autonomous `codex exec` running a model through
`schematic_catalog_*` and then correctly authoring 23/15/62/15
routed Nets requires **authorized model credentials and a completed
trusted write/route integration**, neither available in default
GitHub Actions. If the CLI is unavailable, report
`CODEX_BINARY_INSTALL_BLOCKED`; if installed without model auth,
report `CODEX_MODEL_CALL_BLOCKED_NO_AUTH`. Never call the
`mcp list` output a full model/tool interaction or a real routed
schematic.

The genuine, authentication-independent **native MCP tool call**
is performed by the source pipeline separately. In no case may
the agent enable arbitrary `ConnectPins`, `CommitTransaction`,
change P1.1 HEAD, apply arbitrary SVG patches, or create a fake
electrical Net from a generated image.

## 4. Future fully automated design loop (BLOCKED gates)

1. Read frozen *real* BOM/Net/nominals in a strict trusted
   manifest; reject source SHA or 62 PinRef disagreement before
   prompting the AI.
2. Present exact installed alternative UGO with part+symbol SHA
   locks and 16 physical manufacturer TL494 pins; wait for IC
   owner reversible adapter and normative catalogue review.
3. Emit a typed **proposal** for 23 physical component placements,
   keeping original references and exact 15 distinct Net UUIDs.
   Never route from source pixels. Current P1.1 supports immutable
   six-part saved examples; full native 23-part persisted import is
   **BLOCKED** pending joint owner review.
4. Trusted separate generator (future only) would call NET #114
   complete multi-Net engine and RECON #115 actual A3 geometry
   candidate, iterate at most 3 independently validated revisions.
   No full 15/15 route is currently accepted. DA1.12 INPUT_POS lead
   collision and b continuation must not be waived.
5. Perform independent full printed-ink/titles/fonts/junction DRC
   including applicable 3mm conductor edge / 2mm UGO body /
   1mm glyph spacing and A3 dimensions, before any print PASS.
   Preserve original 91-wire 9 errors + 32 warnings as NEGATIVE.
6. After actual 15/15 + physical/ink DRC PASS, render real new
   `SVG clean + diagnostic`, `PNG300DPI`, BOM, physical Netlist,
   numeric DRC report and SHA for source/input/output. Ask QA #99,
   PAINT #93 and ESKD #112 to accept exact participating owner
   SHA. Do not claim photo-pixel parity without source bitmap.
7. Only a separately reviewed P1.2 write implementation could
   accept CAS `expected_revision`+generation, idempotency and
   atomic rollback. No such MCP write tool is currently available.

**No merge**, no changes to frozen source, main or integration.
