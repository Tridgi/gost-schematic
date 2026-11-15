"""Source-locked TL494CN physical ports for external layout/router proposals.

NO connection is inferred from ink, ELK sections, or coordinates. This is an
immutable factory/geometry witness, not a router, GOST approval, or print gate.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gost_schematic.core.geometry import (
    SIDE_VECTORS,
    Box,
    Point,
    primitive_stroked_bounds,
)
from gost_schematic.electrical.ic import IcPinType
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
)
from gost_schematic.electrical.tl494cn import (
    TI_DEVICE_ID,
    verify_tl494cn_ti_pinout,
)
from gost_schematic.model.circuit import PinRef

if TYPE_CHECKING:
    from gost_schematic.electrical.ic_circuit_adapter import IcCircuitBinding

FROZEN_SOURCE_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
ORIGINAL_DA1_PART_ID = "reference.tl494cn"
# Literal PinRef tuples from the Git SHA1-verified 23-part original fixture.
# These are electric Nets; neither b-X2 nor b-R5 is an electric Net member.
_FROZEN_NETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ADJUSTED_DIVIDER", ("R4.2", "R5.1", "R5.3")),
    ("COMMON", ("X1.2", "X2.2", "VT1.3", "VD1.2", "C5.1", "C6.1",
                "DA1.7", "DA1.1", "DA1.16", "DA1.13", "R6.2", "R7.2",
                "R8.2", "C7.2")),
    ("CONTROL_REFERENCE", ("DA1.14", "DA1.15", "R1.1", "R2.1", "C3.1")),
    ("ERROR_INPUT", ("DA1.2", "R2.2", "R4.1", "C4.1")),
    ("FEEDBACK", ("R3.2", "DA1.3")),
    ("GATE_DRIVE", ("DA1.9", "DA1.10", "R8.1", "VT1.1")),
    ("OSCILLATOR_CT", ("C7.1", "DA1.5")),
    ("OSCILLATOR_RT", ("R7.1", "DA1.6")),
    ("OUT_BEFORE_FUSE", ("L2.2", "FU1.1", "C5.2", "C6.2")),
    ("RC_CORRECTION", ("C4.2", "R3.1")),
    ("SOFT_START", ("DA1.4", "R1.2", "C3.2", "R6.1")),
    ("SWITCH", ("L1.2", "VT1.2", "C1.1", "C2.1")),
    ("TRANSFER", ("C1.2", "C2.2", "VD1.1", "L2.1")),
    ("a_INPUT_PLUS", ("X1.1", "L1.1", "DA1.12", "DA1.8", "DA1.11")),
    ("b_NEGATIVE_OUTPUT", ("FU1.2", "X2.1", "R5.2")),
)
_EXPECTED_COMPONENTS = frozenset((
    "DA1", "VT1", "VD1", "L1", "L2", "FU1", "X1", "X2",
    *(f"C{i}" for i in range(1, 8)),
    *(f"R{i}" for i in range(1, 9)),
))
_ESCAPE_LENGTH_UM = 1800
_ESCAPE_HALF_WIDTH_UM = 400


def _point(point: Point) -> list[int]:
    return [point.x, point.y]


def _box(box: Box) -> list[int]:
    return [box.min_x, box.min_y, box.max_x, box.max_y]


def _source_members(binding: IcCircuitBinding) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple(sorted(
        (net.name, tuple(f"{p.reference}.{p.number}" for p in net.members))
        for net in binding.circuit.nets
    ))


def _escape_box(tip: Point, normal: Point) -> Box:
    end = Point(
        tip.x + normal.x * _ESCAPE_LENGTH_UM,
        tip.y + normal.y * _ESCAPE_LENGTH_UM,
    )
    if normal.x:
        return Box(min(tip.x, end.x), tip.y - _ESCAPE_HALF_WIDTH_UM,
                   max(tip.x, end.x), tip.y + _ESCAPE_HALF_WIDTH_UM)
    return Box(tip.x - _ESCAPE_HALF_WIDTH_UM, min(tip.y, end.y),
               tip.x + _ESCAPE_HALF_WIDTH_UM, max(tip.y, end.y))


@dataclass(frozen=True, slots=True)
class IcRouterPort:
    """Source and manufacturer-owned, no nonphysical waypoint connectivity."""

    pin_ref: PinRef
    net_name: str
    ti_name: str
    manufacturer_function: str
    electrical_type: IcPinType
    tip_um: Point
    normal: Point
    local_ink_port_um: Point
    own_only_escape_box_um: Box

    def to_dict(self) -> dict:
        return {
            "pin_ref": f"{self.pin_ref.reference}.{self.pin_ref.number}",
            "net_name": self.net_name,
            "ti_name": self.ti_name,
            "manufacturer_function": self.manufacturer_function,
            "electrical_type": self.electrical_type.value,
            "tip_um": _point(self.tip_um),
            "outward_normal": _point(self.normal),
            "local_ink_port_um": _point(self.local_ink_port_um),
            "own_only_escape_box_um": _box(self.own_only_escape_box_um),
            "escape_rule": "PIN_REF_ONLY_NO_FOREIGN_NET_CLEARANCE",
        }


@dataclass(frozen=True, slots=True)
class IcRouterPortContract:
    """Rebuildable original source witness; exporter never authorizes routing."""

    source_sha: str
    source_netlist_sha256: str
    source_binding_sha256: str
    manufacturer_record_sha256: str
    part_origin_um: Point
    rotation_deg: int
    mirror_x: bool
    native_draft_ink_box_um: Box
    page_box_um: Box
    ports: tuple[IcRouterPort, ...]
    producer_shas: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict:
        return {
            "schema": "tl494-source-router-ports-v1",
            "status": "DRAFT_ROUTER_INPUT_NOT_PRINTABLE",
            "source_sha": self.source_sha,
            "source_original_part_id": ORIGINAL_DA1_PART_ID,
            "manufacturer_part_id": TI_DEVICE_ID,
            "manufacturer_record_sha256": self.manufacturer_record_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "source_netlist_sha256": self.source_netlist_sha256,
            "source_component_count": 23,
            "source_original_net_count": 15,
            "source_pinref_memberships": 62,
            "physical_manufacturer_pins": 16,
            "source_original_nets": [
                {"name": name, "members": list(members)}
                for name, members in _FROZEN_NETS
            ],
            "nonphysical_b_stubs": ["b-X2", "b-R5"],
            "part_reference": "DA1",
            "part_origin_um": _point(self.part_origin_um),
            "part_rotation_deg": self.rotation_deg,
            "part_mirror_x": self.mirror_x,
            "native_draft_ink_box_um": _box(self.native_draft_ink_box_um),
            "page_box_um": _box(self.page_box_um),
            "ports": [p.to_dict() for p in self.ports],
            "producer_shas": dict(self.producer_shas),
            "requires_geometry_consent_if_moved": True,
            "full_15_net_route_verified": False,
            "printable_candidate": False,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        )

    def verify_against(self, binding: IcCircuitBinding) -> None:
        """Compare to the live trusted record, not a self-asserted JSON hash."""
        expected = export_tl494_router_ports(
            binding, producer_shas=dict(self.producer_shas),
            page_box_um=self.page_box_um,
        )
        if self != expected:
            raise ValueError("IC_ROUTER_PORT_CONTRACT_SOURCE_CHANGED")

    def verify_external_layout(
        self,
        binding: IcCircuitBinding,
        *,
        proposed_origin_um: Point,
        proposed_rotation_deg: int,
        proposed_mirror_x: bool,
        proposed_ports: tuple[IcRouterPort, ...],
        consent: IcGeometryConsent | None = None,
    ) -> None:
        """Fail closed on external ELK/local FIXED_POS and spoofed world tips.

        Consent on its own is NOT a signature of relocated manufacturer pins.
        A genuinely moved component needs a new source-bound Circuit/record
        and independent approval of all connected wire reroutes first.
        """
        self.verify_against(binding)
        if consent is not None and not isinstance(consent, IcGeometryConsent):
            raise TypeError("IC_ROUTER_GEOMETRY_CONSENT_TYPED_REQUIRED")
        if (
            proposed_origin_um != self.part_origin_um
            or proposed_rotation_deg != self.rotation_deg
            or proposed_mirror_x != self.mirror_x
        ):
            raise ValueError("IC_ROUTER_EXTERNAL_PART_REBIND_REQUIRED")
        if type(proposed_ports) is not tuple or len(proposed_ports) != 16:
            raise ValueError("IC_ROUTER_EXTERNAL_PHYSICAL_PORT_COVERAGE")
        if len({p.pin_ref for p in proposed_ports}) != 16:
            raise ValueError("IC_ROUTER_EXTERNAL_DUPLICATE_PINREF")
        by_ref = {p.pin_ref: p for p in self.ports}
        for port in proposed_ports:
            if not isinstance(port, IcRouterPort) or port.pin_ref not in by_ref:
                raise ValueError("IC_ROUTER_EXTERNAL_UNKNOWN_PINREF")
            trusted = by_ref[port.pin_ref]
            if port.tip_um != trusted.tip_um:
                raise ValueError("IC_ROUTER_EXTERNAL_ABSOLUTE_TIP_DRIFT")
            if (port.normal != trusted.normal
                    or port.local_ink_port_um != trusted.local_ink_port_um):
                raise ValueError("IC_ROUTER_EXTERNAL_D4_OR_LOCAL_PORT_DRIFT")
            if (port.net_name != trusted.net_name
                    or port.ti_name != trusted.ti_name
                    or port.manufacturer_function != trusted.manufacturer_function
                    or port.electrical_type != trusted.electrical_type
                    or port.own_only_escape_box_um != trusted.own_only_escape_box_um):
                raise ValueError("IC_ROUTER_EXTERNAL_IDENTITY_OR_KEEP_OUT_FORGED")


def export_tl494_router_ports(
    binding: IcCircuitBinding,
    *,
    producer_shas: dict[str, str] | None = None,
    page_box_um: Box = Box(0, 0, 420000, 297000),
) -> IcRouterPortContract:
    """Export exactly 16 world ports, original literal Nets and DRAFT UGO ink.

    Caller must use a real source-verified IcCircuitBinding; this also
    enforces all frozen original names and ordered physical memberships.
    """
    from gost_schematic.electrical.ic_circuit_adapter import IcCircuitBinding

    if not isinstance(binding, IcCircuitBinding):
        raise TypeError("IC_ROUTER_SOURCE_BINDING_TYPED_REQUIRED")
    binding.validate()
    verify_tl494cn_ti_pinout(binding.record.device)
    if binding.record.device.identifier != TI_DEVICE_ID or binding.component_ref != "DA1":
        raise ValueError("IC_ROUTER_NOT_TL494_DA1")
    if (len(binding.circuit.components) != 23
            or {c.reference for c in binding.circuit.components} != _EXPECTED_COMPONENTS
            or len(binding.circuit.nets) != 15
            or sum(len(n.members) for n in binding.circuit.nets) != 62
            or _source_members(binding) != tuple(sorted(_FROZEN_NETS))):
        raise ValueError("IC_ROUTER_ORIGINAL_23_15_62_TOPOLOGY_DRIFT")
    if {p.pin_ref for p in binding.contacts} != {
        PinRef("DA1", str(i)) for i in range(1, 17)
    }:
        raise ValueError("IC_ROUTER_MANUFACTURER_16_PIN_COVERAGE")
    if type(page_box_um) is not Box:
        raise TypeError("IC_ROUTER_PAGE_TYPED_REQUIRED")
    if not (
        page_box_um.min_x == 0 and page_box_um.min_y == 0
        and (page_box_um.max_x, page_box_um.max_y)
        in ((420000, 297000), (594000, 420000))
    ):
        raise ValueError("IC_ROUTER_INVALID_A3_A2_PAGE")
    shas = {} if producer_shas is None else producer_shas
    if type(shas) is not dict or any(
        type(k) is not str or not k or type(v) is not str
        or len(v) != 40 or any(ch not in "0123456789abcdef" for ch in v)
        for k, v in shas.items()
    ):
        raise ValueError("IC_ROUTER_PRODUCER_SHA_INVALID")
    if binding.symbol_surrogate is None:
        raise ValueError("IC_ROUTER_REAL_DA1_DRAFT_INK_REQUIRED")
    instance = next(c for c in binding.circuit.components if c.reference == "DA1")
    # This is REAL typed DRAFT router ink from the signed record, not printed
    # Type A text/PAINT glyphs or evidence of a complete geometrical DRC.
    outlines = tuple(
        primitive_stroked_bounds(
            instance.transform.primitive(g, instance.origin),
            binding.symbol_surrogate.line_width_um,
        )
        for g in binding.symbol_surrogate.graphics
    )
    if not outlines:
        raise ValueError("IC_ROUTER_NO_SOURCE_INK")
    ink = Box(
        min(b.min_x for b in outlines), min(b.min_y for b in outlines),
        max(b.max_x for b in outlines), max(b.max_y for b in outlines),
    )
    ti = binding.record.device.pin_map
    ports = tuple(
        IcRouterPort(
            pin_ref=c.pin_ref,
            net_name=c.net_id,
            ti_name=c.manufacturer_pin_name,
            manufacturer_function=ti[c.pin_ref.number].function,
            electrical_type=c.electrical_type,
            tip_um=c.world_anchor,
            normal=SIDE_VECTORS[c.world_side],
            local_ink_port_um=Point(
                c.world_anchor.x - ink.min_x, c.world_anchor.y - ink.min_y,
            ),
            own_only_escape_box_um=_escape_box(
                c.world_anchor, SIDE_VECTORS[c.world_side],
            ),
        ) for c in binding.contacts
    )
    if any(p.net_name is None for p in ports):
        raise ValueError("IC_ROUTER_UNCONNECTED_SOURCE_MANUFACTURER_PIN")
    if any(not page_box_um.includes(p.tip_um) for p in ports):
        raise ValueError("IC_ROUTER_MANUFACTURER_TIP_OUTSIDE_PAGE")
    netlist = json.dumps(
        _FROZEN_NETS, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return IcRouterPortContract(
        source_sha=FROZEN_SOURCE_SHA,
        source_netlist_sha256=hashlib.sha256(netlist).hexdigest(),
        source_binding_sha256=hashlib.sha256(
            binding.to_json().encode("utf-8"),
        ).hexdigest(),
        manufacturer_record_sha256=ic_record_fingerprint(binding.record),
        part_origin_um=instance.origin,
        rotation_deg=instance.transform.rotation,
        mirror_x=instance.transform.mirror_x,
        native_draft_ink_box_um=ink,
        page_box_um=page_box_um,
        ports=ports,
        producer_shas=tuple(sorted(shas.items())),
    )
