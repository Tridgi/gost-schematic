# Electrical pins and conservative capacitor polarity checks

This library can now *identify* a capacitor's `+` and `−` contacts,
but it must not claim a connection is safe without electrical information.

## Model and API

```python
from gost_schematic.api import (
    NetPotential, PotentialScenario, assess_polarity,
    polarity_diagnostics, load_part,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef

part = load_part(
    "src/gost_schematic/catalog/parts/capacitors/polarized.json"
)

circuit = Circuit(
    (ComponentInstance("C2", part.identifier),),
    (
        Net("SUPPLY", (PinRef("C2", "1"),)),
        Net("RETURN", (PinRef("C2", "2"),)),
    ),
)
case = PotentialScenario("Nominal DC", (
    NetPotential.from_volts("SUPPLY", "12", reference_id="dc-common"),
    NetPotential.from_volts("RETURN", "0", reference_id="dc-common"),
))

result = assess_polarity(circuit, {part.identifier: part}, scenario=case)
assert result[0].status.value == "forward"
assert result[0].differential_volts == 12
```

For a reversed hookup, swapping the two nets gives `reversed` and
`POLARITY_REVERSED` in `polarity_diagnostics` and `validate_circuit`.
Changing symbol orientation or mirror flags **does not** change pin
identity or the voltage difference. Netlist connectivity is not inferred
from line crossings.

## Review artifact

```bash
python examples/review_polarity_erc.py --output output/polarity-erc-review.json
```

CI publishes `polarized-capacitor-erc-review` (JSON) with cases
`forward`, `reversed`, `unknown` and `no_operating_point`. All numbers
are exact decimal strings in volts.

## Safety boundary

A static rule cannot establish an electrolytic capacitor's safety in
switching, start-up or negative half-cycles. Do not treat `forward`
as proof of electrical correctness across operating conditions. For
power supplies, a later ERC/analysis module should also consider
rated voltage, reverse tolerance, ripple and startup/fault scenarios.

A disconnected pin or missing net potential remains `unknown`, not
`forward`. Equal potentials remain `zero_bias`, which is not proof
of intended orientation.

The polarized capacitor UGO and ГОСТ Type A outline remain **draft**
until the user approves them.
