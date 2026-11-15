"""Source-owned E3 supply display contract, DRAFT pending ESKD Issue #91.

No electrical power pin may be moved, created, renumbered or reclassified by
PAINT. ГОСТ 2.743-91 §2.1.4 L/R nonlogical pins and §2.3.11 fig.6 a/b/c,
plus analog 2.759-82 §1.8, are distinct from arbitrary EDA top/bottom rails.
This contract tags a view with its actual source-owned power allocation; it
does not fabricate fig.6 control-outline strokes from a prose mode name.
"""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Side
from gost_schematic.model.circuit import PinRef


class IcPowerLayout(str, Enum):
    SIDE_PINS = "ordinary_side_pins"
    COMMON_CONTROL_BLOCK = "common_control_block_fig6a"
    ONE_SPLIT_UNIT = "one_split_unit_fig6b"
    SEPARATE_CONTOUR = "separate_power_contour_fig6c"
    EXPERIMENTAL_TOP_BOTTOM = "experimental_top_bottom_draft"
    FREE_SHEET_TEXT = "free_sheet_text_2311"


@dataclass(frozen=True, slots=True)
class IcPowerProfile:
    """Physical-pin-typed selection; structural geometry belongs to owner.

    For fig.6 a/b/c, the source must select the correct control/unit/contour
    view. Merely changing the enum cannot move an already connected PinRef.
    The graphical_owner is the actual unit/view reference, not a vendor
    package footprint. Real manufacturer mappings are a separate gate.
    """

    layout: IcPowerLayout
    physical_pinrefs: tuple[PinRef, ...]
    graphical_owner: str
    related_units: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.layout, IcPowerLayout):
            raise TypeError("IC_POWER_LAYOUT_TYPED_REQUIRED")
        if not self.graphical_owner:
            raise ValueError("IC_POWER_OWNER_REQUIRED")
        if not self.physical_pinrefs:
            raise ValueError("IC_POWER_SOURCE_PINREFS_REQUIRED")
        if any(not isinstance(p, PinRef) for p in self.physical_pinrefs):
            raise TypeError("IC_POWER_PHYSICAL_PINREF_TYPED_REQUIRED")
        if len(set(self.physical_pinrefs)) != len(self.physical_pinrefs):
            raise ValueError("IC_POWER_DUPLICATE_PINREF")
        if len(set(self.related_units)) != len(self.related_units):
            raise ValueError("IC_POWER_DUPLICATE_UNIT")
        if self.graphical_owner in self.related_units:
            raise ValueError("IC_POWER_OWNER_LISTED_AS_OTHER_UNIT")


@dataclass(frozen=True, slots=True)
class IcPowerAudit:
    layout: IcPowerLayout
    physical_pinrefs: tuple[PinRef, ...]
    external_points: tuple[tuple[PinRef, object], ...]
    normative_status: str
    requires_source_outline: bool


def verify_ic_power_profile(unit, profile: IcPowerProfile) -> IcPowerAudit:
    """Verify source facts without deriving power from textual VCC/U/OV.

    Power pins must be explicitly typed as power in the physical view.
    The same resolved external Points and PinRef identities are returned.
    Figure 6 variants are only metadata until ELEKTRIK provides an
    actual corresponding source-owned section/frame/contour to PAINT.
    """
    if not isinstance(profile, IcPowerProfile):
        raise TypeError("IC_POWER_PROFILE_TYPED_REQUIRED")
    if profile.graphical_owner != unit.reference:
        raise ValueError("IC_POWER_VIEW_OWNER_MISMATCH")
    pins_by_number = {p.number: p for p in unit.pins}
    expected = {p.number for p in unit.pins if p.role == "power"}
    actual = {p.number for p in profile.physical_pinrefs}
    if actual != expected:
        raise ValueError(
            "IC_POWER_PINREF_COVERAGE_MISMATCH: declared physical role only"
        )
    if len({p.reference for p in profile.physical_pinrefs}) != 1:
        raise ValueError("IC_POWER_MIXED_PHYSICAL_COMPONENTS")
    primary = profile.physical_pinrefs[0].reference
    if not (
        unit.reference == primary
        or unit.reference.startswith(primary + ".")
    ):
        raise ValueError("IC_POWER_COMPONENT_IDENTITY_MISMATCH")
    side_pins = tuple(pins_by_number[ref.number] for ref in profile.physical_pinrefs)
    if profile.layout is IcPowerLayout.EXPERIMENTAL_TOP_BOTTOM:
        if any(p.side not in (Side.TOP, Side.BOTTOM) for p in side_pins):
            raise ValueError("IC_POWER_TOP_BOTTOM_REQUIRES_TYPED_SOURCE_GEOMETRY")
        return IcPowerAudit(
            profile.layout, profile.physical_pinrefs,
            tuple((ref, pins_by_number[ref.number].anchor)
                  for ref in profile.physical_pinrefs),
            "EXPERIMENTAL_BLOCKED_NORMATIVE", True,
        )
    if any(p.side not in (Side.LEFT, Side.RIGHT) for p in side_pins):
        raise ValueError("IC_POWER_SOURCE_LR_NONLOGICAL_SIDE_REQUIRED")
    if profile.layout is IcPowerLayout.ONE_SPLIT_UNIT and not profile.related_units:
        raise ValueError("IC_POWER_SPLIT_UNITS_NOT_DECLARED")
    if profile.layout is IcPowerLayout.SEPARATE_CONTOUR and any(
        p.role != "power" for p in unit.pins
    ):
        raise ValueError("IC_POWER_SEPARATE_SOURCE_CONTOUR_REQUIRED")
    requires_source_outline = profile.layout in (
        IcPowerLayout.COMMON_CONTROL_BLOCK,
        IcPowerLayout.ONE_SPLIT_UNIT,
        IcPowerLayout.SEPARATE_CONTOUR,
    )
    return IcPowerAudit(
        profile.layout, profile.physical_pinrefs,
        tuple((ref, pins_by_number[ref.number].anchor)
              for ref in profile.physical_pinrefs),
        "DRAFT_SOURCE_FIG6_PENDING_1TO1_ESKD" if requires_source_outline
        else "DRAFT_SOURCE_2311_PENDING_ESKD",
        requires_source_outline,
    )
