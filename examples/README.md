# Manual review — stage 0

The only initial catalog item is an **unapproved** fixed resistor. Run from the
repository root, after installing Python 3.12+:

```sh
python -m pip install -e ".[dev]"
pytest -q
ruff check .
gost-schematic check-symbol src/gost_schematic/catalog/symbols/resistors/fixed.json
gost-schematic render-symbol src/gost_schematic/catalog/symbols/resistors/fixed.json --review-overlay --output output/resistor-review.svg
gost-schematic render-symbol src/gost_schematic/catalog/symbols/resistors/fixed.json --output output/resistor-clean.svg
```

In review-overlay mode **orange dashed lines** mark the body keepout and
**green circles** mark physical pin connection coordinates. They are diagnostic
overlays, not part of the normative UGO. The clean view omits them.

Verify the visual appearance and dimensions against the supplied KOMPAS source.
The current nominal 10 × 4 mm resistor rectangle is a **draft engineering
fixture**, not yet confirmed as normative for the required variant.
