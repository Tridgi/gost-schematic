"""Independent immutable physical source-footprint and router obstacle gates."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from examples.review_tl494_ugo_source_cycle9 import generate
from gost_schematic.agent_project.catalog import value_digest
from gost_schematic.catalog.source_footprints import (
    footprint_record,
    source_footprint,
    verify_footprint_record,
)
from gost_schematic.catalog.source_profiles import (
    SymbolProfileMismatch,
    bind_tl494_source,
    load_catalog_pair,
    read_source_manifest,
    select_tl494_symbol,
)
from gost_schematic.core.geometry import Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.clearance import validate_wire_clearance
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle


def _scene():
    scene, parts, symbols = [], {}, {}
    for row in read_source_manifest()["profiles"]:
        name = row["symbol_id"]
        sym, part = load_catalog_pair(name)
        symbols[name], parts[name] = sym, part
        scene.append(ComponentInstance(
            row["reference"], name,
            Point(*[round(x * 1000) for x in row["source_layout_origin_mm"]]),
            Transform(row["rotation"], row["mirror_x"]),
        ))
    return bind_tl494_source(scene, parts, symbols)


@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
def test_all_13_source_profiles_have_true_D4_footprints(angle, mirror):
    proofs = []
    for bound in _scene():
        comp = replace(bound.instance, transform=Transform(angle, mirror))
        at = comp.pin_positions(bound.symbol)
        moved = replace(
            bound, instance=comp,
            pin_positions=tuple(at[p.number] for p in bound.part.pins),
        )
        footprint = source_footprint(moved)
        record = footprint_record(footprint)
        verify_footprint_record(footprint, record)
        assert record["schema_version"] == 1
        assert record["status"] == "DRAFT_NOT_GOST_CERTIFIED"
        assert len(record["graphic_ink"]) == len(bound.symbol.graphics) + (
            1 if bound.reference == "VT1" else 0
        )
        assert len(record["real_leads"]) == len(bound.part.pins)
        assert len(record["pin_escape"]) == len(bound.part.pins)
        assert tuple(x["number"] for x in record["real_leads"]) == tuple(
            p.number for p in bound.part.pins
        )
        assert len({(x["number"], tuple(x["contact_um"]))
                    for x in record["pin_escape"]}) == len(bound.part.pins)
        assert record["symbol_sha256"] == value_digest(bound.symbol)
        if bound.reference == "VT1":
            assert record["rendered_symbol_sha256"] != record["symbol_sha256"]
            assert len(record["real_leads"]) == 3
        else:
            assert record["rendered_symbol_sha256"] == record["symbol_sha256"]
        assert record["part_sha256"] == value_digest(bound.part)
        assert record["rotation"] == angle
        assert record["mirror_x"] == mirror
        assert value_digest({
            k: v for k, v in record.items() if k != "footprint_sha256"
        }) == record["footprint_sha256"]
        for lead, escape in zip(
            record["real_leads"], record["pin_escape"], strict=True
        ):
            assert escape["contact_um"] in lead["segment_um"]
            assert lead["obstacle_um"] == record["graphic_ink"][
                lead["graphic_index"]
            ]["box_um"]
            assert lead["stroke_um"] > 0
            assert escape["rule"] == "EXACT_PIN_OUTWARD_ONLY_NO_SELF_INK_WAIVER"
        for corridor in footprint.pin_corridors:
            # Outward physical pin escape is the ONLY admitted exception to
            # corridor protection; inward, other pin and unrelated NET fail.
            n = {"left": (-1, 0), "right": (1, 0),
                 "top": (0, -1), "bottom": (0, 1)}[corridor.side.value]
            outward = Point(
                corridor.contact.x + n[0] * 1000,
                corridor.contact.y + n[1] * 1000,
            )
            inward = Point(
                corridor.contact.x - n[0] * 1000,
                corridor.contact.y - n[1] * 1000,
            )
            assert corridor.admits(corridor.contact, outward, corridor.pin)
            assert not corridor.admits(corridor.contact, inward, corridor.pin)
            assert not corridor.admits(
                corridor.contact, outward, PinRef("FAKE", "1")
            )
        proofs.append(record)
    assert len(proofs) == 13
    assert len({r["reference"] for r in proofs}) == 13
    assert sum(len(r["real_leads"]) for r in proofs) == 28


@pytest.mark.parametrize("which", ["VD1", "VT1", "C1", "L1", "R5"])
def test_source_footprint_immutability_and_stale_hash_are_fail_closed(which):
    bound = next(item for item in _scene() if item.reference == which)
    footprint = source_footprint(bound)
    original = footprint_record(footprint)
    with pytest.raises(FrozenInstanceError):
        footprint.rotation = 90
    for field, bogus in (
        ("symbol_sha256", "0" * 64),
        ("rotation", 42),
        ("body_keepout_um", [0, 0, 1, 1]),
        ("pin_escape", []),
        ("real_leads", []),
        ("footprint_sha256", "0" * 64),
    ):
        replaced = {**original, field: bogus}
        with pytest.raises(SymbolProfileMismatch, match="immutable"):
            verify_footprint_record(footprint, replaced)


def test_pin_mapping_swaps_fake_missing_lead_and_missing_symbol_fail():
    original = _scene()
    vd = next(item for item in original if item.reference == "VD1")
    with pytest.raises(SymbolProfileMismatch, match="PinRef"):
        source_footprint(replace(vd, pin_refs=vd.pin_refs[::-1]))
    with pytest.raises(SymbolProfileMismatch, match="endpoint"):
        source_footprint(replace(
            vd, pin_positions=vd.pin_positions[::-1]
        ))
    sym = vd.symbol
    bad = replace(
        sym, conductor_topology=replace(
            sym.conductor_topology, conductor_indices=(1,)
        ),
    )
    with pytest.raises(SymbolProfileMismatch):
        source_footprint(replace(vd, symbol=bad))
    with pytest.raises(SymbolProfileMismatch, match="part/symbol"):
        source_footprint(replace(vd, part=replace(
            vd.part, symbol_id="diode.general"
        )))


def test_wrong_pin_ref_and_wrong_Net_are_not_exempt_by_symbol_corridors():
    vd = next(item for item in _scene() if item.reference == "VD1")
    proof = source_footprint(vd)
    assert len(proof.pin_corridors) == 2
    corridor = proof.pin_corridors[0]
    outward = Point(corridor.contact.x, corridor.contact.y - 1000)
    wire = WireObstacle(
        "W_WRONG_NET", Line(corridor.contact, outward),
        attached_pin=corridor.pin, net_name="WRONG_NET",
    )
    circuit = Circuit(
        (vd.instance,),
        (Net("CORRECT_NET", (corridor.pin,)),),
    )
    errors = validate_wire_clearance(
        (wire,), corridors=proof.pin_corridors, circuit=circuit
    )
    assert "ROUTE_NET_MISMATCH" in {e.code for e in errors}
    assert not corridor.admits(
        wire.line.start, wire.line.end, PinRef("VD1", "2")
    )
    stolen = replace(wire, attached_pin=PinRef("VD1", "2"))
    errors = validate_wire_clearance(
        (stolen,), corridors=proof.pin_corridors, circuit=circuit
    )
    assert "ROUTE_PIN_ESCAPE_BLOCKED" in {e.code for e in errors}
    assert "ROUTE_NET_MISMATCH" in {e.code for e in errors}


def test_footprint_export_matches_13_original_and_104_D4_records(tmp_path: Path):
    generated = generate(tmp_path)
    path = tmp_path / generated["footprint_proofs_file"]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "DRAFT"
    assert data["source_reference_sha"] == read_source_manifest()["reference_sha"]
    assert len(data["source_pose"]) == 13
    assert len(data["d4_proofs"]) == 13 * 8
    assert len({r["footprint_sha256"] for r in data["d4_proofs"]}) == 104
    assert all(r["status"] == "DRAFT_NOT_GOST_CERTIFIED"
               for r in data["source_pose"])
    assert data["release_blocker"] == "NO_INDEPENDENT_CALIBRATED_1TO1"


@pytest.mark.parametrize("reference,good,bad", [
    ("VD1", "diode.schottky", "diode.general"),
    ("VT1", "transistor.mosfet_n_enh", "transistor.bjt_npn"),
    ("C1", "capacitor.polarized", "capacitor.electrolytic"),
    ("L1", "inductor.ferromagnetic", "inductor.air_core"),
    ("R5", "resistor.variable", "resistor.fixed"),
])
def test_exact_catalog_choices_fail_closed_on_ambiguous_and_missing(
    reference, good, bad,
):
    assert select_tl494_symbol(reference, (good,)) == good
    for offered in ((), (good, bad), (bad, good), (good, good),
                    (bad,), ("",), (good, "")):
        with pytest.raises(SymbolProfileMismatch):
            select_tl494_symbol(reference, offered)


def test_unsupported_ref_and_path_traversal_never_fall_back_to_other_symbol():
    for ref in ("C999", "X1", "DA1", "../VD1", ""):
        with pytest.raises(SymbolProfileMismatch):
            select_tl494_symbol(ref, ("diode.schottky",))
    for identifier in ("diode.missing", "diode.../general", "../diode.schottky",
                       "inductor.nonexisting", "resistor.", ""):
        with pytest.raises(SymbolProfileMismatch):
            load_catalog_pair(identifier)


def test_wrong_pin_number_is_not_a_valid_alias_of_correct_physical_role():
    vd = next(item for item in _scene() if item.reference == "VD1")
    wrong = replace(vd.part, pins=(
        replace(vd.part.pins[0], number="K"),
        vd.part.pins[1],
    ))
    with pytest.raises(SymbolProfileMismatch):
        source_footprint(replace(vd, part=wrong))
