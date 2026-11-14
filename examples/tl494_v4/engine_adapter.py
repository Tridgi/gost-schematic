"""Isolated TL494 v4 model adapter. Reuses actual baseline engines and PAINT.

Do not mutate baseline source, MAIN or integration. No handwritten SVG symbols.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from examples.tl494_connected_native import attach_catalog_ic
from examples.tl494_native_rework import build as original_build_power
from examples.tl494_v4.model_contract import (
    PIN_ALIASES, PIN_DESCRIPTIONS, PIN_TYPES, frozen_inventory,
)
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.model.pins import PhysicalPin
from gost_schematic.validation.symbol_checks import validate_symbol


def build_power_v4():
    """Restore the exact catalog MOSFET, undo old unreviewed junction-dot hack."""
    frozen_inventory()
    circuit,parts,symbols,locations=original_build_power()
    original=CatalogResolver().symbols["transistor.mosfet_n_enh"]
    symbols[original.identifier]=original
    if set(part.part_id for part in circuit.components
           if part.reference in {"L1","L2"})!={"inductor.ferromagnetic"}:
        raise ValueError("P1: magnetic core missing")
    if set(part.part_id for part in circuit.components
           if part.reference in {"C1","C2","C5","C6"})!={"capacitor.polarized"}:
        raise ValueError("P1: polarized thin plates missing")
    if any(diag.severity.value=="error" for diag in validate_symbol(original)):
        raise ValueError("P1: catalog real MOSFET invalid")
    return circuit,parts,symbols,locations


def attach_catalog_ic_v4(font_file:Path):
    """Correct physical pin 3 and graphic aliases, rotate PWM only, not leads.

    PAINT PR #93 only supports 0/90. An independent, pinned 270-degree
    experimental *engine patch* is applied in CI before rendering this unit.
    If that patch is unavailable, the model refuses the wrong orientation.
    """
    frozen_inventory()
    unit,targets,part,symbol,instance,style,measure,policy,inspection=(
        attach_catalog_ic(font_file)
    )
    physical=tuple(PhysicalPin(
        pin.number,PIN_DESCRIPTIONS[pin.number],PIN_TYPES[pin.number],
        pin.polarity,pin.function,
    ) for pin in part.pins)
    graphic=tuple(replace(pin,label=PIN_ALIASES[pin.number])
                  for pin in symbol.pins)
    rendered=tuple(replace(pin,label=PIN_ALIASES[pin.number])
                   for pin in unit.pins)
    updated=replace(unit,pins=rendered,function_rotation=270)
    part=replace(part,pins=physical)
    symbol=replace(symbol,pins=graphic)
    if len(updated.pins)!=16:
        raise AssertionError("P2: 16 physical contacts are mandatory")
    if {x.number for x in physical}!={x.number for x in rendered}:
        raise AssertionError("P2: modified physical numbering")
    if physical[2].electrical_type!=PIN_TYPES["3"]:
        raise AssertionError("P2: physical pin 3 is not INPUT")
    if {pin.pin_id:pin.anchor for pin in updated.pins} != {
        pin.pin_id:pin.anchor for pin in unit.pins
    }:
        raise AssertionError("P3: changes to function label moved contact")
    return (
        updated,targets,part,symbol,instance,style,measure,policy,inspection,
    )
