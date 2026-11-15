# Cycle11 / PR #97 ↔ PR #115 ↔ PR #93: true-source identity handoff

**DRAFT integration contract, not a ГОСТ/ЕСКД approval or a printable A3.**
Original source is immutable: `e695c415fdced164b0e0c39c5249d030795a0aa6`.
The 23 components, 15 physical Circuit.Net objects and 62 physical PinRef
memberships (16 numbered TL494 contacts) are the electrical authority.

## Exact real owner pins for the joint live gate

- RECON PR #115: `c58e224700b318892ee92197f8bfd391807a7325` — actual
  `examples.tl494_v5.compact_layout.compact_source_assembly()` A3 source.
- YGO2 PR #113: `eb16121e07efec71de77dfc7b8123bc09f66ddd6` —
  actual catalog native source profile and physical parts.
- PAINT PR #93: `32f2efb2cdcb561cb2567a54448381de3cb87832` —
  actual Type A renderer/physical diagnostic target source.
- ELEKTRIK IC PR #97: current branch, with strict TI manufacturer
  `ti.tl494cn.pdip16` and 16 physical contacts.

## Exact and reversible source identity bridge

RECON's source-authored `ComponentInstance("DA1", "reference.tl494cn", ...)`
is **not** automatically a manufacturer source. It cannot be passed directly
to `bind_ic_circuit_from_catalog` or `validate_ic_circuit` and declared
equivalent to TI. Use the source-pinned, typed adapter instead:

```python
from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_cycle9_circuit_integration import (
    bind_positioned_photo_circuit_from_catalog,
)

native = compact_source_assembly()
trusted = bind_positioned_photo_circuit_from_catalog(
    native.circuit,
    native.owner_ic_record,
    native.parts,
    aliases=native.owner_aliases,
)
```

The adapter verifies the immutable frozen fixture Git blob and manufacturer
pinout; full 23-component identity, quantities, catalog contacts, 16 TI pins,
all 62 numbered PinRef memberships and original Net membership tuples.
It returns a **new in-memory Circuit** replacing only DA1's `part_id`.
`trusted.circuit.nets is native.circuit.nets` must hold. It does not edit
`native.circuit`, write a Git fixture, move a physical pin, infer a wire,
relabel a physical pin number or relax `validate_ic_circuit`. Replacing
the signed DA1 identifier with the exact original literal reverses the
projection to the original Circuit.

RECON's **three source-verified whole-Net display-name translations**:

| Frozen source Net.name | Exact PR #115 Net.name |
|---|---|
| `a_INPUT_PLUS` | `INPUT_POS` |
| `b_NEGATIVE_OUTPUT` | `OUTPUT_NEG` |
| `TRANSFER` | `ENERGY_TRANSFER` |

The adapter accepts either the *complete original* 15-Net namespace or the
*complete PR #115* namespace with **identical members on every one of 15
named Nets**. A hybrid set, another synonym, changed single PinRef, duplicate,
foreign Net, or changed count fails closed. This is a restricted, reversible
source-label translation, **not** Net shorting or Net auto-matching.

## PAINT rendering boundary

1. Run `propose_ic_paint_binding(trusted.record, true_type_a, measurer)`.
2. Obtain `IcGeometryConsent` for the exact original-record fingerprint
   and **all** moved contacts (explicit connected-wire consent if applicable).
3. Call `trusted.revise(proposal.record, consent=consent)` and then
   `updated.seal_paint_overlay(proposal)`. The resulting
   `IcVerifiedPaintSnapshot.verify_against(updated, proposal)` is the only
   trusted physical target/Net input to the marker compositor.
4. Use `snapshot.render(... diagnostics=False)` for **zero** green physical
   targets; `diagnostics=True` for exactly the actual 16 numbered source
   contacts. Preserve FB=FEEDBACK physical pin 3 INPUT and OC=OUTPUT CTRL
   physical pin 13 INPUT (no print-word equivalence to a different pin).
5. PAINT's latest `render_routed_native_sheet` demands an actual
   `ExternalWireGraph`, catalog symbols and *paired* clean/diagnostic typed
   `IcRendered` objects. A real verified IC snapshot is a prerequisite,
   **not** proof of 15/15 globally routed source Nets. NET #114 owns that
   separate route/DRC gate.

The paper source/reconstruction is historically **9 DRC errors, 32 warnings,
91 authored conductor segments and 37 junctions**. The new compact A3 layout
is a separate DRAFT design candidate; there is no independent full printable
15-Net result, no unverified extra earth, and no source-b visual continuation
fabrication.

## Reproducible mandatory independent verification

`.github/workflows/ic-recon115-live-cycle11.yml` checks out exact real
owners in an **ephemeral CI checkout**, stages the owner sources only
in the runner, tests source-vs-signed-vs-reversed Circuit, strict negative
spoofing/one-micron drift, eight D4 poses and measured real PAINT SVGs.
It runs Python 3.12 and 3.13. Python source runner:
`scripts/verify_ic_recon115_live_bridge.py`.

PR #97, #93, #115, #113, integration and main are not merged or modified
by this read-only testing workflow. Never call a merely drawn clean SVG
"print PASS" without NET #114 full routing, PAINT printed-ink and independent
QA/ESKD source acceptance.


## Cycle13 / 15.11.2026 — exact current signed-manufacturer handoff

The SHA list at the top of this RFC is **historical Cycle11 evidence**, not
proof of current owner versions. The renewed `.github/workflows/ic-recon115-live-cycle11.yml`
stages these **immutable Cycle13 snapshots**, with `git rev-parse HEAD`
assertions on every job and no owner-branch merge:

| Owner | Verified checkout SHA |
|---|---|
| RECON PR #115 | `5244608f7e554bb453075f4beb4e46d9a83b6bd1` |
| PAINT PR #93 | `a16c20bc3414434c3af7f9b12192e3e7ea7c55a4` |
| YGO PR #113 | `92347d936c71e6038c836f37992bbbee65d56196` |

These commits are **CI-pinned snapshots**, not promises that other branches
will stop changing. All cross-owner changes require a fresh SHA and a new CI
run; earlier green Actions are not proof for new code.

### Actual typed consumer and renderer contracts

The authoritative RECON consumer is
`examples.tl494_v5.cycle11_ti_bridge.bind_verified_compact_ti(assembly, source_circuit)`.
It rejects a merely value-equal but newly allocated `components` tuple
(`source_circuit.components is not assembly.circuit.components`), even
where all 23 component values match, and it returns
`VerifiedCompactTiBinding`. Its `reverse_source()` returns the **same
source Circuit object**. The signed model preserves the original **Net tuple
object**, all 15 named Nets, all 62 physical PinRefs and the full factory
pinout, including `DA1.3` FEEDBACK INPUT/FB and `DA1.13` OUTPUT CTRL
INPUT/OC.

After the actual `propose_ic_paint_binding(...)`, the owner can call
`verified_owner.seal_paint(proposal)`, returning
`(revised: IcCircuitBinding, snapshot: IcVerifiedPaintSnapshot)`.
Any move of real physical terminals is tied to exact-source
`IcGeometryConsent`. When composing a whole PAINT routed-native sheet,
the three **inseparable** keyword arguments are:

```python
verified_ic_source=revised,
verified_ic_paint_binding=proposal,
verified_ic_snapshot=snapshot,
```

Together with real matched
`physical_ic_renderings_clean={"DA1": clean}` and
`physical_ic_renderings_diagnostic={"DA1": diagnostic}`, where `clean`
and `diagnostic` are produced by `snapshot.render(revised, proposal, ...)`.
`render_routed_native_sheet` validates the signed Circuit identity, 16
factory anchors, complete manifest, serialized clean/diagnostic ink and all
source counts. Neither a standalone cosmetic 16-tip overlay nor two
apparently identical `IcRendered` objects are a trusted manufacturer proof.
A **partial** signed triple, substituted digest or modified clean SVG must
fail closed; CI includes those exact negatives.

The source-Named `b_NEGATIVE_OUTPUT` Net is **one electrical Net with
exactly three physical members**: `FU1.2`, `X2.1`, `R5.2`. In RECON's
legacy namespace it is `OUTPUT_NEG`. The two source `b-X2` and `b-R5`
markers are *typed non-electrical continuation glyphs* — **not** extra
components, Nets or PinRefs. The new IC negative test adds a spurious
`X2.2` PinRef to that original Net and requires the source-binding
adapter to reject it. Actual continuation vector relocation remains
RECON #115 / PAINT #93 responsibility and still requires a valid
`source_continuation_project`; the isolated empty-route smoke has
`source_continuation_project=None` and is **BLOCKED**.

The current signed zero-segment whole-sheet test checks
`manifest["signed_manufacturer_ic_16_verified"] is True` while
`printable_candidate is False`, real **zero green contact targets**
on the clean sheet and exactly 16 in diagnostic, source 23/15/62/16.
The full output is **not** ESKD released: independent complete 15/15 route,
3/2/1 mm wire/UGO/Type A DRC, both b markers, QA and original-user-photo
verification remain separate gates. PNG300DPI from this isolated workflow
proves the genuine physical IC rendering, not a fully wired printable A3.
