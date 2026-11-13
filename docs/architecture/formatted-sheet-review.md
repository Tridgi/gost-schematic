# Page compositor — rendering cycle5 (Issue #56, DRAFT)

## Contract and provenance

The **private** \`gost_schematic.rendering.formatted_sheet\` adapter wraps an already
rendered \`ExternalWireSheet\` and **does not** alter \`Circuit\`, pins,
\`ExternalWireGraph\`, UGO JSON, the public API or routing algorithms. It neither
connects nor splits electrical nets.

This implementation is a **source-based, unapproved engineering preview**, not
certification under ГОСТ/ЕСКД or validation by КОМПАС. Standard: **ГОСТ Р
2.104-2023**, effective 2024-03-01, mandatory **annex Б.1, form 1**, together
with accepted [Issue #35 normative review](../standards/issue-35-full-sheet.md).
Source graphics: [ГОСТ Р 2.104-2023, p. 11 / PDF P14](https://files.stroyinf.ru/Data/816/81679.pdf#page=15).

The page is expressed in **integer micrometres**, with SVG \`width\`,
\`height\`, \`viewBox\` and shape coordinates serialized as exact **millimetres**.
The old SVG artwork is nested under \`schematic-content\` with a **translation
only**, never a scale. Its actual endpoint data and order stay byte-identical
in the nested DOM. The page compositor adds **no clipPath and no viewBox-based
content clipping**: content too large or shifted into a reserved field causes
\`SCHEMATIC_PAGE_OVERFLOW\`. Source geometry and label boxes must already fit
the supplied inner SVG viewBox; unsupported transformed, masked or unsupported
path sources fail closed. There is no automatic paginate/scale behavior.

## Paper profiles

| Profile | Page, mm | Inner frame, mm | B.1 first-sheet form-1, mm |
| --- | --- | --- | --- |
| A4 portrait | 210×297 | [20, 5, 205, 292] | [20, 237, 205, 292] |
| A3 landscape | 420×297 | [20, 5, 415, 292] | [230, 237, 415, 292] |
| A3 portrait | 297×420 | [20, 5, 292, 415] | [107, 360, 292, 415] |

A4 landscape is **not** offered: ГОСТ Р 2.104-2023 Б.5 requires portrait
A4 with the title along the shorter side. Main form is 185×55 mm, positioned
at the lower-right inside the frame. The first-sheet paper profile explicitly
draws a 20-mm left / 5-mm top-right-bottom inner frame; page background is a
separate layer and is not confused with a formal external page border.

The main grid includes the revision-table columns 7 / 10 / 23 / 15 / 10 mm,
the 110-mm main section and 10-mm terminal section, and subdivided rows with
small graph headings. **This is a DRAFT transcription for geometry review, not
a controlled digital clone of all requisites**: additional inventory fields,
organizational additions, official signatures, dates, designations and release
approval are intentionally absent. Further 1:1 manual review against the
annex Б original print and actual font metrics is **BLOCKED** for any claim of
normative approval. Do not fill invented names or signatures.

Content is placed into a conservative inset strip above the 55-mm title:
\`x = frame.left + safe_gap ... frame.right - safe_gap\`, \`y =
frame.top + safe_gap ... title.top - safe_gap\`. This intentionally wastes
some space on A3 to guarantee no stamp overlap. The gap is a project choice
(default 2 mm), **not** a quoted ГОСТ spacing requirement. All source
coords are translated by \`offset_um\` without changing the original geometry.
The same offset can be supplied for the diagnostic SVG so text and wires
stay in exactly the same positions.

## Electronic document exceptions

\`PageProfile(mode="electronic_layout")\` leaves the paper frame and title
absent by default, **not** automatically emitting them for every electronic
SVG. This implements the distinction in ГОСТ Р 2.104-2023 **§4.2**; the final
organizational decision and contract-specific requisites remain external.

\`PageProfile(mode="electronic_layout", electronic_title_block=True)\` includes
the DRAFT first-sheet table but still omits the frame, consistent with the
allowed omission in **§5.6** (using the same 20/5/5/5 information-placement
margins). Omission of supplementary graphs and correct electronic requisite
placement remains an organizational and ГОСТ Р 2.058 policy decision.

## Visual artefacts and regression gates

Run \`python -m examples.review_formatted_sheet --font-file /path/to/OpenGostTypeA.ttf
--output-dir output/formatted-sheet-review\` after installing the same
externally licensed font used by the text measurer. This exports A4 portrait,
A3 landscape and A3 portrait **clean + diagnostic** SVGs and a manifest
recording page geometry, 6 refdes, 18 authored wire segments, 3 explicit
junctions, net names and font SHA256. The specialized CI workflow produces
matching PNGs and uploads \`draft-formatted-sheet-review\`.

Automated tests prove: physical mm page dimensions; 20/5 margins, 185×55 form;
subdivision segments; clean/diagnostic parity; unchanged pin geometry,
component names, net order, 18 source line attributes and 3 explicit dots;
stable deterministic exports; rejection of impossible margins, incorrect A4
orientation, invalid source viewBox, source drawing out of bounds, hidden
clipping and transformed content, illegal explicit placement and unplaceable
text. No renderer inference of connections at unmarked crossings.

## Limitations

- No automatic form filling, approval metadata, sheet-index logic,
  inventory supplement, multi-page splitting, print-driver/DPI validation,
  or actual paper/КОМПАС 1:1 check.
- The title headings use OpenGost Type A by *requested family name*. The font
  binary is never embedded or committed; substitution is possible. Neither
  title text fit nor every glyph curve has normative validation.
- The SVG source audit accepts the path-arcs used by the current specimen;
  unsupported transformed/cubic/unknown artwork is rejected rather than
  silently trusted. The review SVG is not a universal third-party SVG importer.
- All 19+ catalog UGO remain DRAFT. This workstream does not modify their
  symbol/physical-part definition or their normative status.
