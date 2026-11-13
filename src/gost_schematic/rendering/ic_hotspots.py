"""Editor-only E3 pin target metadata. NEVER a physical drawing-layer symbol.

Issue #100: green squares are a future CAD interaction aid measured in screen
pixels, not ГОСТ symbols and not added to clean SVG. Circuit.Net remains the
only electrical topology authority.
"""
from dataclasses import dataclass

from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import PinRef


@dataclass(frozen=True, slots=True)
class IcConnectionTarget:
    pin_id: str
    pin_ref: PinRef
    anchor: Point
    connectable: bool
    net_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pin_id, str) or not self.pin_id:
            raise ValueError("IC_EDITOR_PIN_ID_REQUIRED")
        if not isinstance(self.pin_ref, PinRef) or not isinstance(self.anchor, Point):
            raise TypeError("IC_EDITOR_PHYSICAL_PINREF_AND_POINT_REQUIRED")
        if type(self.connectable) is not bool:
            raise TypeError("IC_EDITOR_CONNECTABLE_TYPED_BOOL_REQUIRED")
        if self.net_id is not None and (
            not isinstance(self.net_id, str) or not self.net_id.strip()
        ):
            raise ValueError("IC_EDITOR_NET_ID_INVALID")
        if self.reason is not None and not isinstance(self.reason, str):
            raise TypeError("IC_EDITOR_REASON_MUST_BE_TEXT")
        if not self.connectable and self.reason is None:
            raise ValueError("IC_EDITOR_DISABLED_TARGET_NEEDS_REASON")


def verify_ic_connection_targets(pins, provided):
    """Strict read-only association; no invented pin or guessed net."""
    pins_by_id = {p.pin_id: p for p in pins}
    selected = {}
    for target in provided:
        if not isinstance(target, IcConnectionTarget):
            raise TypeError("IC_EDITOR_CONNECTION_TARGET_TYPED_REQUIRED")
        if target.pin_id not in pins_by_id or target.pin_id in selected:
            raise ValueError("IC_EDITOR_UNKNOWN_OR_DUPLICATE_PIN")
        pin = pins_by_id[target.pin_id]
        if target.anchor != pin.anchor or target.pin_ref.number != pin.number:
            raise ValueError("IC_EDITOR_PINREF_ENDPOINT_MISMATCH")
        if pin.role == "nc" and (
            target.connectable or target.net_id is not None
        ):
            raise ValueError("IC_EDITOR_NC_TARGET_CONNECTED")
        if not target.connectable and target.net_id and pin.role != "nc":
            # An occupied/locked terminal may have an existing Net. Editor
            # is not allowed to remove it by setting connectable=False.
            pass
        selected[target.pin_id] = target
    return tuple(selected[p.pin_id] for p in pins if p.pin_id in selected)
