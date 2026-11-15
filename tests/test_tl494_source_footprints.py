"""Independent immutable physical source-footprint and router obstacle gates."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_tl494_ugo_source_cycle9 import generate
from gost_schematic.agent_project.catalog import value_digest
from gost_schematic.catalog.source_digest import value_digest as source_value_digest
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
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.routing.clearance import validate_wire_clearance
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.pins import ElectricalType, PhysicalPin
from scripts.verify_tl494_cycle11_owner_strokes import (
    source_pair_conservative_ink_gap_um,
    parse_real_pin_coordinates,
    verify_real_pin_markers,
)


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


def test_frozen_source_pose_cannot_move_but_opt_in_new_A3_may_relocate():
    """New-A3 symbol obstacles must be re-derived, never reuse old 91-wire poses."""
    manifest = read_source_manifest()
    parts, symbols, original = {}, {}, []
    for row in manifest["profiles"]:
        s, p = load_catalog_pair(row["symbol_id"])
        parts[p.identifier] = p
        symbols[s.identifier] = s
        origin = Point(*[round(x * 1000) for x in row["source_layout_origin_mm"]])
        original.append(ComponentInstance(
            row["reference"], p.identifier, origin,
            Transform(row["rotation"], row["mirror_x"]),
        ))
    original = tuple(original)
    preserved = bind_tl494_source(original, parts, symbols)
    vd = original[0]
    moved = (replace(
        vd, origin=Point(205000, 138750), transform=Transform(270, True)
    ), *original[1:])
    with pytest.raises(SymbolProfileMismatch, match="frozen source"):
        bind_tl494_source(moved, parts, symbols)
    shifted = bind_tl494_source(
        moved, parts, symbols, allow_relayout=True
    )
    assert shifted[0].pin_refs == preserved[0].pin_refs
    assert shifted[0].pin_positions != preserved[0].pin_positions
    pinmap = moved[0].pin_positions(shifted[0].symbol)
    assert shifted[0].pin_positions == tuple(
        pinmap[pin.number] for pin in shifted[0].part.pins
    )
    record = footprint_record(source_footprint(shifted[0]))
    assert record["rotation"] == 270 and record["mirror_x"]
    assert record["physical_pin_roles"][0]["name"] == "A"
    assert record["physical_pin_roles"][1]["name"] == "K"
    with pytest.raises(TypeError, match="boolean"):
        bind_tl494_source(original, parts, symbols, allow_relayout="yes")



@pytest.mark.parametrize("which", ("VD1", "VT1", "FU1", "R5"))
def test_swapped_same_set_physical_numbers_are_not_a_role_preserving_pinmap(which):
    binding = next(item for item in _scene() if item.reference == which)
    part = binding.part
    assert len(part.pins) >= 2
    swapped = replace(part, pins=(
        replace(part.pins[0], number=part.pins[1].number),
        replace(part.pins[1], number=part.pins[0].number),
        *part.pins[2:],
    ))
    # Same number SET, same role ORDER: a set-only check would silently
    # claim A=2/K=1, or MOS G=2/D=1. Both MUST be rejected.
    assert {p.number for p in swapped.pins} == {p.number for p in part.pins}
    assert tuple(p.name for p in swapped.pins) == tuple(
        p.name for p in part.pins
    )
    with pytest.raises(SymbolProfileMismatch):
        source_footprint(replace(binding, part=swapped))


@pytest.mark.parametrize("which", ("VD1", "VT1", "C1", "L1"))
def test_swapped_graphic_terminal_numbers_preserving_names_also_blocked(which):
    binding = next(item for item in _scene() if item.reference == which)
    symbol = binding.symbol
    swapped = replace(symbol, pins=(
        replace(symbol.pins[0], number=symbol.pins[1].number),
        replace(symbol.pins[1], number=symbol.pins[0].number),
        *symbol.pins[2:],
    ))
    assert tuple(pin.label for pin in swapped.pins) == tuple(
        pin.label for pin in symbol.pins
    )
    with pytest.raises(SymbolProfileMismatch):
        source_footprint(replace(binding, symbol=swapped))


@pytest.mark.parametrize("which", ("VD1", "VT1", "L1"))
def test_forged_fourth_physical_contact_or_extra_mos_body_pin_rejected(which):
    binding = next(item for item in _scene() if item.reference == which)
    part = replace(binding.part, pins=(
        *binding.part.pins,
        PhysicalPin("99", "IMAGINARY_BODY", ElectricalType.PASSIVE),
    ))
    with pytest.raises(SymbolProfileMismatch):
        source_footprint(replace(binding, part=part))


def test_all_13_source_records_pinmap_is_explicit_and_unique():
    meta = read_source_manifest()
    assert len(meta["profiles"]) == 13
    for row in meta["profiles"]:
        sym, part = load_catalog_pair(row["symbol_id"])
        assert row["expected_pin_numbers"] == [pin.number for pin in part.pins]
        assert row["expected_pin_numbers"] == [pin.number for pin in sym.pins]
        assert len(set(row["expected_pin_numbers"])) == len(part.pins)
        assert len(row["expected_pin_numbers"]) == len(row["expected_physical_roles"])
    assert {
        row["reference"]: row["expected_pin_numbers"]
        for row in meta["profiles"] if row["reference"] in ("VD1", "VT1", "R5")
    } == {
        "VD1": ["1", "2"], "VT1": ["1", "2", "3"], "R5": ["1", "2", "3"],
    }



@pytest.mark.parametrize("value,expected", (
    ("1:0,0", {"1": (0, 0)}),
    ("A:-11000,3000;K:0,-12500",
     {"A": (-11000, 3000), "K": (0, -12500)}),
    ("1:0,0;2:1000,-1000;3:3500,500",
     {"1": (0, 0), "2": (1000, -1000), "3": (3500, 500)}),
))
def test_real_paint_pin_metadata_exact_number_and_micrometre(value, expected):
    assert parse_real_pin_coordinates(value) == expected


@pytest.mark.parametrize("bad", (
    "", "1:0,0;1:0,0", "1:0,0;1:1000,1000",
    "1:0", "1:0,1,2", "1:0,2;", ":1,2",
    "1:2.5,0", "1:0,1;bad", "1:0,a",
))
def test_real_paint_pin_metadata_negative_fails_closed(bad):
    with pytest.raises(ValueError, match="UGO_PIN_METADATA"):
        parse_real_pin_coordinates(bad)


def _test_marker_root(*, coords=("0", "0"),
                      pin="1", size="1.2"):
    ns = "{http://www.w3.org/2000/svg}"
    root = ET.Element(ns + "svg")
    ET.SubElement(root, ns + "rect", {
        "data-editor-target": "true",
        "data-physical-pin": pin,
        "x": coords[0],
        "y": coords[1],
        "width": size,
        "height": size,
    })
    return root


def test_debug_pin_marker_real_tip_on_exact_one_micrometre():
    root = _test_marker_root(coords=("0.634", "-0.325"))
    expected = {"1": (1234, 275)}
    assert verify_real_pin_markers(root, expected, diagnostic=True) == 1
    with pytest.raises(ValueError, match="UGO_CLEAN"):
        verify_real_pin_markers(root, expected, diagnostic=False)
    ns = "{http://www.w3.org/2000/svg}"
    root.remove(root.find(ns + "rect"))
    assert verify_real_pin_markers(root, expected, diagnostic=False) == 0
    with pytest.raises(ValueError, match="UGO_DEBUG_PHYSICAL_PIN"):
        verify_real_pin_markers(root, expected, diagnostic=True)


@pytest.mark.parametrize("coords,pin,size,code", (
    (("0", "0"), "1", "1.2", "UGO_DEBUG_PIN_TIP"),
    (("0.634", "-0.325"), "2", "1.2", "UGO_DEBUG_PIN_UNKNOWN"),
    (("0.634", "-0.325"), "1", "1.3", "UGO_DEBUG_PIN_TIP"),
    (("0.6341", "-0.325"), "1", "1.2", "UGO_MARKER_NOT_EXACT"),
    (("nan", "-0.325"), "1", "1.2", "UGO_MARKER_NOT_EXACT"),
    (("bad", "-0.325"), "1", "1.2", "UGO_MARKER_INVALID"),
))
def test_debug_marker_rejects_non_tip_drift_and_impostor(
    coords, pin, size, code,
):
    root = _test_marker_root(coords=coords, pin=pin, size=size)
    with pytest.raises(ValueError, match=code):
        verify_real_pin_markers(root, {"1": (1234, 275)}, diagnostic=True)


def test_debug_marker_duplicate_true_physical_pin_number_rejected():
    root = _test_marker_root(coords=("0.634", "-0.325"))
    ns = "{http://www.w3.org/2000/svg}"
    ET.SubElement(root, ns + "rect", {
        "data-editor-target": "true",
        "data-physical-pin": "1",
        "x": "0.634", "y": "-0.325", "width": "1.2", "height": "1.2",
    })
    with pytest.raises(ValueError, match="UGO_DEBUG_PIN_UNKNOWN_OR_DUPLICATED"):
        verify_real_pin_markers(root, {"1": (1234, 275)}, diagnostic=True)



@pytest.mark.parametrize("which", (
    "VD1", "VT1", "C1", "C2", "C3", "C4", "C5", "C6", "C7",
    "L1", "L2", "FU1", "R5",
))
def test_catalog_digest_matches_old_project_exact_format(which):
    """Live owner consumers must not pull AI-agent package for SHA-only code."""
    bound = next(entry for entry in _scene() if entry.reference == which)
    for record in (bound.part, bound.symbol, footprint_record(source_footprint(bound))):
        assert source_value_digest(record) == value_digest(record)
    assert source_value_digest(bound.part) == source_footprint(bound).part_sha256
    assert source_value_digest(bound.symbol) == source_footprint(bound).symbol_sha256


@pytest.mark.parametrize("invalid", (object(), 3.14, {1, 2}, float("nan")))
def test_ugo_digest_refuses_unknown_noncanonical_inputs(invalid):
    with pytest.raises(ValueError, match="UGO_DIGEST_UNSUPPORTED"):
        source_value_digest(invalid)



@pytest.mark.parametrize("gap_um", (0, 1999, 2000, 2001, 3500))
def test_conservative_source_ugo_ink_pair_integer_threshold(gap_um):
    """Typed source ink obstacles; no float-rounding at 2mm boundary."""
    original = _scene()
    diode = source_footprint(next(x for x in original if x.reference == "VD1"))
    mosfet = source_footprint(next(x for x in original if x.reference == "VT1"))
    first = replace(
        diode,
        ink_obstacles=(replace(diode.ink_obstacles[0],
                               box=Box(0, 0, 1000, 1000)),),
    )
    second = replace(
        mosfet,
        ink_obstacles=(replace(mosfet.ink_obstacles[0],
                               box=Box(1000 + gap_um, 0,
                                       2000 + gap_um, 1000)),),
    )
    measured = source_pair_conservative_ink_gap_um(first, second)
    assert measured == gap_um
    assert (measured >= 2000) == (gap_um >= 2000)


def test_conservative_source_ugo_empty_ink_never_counts_as_clear():
    original = _scene()
    diode = source_footprint(next(x for x in original if x.reference == "VD1"))
    mosfet = source_footprint(next(x for x in original if x.reference == "VT1"))
    with pytest.raises(AssertionError, match="UGO_INK_EMPTY_OBSTACLES"):
        source_pair_conservative_ink_gap_um(
            replace(diode, ink_obstacles=()), mosfet,
        )
