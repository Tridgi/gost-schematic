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

**Now implemented as opt-in DRAFT:** true TOP/BOTTOM source physical terminal mapping according to ГОСТ 2.743-91 §2.1.6/fig.3 and ГОСТ 2.759-82 §1.8, not simply a D4 rotation of an L/R source. Separate explicit main function and auxiliary text orientation 0° or 90°, all eight D4 placement transformations, and externally supplied world endpoints retained at integer-µm equality. See the new ic_orientation module. Number placement for genuinely top/bottom source leads, inverse flow arrows and actual 90° function lettering require independent ESKD image sign-off: passing programmatic geometry does NOT mean fully source-certified pictograms. Function remains first main-field row in the local semantic layout. Opposite source side combinations fail closed. 

**Intentional BLOCKED modes:** reverse information flow needing ESKD arrows; specific analog math/logic/inversion/NC/OC/power indicator marks; real manufacturer full pin maps; caller production sheet integration; certified 1:1 paper print. Never infer missing content from DA1/DD1 prefix.

## Evidence

Run the sample command: python -m examples.review_ic_cycle7 --font-file REAL_FONT_PATH --output-dir output/ic-cycle7 .

The gallery uses installed OpenGost Type A at measured Cyrillic cap h=3500µm (SVG font em can differ). Explicitly synthetic test parts TEST_IC_4/8/14/40/64: one 8-pin analog DA1, four digital DD1, long Cyrillic labels, special arrows/numerals, 1/10/40 pin numbers, optional empty fields and zone separators. Every test output now has **two source orientations**, 5 L/R and 5 true TOP/BOTTOM, with clean and diagnostic SVG for each, real physical 300-DPI PNG (20 raster files total), and a 5×2 comparative visual montage (not scale 1:1 print). The metric JSON contains all source physical world endpoints, 1 mm project run-to-stroke clearances, 3.500 mm actual Type A Cyrillic cap-height, font SHA, glyph review boxes and exact word ink. A small sample of each individual glyph box is checked against real black glyph pixels in the raster preview. Kerning-aware full-text-run ink is authoritative; individual-codepoint bbox is a diagnostic subregion clamped to its parent to avoid falsely failing on context-sensitive shaping. Source font binary is never embedded or redistributed.

Tests use separate synthetic deterministic font metrics for data-contract invariants; gallery uses actual OpenGost Type A/Pillow and verifies SHA. Large 64-pin tall IC must fail if the selected page zone is smaller; it is not shrunk to A4.

## Acceptance gates

ESKD #91 must independently approve source-specific DA/DD functions, numbers and 1:1 modular drawings, including Table19 ratios; no approval is inferred from a successful code test. ELEKTRIK #87 must publish stable immutable physical source and net ownership, so PAINT can add a read-only contract adapter without changing real physical PinRef Points. MAIN2 must approve any public E3 SVG/page API. QA to compare 4/8/14/40/64 and transformations, multiple logical unit views of one physical package, true NC/no-net behavior, overlapping other UGO/wires, and 1µm negative cases. Everything remains DRAFT/BLOCKED until these gates close.

**No merge or other branch mutations performed.**


## 14 November final deep owner verification additions

### True vertical field geometry and exact external resolved contacts

Source TOP input and BOTTOM output are explicitly declared in IcOrientation.TOP_BOTTOM. A private D4 composition maps the vertical body's LOCAL main region to a canonical measured composer while preserving the externally resolved PinRef→Point in WORLD coordinates. Source pins never mutate and the external lead ends exactly at the provided coordinate; mismatch by 1µm raises IC_PIN_ANCHOR_MISMATCH. This is not the same as creating a left/right view then rotating it. The first main function row is retained under transform; field rows, separators, outer frame, pin numbers, DA/DD refdes and all glyphs have independent protected ink regions. Main function rotation (0 or approved 90 candidate) and other field lettering rotation are controlled independently; arbitrary 270-degree text rotation is rejected. The whole symbol may still use eight conventional D4 poses. Refdes chooses a physical WORLD side with no source pins, avoiding collisions after mirror/rotation, and fails closed IC_REFDES_UNPLACEABLE if none exist.

Project values: M=2.500mm, row pitch 7.500mm in the five actual Type A cases (greater than the recommended ≥2M), h=3.500mm, stroke 0.300mm, enforced glyph-run ink clearance minimum 1.000mm. **Neither selected M nor absolute 1mm number is unconditionally prescribed for every IC by ГОСТ 2.743-91**. 64-terminal horizontal sample body 80×247.5mm; vertical sample 247.5×80mm. Neither may be silently shrunk to the selected A4 safe zone; larger A3 landscape can accommodate an explicitly positioned vertical variant. All sizes are based on real glyphs, not char counts.

### Real external electrical model owner #97

The optional ic_electrical_binding module lazily imports the **actual typed ELEKTRIK PR #97** IcPaintBinding at runtime. On a verified binding it compares all physical PinRefs with the source resolve_ic_pin_positions, verifies the immutable device/unit/side/row contract and confirms the source Circuit Nets do not change before/after rendering. Explicit model reflow and a new IcSymbolSpec revision come from ELEKTRIK's separate propose_ic_paint_binding; PAINT does not re-resolve the model's previously approved Points. Only correctly typed input can be rendered; missing unmerged source is IC_ELECTRICAL_MODEL_UNAVAILABLE. This adapter is optional and does not extend the default ordinary sheet renderer, Circuit/Net public API or physical symbol catalog. In current #97 owner code, TOP/BOTTOM authoring is still rejected by its explicit source-specific gate: **true vertical end-to-end typed owner bridge is BLOCKED**, even though PAINT source vertical renderer and 300DPI gallery now work. No fake PASS claim.

The pinned-source ephemeral GitHub workflow fetches exact ELEKTRIK SHA c0f9ca684852b148d040d864772c8d74cd1ddac7, overlays only temporary runner files (including authentic owner synthetic_ic fixture), exercises the owner's 24 dedicated tests under real verified external Type A, and independently renders 12 synthetic analog/digital package sets 2/4/8/14/40/64 through the typed adapter. The owner source is not copied into PAINT PR and no physical model data are mutated.

### Issue #100 green connection-target interface

ic_hotspots provides immutable editor-only IcConnectionTarget(pin_id,PinRef,external-world-Point,connectable,net_id,reason) and strict typed identity check. A separate explicitly enabled SVG layer data-layer="editor-connection-targets" can draw 0.7mm green/disabled squares over existing true points solely for diagnostic inspection; the default clean ГОСТ SVG contains **no colored targets**. The future interactive CAD UI MUST implement screen-pixel zoom-independent hit-testing, accessible hover/focus, routing, junction permissions, revision CAS/rollback and non-merging Net identity under Issue #100/#74. This PAINT PR implements **metadata and static diagnostics only**, not an interactive editor.

### Measured 10-case render/CI and regression contract

Full Type A cap 3500µm, file SHA256 f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a, no embedding/distribution. All 10 real sample bodies (L/R vs genuine TOP/BOTTOM) in mm:

| Test pins | L/R W×H | TOP/BOTTOM W×H | Real measured run-to-stroke ink gap |
| --- | --- | --- | --- |
| 4 | 37.5×22.5 | 22.5×37.5 | 1.000mm |
| 8 analog | 47.5×37.5 | 37.5×47.5 | 1.000mm |
| 14 | 55×60 | 60×55 | 1.000mm |
| 40 | 87.5×157.5 | 157.5×87.5 | 1.000mm |
| 64 | 80×247.5 | 247.5×80 | 1.000mm |

The dedicated workflow verifies all 20 SVG/PNG pairs, PNG pixel dimensions computed from physical mm and 300DPI, raster Type A glyphs in measured ink regions, source pin identity/count, clean diagnostic difference only where requested, and a full 10-case metric JSON. 21 original DRAFT catalog UGO, 16 conductors, 3 junctions and form1 regression remain unchanged.

PASS: Python static/type-safe E3 IC frame, actual Type A ink/300DPI, 1µm PinRef equality, main and optional left/right fields, 10 genuine source orientation examples, all eight D4 poses, typed real owner bridge horizontal, 2/4/8/14/40/64, NC editor target rejection, default uncolored image and existing full CI. FAIL: none remaining in supported 10-case executable regression scenarios at checked SHA. BLOCKED: physical TOP/BOTTOM typed model bridge #97 (owner revision pending), exact per-indicator and function graph conformity, full 1:1 printed and manufacturer pin evidence, interactive green UI and final QA/ESKD acceptance. This is deliberately an engineering DRAFT, not an approved ГОСТ component.

**No merge executed.**
