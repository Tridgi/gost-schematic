"""Conservative ERC for opted-in polarized two-terminal parts.

The evaluator cannot infer voltages from net names, wire colors or a drawn
ground mark. It compares explicit signed, same-reference net potentials at
ONE declared operating point. For alternating, transient or unspecified
conditions, the result is NOT a lifetime safety guarantee.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import TerminalPolarity
from gost_schematic.model.potentials import PotentialScenario


class PolarityStatus(str, Enum):
    FORWARD = "forward"  # V(PLUS) > V(MINUS) at this operating point
    REVERSED = "reversed"  # V(PLUS) < V(MINUS)
    ZERO_BIAS = "zero_bias"  # equal potentials: direction not established
    UNKNOWN = "unknown"  # missing or incomparable evidence


@dataclass(frozen=True, slots=True)
class PolarityAssessment:
    component: str
    positive_pin: PinRef
    negative_pin: PinRef
    positive_net: str | None
    negative_net: str | None
    scenario: str | None
    status: PolarityStatus
    differential_volts: Decimal | None
    explanation: str


def _pin_net_membership(circuit: Circuit) -> dict[PinRef, set[str]]:
    result: dict[PinRef, set[str]] = {}
    for net in circuit.nets:
        for member in net.members:
            result.setdefault(member, set()).add(net.name)
    return result


def assess_polarity(
    circuit: Circuit,
    parts: Mapping[str, PartDefinition],
    *,
    scenario: PotentialScenario | None = None,
) -> tuple[PolarityAssessment, ...]:
    """Assess only parts that *explicitly* request a differential voltage rule.

    The netlist is semantic and independent of placement/mirroring. Unsupported
    component classes (such as diodes) must not inherit a capacitor rule simply
    because they expose two poles or anodes/cathodes.
    """
    membership = _pin_net_membership(circuit)
    potentials = scenario.by_net() if scenario is not None else {}
    outcomes: list[PolarityAssessment] = []

    for component in circuit.components:
        part = parts.get(component.part_id)
        if part is None or part.voltage_orientation_rule == VoltageOrientationRule.NONE:
            continue

        physical_plus = next(
            pin.number for pin in part.pins if pin.polarity == TerminalPolarity.POSITIVE
        )
        physical_minus = next(
            pin.number for pin in part.pins if pin.polarity == TerminalPolarity.NEGATIVE
        )
        pos = PinRef(component.reference, physical_plus)
        neg = PinRef(component.reference, physical_minus)
        plus_nets, minus_nets = membership.get(pos, set()), membership.get(neg, set())
        plus_net = next(iter(plus_nets)) if len(plus_nets) == 1 else None
        minus_net = next(iter(minus_nets)) if len(minus_nets) == 1 else None
        status = PolarityStatus.UNKNOWN
        delta = None
        explanation = "No operating-point potentials supplied"

        if plus_net is None or minus_net is None:
            explanation = "One or both physical terminals have no unambiguous net"
        elif scenario is None:
            explanation = "Both terminals are connected, but no potentials were supplied"
        elif plus_net not in potentials or minus_net not in potentials:
            explanation = "Potential is missing for one or both connected nets"
        elif potentials[plus_net].reference_id != potentials[minus_net].reference_id:
            explanation = "Potentials use different reference coordinate systems"
        else:
            delta = potentials[plus_net].volts - potentials[minus_net].volts
            if delta > 0:
                status = PolarityStatus.FORWARD
                explanation = "Positive terminal has higher potential in this scenario"
            elif delta < 0:
                status = PolarityStatus.REVERSED
                explanation = "Positive terminal has lower potential than negative terminal"
            else:
                status = PolarityStatus.ZERO_BIAS
                explanation = "Both terminals are at equal potential in this scenario"

        outcomes.append(PolarityAssessment(
            component=component.reference,
            positive_pin=pos,
            negative_pin=neg,
            positive_net=plus_net,
            negative_net=minus_net,
            scenario=scenario.name if scenario else None,
            status=status,
            differential_volts=delta,
            explanation=explanation,
        ))
    return tuple(outcomes)


def polarity_diagnostics(
    assessments: tuple[PolarityAssessment, ...],
) -> tuple[Diagnostic, ...]:
    """Errors for actual reversed bias; unknowns are warnings, not silent success."""
    results: list[Diagnostic] = []
    for item in assessments:
        if item.status == PolarityStatus.FORWARD:
            continue
        code = {
            PolarityStatus.REVERSED: "POLARITY_REVERSED",
            PolarityStatus.UNKNOWN: "POLARITY_UNVERIFIABLE",
            PolarityStatus.ZERO_BIAS: "POLARITY_ZERO_BIAS",
        }[item.status]
        severity = {
            PolarityStatus.REVERSED: Severity.ERROR,
            PolarityStatus.UNKNOWN: Severity.WARNING,
            PolarityStatus.ZERO_BIAS: Severity.INFO,
        }[item.status]
        results.append(Diagnostic(
            code,
            severity,
            f"{item.component} ({item.positive_pin.number}:+ on {item.positive_net}, "
            f"{item.negative_pin.number}:- on {item.negative_net}): {item.explanation}",
            item.component,
        ))
    return tuple(results)
