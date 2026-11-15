# Cycle 14 / PR #97: canonical source-signed TL494+typed-b witness

**Status: DRAFT source/model geometry proof only; print acceptance BLOCKED.**

This document defines the cross-owner, reproducible, typed interface produced by
`scripts/verify_ic_recon115_live_bridge.py` when run against genuine, exact
version-pinned source checkouts. It does **not** establish a new 15/15 routed
sheet or approval of any ESKD UGO.

## Immutable source and verified owner snapshots

- Original `e695c415fdced164b0e0c39c5249d030795a0aa6`, frozen JSON Git
  blob `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`: 23 components,
  15 **original literal named** Nets, 62 numbered PinRef memberships,
  16 factory TL494CN DA1 terminals, 91 historic wires, 37 historic junctions,
  two **non-electrical** `b-X2` and `b-R5` continuations.
- IC #97: this branch, exact `$GITHUB_SHA` supplied by the CI host.
- PAINT #93: `99fbad0f904ef49e07c15e8ce06a5bdc1233c877`.
- RECON #115: `2c53aacc4f07b265756b25ff1d8145e6a87bc114`.
- YGO #113: `c3e81d1cbe22ee149a7fd842a39e50752a813642`.
- This is a **CI-pinned set**, not a claim that source branches cannot advance.

The original contains **9 DRC ERROR / 32 WARNING**, which are kept as a
known-bad negative control; never substitute its 91 wires for a new route.

## Reproducible actual API, not a synthesized witness

The owner CI `.github/workflows/ic-recon115-live-cycle11.yml` stages only
these versions in a throwaway checkout, verifies each `git rev-parse HEAD`,
uses the SHA256-pinned original Type A font, and executes the actual
`scripts/verify_ic_recon115_live_bridge.py` on Python 3.12 and 3.13.
The critical production flow is:

1. `assembly = compact_source_assembly()` with real 23-part placements.
2. `fixture, _ = load_original_owner_fixture()`, followed by
   `original = restore_original_named_nets(assembly, fixture)` from RECON.
   The resulting Circuit uses **all 15 literal original Net names**, not
   convenient `INPUT_POS`, `OUTPUT_NEG`, `ENERGY_TRANSFER` aliases.
3. `owner = bind_verified_compact_ti(assembly, original)` and
   `owner.verify()`: only DA1 `reference.tl494cn` can be translated to
   manufacturer `ti.tl494cn.pdip16`, without reordering/rewiring one
   member. `owner.reverse_source() is original` and
   `owner.signed.circuit.nets is original.nets`.
4. `proposal = propose_ic_paint_binding(owner.signed.record, style, measurer)`;
   `revised, snapshot = owner.seal_paint(proposal)`. Real moved contacts
   require **source-fingerprint-bound** `IcGeometryConsent` with a separate
   exact set of connected members authorized for rerouting. This consent is
   not a claim that a wire was actually rerouted.
5. Real `_bind_verified_source_b(font, revised.circuit, symbols)` obtains
   the RECON source-validated continuation project with **exactly two** original
   local H/V stubs: `X2.1→b-X2`, `R5.2→b-R5`.
   They remain non-electrical. The only `b_NEGATIVE_OUTPUT` Net has
   exactly `FU1.2`, `X2.1`, `R5.2`.
6. Call `render_routed_native_sheet` with **all three** authenticated
   `verified_ic_source=revised`, `verified_ic_paint_binding=proposal`,
   `verified_ic_snapshot=snapshot`, the actual pair of snapshot-rendered
   `physical_ic_renderings_clean/diagnostic`, full `symbols_by_part`,
   and real `source_continuation_project`. In this dedicated witness the
   `ExternalWireGraph(())` is **deliberately empty**. It is NOT routed.
   The returned native whole-sheet must be `printable_candidate=False`,
   with signed 16 physical pins, exact 2 printed nonphysical b stub XML lines,
   and explicit blockers.

## Machine-readable output contract

The script writes these genuine source/PAINT products (no SVG hand editing):

- `DA1-recon115-ic97-paint93-clean.svg`: **0** diagnostic green contacts.
- `DA1-recon115-ic97-paint93-diagnostic.svg`: **16** real factory contacts.
- `bridge-manifest.json`: original 23/15/62, 16 manufacturer contacts and
  truthful `all_15_net_routed=false`.
- **`source-physical-witness.json`**: schema v1, the four exact checkout SHAs
  from the CI environment, immutable original SHA, complete list of all
  original named Nets with all 62 physical members, a canonical SHA-256 digest
  of the source named Net list, and all 16 signed physical terminal
  `{pin_ref, manufacturer_name, display_alias, electrical_type,
  source_named_net, physical_tip_um}` entries. Includes exact two b
  `{id, endpoint_id, source_pin_ref, start_um, end_um}` non-electrical
  strokes, verified font SHA-256 and 3500-µm cap, 0/16 green targets,
  `new_route_segments=0`, `new_route_15_of_15_complete=false`,
  `printable_candidate=false`, and actual native sheet blockers.

The CI shell rejects any mismatch between artifact `owner_sha` and
its real `git rev-parse HEAD`/IC `$GITHUB_SHA`, the 23/15/62/16/2 counts
or false print claims, before accepting the artifact. Linux CI additionally
rasterizes both physical IC SVGs with `rsvg-convert --dpi-x 300 --dpi-y 300`
and writes `SHA256SUMS.txt`. A successful SVG/PNG proves a physical-IC
render and never that the whole 15-Net circuit is printable.

## Genuine adversarial matrix

No skips or missing negatives: NC spoof on DA1.3 FB INPUT, DA1.13 OC
INPUT or DA1.14 REF POWER_OUTPUT; changed manufacturer identity; counterfeit
legacy PartID; wrong or duplicated Net/PinRef; 1µm moved connected
terminal without exact fingerprint + separately connected reroute consent;
stale consent; counterfeit 16 green UI-only terminals without signed triple;
tampered signed digest or clean SVG; all eight D4 physical poses; wrong b
source-pin, missing second stub, one-µm continuation marker drift; incorrect
Type A family/cap or forged font file.

The first real Cycle 14 cross-owner regression found that PAINT's strict
`_declared_type_a_family()` rejected genuine RECON
`inspect_type_a_font(font_file, ...)` because `font_file` was the sole
positional path argument. Reported to PAINT #93 as
[real LOCAL reproducer](https://github.com/Tridgi/gost-schematic/pull/93#issuecomment-6895138987).
PAINT fixed this without weakening the family/3500µm/SHA requirements.
Its newer `append_verified_sheet_continuations` also requires a genuine
`symbols_by_part` map, which the IC caller now supplies. This correct
strict validation is not bypassed.

## Independent Windows LOCAL proof (not GitHub Actions)

Isolated Git clones in a unique TEMP directory; no shared repository branch
switched or edited. Source fixture restored from `git show HEAD:<path>`
to preserve the original exact blob bytes when Windows autocrlf would
otherwise corrupt the frozen hash. `uv`-created Python 3.12.14 and 3.13.15
environments; **Ruff PASS, 53 pytest PASS and 0 FAIL each** on pinned exact
PAINT/RECON/YGO source. Verified local Type A SHA:
`f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`.

Deterministic LOCAL artifact SHA-256 (not CI-derived):
- clean SVG: `2468d97f676503e1e6d3f80720a3d3766b7302612a143ea70c48ebe51984e8d1`;
- diagnostic SVG: `30c3f9723afc9ffdaa552bc383e2ad48f9f5c52d0cc3a9fe0b004919e1a11370`;
- local witness JSON: `45a5a293e6f1e2d2ef200ffd45cccb47e307be053489626a4e01993f01607a81`;
- local 300-DPI clean PNG: `d7a68c4eb1c7d62c5db9fa17529daa092506d4bf7560fbee677b9bc566461704`;
- local 300-DPI diagnostic PNG:
  `1bc5c43964a80674e7e884276f9c60a218042b3fa3b3dab88fc2d09bb53a5c23`.

PNG is genuine resvg raster output from source SVG with physical 300-DPI
dimensions 996×1438 and PNG DPI metadata verified within 1 DPI; it is
**not** a hand-drawn circuit or full-sheet A3. Its bytes need not match
Linux `librsvg` CI output across different independent raster engines.

## Release boundary

**DRAFT/BLOCKED** until NET #114 independently delivers all **15/15**
electrically connected original Nets on a legal A3/A2/multi-sheet candidate,
with a real completed wire graph and exhaustive full printed-sheet DRC/ERC,
all textual/glyph/UGO clearances, nonphysical b stubs, full source
BOM/Netlist, QA/ESKD normative review and actual user source-photo
comparison when original image is accessible. Nothing here grants merge
authorization, sets UGO status APPROVED, or modifies the original 91-wire
negative fixture.
