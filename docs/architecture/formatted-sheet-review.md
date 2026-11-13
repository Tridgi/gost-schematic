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

## 3. Unchanged six-component topology and C3 Issue #44

Original authored device inventory is R1, R2, C1, C2, L1, C3; **five nets,
18 authored wire segments, three explicit junctions**. The renderer only
relocates its source SVG as a single group. No net inference is performed
from geometric X/T crossings. Original C3 uses exact versioned
`capacitor.electrolytic` **revision 1, DRAFT** with plus pin 1 at
(91,75) mm and minus pin 2 at (109,75) mm (C3 origin (100,75) mm).
Its shape may be deliberately a wide electro­lytic and is *not* evidence of a
stale catalog. C3's dogleg is a **separate authored placement fault**.

Issue [#44](https://github.com/Tridgi/gost-schematic/issues/44) records
the exact ELEKTRIK patch plan: move C3 to (100,80) mm and replace the old
4-segment TOP + 2-segment RIGHT branch with 2+2 segments, preserving all 3
junctions and 5 nets. `examples/review_c3_placement_proposal.py` constructs
only an **independent ephemeral copy** and outputs cropped original / candidate
clean+diagnostic SVG, and a JSON before/after. It validates the candidate with
the existing electrical/wire checkers before generating anything; existing
authoritative `authored_specimen`, catalog JSON, data models and tests are
**not modified**. The candidate has **16 wire segments**, not 18, and is
explicitly **NOT MERGED / only concept** pending ELEKTRIK coordinator approval.

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
