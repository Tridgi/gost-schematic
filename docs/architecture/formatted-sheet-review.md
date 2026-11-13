# PAINT cycle5 / Issue #56 — SVG export and form-1 title review

**Status:** DRAFT, normative source checked, not an approved КД or КОМПАС file.
Existing Draft PR [#59](https://github.com/Tridgi/gost-schematic/pull/59).

## 1. Default and explicit export modes

The executable `examples/review_formatted_sheet.py` now defaults to **`--mode clean`**.
This is a **bare physical-mm SVG schematic** with no A4/A3 page, inner frame,
form-1 title or fabricated requisites, matching the visual reviewer's preference.
It emits `schematic-clean.svg` and `schematic-diagnostic.svg`.

Choose `--mode a4` for A4 portrait, `--mode a3` for A3 landscape/portrait,
or `--mode all` to export the unframed schematic *and* all three paper pages.
`--title-headings` is an **additional explicit opt-in** for form-1 structural
captions only (not completed document requisites). `--compare-c3` produces
comparison-only Figure #44 previews. Example:

```bash
python -m examples.review_formatted_sheet --font-file /path/OpenGostTypeA.ttf \
  --mode all --title-headings --compare-c3 \
  --output-dir output/formatted-sheet-review
```

For genuine field filling, the operator must separately pass
`--title-field designation=...` and/or `--title-field name=...` together
with `--mode a4|a3|all`. The same selected format receives a
`<format>-explicit-fields.svg` file, while the normal `<format>-clean.svg`
**remains completely blank** in its title table. Unknown keys, duplicate
assignments, incorrect font metrics and fields that exceed available space
fail closed; nothing is auto-shrunk or fabricated. The CI deliberately does
not emit any pretend legal signatories, part numbers, organization names,
document names or approvals. Generated manifest lists the originating
C3 version and still marks all outputs DRAFT.

The comparison and title zoom are clearly marked DRAFT. The currently accepted
source `examples/review_end_to_end_circuit.py::authored_specimen()` is unchanged.

## 2. Normative basis and explicit geometry

Source: **ГОСТ Р 2.104-2023** (effective March 1, 2024; September 2024
edition with corrections), **§§4.2, 5.1–5.2, 5.6–5.8, mandatory annex Б.1**
(form 1) and accepted [Issue #35 packet](../standards/issue-35-full-sheet.md).
Source illustration in the public [PDF, page 15](https://files.stroyinf.ru/Data/816/81679.pdf#page=15).

| Page | Canvas (mm) | Inset frame [l,t,r,b] mm | Form-1 [l,t,r,b] mm |
| --- | --- | --- | --- |
| A4 portrait | 210×297 | 20,5,205,292 | 20,237,205,292 |
| A3 landscape | 420×297 | 20,5,415,292 | 230,237,415,292 |
| A3 portrait | 297×420 | 20,5,292,415 | 107,360,292,415 |

The standard supports A4 portrait for this profile; landscape A4 is rejected.
The first-sheet block has **185×55 mm** outer dimensions. The mandatory B.1
drawing explicitly dimensions the principal **7+10+23+15+10+110+10 = 185 mm**
column widths and 55-mm height; "Лит." is represented as **three 5-mm cells**
under one caption, not an unbroken 15-mm box. The **17-mm** author-role area
must not be mistaken for a **7-mm** revision cell; former bugs placed text in
the latter and shrunk it to 1.6-mm CSS size.

`rendering/form_one.py` now owns **only** the B.1 grid geometry and cell bounds.
`rendering/formatted_sheet.py` independently places the original source SVG
with **translation only** and serializes exact mm. `write_form_one_fields`
handles only **explicit provided** values, fixed calibrated Type A h=2.5/3.5 mm,
no autofit/ellipsis. The **printed uppercase height** is checked by measuring
glyph "Н" from the declared font, rather than equating SVG font-size to cap
height. The same SHA256-identified physical font must be installed in the SVG
viewer. Text placement uses the actual measured ink bounding box, centred
horizontally and vertically with ≥0.4-mm padding from **all** cell borders.
A value that does not fit raises `TITLE_FIELD_OVERFLOW`; a false height raises
`TITLE_FONT_CAP_HEIGHT_MISMATCH`. None of these replaces human inspection.

**Default title geometry contains no text.** On explicit `--title-headings`,
only source-derived headings ("Изм.", "Лит.", "Масса", "Разраб.", etc.) are
inserted; document title, designation, organization, signature, full names,
dates and approvals are **never invented**. Non-empty user/organization
requisites are accepted only by the separate opt-in filling function.
`form-one-title-closeup.svg` (and PNG) is a 1:1 crop of the *title only*,
not a clipped version of the electrical diagram.

### Normative comparison status

**Confirmed from controlled image:** 185×55 envelope, A4/A3 page dimensions,
20/5/5/5 inner frame, 7+10+23+15+10+110+10 principal partition, 5+5+5
"Лит." cells, distinct role/revision regions, printed cap-height principle,
and applicability of electronic document exceptions.

**Still DRAFT:** complete interpretation of dashed supplementary
B.1 graphics including (27)–(35), optional additional inventory columns
outside the title box, precise caption glyph forms, per-graph legal requisites,
types/widths of all strokes at full-size printer output, font matching across
third-party viewers, approved signatures and final manual 1:1 overlay against
the edition's original printed page. The B.1-derived grid in this PR is a
source-backed experiment, **not** proof of full formal conformance.

`electronic_layout` is a separate `PageProfile`, without mandatory frame/title
under §4.2 and optionally without a frame under §5.6 when a title is selected.
When not using a paper profile, the generator does not automatically attach
them to every SVG.

## 3. Accepted post-PR62 circuit versus historical Issue #35 archive

The **current integration** now includes PR #62 (manual C3 layout correction),
the 21-UGO DRAFT catalog and the PR #39 two-pin router. Its actual
`examples/review_end_to_end_circuit.py::authored_specimen()` has **6 parts,
5 nets, 16 authored wire segments and 3 explicit junctions**, with C3 origin
**(100,80) mm**, physical pin 1=(91,80), pin 2=(109,80) mm. Symbol is
`capacitor.electrolytic` revision 1 DRAFT, not a stale UGО. The visible
TOP branch is now (40,40)→(40,80)→(91,80) mm with no dogleg.

The **archived Issue #35** fixture is independently stored, unchanged in
`tests/fixtures/electrical-cycle3/end-to-end-{clean,review}.svg`:
historical C3 origin (100,75) mm, pin 1=(91,75), pin 2=(109,75),
**18 wires** and 3 drawn junctions. The old TOP segment
(84,80)→(84,75) mm explains the removed backtrack.

`examples/review_c3_placement_proposal.py` now only **reads both**:
archived historical SVG fixtures in read-only mode, and current authoritatively
validated PR62 `authored_specimen()`. It does **not** move C3 or create an
alternative `Circuit`. It compares archived vs current
`c3-archived-issue35-{clean,diagnostic}.svg` and
`c3-current-{clean,diagnostic}.svg`, alongside the side-by-side PNG and
manifest recording provenance, both pin positions, both wire counts and
unchanged junction locations. The source fixture filenames are compatibility
inputs; their byte content is never regenerated by PAINT.

This rendering-only preview does **not** turn Issue #44 into a router or
change the accepted electrical model, public API, source examples, physical
passports or catalog. All live wire/layout/physical/ERC checks refer to the
accepted 16-segment graph, while archive checks strictly validate the 18-wire
historical fingerprint. Route safety remains ELEKTRIK's responsibility.

## 4. Positive / negative regression evidence and limitations

`tests/test_rendering_formatted_sheet.py`: three paper formats,
exact title/frame bounds, official column partitions and 3 × 5-mm letter
cells, measured text-centering, blank inputs, illegal field names, long-field
overflows (no font shrink), cap-height mismatches, viewport/stroke clipping,
invalid placement, unchanged physical pins and wire/junction semantics.
`tests/test_rendering_c3_placement_review.py`: current C3 symbol ID/revision,
physical polarity/contact positions and read-only candidate, original 5-net
invariance and validators. Font installer token is restricted to
`api.github.com`, never leaked to redirected asset hosts.

`.github/workflows/rendering-review.yml` runs these checks with the externally
installed OpenGost Type A font, generates bare SVG, page SVG, title close-up
and C3 comparisons, rasterizes all as PNG, checks the manifest and uploads
`draft-formatted-sheet-review` (font binary remains out of the repository).
Human visual review of the exported PNG is mandatory before coordinating merge.
