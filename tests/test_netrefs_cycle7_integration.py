"""Independent integration regressions for Issue #90 Draft PR #98.

Every test uses actual owner code; the measured suite runs with a pinned
OpenGost Type A file supplied by the dedicated workflow (never a fake font).
"""
import importlib
import itertools
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_net_continuations_cycle7 import sheet_svg, specimen
from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import (
    ContinuationDirection,
    ContinuationPair,
    ContinuationScope,
    ContinuationSheet,
    ContinuationStub,
    NetContinuationEndpoint,
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef

SVG_NS = "http://www.w3.org/2000/svg"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
FIXTURES = Path(__file__).parent / "fixtures" / "electrical-netrefs-cycle7"


@pytest.mark.parametrize("namespace_alias", ("", "alt", "svg"))
def test_real_svg_modules_in_one_process_cannot_duplicate_xmlns(namespace_alias):
    # No auto-registration by netrefs. Existing modules may register any alias.
    for module in (
        "gost_schematic.rendering.svg",
        "gost_schematic.rendering.sheet_svg",
        "gost_schematic.rendering.formatted_sheet",
        "gost_schematic.rendering.external_wire_sheet",
    ):
        importlib.import_module(module)
    # Restore process-global namespace registry so this test cannot drift
    # later SVG goldens or cause exactly the import-order defect it checks.
    original = ET._namespace_map.copy()
    try:
        ET.register_namespace(namespace_alias, SVG_NS)
        for sheet in specimen().sheets:
            actual = sheet_svg(specimen(), sheet.id)
            assert actual.count('xmlns="http://www.w3.org/2000/svg"') == 1
            assert actual == (FIXTURES / f"sheet-{sheet.number}.svg").read_text("utf-8")
            root = ET.fromstring(actual)
            assert root.tag == f"{{{SVG_NS}}}svg"
            assert len(root.findall(f"{{{SVG_NS}}}title")) == 1
    finally:
        ET._namespace_map.clear()
        ET._namespace_map.update(original)


@pytest.mark.parametrize("order", tuple(itertools.permutations((
    "gost_schematic.rendering.svg",
    "gost_schematic.rendering.sheet_svg",
    "gost_schematic.rendering.external_wire_sheet",
))))
def test_different_import_orders_in_fresh_python_process_preserve_svg(order):
    # Two runtime states: with and without another module registering the SVG URI.
    script = (
        "import importlib, xml.etree.ElementTree as E\n"
        + "".join(f"importlib.import_module({m!r})\n" for m in order)
        + "E.register_namespace('other', 'http://www.w3.org/2000/svg')\n"
        + "from examples.review_net_continuations_cycle7 import sheet_svg,specimen\n"
        + "for sheet in specimen().sheets:\n"
        + " svg=sheet_svg(specimen(),sheet.id)\n"
        + " assert svg.count('xmlns=')==1\n"
        + " assert E.fromstring(svg).tag=='{http://www.w3.org/2000/svg}svg'\n"
        + "print('ORDER_INDEPENDENT')\n"
    )
    run = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        check=False, timeout=25,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "ORDER_INDEPENDENT"


def test_three_sheet_two_pairs_no_hidden_crosspage_wire():
    project = specimen()
    extra_pins = (PinRef("DD3", "1"), PinRef("VT3", "G"))
    parts = (*project.circuit.components, ComponentInstance("DD3", "SYNTHETIC_DD"),
             ComponentInstance("VT3", "SYNTHETIC_FET"))
    real_net = Net("CTRL", (*project.circuit.nets[0].members, *extra_pins))
    e2 = NetContinuationEndpoint(
        "M2-OUT", "N-CTRL-001", "S2", 2, "2/C3", "3/A2",
        Point(100000, 70000), "CTRL", ContinuationDirection.SOURCE,
    )
    e3 = NetContinuationEndpoint(
        "M3-IN", "N-CTRL-001", "S3", 3, "3/A2", "2/C3",
        Point(140000, 70000), "CTRL", ContinuationDirection.TARGET,
    )
    expanded = replace(
        project, circuit=Circuit(parts, (real_net,)),
        nets=(NetIdentity("N-CTRL-001", real_net.name, real_net.members),),
        sheets=(*project.sheets, ContinuationSheet("S3", 3)),
        endpoints=(*project.endpoints, e2, e3),
        pairs=(*project.pairs, ContinuationPair(
            "SECOND-PAIR", "M2-OUT", "M3-IN", ContinuationScope.GLOBAL,
        )),
        stubs=(*project.stubs,
               ContinuationStub("S2-DRAFT-WIRE", e2.id, extra_pins[0],
                                Point(80000, 70000), e2.anchor),
               ContinuationStub("S3-DRAFT-WIRE", e3.id, extra_pins[1],
                                Point(160000, 70000), e3.anchor)),
    )
    assert validate_net_continuations(expanded) == ()
    assert expanded.circuit.nets[0].members == real_net.members
    for sheet in expanded.sheets:
        root = ET.fromstring(sheet_svg(expanded, sheet.id))
        lines = root.findall(f".//{{{SVG_NS}}}line")
        assert len(lines) == (2 if sheet.id == "S2" else 1)
        assert all(x.attrib["data-role"] == "explicit-real-wire-stub" for x in lines)
        assert all(x.attrib["data-net-id"] == "N-CTRL-001" for x in lines)
        assert not root.findall(f".//{{{SVG_NS}}}circle")


def test_sheet_zone_address_points_at_real_declared_sheet():
    project = specimen()
    wrong = replace(project, endpoints=(
        replace(project.endpoints[0], address="9/D4"),
        replace(project.endpoints[1], target_address="9/D4"),
    ))
    assert "E3_CONT_ADDRESS_SHEET_MISMATCH" in {
        d.code for d in validate_net_continuations(wrong)
    }
    # Device/contact-based address is legitimate as an alternative to the
    # project's numeric sheet/zone convention; do not fake a normative regex.
    different = replace(project, endpoints=(
        replace(project.endpoints[0], address="DD1.5"),
        replace(project.endpoints[1], target_address="DD1.5"),
    ))
    assert validate_net_continuations(different) == ()


@pytest.mark.parametrize("bad", ("CTRL\nMORE", "CTRL\x00FAKE", "CTRL\tFAKE"))
def test_illegal_printed_control_characters_rejected_before_xml(bad):
    with pytest.raises(ValueError, match="XML-unsafe"):
        replace(specimen().endpoints[0], label=bad)


def _font():
    path = os.environ.get("GOST_NETREF_FONT")
    if not path:
        pytest.skip("Measured Type A suite runs with GOST_NETREF_FONT in dedicated CI")
    from gost_schematic.engines.annotation.metrics import font_sha256

    font = Path(path)
    assert font.is_file()
    assert font_sha256(str(font)) == FONT_SHA
    return font


def test_measured_type_a_two_sheets_real_glyph_bboxes_keepouts_and_300dpi():
    from io import BytesIO

    import resvg_py
    from PIL import Image

    font = _font()
    project = specimen()
    for sheet in project.sheets:
        svg = sheet_svg(project, sheet.id, font_path=font, review_overlay=True)
        root = ET.fromstring(svg)
        assert root.attrib["data-font-sha256"] == FONT_SHA
        assert root.attrib["data-approval"] == "DRAFT_MEASURED_TYPE_A_ESKD_PENDING"
        assert svg.count('xmlns="http://www.w3.org/2000/svg"') == 1
        texts = root.findall(f".//{{{SVG_NS}}}text")
        keepouts = root.findall(f".//{{{SVG_NS}}}rect")
        lines = root.findall(f".//{{{SVG_NS}}}line")
        assert len(texts) == len(keepouts) == 2
        assert len(lines) == 1
        assert {e.attrib["data-role"] for e in texts} == {
            "measured-net-label", "measured-remote-address",
        }
        assert texts[0].attrib["data-font-sha256"] == FONT_SHA
        assert texts[1].attrib["data-font-sha256"] == FONT_SHA
        for text in texts:
            lo = tuple(map(int, text.attrib["data-ink-box"].split(",")))
            safe = tuple(map(int, text.attrib["data-protected-box"].split(",")))
            assert safe[0] <= lo[0] < lo[2] <= safe[2]
            assert safe[1] <= lo[1] < lo[3] <= safe[3]
            assert safe[2] - safe[0] >= lo[2] - lo[0] + 2000
        assert all(x.attrib["data-role"] == "review-text-keepout" for x in keepouts)
        clean = sheet_svg(project, sheet.id, font_path=font)
        assert not ET.fromstring(clean).findall(f".//{{{SVG_NS}}}rect")
        assert clean.count('data-role="explicit-real-wire-stub"') == 1
        with Image.open(BytesIO(resvg_py.svg_to_bytes(svg_string=clean, dpi=300))) as img:
            assert img.format == "PNG"
            assert img.width >= 2480 and img.height >= 3507


def test_long_cyrillic_ink_overflow_and_nearby_marker_collision_fail_closed():
    font = _font()
    project = specimen()
    huge = "СИГНАЛ_УПРАВЛЕНИЯ_АВТОМАТИЗАЦИИ_" * 30
    long_labels = replace(project, endpoints=tuple(
        replace(e, label=huge) for e in project.endpoints
    ))
    assert validate_net_continuations(long_labels) == ()
    with pytest.raises(ValueError, match="E3_CONT_TEXT_PAGE_OVERFLOW"):
        sheet_svg(long_labels, "S1", font_path=font)
    # Two separate graphic marker positions on the SAME sheet; this is not
    # evidence of an electrical junction and may not overlap measured ink.
    a, b = project.endpoints
    near = replace(b, sheet_id="S1", sheet_number=1,
                   address="1/B7", anchor=Point(83000, 40000))
    first = replace(a, target_address="1/B7")
    local = replace(
        project, endpoints=(first, near),
        pairs=(replace(project.pairs[0], scope=ContinuationScope.SHEET_LOCAL),),
        stubs=(project.stubs[0], replace(project.stubs[1], end=near.anchor)),
    )
    assert validate_net_continuations(local) == ()
    with pytest.raises(ValueError, match="E3_CONT_TEXT_(TEXT|WIRE)_COLLISION"):
        sheet_svg(local, "S1", font_path=font)


def test_explicit_xml_measured_is_import_order_independent_when_font_available():
    font = _font()
    importlib.import_module("gost_schematic.rendering.sheet_svg")
    original = ET._namespace_map.copy()
    try:
        ET.register_namespace("netrefs_external", SVG_NS)
        a = sheet_svg(specimen(), "S1", font_path=font)
        assert ET.fromstring(a).tag == f"{{{SVG_NS}}}svg"
        ET.register_namespace("", SVG_NS)
        assert sheet_svg(specimen(), "S1", font_path=font) == a
    finally:
        ET._namespace_map.clear()
        ET._namespace_map.update(original)
