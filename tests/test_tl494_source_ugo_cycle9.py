"""TL494 source-photo exact UGO type/pin contracts and negative substitutions.

Source is reference/tl494-native-rework-20261114 HEAD e695c415,
NOT a fabricated printed GOST 1:1 acceptance. All new gates are DRAFT.
"""

import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_tl494_ugo_source_cycle9 import (
    D4_IDS, _actual_root, _source_variant, generate, pose_symbol,
)
from gost_schematic.catalog.source_profiles import (
    PINNED_REFERENCE_SHA, REQUIRED_REFERENCES, SymbolProfileMismatch,
    bind_tl494_source, check_ink_contract, load_catalog_pair,
    read_source_manifest,
)
from gost_schematic.core.geometry import Circle, Line, Point, Semicircle, StyledLine
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import ComponentInstance, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"


def source_scene():
    source = read_source_manifest()
    instances, parts, symbols = [], {}, {}
    for entry in source["profiles"]:
        identifier = entry["symbol_id"]
        symbol, part = load_catalog_pair(identifier)
        parts[identifier], symbols[identifier] = part, symbol
        origin = Point(*(int(n * 1000) for n in entry["source_layout_origin_mm"]))
        instances.append(ComponentInstance(
            entry["reference"], identifier, origin,
            Transform(entry["rotation"], entry["mirror_x"]),
        ))
    return instances, parts, symbols


def test_reference_pinned_13_actual_roles_and_positions():
    meta = read_source_manifest()
    assert meta["reference_sha"] == PINNED_REFERENCE_SHA
    assert tuple(row["reference"] for row in meta["profiles"]) == REQUIRED_REFERENCES
    assert meta["source_counts"] == {
        "components": 23, "nets": 15, "wires": 91, "DA1_physical_pins": 16
    }
    scene, parts, symbols = source_scene()
    bindings = bind_tl494_source(scene, parts, symbols)
    assert len(bindings) == 13
    for binding, entry in zip(bindings, meta["profiles"], strict=True):
        assert binding.reference == entry["reference"]
        assert binding.symbol.status is SymbolStatus.DRAFT
        assert tuple(pin.name for pin in binding.part.pins) == tuple(
            entry["expected_physical_roles"]
        )
        assert tuple(pin.label for pin in binding.symbol.pins) == tuple(
            entry["expected_graphic_labels"]
        )
        assert tuple(binding.pin_positions) == tuple(Point(
            round(x * 1000), round(y * 1000)
        ) for x, y in entry["source_pin_endpoints_mm"])
        assert all(p.reference == entry["reference"] for p in binding.pin_refs)
        assert not binding.figure_reference.startswith("APPROVED")


@pytest.mark.parametrize("wrong_ref,wrong_id", [
    ("VD1", "diode.general"), ("VT1", "transistor.bjt_npn"),
    ("L1", "inductor.air_core"), ("L2", "inductor.ferrite"),
    ("C1", "capacitor.electrolytic"), ("C2", "capacitor.fixed"),
    ("C3", "capacitor.electrolytic"), ("C4", "capacitor.polarized"),
    ("C5", "capacitor.fixed"), ("C6", "capacitor.electrolytic"),
    ("C7", "capacitor.polarized"), ("FU1", "resistor.fixed"),
    ("R5", "resistor.fixed"),
])
def test_wrong_photo_symbol_selection_fails_closed(wrong_ref, wrong_id):
    scene, parts, symbols = source_scene()
    wrong = tuple(
        replace(x, part_id=wrong_id) if x.reference == wrong_ref else x
        for x in scene
    )
    with pytest.raises(SymbolProfileMismatch, match=wrong_ref):
        bind_tl494_source(wrong, parts, symbols)


def test_missing_duplicate_and_wrong_source_orientation_fail_closed():
    scene, parts, symbols = source_scene()
    for bad in (
        tuple(x for x in scene if x.reference != "VD1"),
        (*scene, scene[0]),
        tuple(replace(x, transform=Transform(180)) if x.reference == "VD1"
              else x for x in scene),
        tuple(replace(x, part_id="capacitor.fixed") if x.reference == "C5"
              else x for x in scene),
    ):
        with pytest.raises(SymbolProfileMismatch):
            bind_tl494_source(bad, parts, symbols)


def test_reference_schottky_asymmetry_both_hooks_and_A_top_K_bottom():
    symbol, part = load_catalog_pair("diode.schottky")
    simple, _ = load_catalog_pair("diode.general")
    assert tuple(p.name for p in part.pins) == ("A", "K")
    assert len(symbol.graphics) == 10 and len(simple.graphics) == 6
    assert symbol.graphics[:6] == simple.graphics
    check_ink_contract(symbol, part)
    # Original GOST uses two OPPOSITE cathode barbs, not an equal-sided Zener.
    top = symbol.graphics[6:8]
    bottom = symbol.graphics[8:10]
    assert top[0].end.x > top[0].start.x
    assert bottom[0].end.x < bottom[0].start.x
    assert top[1].end.y > top[1].start.y
    assert bottom[1].end.y > bottom[1].start.y
    assert top[1].end.x != bottom[1].end.x
    # Source pose is exactly 90deg clockwise in a y-down page coordinate set.
    rotated = pose_symbol(symbol, Transform(90))
    assert rotated.pins[0].at == Point(0, -10000)
    assert rotated.pins[1].at == Point(0, 10000)
    assert rotated.pins[0].label == "A"
    assert rotated.pins[1].label == "K"
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",))


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("identifier", D4_IDS)
def test_true_ink_every_D4_and_physical_roles_is_preserved(identifier, angle, mirror):
    symbol, part = load_catalog_pair(identifier)
    t = Transform(angle, mirror)
    posed = pose_symbol(symbol, t)
    assert len(posed.pins) == len(part.pins)
    assert tuple(p.number for p in posed.pins) == tuple(p.number for p in part.pins)
    assert len({p.at for p in posed.pins}) == len(part.pins)
    assert posed.graphics == tuple(t.primitive(g) for g in symbol.graphics)
    assert tuple(p.at for p in posed.pins) == tuple(t.apply(p.at) for p in symbol.pins)
    assert tuple(p.side for p in posed.pins) == tuple(
        t.side(p.side) for p in symbol.pins
    )
    assert inspect_conductor_topology(posed).valid
    rendered, _ = _actual_root(symbol, "VD" if identifier.startswith("diode")
                               else "VT", t, diagnostic=False)
    assert rendered.find(f".//{SVG}g") is not None
    assert not rendered.findall(f".//{SVG}rect[@data-editor-target]")
    assert not rendered.findall(f".//{SVG}image")


def test_schottky_wrong_hook_or_swapped_physical_A_K_is_not_accepted():
    symbol, part = load_catalog_pair("diode.schottky")
    bad = list(symbol.graphics)
    bad[9] = Line(Point(800, 3300), Point(800, 1800))
    with pytest.raises(SymbolProfileMismatch, match="asymmetric"):
        check_ink_contract(replace(symbol, graphics=tuple(bad)), part)
    swapped = replace(part, pins=(replace(part.pins[0], name="K"),
                                  replace(part.pins[1], name="A")))
    scene, parts, symbols = source_scene()
    parts["diode.schottky"] = swapped
    with pytest.raises(SymbolProfileMismatch, match="VD1"):
        bind_tl494_source(scene, parts, symbols)


def test_MOS_three_physical_roles_no_4th_gate_touch_and_real_source_dot():
    symbol, part = load_catalog_pair("transistor.mosfet_n_enh")
    check_ink_contract(symbol, part)
    assert tuple(pin.name for pin in part.pins) == ("G", "D", "S")
    assert len(symbol.pins) == len(part.pins) == 3
    assert symbol.graphics[0].end == Point(-4000, 0)
    assert symbol.graphics[3].start == Point(-4000, -3000)
    assert symbol.graphics[4].end.y == -1000
    assert symbol.graphics[5].start.y == 1000
    assert symbol.conductor_topology.conductor_indices == (0, 1, 2)
    variant = _source_variant(symbol, "VT1")
    assert len(variant.pins) == 3
    assert len(variant.graphics) == len(symbol.graphics) + 1
    assert isinstance(variant.graphics[-1], Circle)
    assert variant.graphics[-1].center == Point(0, 5000)
    assert variant.conductor_topology == symbol.conductor_topology
    assert inspect_conductor_topology(variant).pin_islands == (
        ("1",), ("2",), ("3",)
    )
    # Optional schematic circle is a drawing, not an electrical case pin/footprint.
    encased, case_part = load_catalog_pair("transistor.mosfet_n_enh.with_case")
    assert len(encased.pins) == len(case_part.pins) == 3
    assert isinstance(encased.graphics[-1], Circle)
    assert encased.pins == symbol.pins
    assert encased.conductor_topology == symbol.conductor_topology


def test_negative_fake_MOS_gate_to_channel_or_fourth_pin_fails():
    symbol, part = load_catalog_pair("transistor.mosfet_n_enh")
    fake = list(symbol.graphics)
    fake[0] = Line(Point(-11000, 0), Point(0, 0))
    with pytest.raises(SymbolProfileMismatch, match="gate"):
        check_ink_contract(replace(symbol, graphics=tuple(fake)), part)
    fake = list(symbol.graphics)
    fake[6] = Line(Point(1, 0), Point(4, 0))
    with pytest.raises(SymbolProfileMismatch, match="arrow"):
        check_ink_contract(replace(symbol, graphics=tuple(fake)), part)


@pytest.mark.parametrize("name", ["transistor.bjt_npn", "transistor.bjt_pnp"])
def test_BJT_emitter_arrow_and_schematic_case_not_manufacturer_package(name):
    symbol, part = load_catalog_pair(name)
    enclosed, enclosed_part = load_catalog_pair(name + ".with_case")
    assert len(part.pins) == len(enclosed_part.pins) == 3
    assert tuple(p.name for p in part.pins) == ("B", "C", "E")
    assert enclosed.graphics[:-1] == symbol.graphics
    assert isinstance(enclosed.graphics[-1], Circle)
    assert all(not isinstance(g, Circle) for g in symbol.graphics)
    assert enclosed.conductor_topology == symbol.conductor_topology
    assert inspect_conductor_topology(symbol).pin_islands == (
        ("1",), ("2",), ("3",)
    )
    emitter = symbol.graphics[2]
    marker = symbol.graphics[4]
    dot = ((marker.end.x - marker.start.x) * (emitter.end.x - emitter.start.x)
           + (marker.end.y - marker.start.y) * (emitter.end.y - emitter.start.y))
    assert dot > 0 if name.endswith("npn") else dot < 0
    if name.endswith("npn"):
        assert any("EXPERIMENTAL_DERIVED_NOT_SOURCE_FIGURE" in s
                   for s in symbol.standard_refs)


def test_all_seven_capacitor_profiles_are_thin_plate_and_have_right_polarity():
    source = read_source_manifest()
    for p in source["profiles"]:
        if not p["reference"].startswith("C"):
            continue
        symbol, part = load_catalog_pair(p["symbol_id"])
        check_ink_contract(symbol, part)
        if p["reference"] in ("C1", "C2", "C3", "C5", "C6"):
            assert p["symbol_id"] == "capacitor.polarized"
            assert tuple(x.label for x in symbol.pins) == ("+", "-")
            assert part.pins[0].polarity.value == "positive"
            assert part.pins[1].polarity.value == "negative"
        else:
            assert p["symbol_id"] == "capacitor.fixed"
            assert all(not x.label for x in symbol.pins)
        assert all(isinstance(item, Line) for item in symbol.graphics)


def test_ferromagnetic_core_is_a_real_nonconductive_graphic_not_air():
    for candidate in ("L1", "L2"):
        symbol, part = load_catalog_pair("inductor.ferromagnetic")
        check_ink_contract(symbol, part)
        assert sum(isinstance(s, Semicircle) for s in symbol.graphics) == 4
        core = [g for g in symbol.graphics if isinstance(g, StyledLine)]
        assert len(core) == 1
        assert not any(symbol.graphics[i] is core[0] for i
                       in symbol.conductor_topology.conductor_indices)
        air, _ = load_catalog_pair("inductor.ferromagnetic")
        no_core = replace(air, graphics=air.graphics[:-1])
        with pytest.raises(SymbolProfileMismatch, match="core"):
            check_ink_contract(no_core, part)
        assert candidate in ("L1", "L2")


def test_real_R5_wiper_and_FU1_not_short():
    for key in ("resistor.variable", "fuse.general"):
        symbol, part = load_catalog_pair(key)
        check_ink_contract(symbol, part)
        assert len(inspect_conductor_topology(symbol).pin_islands) == len(part.pins)


def test_native_source_gallery_is_deterministic_and_all_debug_only(tmp_path: Path):
    a = generate(tmp_path)
    assert a["gallery_count"] == 13
    assert a["normative_approved"] == 0
    assert len(a["d4"]) == 8 * len(D4_IDS)
    assert len(a["files"]) == 13 * 2 + 8 * len(D4_IDS) + 2
    assert a["source_1to1_status"].startswith("BLOCKED")
    assert not a["source_bitmap_available"]
    expected = {name: (tmp_path / name).read_bytes() for name in a["files"]}
    assert (tmp_path / "index.html").is_file()
    assert generate(tmp_path) == a
    assert expected == {name: (tmp_path / name).read_bytes() for name in a["files"]}
    for name in a["files"]:
        root = ET.fromstring((tmp_path / name).read_bytes())
        if name.endswith("-diagnostic.svg"):
            assert root.findall(f".//{SVG}rect[@data-editor-target='true']")
        else:
            assert not root.findall(f".//{SVG}rect[@data-editor-target='true']")
        assert root.attrib["width"].endswith("mm")
        assert not root.findall(f".//{SVG}image")
    metadata = json.loads(
        (tmp_path / "TL494-UGO-cycle9-manifest.json").read_text(encoding="utf-8")
    )
    assert metadata == a
