"""Cycle16: signed original 23/15/62/16 TL494 physical router-port boundary.

No external graph, ELK dummy node, source photograph, junction or DRC skip
is made authoritative by a JSON candidate that passes this narrow check.
"""
from dataclasses import replace

import pytest

from examples.tl494_cycle9_circuit_integration import build_frozen_photo_23
from gost_schematic.core.geometry import Box, Point
from gost_schematic.electrical.ic import IcPinType
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
)
from gost_schematic.electrical.ic_router_ports import (
    FROZEN_SOURCE_SHA,
    IcRouterPort,
    export_tl494_router_ports,
)
from gost_schematic.electrical.tl494cn import TI_DEVICE_ID
from gost_schematic.model.circuit import PinRef


def _contract():
    binding, _source = build_frozen_photo_23()
    proof = export_tl494_router_ports(
        binding, producer_shas={"IC97": "a" * 40},
    )
    return binding, proof


def test_cycle16_true_source_locked_original_23_15_62_and_factory_16():
    binding, proof = _contract()
    proof.verify_against(binding)
    doc = proof.to_dict()
    assert doc["source_sha"] == FROZEN_SOURCE_SHA
    assert doc["source_original_part_id"] == "reference.tl494cn"
    assert doc["manufacturer_part_id"] == TI_DEVICE_ID
    assert doc["source_component_count"] == 23
    assert doc["source_original_net_count"] == 15
    assert doc["source_pinref_memberships"] == 62
    assert doc["physical_manufacturer_pins"] == 16
    assert len(doc["ports"]) == 16
    assert len(doc["source_original_nets"]) == 15
    assert sum(len(net["members"]) for net in doc["source_original_nets"]) == 62
    assert doc["nonphysical_b_stubs"] == ["b-X2", "b-R5"]
    assert not doc["full_15_net_route_verified"]
    assert not doc["printable_candidate"]
    assert "b-X2" not in {n["name"] for n in doc["source_original_nets"]}
    assert "b-R5" not in {n["name"] for n in doc["source_original_nets"]}
    assert doc["producer_shas"]["IC97"] == "a" * 40
    assert len(doc["source_netlist_sha256"]) == 64
    assert len(doc["source_binding_sha256"]) == 64
    assert len(doc["manufacturer_record_sha256"]) == 64
    assert doc["manufacturer_record_sha256"] == ic_record_fingerprint(
        binding.record
    )


def test_cycle16_factory_roles_exact_and_own_only_physical_escape():
    _, contract = _contract()
    pins = {p.pin_ref.number: p for p in contract.ports}
    assert set(pins) == {str(i) for i in range(1, 17)}
    assert pins["3"].ti_name == "FEEDBACK"
    assert pins["3"].electrical_type is IcPinType.INPUT
    assert pins["3"].net_name == "FEEDBACK"
    assert pins["13"].ti_name == "OUTPUT CTRL"
    assert pins["13"].electrical_type is IcPinType.INPUT
    assert pins["13"].net_name == "COMMON"
    assert pins["14"].ti_name == "REF"
    assert pins["14"].electrical_type is IcPinType.POWER_OUTPUT
    for p in contract.ports:
        assert p.normal in (
            Point(-1, 0), Point(1, 0), Point(0, -1), Point(0, 1),
        )
        assert p.own_only_escape_box_um.includes(p.tip_um)
        far = Point(
            p.tip_um.x + p.normal.x * 1800,
            p.tip_um.y + p.normal.y * 1800,
        )
        assert p.own_only_escape_box_um.includes(far)
        assert contract.page_box_um.includes(p.tip_um)
        assert p.to_dict()["escape_rule"] == (
            "PIN_REF_ONLY_NO_FOREIGN_NET_CLEARANCE"
        )


def test_cycle16_external_exact_source_candidate_positive_without_rerouting():
    binding, contract = _contract()
    contract.verify_external_layout(
        binding,
        proposed_origin_um=contract.part_origin_um,
        proposed_rotation_deg=contract.rotation_deg,
        proposed_mirror_x=contract.mirror_x,
        proposed_ports=contract.ports,
    )


@pytest.mark.parametrize("dx,dy", [(1, 0), (0, -1), (-1, 1)])
def test_cycle16_external_fixed_pos_that_moves_absolute_tip_1um_rejected(dx, dy):
    binding, contract = _contract()
    shifted = replace(
        contract.ports[0],
        tip_um=contract.ports[0].tip_um + Point(dx, dy),
    )
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_ABSOLUTE_TIP_DRIFT",
    ):
        contract.verify_external_layout(
            binding,
            proposed_origin_um=contract.part_origin_um,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=(shifted, *contract.ports[1:]),
        )


@pytest.mark.parametrize("field,value", (
    ("net_name", "a_INPUT_PLUS"),
    ("ti_name", "FORGED_FEEDBACK"),
    ("electrical_type", IcPinType.NC),
    ("own_only_escape_box_um", Box(1, 2, 3, 4)),
))
def test_cycle16_external_renamed_net_nc_role_or_fake_clearance_rejected(field, value):
    binding, contract = _contract()
    old = contract.ports[2]  # factory DA1.3 FEEDBACK INPUT
    fake = replace(old, **{field: value})
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_IDENTITY_OR_KEEP_OUT_FORGED",
    ):
        contract.verify_external_layout(
            binding, proposed_origin_um=contract.part_origin_um,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=(*contract.ports[:2], fake, *contract.ports[3:]),
        )


@pytest.mark.parametrize("kind", ("inward_normal", "local_point_1um"))
def test_cycle16_external_wrong_d4_normal_or_local_port_rejected(kind):
    binding, contract = _contract()
    first = contract.ports[0]
    if kind == "inward_normal":
        fake = replace(first, normal=Point(-first.normal.x, -first.normal.y))
    else:
        fake = replace(
            first, local_ink_port_um=first.local_ink_port_um + Point(0, 1),
        )
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_D4_OR_LOCAL_PORT_DRIFT",
    ):
        contract.verify_external_layout(
            binding, proposed_origin_um=contract.part_origin_um,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=(fake, *contract.ports[1:]),
        )


@pytest.mark.parametrize("kind", ("missing", "duplicate", "not_typed"))
def test_cycle16_external_all_16_pinrefs_are_mandatory(kind):
    binding, contract = _contract()
    if kind == "missing":
        fake = contract.ports[:-1]
        reason = "IC_ROUTER_EXTERNAL_PHYSICAL_PORT_COVERAGE"
    elif kind == "duplicate":
        fake = (*contract.ports[:-1], contract.ports[0])
        reason = "IC_ROUTER_EXTERNAL_DUPLICATE_PINREF"
    else:
        fake = ("DA1.1", *contract.ports[1:])
        reason = "IC_ROUTER_EXTERNAL_UNKNOWN_PINREF"
    with pytest.raises(ValueError, match=reason):
        contract.verify_external_layout(
            binding, proposed_origin_um=contract.part_origin_um,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=fake,
        )


def test_cycle16_external_elk_fixed_pos_node_shift_even_with_consent_blocked():
    binding, contract = _contract()
    moved = Point(contract.part_origin_um.x + 1, contract.part_origin_um.y)
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_PART_REBIND_REQUIRED",
    ):
        contract.verify_external_layout(
            binding, proposed_origin_um=moved,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=contract.ports,
        )
    # Consent is NOT a fake source rebind and is not proof of rewired copper.
    permit = IcGeometryConsent(
        ic_record_fingerprint(binding.record),
        tuple(p.pin_ref for p in contract.ports),
        tuple(p.pin_ref for p in contract.ports),
    )
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_PART_REBIND_REQUIRED",
    ):
        contract.verify_external_layout(
            binding, proposed_origin_um=moved,
            proposed_rotation_deg=contract.rotation_deg,
            proposed_mirror_x=contract.mirror_x,
            proposed_ports=contract.ports, consent=permit,
        )


@pytest.mark.parametrize("kind", ("rotated", "mirror"))
def test_cycle16_external_d4_cannot_change_pins_unilaterally(kind):
    binding, contract = _contract()
    with pytest.raises(
        ValueError, match="IC_ROUTER_EXTERNAL_PART_REBIND_REQUIRED",
    ):
        contract.verify_external_layout(
            binding, proposed_origin_um=contract.part_origin_um,
            proposed_rotation_deg=(
                (contract.rotation_deg + 90) % 360
                if kind == "rotated" else contract.rotation_deg
            ),
            proposed_mirror_x=(
                not contract.mirror_x if kind == "mirror"
                else contract.mirror_x
            ),
            proposed_ports=contract.ports,
        )


def test_cycle16_forged_full_binding_or_wrong_net_is_not_an_authority():
    binding, proof = _contract()
    rogue = replace(proof, source_binding_sha256="f" * 64)
    with pytest.raises(
        ValueError, match="IC_ROUTER_PORT_CONTRACT_SOURCE_CHANGED",
    ):
        rogue.verify_against(binding)
    source_nets = list(binding.circuit.nets)
    source_nets[0] = replace(source_nets[0], name="OTHER_NET")
    bad_source = replace(binding, circuit=replace(
        binding.circuit, nets=tuple(source_nets),
    ))
    with pytest.raises(ValueError):
        export_tl494_router_ports(bad_source)


@pytest.mark.parametrize("badsha", (
    "a" * 39, "G" * 40, "0" * 64, "a" * 41,
))
def test_cycle16_producer_sha_provenance_fails_closed(badsha):
    binding, _ = _contract()
    with pytest.raises(ValueError, match="IC_ROUTER_PRODUCER_SHA_INVALID"):
        export_tl494_router_ports(
            binding, producer_shas={"IC97": badsha},
        )


def test_cycle16_source_contract_never_accepts_forced_foreign_part():
    binding, _ = _contract()
    fake = replace(binding, part=replace(
        binding.part, identifier="fake.tl494cn.pdip16",
    ))
    with pytest.raises(ValueError):
        export_tl494_router_ports(fake)


def test_cycle16_original_pinref_identity_exact_without_phantom_x_or_t():
    _, contract = _contract()
    original = {
        item for item in contract.to_dict()["source_original_nets"]
        for item in item["members"]
    }
    assert len(original) == 62
    assert {f"DA1.{i}" for i in range(1, 17)} <= original
    assert PinRef("DA1", "13") in {p.pin_ref for p in contract.ports}
    assert not any(name in original for name in (
        "b-X2", "b-R5", "ELK.dummy", "fake.T", "fake.X",
    ))
    assert all(isinstance(p, IcRouterPort) for p in contract.ports)
