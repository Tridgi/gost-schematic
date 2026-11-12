# Inductor and choke family — ГОСТ 2.723-68 (draft profile)

**Status: implementation is experimental. No UGO is approved by the user yet.**

## Standards and verified regulatory scope

ГОСТ 2.723-68 is **currently active** in the Rosstandart standards register,
including amendments 1, 2 and 3:
https://protect.gost.ru/gost/details/69e5c69a-bbb9-4a6a-a8d1-2cf54c2a2164

- Section 4: expanded transformer/autotransformer windings are a chain of
  semicircles.
- Table 1: basic winding; magnetic core styles, ferromagnetic, gapped,
  magnetodielectric, ferrite; ferrite uses an emphasized solid stroke;
  a metal nonmagnetic core is marked by its chemical symbol (e.g. Cu).
- Table 2: examples of air-core inductors, reactors, taps, sliding contacts,
  magnetodielectric core and tuning, nonmagnetic copper core tuning,
  ferromagnetic choke, coaxial choke, three-phase choke, variometer,
  goniometer and transformer configurations.
- The number of semicircles and terminal directions is NOT prescribed by the
  standard (table 1 notes).

Representative images of the original table:
https://files.stroyinf.ru/Data2/1/4294833/4294833337.htm

**Geometry note:** the implemented default `r=2 mm`, 4 humps, lead
length 4 mm, winding stroke 0.3 mm and all obstacle padding are catalog
draft parameters, not a claim that the standard fixes these values.
The generator accepts 1.5–4 mm radius within the currently selected review
profile, and remains marked `draft` until checked against the original
drawings and user-provided KOMPAS sources.

## Implemented variations

Each variation has a separate JSON definition in `catalog/inductors/`.
Each passport has a `normative_basis` text and a `normative_relation`
(`table_2_example`, `table_1_composition`, or `editorial_adaptation`).
This provenance identifies whether a symbol corresponds to an illustrated
example or to a reviewed composition; it is NEVER a certificate of conformity.
All are generated from the SAME semantic winding construction function,
which avoids modifying duplicate drawing code.

| Variant | Core / modulation | Electrical pins | Status |
|---|---|---|---|
| `inductor.air_core` | no core | two | draft |
| `inductor.ferromagnetic` | solid ferromagnetic core | two | draft |
| `inductor.gapped_core` | interrupted ferromagnetic core | two | draft |
| `inductor.ferrite` | heavy core stroke (2 × base) | two | draft |
| `inductor.magnetodielectric` | dashed core stroke | two | draft |
| `inductor.trim_magnetodielectric` | tunable core arrow + dashed core | two | draft |
| `inductor.trim_copper` | nonmagnetic core + `Cu` label | two | draft |
| `inductor.tapped` | one real tap | three | draft |
| `inductor.double_tapped` | two real taps | four | draft |
| `inductor.sliding_contact` | movable contact | three | draft |
| `inductor.double_sliding` | two movable contacts | four | draft |
| `inductor.variable` | variable inductance modifier | two | draft |
| `choke.air_core` | un-cored choke | two | draft |
| `choke.ferromagnetic` | ferromagnetic choke | two | draft |
| `choke.ferrite` | ferrite choke | two | draft |

`inductor.variable` and `choke.air_core/ferrite` are practical editorial
variations built from the standard's elementary shapes. They are NOT
independently certified Table-2 rows.

### Explicitly NOT included

- True 3-phase, coaxial or power-supply reactor symbols (a **different
  topological and/or multiline arrangement**, not a two-pin inductor variant).
- Transformers, autotransformers and multiwinding coupled systems: require a
  magnetic-coupling model and more than one winding with independent terminals.
- Exact adjustable core nomenclature, goniometer and variometer-specific
  topology. These should be separate families after normative/user review.
- Voltage/current/flux ratings, permeability and nonlinear B-H simulation.

The family structure is ready for those components later without pretending
one coil covers all cases.

## Data architecture

- `catalog/inductors.py`: `InductorSpec`, `CoreKind`,
  `AdjustmentKind`, `build_inductor` and `load_inductor`.
- `catalog/inductors/<name>.json`: versioned style and terminal intent.
- `core/geometry.py`: real `Semicircle` and `StyledLine` primitives.
- `core/transforms.py`: single-point exact quarter-turn/mirror transformations
  of arcs, styled core lines, and other shapes.
- `rendering/primitives.py`: one renderer for all SVG targets; real `A`
  paths (not approximated jagged polylines).
- `SymbolDefinition`: distinct keepout, graphics, pin identity and font-measured
  literal label slots (for metal marking `Cu`).
- `PartDefinition`: physical START, END, TAP1/TAP2 or SLIDER1/SLIDER2
  contacts; all passive, nonpolar, with SI inductance values.
- `validation/circuit_checks.py`: checks mapping to actual netlist pins.
- `engines/sheet_layout.py`: protects arc bounds AND individually styled
  core strokes; respects text clearances and pin escape corridors.

## Controls, review and limitations

- Rotating/mirroring the UGO keeps physical contact numbering and pin role
  intact; the arc bulge is transformed.
- Changing `turns` regenerates the winding without modifying symbols.
- Tap wires and slider arrows are visually separate from netlist connectivity;
  their graph terminals are actual declared numbered pins.
- Text nominal `33 мкГн` is generated in full SI format. The current
  `eskd_compact` policy does not invent a compact inductance rule because
  ГОСТ 2.702-2011 §5.3.20 covers resistor/capacitor compact labels.
- Coupled coil polarity dots, interwinding insulation, shield and magnetic
  orientation will need distinct symbols and models in the next family.

## Reproduction

```bash
git switch feature/parametric-inductors-gost2723
python -m pip install -e ".[dev]"
pytest -q
ruff check .
python scripts/install_opengost_type_a.py
fc-cache -f
FONT_FILE="$(find "$HOME/.local/share/fonts" -type f -iname '*TypeA*.ttf' | head -1)"
python examples/review_inductors.py \
  --font-file "$FONT_FILE" --font-family "OpenGost Type A" \
  --output-dir output/inductors
```

CI publishes `draft-gost2723-inductor-family` with clean/review SVG,
font-rasterized PNG, a versioned JSON manifest identifying each UGO,
and **30 individual SVGs** (clean/overlay for each of 15 variants).
