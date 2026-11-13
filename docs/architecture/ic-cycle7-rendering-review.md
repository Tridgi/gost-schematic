# PAINT Cycle 7 — rectangular E3 IC renderer review (Issue #88)

**Status:** independent experimental DRAFT. Draft PR #93; NOT E1 FunctionalBlock, not a physical footprint, and no code changes in L1 PR #79 or existing 21-Ugo catalog. No merge.

## Source-checked normative / editorial separation

ГОСТ 2.743-91 §§2.1.1–2.1.9: digital IC rectangular main field, optional 0/1/2 left/right auxiliary fields, function on first main row, pin labels in supplementary zones and eligible separators. Height depends on pin count/rows/physical font; width on printed glyph content (including spaces). ГОСТ 2.743 §2.2.1 DOES NOT define a fixed character maximum. §2.1.5 forbids pin lines on rectangle corners. §2.3.12 requires physical pin numbers ABOVE external line, left of inputs or right of outputs, with gap-in-lead alternative; numbering is NOT a pin function label inside field. Appendix 5 Table19 is RECOMMENDED and specifies pin line spacing at least 2M, not a universal absolute M=2.5mm. ГОСТ 2.759-82 governs analog function pictograms separately. ГОСТ 2.304-81 Type A physical Cyrillic height h is measured by font glyph ink, not SVG CSS em. ESKD #91 latest unmerged standards dossier independently verifies these requirements; it is not a sign-off of the generated IC.

**Editorial pending ESKD #91:** M=2500µm; pitch at least 2M; separate *project* ink-to-stroke guard=1000µm, line stroke=300µm, minimum main field width=15000µm, initial lead=8000µm rounded upward to M, refdes gap=1600µm. Do NOT present these as fixed mandatory ГОСТ dimensions; numeric profiles configurable, full actual appendix-5 dimensional validation still BLOCKED. No upper limit on text length; no silent shrink, ellipsis or unapproved grapheme wrapping.

## Read-only two-phase contract with ELEKTRIK #87

1. IcFieldContent holds the primary function plus following information rows, optional supplementary left/right rows and optional horizontal zone separators. Empty auxiliary fields are omitted.
2. ResolvedIcPin holds exact physical number distinct from displayed pin label, side, drawing row, identity, electrical role, optional shared logical row_key, and an **authoritative externally resolved WORLD Point at the end of the lead**, not on the UGO frame.
3. propose_ic_dimensions reads PillowTextMeasurer real FreeType ink boxes in every existing text row and pin-number label. Row pitch is ceiling-to-module of maximum of minimum 2M and measured ink-height+2×padding+stroke; field width is module-rounded maximum measured glyph ink-width+2×padding+stroke; height is the number of required pin/contents rows times pitch. Lead length is rounded up to fit real physical number ink and guards. This step **never changes Points**.
4. ELEKTRIK is required to re-resolve pin coordinates if an IC body grows; otherwise fail IC_PIN_ANCHOR_MISMATCH. render_resolved_ic validates every pin against exact transformed frame-side intersection PLUS selected outward lead length. Terminal Point is compared by exact integer µm equality with no tolerance or rounding. SVG lead begins at body and ends at the unchanged supplied external Point; connection identity is not inferred from stroke geometry.
5. Existing Circuit, Net, PartDefinition, PinRef, E3 symbol catalog and ordinary render_sheet_svg APIs are NOT touched. A separately reviewed adapter will be required when ELEKTRIK publishes typed IcSymbolSpec and IcDeviceDefinition. Multi-unit ownership, real pin maps, NC/power and manufacturer datasheet evidence are entirely ELEKTRIK's responsibility.

## Full ink safety and transform behavior

Graphic stroke boxes are distinct for outer frame (including line width), field separators, functional zone lines and each external physical lead. Actual labels have separate FreeType run ink boxes for function, extra rows, pin functions, physical numbers and external DA1/DD1. Optional detailed diagnostics also compute kerning-aware per-character FreeType boxes, solely as an extra visual audit; full text-run ink is authoritative. Text/text and text/stroke guards reject collisions before SVG, including pin number overlap. Explicit neighbor obstacles and optional page Box trigger IC_OBSTACLE_COLLISION / IC_PAGE_OVERFLOW, not silent scale. Font SHA-256 travels in SVG/JSON. All four orthogonal rotations and both mirror states preserve physical pin identity and text upright; impossible text fit or reversed-role policy fails closed rather than clipping.

**Intentional unsupported modes, DRAFT:** actual top/bottom physical terminal mapping; reversing logical input/output orientation that needs arrows; device-specific inversion/power/NC indicator glyphs; manufacturer-backed pin inventory; automatic integration with true IcSymbolSpec; certified paper print. Never infer missing content from an analog DA label or bare DD rectangle.

## Evidence

Run the sample command: python -m examples.review_ic_cycle7 --font-file REAL_FONT_PATH --output-dir output/ic-cycle7 .

The gallery uses installed OpenGost Type A at measured Cyrillic cap h=3500µm (SVG font em can differ). Explicitly synthetic test parts TEST_IC_4/8/14/40/64: one 8-pin analog DA1, four digital DD1, long Cyrillic labels, special arrows/numerals, 1/10/40 pin numbers, optional empty fields and zone separators. Every test output has clean SVG, diagnostic SVG, real 300DPI PNG with physical mm sizes and retained DPI metadata, a 5-panel visually scaled overview (not a scale 1:1 print), exact per-pin endpoint map and full measured glyph/text/stroke hitboxes in ic-metric-audit.json. Source font binary is never embedded or redistributed.

Tests use separate synthetic deterministic font metrics for data-contract invariants; gallery uses actual OpenGost Type A/Pillow and verifies SHA. Large 64-pin tall IC must fail if the selected page zone is smaller; it is not shrunk to A4.

## Acceptance gates

ESKD #91 must independently approve source-specific DA/DD functions, numbers and 1:1 modular drawings, including Table19 ratios; no approval is inferred from a successful code test. ELEKTRIK #87 must publish stable immutable physical source and net ownership, so PAINT can add a read-only contract adapter without changing real physical PinRef Points. MAIN2 must approve any public E3 SVG/page API. QA to compare 4/8/14/40/64 and transformations, multiple logical unit views of one physical package, true NC/no-net behavior, overlapping other UGO/wires, and 1µm negative cases. Everything remains DRAFT/BLOCKED until these gates close.

**No merge or other branch mutations performed.**
