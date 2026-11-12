# Cycle 4: minimal independent reproductions

Baseline `caf7db7ad22d9cd22202664471da5ff3a49a754c`; these cases use the **real installed catalog** and are not geometry invented for demonstration. Reproduce with `python -m pip install -e ".[dev]"`. The failing expectations are intentionally documented as `xfail` in the QA suite, because changing production implementations is out of scope.

## MAJOR: an unassigned physical pin crossed by a wire gets no diagnostic — Issue #40

```python
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph, WireSegment, validate_external_wires,
)

root = Path(str(files("gost_schematic").joinpath("catalog")))
part = load_part(root / "parts/resistors/fixed.json")
symbol = load_symbol(root / "symbols/resistors/fixed.json")
pins = {pin.number: pin.at for pin in symbol.pins}
offset = pins["2"] - pins["1"]
first = ComponentInstance("R1", part.identifier, Point(0, 0) - pins["1"])
second = ComponentInstance(
    "R2", part.identifier, offset + Point(30_000, 0) - pins["1"]
)
circuit = Circuit(
    (first, second),
    (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
)
start = first.pin_positions(symbol)["1"]
end = second.pin_positions(symbol)["1"]
unassigned_pin = first.pin_positions(symbol)["2"]
assert min(start.x, end.x) < unassigned_pin.x < max(start.x, end.x)
graph = ExternalWireGraph((WireSegment(start, end, "SIG"),))
diagnostics = validate_external_wires(
    circuit, graph, {part.identifier: part}, {symbol.identifier: symbol}
)
print([issue.code for issue in diagnostics])  # ACTUAL: []  (undesirable silent contact)
```

Expected behavior needs an agreed precise electrical-safety contract (diagnose the unassigned connector contact without automatically joining an unmarked crossing). The observed defect is precisely that **no warning or error exists at all**. Dedicated test: `tests/qa_wires_test.py::test_unassigned_physical_pin_never_disappears_into_a_valid_net`.

## MINOR: malformed geometry JSON escapes the catalog error boundary — Issue #41

```python
from gost_schematic.catalog.loader import parse_symbol, CatalogError

data = {"schema_version": 1, "id": "qa.invalid", "geometry": []}
try:
    parse_symbol(data)
except CatalogError:
    print("Correctly rejected")
```

Actual: `AttributeError: 'list' object has no attribute 'get'`. Expected: public `CatalogError` with a helpful nested schema diagnostic. Dedicated test: `tests/qa_catalog_test.py::test_json_array_in_geometry_returns_catalog_error_instead_of_attribute_error`.

## Regression after owner fixes

Run `pytest -q tests/qa_catalog_test.py tests/qa_wires_test.py` and inspect the two known `xfail` cases. Remove the corresponding `xfail` decorators **only after** verifying fixed behavior and asserting the actual diagnostic codes. Treat `XPASS` as a request to review, not as proof the contract is satisfied. Do not change physical pin identities, guess nets from visible SVG, or drop the no-junction X-crossing behavior.
