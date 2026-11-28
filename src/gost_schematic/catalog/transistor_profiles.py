"""Bounded registry of exact, deterministic transistor layout IDs.

No arbitrary imports, user-supplied geometry or implicit legacy substitution.
Definitions remain DRAFT. The base catalog's installed inventory is unchanged.
"""
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from gost_schematic.catalog.transistor_switches import SwitchKind, switch_review_variants
from gost_schematic.catalog.transistors import (
    bipolar_review_variants,
    mosfet_body_diode_variants,
    mosfet_extended_variants,
)
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition


@lru_cache(maxsize=1)
def transistor_profiles() -> Mapping[str, tuple[PartDefinition, SymbolDefinition]]:
    variants = (
        *bipolar_review_variants(),
        *(variant
          for depletion in (False, True)
          for separate_body in (False, True)
          for variant in mosfet_extended_variants(
              depletion=depletion, separate_body=separate_body,
          )),
        *mosfet_body_diode_variants(),
        *(variant for kind in SwitchKind for variant in switch_review_variants(kind)),
    )
    pairs: dict[str, tuple[PartDefinition, SymbolDefinition]] = {}
    for variant in variants:
        part, symbol = variant.part, variant.symbol
        if part.identifier in pairs or part.symbol_id != symbol.identifier:
            raise ValueError(f"Duplicate or mismatched transistor profile: {part.identifier}")
        pairs[part.identifier] = (part, symbol)
    return MappingProxyType(pairs)
