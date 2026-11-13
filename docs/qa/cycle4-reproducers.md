# Cycle 4: minimal independent reproductions

Historical finding baseline: `caf7db7ad22d9cd22202664471da5ff3a49a754c`. **Updated verification:** integrated validator fix #40 at `2052e9d3a903edea860c100e00609ceee3c9062b` (PR #48). All reproductions use actual catalog parts, never synthetic terminals. Run `python -m pip install -e ".[dev]"`. The fixed #40 regression is now **ordinary passing test**, not an xfail; #41 remains a separate expected failure, and newly confirmed #58 from Issue #54 has its own strict xfail until an owner fixes it.

## RESOLVED MAJOR — Issue #40: unassigned physical pin contact now produces ERROR

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
assert [issue.code for issue in diagnostics] == ["WIRE_PIN_CONTACT_UNDECLARED"]
```

With PR #48, the expected actual result is **ERROR `WIRE_PIN_CONTACT_UNDECLARED`**, with no implicit net joining. Before this fix the validator returned `[]`. Dedicated passing test: `tests/qa_wires_test.py::test_unassigned_physical_pin_never_disappears_into_a_valid_net`.

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

## Confirmed new MAJOR — Issue #54 / production fix #58

The narrower #40 fix still misses a **foreign-net interior crossing of a pin already connected to its legitimate net**. Four real resistors with physical pin #1 positioned at R1=(0,0), R2=(-20000,0), R3=(0,-10000), R4=(0,10000) µm are wired as A: R2.1→R1.1 and B: R3.1→R4.1. R1.1 is attached to A at its endpoint while B traverses it as an interior point. There is no junction.

On current integrated validator SHA `2052e9d3a903edea860c100e00609ceee3c9062b`, **actual diagnostics are empty**, not the expected `WIRE_PIN_CONTACT_UNDECLARED`. This is distinct from free-contact #40.

Dedicated D4/reversed-direction/1µm control matrix: `tests/qa_wires_test.py::test_foreign_net_interior_hits_preassigned_real_pin_without_false_short`; 16 exact-crossing inputs are strict xfail and 16 near-miss cases pass. See [Issue #58](https://github.com/Tridgi/gost-schematic/issues/58).

## Regression status after integrated #40 fix

Run `pytest -q tests/qa_catalog_test.py tests/qa_wires_test.py`. **No xfail remains for #40.** The #41 parser regression remains xfail, and new Issue #58 stays strict xfail until independently verified corrected. Do not infer junctions from SVG; an unmarked X away from a pin must not turn into a short. A correction to #58 must preserve real pin identity and all 1 µm near-miss controls.
