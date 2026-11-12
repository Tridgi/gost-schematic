# ADR-0005: Physical quantities are independent from nominal text

Status: implemented experimentally — pending manual review (2026-11-12).

## Normative reference

ГОСТ 2.702-2011 §5.3.20 **permits**, but does not mandate, abbreviated
resistance and capacitance labels beside their УГО. The Russian national
standards register marks it active.

Rules implemented by the default `eskd_compact` policy:
- 0–999 ohm: number only (e.g. `470`);
- 1–999 kilohm: number followed by **lowercase Cyrillic** `к`;
- 1–999 megohm: number followed by **uppercase Cyrillic** `М`;
- gigaohm range: number followed by **uppercase Cyrillic** `Г`;
- 0–9999 pF: numerical value in picofarads, no unit;
- 0.01–9999 µF: numerical value in microfarads, followed by `мк`.

The literal wording uses "above 10^9 ohm" but leaves exactly 1 GΩ
unclassified. This implementation makes **an explicit boundary convention**
of `1Г` for 1 GΩ, documented and covered by tests; it is not a claim that
the exact boundary is explicitly stated in §5.3.20.

The literal ranges similarly leave gaps such as 999.5 Ω, 999.5 kΩ or
9999.5 pF. The library DOES NOT invent compact syntax for these values:
it emits `NOMINAL_COMPACT_UNSUPPORTED` and uses full units, or raises
`NominalRangeError` when strict compact display is enabled.

No compact syntax for inductors is claimed based on §5.3.20; they use full
units and a warning in compact mode.

## Domain separation

1. `Quantity` stores exact SI Decimal values and a semantic kind (Ω/F/H).
2. `ComponentInstance.nominal` holds an optional quantity, not a label string.
3. `PartDefinition.nominal_kind` can restrict physical families; the
   validator reports incompatible component nominals.
4. `NominalDisplayConfiguration` contains the document default, plus
   reference-specific overrides (mode, visibility, strictness).
5. `standards.nominals.format_nominal` makes the annotation string and
   machine-readable diagnostics without mutating the quantity.
6. `bind_component_annotations` links the formatted string to the existing
   annotation engine. The label and its collision rectangle are recalculated
   on subsequent calls; the routing obstacle list must be rebuilt from the
   fresh placements.

## Full-unit mode

`full_units` uses SI-prefixed Russian unit labels separated by one space:
`2,3 кОм`, `100 нФ`, `470 мкФ`. It is a deliberately configurable
readability format, not a separate claim of normalized ESKD abbreviations.

Decimal comma is the default; decimal dot is available for interoperability.
Neither mode rounds or truncates the input quantity.

## Persistence

Quantity records have `schema_version: 1`, `kind`, and decimal-string
`si_value`. Presentation settings are saved in an independent versioned
record. Neither JSON floats nor already-formatted display strings form the
authoritative physical value. Original unit spellings may be retained later
as optional provenance, but must not affect calculations.

## Review and limitations

The actual drawing still uses a *draft* resistor UGO and a diagnostic font.
The preview's font is not verified ГОСТ type A or B. Font embedding/path
outlines, whole-sheet rerouting and official document templates remain
separate milestones.

Sources:
- https://protect.gost.ru/gost/details/d9c1c334-2a90-45cb-ac00-c31da92d706b
- https://ru.wikisource.org/wiki/ГОСТ_2.702—2011
