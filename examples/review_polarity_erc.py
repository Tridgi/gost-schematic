"""Reproducible polarity ERC review: electrical pins vs explicit net voltages.

Produces JSON evidence; not a drawing, finished SPICE model or proof of
electrolytic capacitor safety in every operating condition.
"""

import argparse
import json
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.potentials import NetPotential, PotentialScenario
from gost_schematic.validation.polarity_checks import assess_polarity, polarity_diagnostics


def _case(name: str, *, reversed_connection: bool = False) -> Circuit:
    plus_net, minus_net = (
        ("RETURN", "SUPPLY") if reversed_connection else ("SUPPLY", "RETURN")
    )
    component = ComponentInstance(
        "C2", "capacitor.polarized", Point(20000, 15000),
        Transform(rotation=90, mirror_x=True),
    )
    return Circuit((component,), (
        Net(plus_net, (PinRef("C2", "1"),)),
        Net(minus_net, (PinRef("C2", "2"),)),
    ))


def build_report() -> dict[str, object]:
    source = files("gost_schematic").joinpath(
        "catalog/parts/capacitors/polarized.json"
    )
    part = load_part(Path(str(source)))
    assert part.voltage_orientation_rule.value == "positive_not_below_negative"
    known = PotentialScenario("DC nominal", (
        NetPotential.from_volts("SUPPLY", "12", reference_id="dc-common"),
        NetPotential.from_volts("RETURN", "0", reference_id="dc-common"),
    ))
    missing = PotentialScenario("Unknown supplies", ())
    cases = (
        ("forward", _case("forward"), known),
        ("reversed", _case("reversed", reversed_connection=True), known),
        ("unknown", _case("unknown"), missing),
        ("no_operating_point", _case("no_operating_point"), None),
    )
    results = []
    for name, circuit, scenario in cases:
        assessment = assess_polarity(
            circuit, {part.identifier: part}, scenario=scenario,
        )[0]
        messages = polarity_diagnostics((assessment,))
        results.append({
            "case": name,
            "status": assessment.status.value,
            "component": assessment.component,
            "positive_pin": assessment.positive_pin.number,
            "negative_pin": assessment.negative_pin.number,
            "positive_net": assessment.positive_net,
            "negative_net": assessment.negative_net,
            "scenario": assessment.scenario,
            "differential_volts": (
                str(assessment.differential_volts)
                if assessment.differential_volts is not None else None
            ),
            "explanation": assessment.explanation,
            "diagnostics": [
                {"code": issue.code, "severity": issue.severity.value}
                for issue in messages
            ],
        })
    return {
        "schema_version": 1,
        "technical_status": "experimental ERC; user approval pending",
        "physical_terminal_roles": {
            pin.number: pin.polarity.value for pin in part.pins
        },
        "warning": (
            "Single operating-point verification cannot guarantee no reverse "
            "voltage during startup, faults, AC ripple, or transients."
        ),
        "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("output/polarity-erc-review.json"),
    )
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for case in report["cases"]:
        print(f"{case['case']}: {case['status']}")
    print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
