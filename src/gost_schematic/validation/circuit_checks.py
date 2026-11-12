"""Check electrical identifiers and net ownership without using drawn wires."""
from collections.abc import Mapping

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import TerminalPolarity
from gost_schematic.model.potentials import PotentialScenario
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.polarity_checks import assess_polarity, polarity_diagnostics
from gost_schematic.validation.symbol_checks import validate_symbol


def validate_circuit(
    circuit: Circuit,
    parts: Mapping[str, PartDefinition],
    symbols: Mapping[str, SymbolDefinition],
    *,
    scenario: PotentialScenario | None = None,
) -> tuple[Diagnostic, ...]:
    issues: list[Diagnostic] = []
    instances = {}
    for instance in circuit.components:
        if instance.reference in instances:
            issues.append(Diagnostic(
                "DUPLICATE_REFERENCE", Severity.ERROR,
                f"Duplicate component reference: {instance.reference}", instance.reference))
        instances[instance.reference] = instance
        part = parts.get(instance.part_id)
        if part is None:
            issues.append(Diagnostic(
                "UNKNOWN_PART", Severity.ERROR,
                f"Unknown part {instance.part_id}", instance.reference))
            continue
        symbol = symbols.get(part.symbol_id)
        if symbol is None:
            issues.append(Diagnostic(
                "UNKNOWN_SYMBOL", Severity.ERROR,
                f"Unknown symbol {part.symbol_id}", instance.reference))
            continue
        if (
            instance.nominal is not None
            and part.nominal_kind is not None
            and instance.nominal.kind != part.nominal_kind
        ):
            issues.append(Diagnostic(
                "NOMINAL_KIND_MISMATCH", Severity.ERROR,
                f"{instance.reference} has {instance.nominal.kind.value}, "
                f"but part {part.identifier} requires {part.nominal_kind.value}",
                instance.reference,
            ))
        physical_numbers = {pin.number for pin in part.pins}
        graphic_numbers = {pin.number for pin in symbol.pins}
        if physical_numbers != graphic_numbers:
            issues.append(Diagnostic(
                "PIN_MAPPING_MISMATCH", Severity.ERROR,
                f"Graphic pins differ from physical pins of {instance.part_id}",
                instance.reference))
        if part.voltage_orientation_rule != VoltageOrientationRule.NONE:
            graphic_by_number = {pin.number: pin for pin in symbol.pins}
            for physical_pin in part.pins:
                symbol_pin = graphic_by_number.get(physical_pin.number)
                if symbol_pin is None or symbol_pin.label not in ("+", "-"):
                    continue
                expected = (
                    "+" if physical_pin.polarity == TerminalPolarity.POSITIVE else "-"
                    if physical_pin.polarity == TerminalPolarity.NEGATIVE else None
                )
                if symbol_pin.label != expected:
                    issues.append(Diagnostic(
                        "GRAPHIC_POLARITY_MISMATCH", Severity.ERROR,
                        f"{instance.reference}.{physical_pin.number}: graphic marker "
                        f"{symbol_pin.label!r} contradicts physical polarity "
                        f"{physical_pin.polarity.value}",
                        instance.reference,
                    ))
        issues.extend(validate_symbol(symbol))

    connected: dict[PinRef, str] = {}
    names: set[str] = set()
    for net in circuit.nets:
        if net.name in names:
            issues.append(Diagnostic(
                "DUPLICATE_NET_NAME", Severity.ERROR,
                f"Duplicate net name: {net.name}", net.name))
        names.add(net.name)
        local_members: set[PinRef] = set()
        for ref in net.members:
            if ref in local_members:
                issues.append(Diagnostic(
                    "DUPLICATE_NET_MEMBER", Severity.ERROR,
                    f"Pin {ref.reference}.{ref.number} repeated in {net.name}", net.name))
            local_members.add(ref)
            instance = instances.get(ref.reference)
            if instance is None:
                issues.append(Diagnostic(
                    "UNKNOWN_COMPONENT", Severity.ERROR,
                    f"Unknown component {ref.reference}", net.name))
                continue
            part = parts.get(instance.part_id)
            if part is not None and ref.number not in {pin.number for pin in part.pins}:
                issues.append(Diagnostic(
                    "UNKNOWN_PIN", Severity.ERROR,
                    f"Unknown physical pin {ref.reference}.{ref.number}", net.name))
                continue
            if ref in connected and connected[ref] != net.name:
                issues.append(Diagnostic(
                    "MULTIPLE_NET_OWNERSHIP", Severity.ERROR,
                    f"{ref.reference}.{ref.number} belongs to multiple nets", net.name))
            connected[ref] = net.name
    issues.extend(polarity_diagnostics(assess_polarity(circuit, parts, scenario=scenario)))
    return tuple(issues)
