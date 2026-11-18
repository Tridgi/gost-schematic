# Stage 0.7 — sheet-level reference/nominal placement

Status: **experimental and awaiting the user's approval**. This module does not
approve a component or replace a production schematic editor.

## Normative decisions and non-normative preferences

ГОСТ 2.702-2011 §5.3.11 specifies positional designators **above or to the
right of an element's UGO**, with an allowance inside a rectangular UGO.

The new sheet policy applies:
- REFDES: above the global symbol body, with a fallback on the right.
- VALUE: below the global body by default, then right/below or left/below.

The VALUE placement is a **configurable editorial preference**, not a claim
of a mandated ГОСТ position.

Offsets are `SheetLabelProfile.body_gap_um=1700` and
`side_gap_um=2000`. These are draft layout clearances, **not ГОСТ UGO
dimensions**. The local symbol catalog keeps independently editable slots;
the sheet engine resolves its own global candidates and does not modify
the symbol definition or the electrical model.

## Architecture

`engines/sheet_layout.py` is the orchestration layer:
1. Collect component instances from `Circuit` and lookup immutable symbols.
2. Transform every symbol's body and connection corridors to global coordinates.
3. Bind instance nominals using the established ESKD/full display settings.
4. Create global candidate anchors for positional references and values.
5. Call `place_annotations` once for ALL labels with ALL symbol and pin
   obstacles and any given wire geometry.
6. Validate overlaps, duplicate references, missing symbols, and pin exits.
7. Return immutable `SheetLayout(placements, diagnostics)`.

The rotation of an UGO transforms its geometry, NOT the reading orientation of
its reference and value labels. This keeps those labels horizontal on the
drawing regardless of a 90/180/270-degree UGO rotation.

`rendering/sheet_svg.py` uses already-resolved geometry, not circuit
inference or string formatting. The clean mode excludes all debug geometry;
review mode shows individual bounds and pin-corridor rectangles.

Any change in nominal value, display mode, component transform or font requires
a new call to `layout_sheet`, and new router obstacles from the returned
placements. The function is deterministic but **not incremental**:
recomputation is whole-sheet at this experimental stage.

If the sheet cannot accommodate a label, `ANNOTATION_UNPLACEABLE`
is returned as an ERROR, rather than silently moving text on top of another
element. Graphic overlaps are diagnosed separately from text overlaps.

## How to inspect it

Install the experimental branch in a Codespace:
```bash
git fetch origin
git switch feature/sheet-annotation-layout
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

Use the diagnostic font already available in the Linux environment:
```bash
FONT_PATH="$(fc-match -f '%{file}' 'DejaVu Sans')"
python examples/review_sheet_annotations.py \
  --font-file "$FONT_PATH" --font-family "DejaVu Sans" \
  --output-dir output/sheet-review
```

The example outputs six SVGs: ESKD compact, full units and hidden nominal,
each with a clean and a review-overlay variant. The fixture places four
resistors including one rotated 90 degrees.

## Quality and future requirements

- Check with a legitimately licensed ГОСТ type A/B font and compare actual
  FreeType metrics with final CAD vector or embedded-font export.
- Match the resistor's actual normative geometry and text arrangement to
  KOMPAS source and user approval. The resistor remains DRAFT.
- The sheet does **not** route wires; it only accepts existing wire obstacles.
- It does not place components automatically or select optimal global layouts.
- Full pin labels and multiline IC texts need specialized slot generation.
- Approved textual exceptions (leaders, internal IC markings, net labels)
  must eventually be explicit rules, not blanket owner-based exemptions.
- Recompute only affected areas using a spatial index in a later performance
  milestone; do not optimize before tests and a realistic benchmark.

Normative source:
- ГОСТ 2.702-2011, §5.3.11, https://meganorm.ru/mega_doc/norm/gost_gosudarstvennyj-standart/3/gost_2_702-2011_mezhgosudarstvennyy_standart_edinaya_sistema.html
