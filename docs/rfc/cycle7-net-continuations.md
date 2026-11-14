# RFC NET-C7-001 — typed named E3 net continuation

Status: DRAFT EXPERIMENTAL, no normative approval. Issue #90; ESKD #91; QA #92.
Design request: https://github.com/Tridgi/gost-schematic/issues/90#issuecomment-6866828267

## Electrical truth and graphical continuity are separate

NetIdentity(id,net_name,members) binds one stable semantic ID to the exact frozen PinRef membership of one existing Circuit.Net. The original Circuit is ALWAYS supplied; rendering cannot infer or mutate physical connectivity by matching labels, positions or ink intersections.
ContinuationSheet(id,number) declares unique page IDs/numbers. NetContinuationEndpoint(id,net_id,sheet_id,sheet_number,address,target_address,anchor,label,direction) stores a nonphysical view marker and explicit reciprocal remote address. ContinuationPair(id,source_id,target_id,scope) only pairs two markers of the SAME existing Net ID; scope is sheet_local or global. Direction is SOURCE/TARGET/BIDIRECTIONAL visual meaning, not digital logic electrical type.
ContinuationStub(id,endpoint_id,pin,start,end) represents one short, real, orthogonal conductor ending EXACTLY at the marker Point; the beginning is an actual physical PinRef already contained in the bound Circuit.Net. Optional exact physical pin anchor map catches even 1µm mismatch. There is NO invisible line across pages.

Fail-closed diagnostics: duplicate sheet/page/endpoint/net/pair/stub, missing or ambiguous actual Net, physically duplicated PinRef, wrong members, unknown target, reused marker, missing reciprocal address, direction/scope mismatch, false cross-net join, wrong local physical PinRef, 1µm stub off endpoint, unpaired marker, and ambiguous same/global-scope printed labels. A marker masquerading as XP/XS is rejected. Genuine plug/socket is a different physical PartDefinition with PinRef, not a continuation marker.

Strict deterministic DRAFT_E3_NET_CONTINUATIONS JSON v1 requires the REAL existing Circuit on import, rejects float/NaN, unknown keys, duplicate JSON keys, invalid graphs and cannot fabricate a net. Eight D4 transforms alter only visible marker/stub coordinates, preserving stable IDs and exact Net members.

## DRAFT two-sheet CTRL proof

examples/review_net_continuations_cycle7.py::specimen() has synthetic DD1.5 and VT1.G physical PinRefs in one existing Circuit.Net('CTRL'), with S1 marker 1/D4 targeting 2/B7 and S2 marker 2/B7 targeting 1/D4. Exactly two short independent H/V visible wire stubs, no automatic PartDefinition or SVG conductor across sheets. Two deterministic A4 SVG images and optional 300 DPI PNG are review-only; actual OpenGost Type A glyph ink, overflow, GOST symbol geometry and accurate sheet-address mark remain BLOCKED pending PAINT/ESKD. The font family in the SVG is a request, not verified measured face.

Commands: python -m examples.review_net_continuations_cycle7 --output-dir output/netrefs-cycle7 --png
          pytest -q tests/test_netrefs_cycle7.py
          ruff check .
          python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
          python -m pip wheel . --no-deps --wheel-dir dist
          python scripts/verify_wheel_payload.py dist

Independent branch parallel/electrical-netrefs-cycle7: NO import of incomplete IC #87, NO edits to Circuit/PinRef/ExternalWireGraph/E1/public API/main. Issue #90 normative source pointers: ГОСТ 2.721-74 table 6 pos 8, ГОСТ 2.709-89 §§5.13–5.14. DO NOT MERGE.


## Independent second-pass integration gate (ELEKTRIK NET)

After the initial QA #92 duplicate-xmlns finding, `sheet_svg` no longer
registers an SVG namespace globally or creates namespace-qualified tags
together with a manually injected namespace. Instead it builds a
**single default xmlns** on a plain ElementTree root and children. It
is parseable via strict `ET.fromstring` regardless of other imports and
does not mutate the process-global namespace registry. The original
DRAFT-unmeasured SVG golden images remain byte-for-byte unchanged.

New opt-in `sheet_svg(..., font_path=actual_type_a_file, review_overlay=True)`
is an **isolated diagnostic preview**, not a production PAINT replacement:
it uses the shared existing `inspect_type_a_font` and
`PillowTextMeasurer`, tests the real SHA-256 and actual Cyrillic glyph
ink at h=3.5 mm for the Net label and h=2.5 mm for its remote address.
The same calibrated em size is rendered in SVG; each annotation carries
`data-ink-box`, `data-protected-box`, `data-font-sha256` and owner
marker ID. Widths are never approximated by character count.
Ink protection is an **editorial 1.0 mm padding**, and the preview
uses an **editorial 10 mm A4 safe region**; none is asserted as a
fixed requirement of ГОСТ 2.721-74. Colliding text, text/wire overlap,
unsupported vertical marker rendering and out-of-page text **fail closed**.
Optional green dashed rectangles are only diagnostic overlays and never
electrical conductors or production UGO.

For the horizontal 2-sheet specimen the measured DRAFT renderer puts the
net designation above the conductor and the remote continuation address
outside the arrow, to the right of a right-facing break and to the left
of a left-facing break. The filled arrow is closer to the original figure
than the legacy chevron but its geometry and dimensions are still **DRAFT**;
the exact 1:1 figure and alignment require the normative ESKD #91 owner.
The project-specific `1/D4` sheet/zone address convention now checks that
the numeric prefix is the declared **local** sheet number. The contract
also preserves non-zone device/contact addresses such as `DD1.5`
per ГОСТ 2.709-89 §5.14; **there is no assertion that `1/D4` is a
universally prescribed GOST address format**.

Independent integration tests `tests/test_netrefs_cycle7_integration.py`
cover real XML parses after loading other rendering modules with three
namespace aliases, all six import permutations in fresh processes,
exact 3-sheet/2-pair single-Net semantics, wrong sheet/zone addresses,
control characters rejected before XML, real measured glyph/keepout
boxes, Cyrillic overflow, collision and both A4 300-DPI PNG images.
Namespace changes in in-process tests are restored immediately.
The dedicated `.github/workflows/netrefs-cycle7-review.yml`
requires pinned release OpenGost Type A SHA
`f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`
and proves the fontconfig SVG viewer points at the **same** font file
before `rsvg-convert --dpi-x 300 --dpi-y 300`. Real clean/diagnostic
SVG and PNG are uploaded for **both** Python 3.12 and 3.13. Ordinary
base CI does not claim to run font-measured tests without that asset.

### Integration ownership and remaining BLOCKED gates

- **ELEKTRIK #90** owns real stable `NetIdentity`, physical membership,
  reciprocal typed continuations, identity/sheet validation and no inferred
  connection or phantom XP/XS. The preview does not introduce a new part.
- **PAINT #88 / PR #93** owns final unified render integration, exactly
  measured ink geometry, 1:1 GOST figure comparison, page/title-block
  layout and collision with nearby actual component geometry. The isolated
  two-sheet preview does not prove those combined cases.
- **ESKD #91 / PR #95** must approve the break/arrow form against
  ГОСТ 2.721-74 tab.6в item 8 and site-specific address semantics against
  ГОСТ 2.709-89 §§5.13–5.14 (plus full-source provenance). The numeric
  sheet/zone notation and dimensions are editorial until then.
- **QA #92 / PR #99** must test a combined snapshot of #87/#88/#89/#90
  with actual SVG before merge. The still-isolated branches cannot certify
  cross-owner integration independently. Any golden SHA snapshot of older
  #90 must be updated **only after** independent review.
- Physical mating XP/XS and actual manufacturer pin numbers are separate
  future physical-component work; UI green connection zones are not
  electrical nets or required visible GOST graphics.

**RELEASE STATUS: DRAFT / experimental integration only. No merge, no
approval of new UGO, no GOST certification.**


## 2026-11-14 — source-checked address contract and v2 opt-in (ELEKTRIK NET)

### ГОСТ source scope — do not confuse graphic navigation with a physical link

- ГОСТ 2.721-74 §7, table **6в, position 8**: the **line break** arrow
  uses placeholder X for necessary continuation information. It is not an
  XP/XS connector and its printed mark alone is not an ERC net join.
  Source: https://e-ecolog.ru/docs/qO9rMExlXIL-CffRN3D7U
- ГОСТ 2.709-89 **§5.13**: circuit designation is normally above a
  horizontal run or left of a vertical run, near its end or midpoint.
  **§5.14**: reciprocal **addresses of actual connecting elements, devices,
  or functional groups**, with optional combined net+address form. Figure 11
  illustrates A7/X16 ↔ A4/X11; it does not prescribe a single sheet-zone
  syntax. Sources: https://e-ecolog.ru/docs/bujAS0DLkZo5zQovKPCJN
  and ESKD #91 PR #95 deep-source audit.
- `1/D4` and `2/B7` are an **editorial project sheet/zone profile**,
  not the universal normative continuation-address grammar. The
  `DD3.1` ↔ `DA1.2` pair in the new three-sheet example demonstrates
  the physical contact-address alternative. No syntax regex can itself
  establish or merge an electrical network.
- The marker's filled arrow dimensions and sheet-zone presentation remain
  **DRAFT** until ESKD/PAINT compare the final glyph one-to-one with the
  original figure, including opposite arrow orientation and legibility.

### Address provenance schema v2 — strict and backward compatible

The existing exact `DRAFT_E3_NET_CONTINUATIONS` **v1** remains unchanged
and byte-for-byte roundtrippable. New v2 is explicit opt-in and requires
a `ContinuationAddressBinding` for **every** endpoint; no partial v2
arrays or silent auto-upgrades are allowed. Each binding is identified
by `endpoint_id` and carries `kind`, `owner_ref` and an optional
`physical_pin` reference. A binding is *descriptive evidence* of the
locally displayed address, not an edge of a new Net.

| Address kind | Evidence and validation | Release implication |
|---|---|---|
| `sheet_zone` | `owner_ref` matches exact declared `sheet_id`; recognized numeric sheet-prefix matches real page; **no** physical pin | Project navigation, NOT itself GOST §5.14 physical address |
| `element_pin` | exact `PinRef` matches the local visible `ContinuationStub.pin`; element reference and printed `DD3.1`/ `DA1.2` match the real contact | A concrete physical contact can be verified against existing Circuit |
| `device_contact` | exact `PinRef`, plus external authoritative `(kind, owner_ref) → frozenset[PinRef]` ownership | **BLOCKED** without verified inventory |
| `functional_group_contact` | same external membership requirement; e.g. A7:X16 may name the group but only a *resolved actual PinRef* establishes contact evidence | **BLOCKED** without verified inventory |

`netrefs_to_json(..., verified_address_owners=...)` and
`netrefs_from_json(..., verified_address_owners=...)` fail closed on
an unresolved device/group. The caller must supply the *actual*
authoritative group/device inventory, not a map inferred from printed
addresses. The external map is rechecked at import. `schema_version=1`
forbids `address_bindings`; v2 without all bindings is invalid.
The decoder always requires the original real Circuit with its
exact immutable PinRef membership; no editing of `Circuit.Net` occurs.

### Layout / measured graphic protection

`sheet_svg(project, sheet_id, font_path=...,
external_keepouts=(Box(...),), review_overlay=...,
review_connection_zones=...)` now checks **actual OpenGost Type A
ink** (the exact existing measured font path / hash), its padding,
the short H/V conductor stroke, the termination arrow polygon including
stroke, other continuation marker graphics, and caller-authored external
Box obstacles (nearby DA/DD/VT outlines, annotations, frame or title
block). A conservative 10mm A4 interior remains **editorial** and is
NOT asserted as the ESKD mandatory print margin. Actual A4 dimensions,
real baseline, real glyph ink and 300 DPI raster remain independently
checked in CI.

`external_keepouts` must exclude the explicitly authored contact aperture
at the start of a local wire so the component's genuine pin can connect.
A violation yields typed `E3_CONT_GRAPHIC_EXTERNAL_COLLISION`,
`E3_CONT_TEXT_EXTERNAL_COLLISION`,
`E3_CONT_GRAPHIC_GRAPHIC_COLLISION`,
`E3_CONT_GRAPHIC_PAGE_OVERFLOW` or the preexisting text/line errors.
No external keepouts are permitted with unmeasured font preview.
`review_connection_zones` requires both a measured font and
`review_overlay=True`; green endpoint rectangles are flagged
`data-print=false` and **never** emitted in clean SVG/PDF.
These are editor hit targets, not a GOST mark, a fake connector or a Net.

### Three-sheet multi-Net witness

`examples.review_net_continuations_cycle7 --three-sheet --font-file ...`
creates three A4 pages, three distinct real Circuit.Nets
(`CTRL`, `REF`, `ENABLE`), four explicit pairs (including two
`CTRL` pairs spanning **all three** sheets), eight visible local real
PinRef wire stubs, synthetic physical DD/DA/VT components and exact
strict JSON v2. It deliberately contains **no** hidden cross-sheet
SVG conductor. Each page has only its own two or three short stubs.
An attempted *second* Net with the same visible CTRL label fails as
`E3_CONT_LABEL_AMBIGUOUS`, without modifying Circuit or joining Nets.
The example still uses synthetic reference designations and is
**not** a manufacturer physical-pin certification.

### Minimal ProjectService handoff; no unsafe string-based net merger

Future `ProjectService` must persist an opaque, revisioned envelope
that references the **existing authoritative Circuit** independently.
A minimal contract is:

```json
{
  "record_type": "E3_CONTINUATION_ENVELOPE_DRAFT",
  "envelope_version": 1,
  "circuit_revision_sha256": "<sha256 of canonical, authoritative real Circuit>",
  "netrefs_overlay_schema_version": 2,
  "netrefs_overlay": "<strict netrefs_to_json v2 document>",
  "verified_address_owner_inventory_revision": "<required for device/group addresses>",
  "mutation_policy": "read_only_until_typed_atomic_transaction"
}
```

Here angle-bracketed values are **placeholders**, not actual hashes.
The overlay itself contains the stable net IDs, exact frozen member PinRefs,
sheet IDs/numbers, every endpoint's local/remote address+anchor+direction,
typed address bindings, reciprocal explicit pair IDs and local real stubs.
The envelope revision must be compared against the actual current Circuit
before deserializing. A stale revision, new/unrecognized field, unverified
group membership or ambiguous equal-label multi-Net project is rejected.

A future `AttachNetContinuation` typed transaction may add **only**
endpoints/pairs/stubs to an existing validated `net_id` after a revision
compare-and-swap and full revalidation; *never* alter `Net.members`,
create PartDefinitions, or join Nets by matching `label`, `address`,
SVG proximity or bare user-provided JSON. New project formats need an
explicit schema migration; v1 ProjectService must not silently import v2.
