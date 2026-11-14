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
