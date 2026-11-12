# Nominal values: model → ESKD formatter → annotation → hitbox

This is a library API with command-line preview flags, not a graphical switch
widget. A future UI can bind a switch to the exact same display settings.

## Examples

| Physical quantity | `eskd_compact` | `full_units` |
|---|---|---|
| 470 Ω | `470` | `470 Ом` |
| 2300 Ω | `2,3к` | `2,3 кОм` |
| 4.7 MΩ | `4,7М` | `4,7 МОм` |
| 4700 pF | `4700` | `4,7 нФ` |
| 10 nF | `0,01мк` | `10 нФ` |
| 100 nF | `0,1мк` | `100 нФ` |
| 220 µF | `220мк` | `220 мкФ` |
| 33 µH | full units + warning | `33 мкГн` |

For compact intervals not explicitly defined by ГОСТ 2.702-2011 §5.3.20,
the formatter emits a warning and returns full units instead. The optional
strict mode raises an error, blocking silent production of a nonstandard label.

## Python API

```python
from gost_schematic.api import (
    ComponentNominalOverride,
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
    Quantity,
    Unit,
    bind_component_annotations,
    format_nominal,
)

physical = Quantity.from_unit("2,3", Unit.KOHM)
assert physical.to_record()["si_value"] == "2300"
assert format_nominal(physical).text == "2,3к"

configuration = NominalDisplayConfiguration(
    default=NominalDisplaySettings(
        mode=NominalDisplayMode.ESKD_COMPACT,
        show_nominal=True,
    ),
    overrides=(
        ComponentNominalOverride("R2", mode=NominalDisplayMode.FULL_UNITS),
        ComponentNominalOverride("R3", show_nominal=False),
    ),
)
```

Store `physical` on `ComponentInstance.nominal`. Use
`bind_component_annotations(symbol, component, style, configuration)`,
then `place_annotations(...)`, and after each mode/value change regenerate
`annotation_obstacles(new_placements)`. Never reuse the old hitbox.

The legacy `requests_for_component` string API is preserved for other
annotations. Raw value labels produce `NOMINAL_LITERAL_UNVERIFIED` warnings;
strict compact mode rejects them. Supplying both a typed nominal and the raw
`value` string is rejected because it would break data provenance.

## CLI preview (Codespaces)

```bash
python -m pip install -e ".[dev]"
FONT_PATH="$(fc-match -f '%{file}' 'DejaVu Sans')"

python -m gost_schematic.cli render-annotated-symbol \
  src/gost_schematic/catalog/symbols/resistors/fixed.json \
  --nominal 2300 --unit ohm --nominal-mode eskd_compact \
  --font-file "$FONT_PATH" --font-family 'DejaVu Sans' \
  --review-overlay --output output/resistor-eskd.svg

python -m gost_schematic.cli render-annotated-symbol \
  src/gost_schematic/catalog/symbols/resistors/fixed.json \
  --nominal 2300 --unit ohm --nominal-mode full_units \
  --font-file "$FONT_PATH" --font-family 'DejaVu Sans' \
  --review-overlay --output output/resistor-full.svg

python -m gost_schematic.cli render-annotated-symbol \
  src/gost_schematic/catalog/symbols/resistors/fixed.json \
  --nominal 2300 --unit ohm --hide-nominal \
  --font-file "$FONT_PATH" --font-family 'DejaVu Sans' \
  --review-overlay --output output/resistor-no-value.svg
```

This does **not** yet implement a GUI, editable KOMPAS integration or
sheet-wide incremental autorouting. The three SVGs demonstrate the exact
shared formatting-and-collision contract for one UGO.

## Further requirements

- Replace diagnostic font with a legitimate licensed ГОСТ A/B font and check
  SVG viewer matching/embedding, not just free font measurement.
- Keep BOM/list-of-elements descriptions separate from compact schematic labels.
- Add document-file persistence/migrations before building a full schematic editor.
- Extend typed formats for other components only after verifying the relevant
  standards; never reuse a resistor suffix rule for inductors or integrated circuits.
