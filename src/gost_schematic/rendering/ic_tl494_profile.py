"""TL494CN DRAFT source-verified display-name policy (Issue #110).

This module does not create the physical TL494 part or infer its Nets.
It maps an already resolved 16-pin TI-labelled model to editorial text.
A missing/ambiguous manufacturer label fails closed, never truncates.
"""
from dataclasses import replace

from gost_schematic.rendering.ic_rectangular import (
    IcFunctionReading,
    IcResolvedUnit,
    IcTypographyProfile,
)

# TI TL494CN manufacturer full label -> explicit user-approved display label.
# Physical number, exact world anchor, electrical role and Net are untouched.
TI_TL494_PIN_NAMES = {
    "1": ("1IN+", "1IN+"),
    "2": ("1IN−", "1IN−"),
    "3": ("FEEDBACK", "FB"),
    "4": ("DTC", "DTC"),
    "5": ("CT", "CT"),
    "6": ("RT", "RT"),
    "7": ("GND", "GND"),
    "8": ("C1", "C1"),
    "9": ("E1", "E1"),
    "10": ("E2", "E2"),
    "11": ("C2", "C2"),
    "12": ("VCC", "VCC"),
    "13": ("OUTPUT CTRL", "OC"),
    "14": ("REF", "REF"),
    "15": ("2IN−", "2IN−"),
    "16": ("2IN+", "2IN+"),
}


def apply_tl494_portrait_profile(unit: IcResolvedUnit) -> IcResolvedUnit:
    """Apply exact labels + default bottom-to-top in a new view only.

    This does not overwrite the manufacturer full label or electrical type.
    Multi-device/multi-unit assembly is source-authoritative elsewhere.
    """
    if not isinstance(unit, IcResolvedUnit):
        raise TypeError("IC_TL494_RESOLVED_UNIT_REQUIRED")
    actual = {pin.number for pin in unit.pins}
    expected = set(TI_TL494_PIN_NAMES)
    if actual != expected or len(unit.pins) != 16:
        raise ValueError("IC_TL494_EXACT_16_PHYSICAL_PINS_REQUIRED")
    mapped = []
    for pin in unit.pins:
        full, alias = TI_TL494_PIN_NAMES[pin.number]
        if pin.label != full:
            raise ValueError(
                f"IC_TL494_MANUFACTURER_PIN_LABEL_MISMATCH: {pin.number}"
            )
        mapped.append(replace(pin, display_alias=alias))
    shown = replace(unit, pins=tuple(mapped))
    # Profile selection affects typography only, not physical authoring.
    shown = shown.select_typography_profile(
        IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT,
    )
    return shown.select_function_text_reading(
        IcFunctionReading.BOTTOM_TO_TOP,
    )
