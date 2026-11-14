# Cycle 11 — RECON #115 real manufacturer + historical b continuation integration

**Status:** DRAFT / PRINT BLOCKED. Existing PR #115 only, base
\`reference/tl494-native-rework-20261114\`. No new PR, merge, main,
integration or frozen commit mutation.

## Coordinator and immutable inputs

- New assignment: https://github.com/Tridgi/gost-schematic/pull/115#issuecomment-6885775029
- Global audit: https://github.com/Tridgi/gost-schematic/issues/107#issuecomment-6885788255
- Frozen original: \`e695c415fdced164b0e0c39c5249d030795a0aa6\`.
- Physical source inventory: **23 components / 15 ORIGINAL Net names / 62
  unique physical PinRefs / all 16 numbered TL494 DA1**, frozen IC #97 Git
  source fixture blob \`a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65\`.
- Historical original: 91 old authored conductor segments, 37 junctions,
  **9 DRC ERROR, 32 WARNING** — deliberately retained negative benchmark.

## New code / actual nonvisual owner contracts

1. [cycle11_ti_bridge.py](cycle11_ti_bridge.py) invokes OWNER #97's
   \`bind_positioned_photo_circuit_from_catalog\` on the **real** compact A3
   source circuit with original named Nets (not a synthetic 3–6-part model).
   Only DA1 source \`reference.tl494cn\` is changed in a fresh in-memory
   Circuit to true manufacturer \`ti.tl494cn.pdip16\`. Source and signed
   Circuit retain the identical original \`nets\` tuple by object identity;
   other 22 component instances retain real part ID, nominal, origin and D4.
   All 16 actual factory pin name/type/physical Net/anchor contacts checked;
   DA1.3 FEEDBACK INPUT and DA1.13 OUTPUT CTRL INPUT preserved.
   \`VerifiedCompactTiBinding.reverse_source()\` returns the source, not a
   third invented circuit.
2. The same signed bridge calls **real PAINT #93** for text/physical lead
   geometry and **actual IC #97** \`IcGeometryConsent\` with precisely the
   changed factory-contact world locations, then
   \`revised.seal_paint_overlay(paint_binding)\`. Its
   \`IcVerifiedPaintSnapshot.render()\` produces verified 16-contact clean
   and debug \`IcRendered\` objects. The current 15-Net candidate driver
   uses the true manufacturer \`PartDefinition\` and the real signed PAINT
   lead/stroke/ink keepouts in NET #114 routing. Source aliases are
   explicitly reversible; raw cosmetic hotspots are not accepted.
3. [cycle11_b_continuation.py](cycle11_b_continuation.py) takes the genuine
   **old** typed source \`NetContinuationProject\` created by
   \`examples/tl494_named_photo_sheet.py\`, verifies its *entire* 23/15
   historical physical Net/part inventory against the frozen fixture and
   exact two source markers \`b-X2\`, \`b-R5\` with X2.1/R5.2 reciprocal
   addresses. It retains their true source physical pin→marker vectors and
   moves each nonphysical marker to its new compact A3 physical PinRef
   endpoint (strict integral µm), checks 10-mm paper boundaries and
   \`validate_net_continuations\`; the single real existing Net retains
   the exact original name \`b_NEGATIVE_OUTPUT\`, three members
   \`FU1.2,X2.1,R5.2\` and is never duplicated. Invalid provenance,
   wrong physical PinRef, source-Net edit, label change or out-of-paper is
   BLOCKED, not cosmetically repositioned.
4. [cycle11_binding_preflight.py](cycle11_binding_preflight.py) emits only
   \`C11_SIGNED_REAL_SOURCE_B_PROOF.json\` with exact factory PinRef/Net/
   world anchors and the real two b marker/stub points, historical negative
   source metadata and owner SHA. It cannot create an approved FULL E3;
   no full SVG/PNG output is claimed.
5. [test_cycle11_ti_bridge.py](test_cycle11_ti_bridge.py) and
   [test_cycle11_b_continuation.py](test_cycle11_b_continuation.py) exercise
   positive signed manufacturer, exact Net identity, real PAINT consent
   and marker source and various negative/boundary forgeries, integrated
   into [tl494-v5-current-owner-candidates.yml](../../.github/workflows/tl494-v5-current-owner-candidates.yml)
   with real ephemeral GitHub owner SHAs, Python3.12/3.13, Ruff, pytest,
   frozen Git blob SHA and full 15-Net route attempts. The workflow uploads
   both new source proof JSON and partial multi-Net route JSON.

## Source-owner pinned code (no cross-repo merge)

| Module | Pinned owner SHA used by new specialized 3.12/3.13 CI |
|---|---|
| IC #97 | \`c8991bf232428645cad6e8b402d70abccf12a546\` |
| PAINT #93 | \`df49c16fb082ee98213299358f374894fe1da220\` |
| YGO2 #113 | \`2dae5306c0690f2fc2d402bb4b65266dabd778b8\` |
| NET #114 | \`e604ab355f1f704aa11f5545d048a0087c97e39a\` |

GitHub compare on this exact-owner snapshot shows IC/PAINT/YGO2 modified
only their runner, documentation or CI workflows; the NET owner also changed
`multiterminal_router.py` internally while preserving the public route API.
The new NET implementation is pinned for fresh 3.12/3.13 revalidation,
not assumed behaviorally identical. Further owner HEAD movement needs a new
explicit exact SHA check.

## Evidence and honest CI status

- Earlier PR #115 exact commit \`c58e224700b318892ee92197f8bfd391807a7325\`:
  [full push Python3.12/3.13 CI #43652418186](https://github.com/Tridgi/gost-schematic/actions/runs/43652418186)
  **SUCCESS**, [special IC/PAINT #43652418148](https://github.com/Tridgi/gost-schematic/actions/runs/43652418148)
  **SUCCESS**, full PR #43652423311 initially 3.13 success and 3.12 in progress.
  This is only the **PRE-CYCLE11** owner baseline.
- **New Cycle11 files and updated routing hooks:** codes committed, many
  GitHub Actions jobs **QUEUED** due concurrency; no completed dual-version
  actual new HEAD Ruff/pytest/15-Net report yet. Do not call them PASS.
  Remote standalone Windows device is OFFLINE, so no independent local
  Python execution occurred this Cycle11; this report distinguishes
  code-committed from runtime-confirmed.
- Last actual compact 15-Net routing data from earlier owner snapshot
  \`5033659747f01fdc03adc084b846f47b05001963\`:
  **6/15 Net complete, 30 partial accepted segments, 919.502mm**,
  0 DRC ERROR on *accepted partial* only, **nine Nets BLOCKED**.
  This result must NOT be represented as an exact new Cycle11 route outcome.
- Source bitmap 1:1 reference, YGO2 36 DRAFT/0 approved, real wire/UGO/text
  3/2/1mm whole-sheet DRC, physically correct multi-terminal topology,
  exact source b continuation as printed and independent QA #99 plus
  ESKD #112 acceptance all require further checks.

## Critical next action / independent acceptance

1. Finish GitHub Python3.12/3.13 jobs on the **exact final PR #115 HEAD**;
   inspect step logs and fix errors, keeping original 9/32 negatives intact.
2. Confirm preflight JSON real two b markers and true 16 signed anchors.
   If b source vector, PAINT or actual A3 margin is impossible, keep
   \`BLOCKED_HISTORICAL_B_NOT_REBOUND\` with exact diagnostic and ask
   coordinator for source-approved layout/continuation geometry, never
   invent a physical wire or marker.
3. Owner NET #114 must achieve **15/15 and all 62 exact physical connections**
   with real global 0 ERROR measured DRC; owner PAINT #93 then produces
   actual new whole-sheet clean SVG/debug SVG/PNG 300DPI from typed graph.
4. QA #99 independently verifies true source/after and physical DRC; ESKD
   #112 conducts normative figure approval. Until then full print
   **BLOCKED** and no merge.
