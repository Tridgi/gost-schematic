# QA 2 — Cycle 13 source-signed TL494 b continuations and verified Type A

**Status: NOT PRINT APPROVED.** This document records exact owner
integration and independently enforceable QA gates. It is not a change to
immutable source, Netlist, 16 manufacturer contacts or any rendered SVG.

## Reproducible source provenance

- Frozen TL494 physical source commit:
  `e695c415fdced164b0e0c39c5249d030795a0aa6`.
- Photo topology fixture Git blob:
  `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`.
- Source topology **23 components / 15 user-named electrical Nets /
  62 unique physical memberships / 16 real DA1 manufacturer pins**.
- Original source drawing, **91 segments, 37 original junctions,
  9 real DRC errors + 32 warnings** remains a permanently negative
  baseline, not a valid AFTER result.
- Real Type A file SHA256:
  `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`.
  Measured capital height 3500µm; do not loosen family+SHA checks.
- Physically non-electrical source continuations `b-X2` and `b-R5`
  are printed on the **single original** Net `b_NEGATIVE_OUTPUT`;
  their physical source PinRef set `{FU1.2,X2.1,R5.2}` MUST NOT
  become an extra electrical Net.

## Reproduced prior specialized failures

Prior [QA old b/type-A run 43702714399](https://github.com/Tridgi/gost-schematic/actions/runs/43702714399)
failed six RECON fixture tests on genuine font family mismatch
(`OpenGost Type A TT` vs `OpenGOST type A`) and a further
unbound or undefined symbol in an older PAINT example. Source
builder was mistakenly overwritten by legacy E695 in the
cross-owner CI overlay.

Prior [QA old owner run 43702714252](https://github.com/Tridgi/gost-schematic/actions/runs/43702714252)
rejected unconsented image geometry with real
`IC_ADAPTER_STALE_PAINT_GEOMETRY`. This is the **correct**
manufacturer security behavior; the old QA incorrectly expected
a direct unsigned `seal_paint_overlay` to pass.

QA Cycle13 changes preserve the negative: assert the raw PAINT
overlay rejects, compute actual moved typed physical PinRefs,
generate `IcGeometryConsent` using real source record fingerprint
and every active moved contact, call production `revise`,
then verify the trusted source-retained
`IcVerifiedPaintSnapshot`. Three additional active malicious
consent cases must fail (absent permit, forged source fingerprint,
omitted connected reroute).

## Exact owner-signed CI execution snapshot

The Cycle13 independent b/runtime matrix uses a coherent immutable
RECON package SHA and its true internally signed owner hashes:

| Source | Exact immutable checked-out SHA |
| --- | --- |
| RECON PR115 | `73025965efeb94585e8723ba3f0b636229e8a5de` |
| IC PR97 | `7c30c209ea5e97a245844b24a3bbc4d3d30118ea` |
| PAINT PR93 | `2e9d3fa41794eb773645e112ec8c44fc273e9f52` |
| NET PR114 | `61df41377cc9326f7fa0f594a804d329b447ec69` |
| YGO PR113 | `3e47cdf32ccf211ded97e3be1ad874035653e090` |

Pinned owner snapshots do not claim to be all later moving branch HEADs.
The RECON driver binds each real 15-Net tree via signed original raw
a_/b_/TRANSFER member sets, not a heuristic label classifier.

## Native b marker source and print QA

`scripts/qa_tl494_cycle11_b_binding_gate.py` validates authentic
RECON `cycle11_binding_preflight` signed JSON, all physical source
Net memberships, exact typed continuation endpoint/stub vector and
12 cloned evidence mutations + three production source mutations.

`scripts/qa_tl494_cycle11_native_300dpi.py` now **requires**
`--source-b-witness` with authentic RECON JSON alongside the actual
PAINT DRC manifest and CLEAN/DIAGNOSTIC native SVG pair. Verifies:

- Each model Net, with only three explicitly reversible
  source aliases, equals the same signed 15 Net/62 PinRef
  original source membership. No invented protective ground.
- All 16 physical DA1 manufacturer terminals belong to their
  real source electrical Net; FEEDBACK pin 3 and OUTPUT CTRL pin
  13 are manufacturer **INPUT**.
- Exactly two actual native typed `b` glyph circles at source
  integer-µm signed positions; both non-electrical, white, with
  genuine Type A font SHA on 2 text labels; 2 diagnostic
  nonconnectable orange zones, 0 clean, 16 genuine IC editor
  green contact squares only in diagnostic.
- 8 adverse mutations of **actual emitted native b SVG in RAM**:
  1µm marker displacement, foreign address, made-up electrical
  junction, duplicate endpoint, forged `a` label, wrong font
  digest, false active editor pad, removed nonphysical source
  policy. None are masked with `xfail`; real owner source SVG
  remains byte-for-byte untouched.
- Original SVG rendered using CairoSVG to actual 300 DPI PNG,
  both physical millimetres and 300 DPI metadata verified.
  This is **diagnostic output ONLY** until all 15 Nets routed,
  complete ERC and full print DRC pass and source photo is
  available for independent comparison.

### Independent remaining PAINT b-stub defect

On actual PAINT #93 SHA
`f872ce50ac699ad089391b0bbd58e2cb92f2b7f6`,
`src/gost_schematic/rendering/ic_sheet_composition.py:170–230`,
`append_verified_sheet_continuations` prints the two source
marker circles/text but **does not iterate `project.stubs`**.
RECON source `cycle11_b_continuation.py:202–212` has the two
real typed physical-pin-to-marker stub segments. Missing printed
strokes mean no proof that the source-authoritative `b`
continuation graphics are complete. PAINT owner was notified
[PR93 issuecomment-6893975462](https://github.com/Tridgi/gost-schematic/pull/93#issuecomment-6893975462).

QA `assess_source_b_stub_ink` checks two exact non-electrical
pin-to-marker lines when present; detects missing strokes as
`BLOCKED_PAINT_OMITTED_TWO_AUTHENTIC_B_STUB_STROKES`, not a
forged green DRC success. A partial or spoofed stroke set must
fail. PAINT must implement real line ink, not add wires to
`ExternalWireGraph` or hand-edit final SVG.

### Independent remaining cross-owner Type A adapter defect

On PAINT #93 SHA
`f872ce50ac699ad089391b0bbd58e2cb92f2b7f6`,
`examples/render_tl494_full_native_cycle9.py:94–129`,
`_compose_frozen_circuit_with_real_type_a` intercepts only
the **old** declared `OpenGost Type A TT` family and rejects
the corrected RECON builder's `OpenGOST type A`.
`construct_native_paint`, consumed by PAINT compact
source `_bind_verified_source_b`, may therefore fail
`FROZEN_REFERENCE_TYPE_A_SIGNATURE_CHANGED` when both owner
modules are staged together. This must be fixed at the PAINT
owner API WITHOUT spoofing Type A, altering E695 or skipping
the negative font signature tests. PAINT notified
[PR93 issuecomment-6894022531](https://github.com/Tridgi/gost-schematic/pull/93#issuecomment-6894022531).

## Go/no-go

Known best independently checked physical A3 new route is
**10/15**, **62 accepted partial segments**,
**0 DRC errors on PARTIAL output ONLY**. Actual native
A3-labelled SVG had off-nominal physical dimensions and
frame-boundary violations. Nothing in this Cycle13 QA
approves print or advances certified UGO status. All unknown
original-photo pixel equality stays BLOCKED.

The next acceptance requires BOTH signed source b stub strokes,
cross-owner PAINT/RECON Type A compatibility, true all-15 source
routing, complete ERC/global native ink DRC, exact physical paper
scale and independent ESKD. New exact QA code must pass
**CI 3.12 and 3.13 ON ITS LAST SHA** before any MAIN3 merge.

## Cycle 13 concurrent continuation — independent real SVG acceptance delta (2026-11-15)

This is a **new test iteration**, not a retroactive PASS for the
previously documented defective PAINT snapshots. All historical
failures remain recorded above.

Current staged *exact snapshot commits*, verified through GitHub refs:

| Owner | Exact source commit used by QA dedicated two-stub matrix |
| --- | --- |
| RECON #115 | `e4eb565820e54889456f64d36598b608597ca2c2` |
| PAINT #93 | `d74300580dfd28cc3400a512828dac6b49d529f0` |
| IC #97 | `bc03a31c5d15c9e962f9b26a209aab373e39bee6` |
| NET #114 | `a370d637fe67ec44870899d503f53c0a6f8ee3af` |
| YGO #113 | `3e47cdf32ccf211ded97e3be1ad874035653e090` |

New PAINT owner **source code inspection** shows:
`append_verified_sheet_continuations` now iterates
`project.stubs` and produces two SVG `<line>` children with
`data-layer=nonphysical-continuation-stub`, original
`data-source-pin-ref`, `data-source-stub-id`, and explicit
`data-connectable=false`/`data-electrical-junction=false`.
Its Type A adapter now accepts two precisely declared builder
signatures, retaining authentic measured family/hash checks.
**Source inspection is not an executed native-artifact PASS.**

New QA changes in existing Draft #99:

- `scripts/qa_tl494_cycle11_native_300dpi.py` **requires** exactly
  two actual non-electrical SVG line elements, not just metadata,
  circles, text or editor zones. Missing both, missing one, extra
  anonymous/duplicate line, untrusted layer and path substitution
  are hard failures, not silent `BLOCKED` successful verification.
- The real source vector `X2.1→b-X2`, `R5.2→b-R5` is compared
  on **both endpoints** as exact Decimal mm-to-µm coordinates;
  both strokes must preserve black 0.3 mm printed ink, real PinRef,
  distinct source stub IDs, authored layer and no electrical role.
- The actual Type A text family **and** font file SHA256 are
  independently checked; old `OpenGost Type A TT`-only
  spoof is rejected while the genuine `OpenGOST type A`
  builder remains allowed.
- Expanded **24 hostile in-memory mutations** of *genuine produced
  native SVG bytes*, including 1-µm stroke tip changes, missing /
  duplicate / switched segments, forged contact `X2.2`, wrong
  family, invisible or wrong-width ink, fake green connectable
  continuation, duplicate source IDs and extra anonymous strokes.
  Source owner artwork is never modified.
- Dedicated workflow
  `.github/workflows/qa92-cycle11-live-b-and-native.yml`
  stages exactly the five source commits above with frozen E695;
  covers Python 3.12 and 3.13 and retains signed 23/15/62/16
  source/BOM/Netlist, real 300-DPI PNG, global post-render DRC
  checks. It never turns a partial route into whole-sheet PASS.
- `scripts/qa_tl494_cycle11_b_binding_gate.py` now checks the
  current RECON exact SHA. An existing source import-order
  Ruff `I001` was detected and repaired with no suppressed test.

**Actually executed independently on a fresh temporary working
copy of the updated QA branch:** native Windows Python 3.13
`py_compile` on both changed QA scripts **PASS**; `ruff check`
on those two scripts **PASS** at QA commit
`8cf6a4a6c5e01e5fd2d847d6ee44b1e36dfa026f`.
These are local scoped lint/syntax checks; they are **not** substituted
for full Python 3.12/3.13 GitHub CI or actual PAINT raster acceptance.

All current exact-head GitHub Actions are **QUEUED as of this edit**
and must be read again at actual execution completion. In particular,
neither the two real PAINT stub strokes in emitted SVG/PNG nor
the latest NET X1=17mm 15/15 route has independent runtime PASS.
Keep 15/15, full ERC, measured 3/2/1-mm global print DRC,
original user-photo equivalence, and all normative DRAFT UGO
**BLOCKED / NO-GO** until independently proven by actual artifacts.
