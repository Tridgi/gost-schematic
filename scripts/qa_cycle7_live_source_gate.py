"""Independent Cycle7 live-source QA gate. Runs ONLY in pinned owner overlay CI.

Every imported implementation comes from an exact owner commit, never a mock.
All graphical and normative results are DRAFT; no production source is edited.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
from PIL import Image

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import SIDE_VECTORS, Box, Circle, Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

ROOT = Path(__file__).resolve().parents[1]
SVG = "{http://www.w3.org/2000/svg}"
OWNER = {
    "paint": "165017630dc911c3006eda35424d8293498db100",
    "ic": "e65ee3f220084ee32ef8f71a48274ce39e933bf2",
    "net": "8ab0778a67c2e56be4be9cd0297e454413f56028",
    "catalog": "37f7c5e58938db1d5bcf308ff04e740356afc0e4",
    "project": "a58ecd388a7cf99fe6cc2f7340d39403b0fa9abf",
    "norm_merge": "1e54166304928ba27eaf674d79597e1d527fb3bb",
}
SOURCE_BLOBS = {
    "src/gost_schematic/rendering/ic_rectangular.py": "bff0caf982a14ebd2bacda15b419f9b4bcc16f70",
    "src/gost_schematic/electrical/ic.py": "879ced36cd11c2607bcac1db345bd75cae06e54a",
    "src/gost_schematic/electrical/netrefs.py": "729a53b4ea19d68b0be1372e745863a11eb83d07",
    "src/gost_schematic/electrical/ic_paint_bridge.py": "99148380fe6b44c0458cb519dbc1d461de886e7c",
    "src/gost_schematic/agent_project/service.py": "6d20a3020e30c114d9e9931e5e4762b1c3cb9489",
    "docs/standards/issue-91-deep-source-audit.json": "07b2ab53b64fe40fe35750f0a21b52db8ca66c30",
    "docs/catalog/electronic-cycle7-second-batch-cards.json": "19e0b0ad1c8d88819bf8a6e46511c386b30f7899",
    "docs/catalog/issue89-acceptance-matrix.json": "0c16ba218f64437aa202ec56a7e30b02fdc73866",
}
NAMES = (
    "resistor.variable", "resistor.trimmer", "fuse.general",
    "transistor.bjt_pnp", "transistor.bjt_pnp.with_case",
    "transistor.bjt_npn", "transistor.bjt_npn.with_case",
    "transistor.mosfet_n_enh", "transistor.mosfet_n_enh.with_case",
    "transistor.mosfet_p_enh", "transistor.mosfet_p_enh.with_case",
    "diode.schottky", "diode.led", "diode.photodiode", "diode.varicap",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _blob(path):
    b = (ROOT / path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()


def provenance():
    for path, sha in SOURCE_BLOBS.items():
        require(_blob(path) == sha, f"OWNER_BLOB_SHA_MISMATCH: {path}")
    a = json.loads((ROOT / "docs/standards/issue-91-deep-source-audit.json").read_text())
    b = json.loads((ROOT / "docs/standards/issue-91-cycle7-electronics-cards.json").read_text())
    require(len(b["cards"]) == 107, "ESKD_NEW_107_CARD_COUNT")
    require(all(c["approval"] == "DRAFT" and c["acceptance"] == "BLOCKED"
                for c in b["cards"]), "ESKD_FALSE_APPROVAL")
    require(len(a["exceptions_for_legacy_107"]) >= 4, "ESKD_DEEP_EXCEPTIONS")
    require(b["stats"]["approved_ugos"] == 0, "ESKD_ANY_APPROVED")
    return {"source_sha1_verified": len(SOURCE_BLOBS),
            "norm_new_candidates": 107, "norm_approved": 0,
            "norm_downgraded": a["exceptions_for_legacy_107"]}


def _symbol_paths(identifier):
    prefix, name = identifier.split(".", 1)
    folder = {
        "resistor": "resistors", "fuse": "fuses",
        "transistor": "transistors", "diode": "diodes",
    }[prefix]
    filename = name.replace(".with_case", "_with_case") + ".json"
    folder1 = ROOT / "src/gost_schematic/catalog"
    return (folder1 / "symbols" / folder / filename,
            folder1 / "parts" / folder / filename)


def _save_svg_png(svg, output, stem, *, count):
    xml = ET.fromstring(svg)
    require(xml.tag == SVG + "svg", f"INVALID_XML_{stem}")
    f_svg = output / (stem + ".svg")
    f_png = output / (stem + "-300dpi.png")
    f_svg.write_text(svg, encoding="utf-8")
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(f_png), dpi=300)
    with Image.open(f_png) as original:
        pic = original.convert("RGB")
        require(pic.width > 30 and pic.height > 30, f"ZERO_RASTER_{stem}")
        dark = sum(max(p) < 150 for p in pic.getdata())
        require(dark > count, f"NO_VISIBLE_INK_{stem}")
        size = [pic.width, pic.height]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (f_svg, f_png)}, size


def catalog_gallery(output):
    from gost_schematic.validation.circuit_checks import validate_circuit

    review = json.loads((ROOT / "docs/catalog/electronic-cycle7-second-batch-cards.json").read_text())
    first = json.loads((ROOT / "docs/catalog/electronic-cycle7-first-batch-cards.json").read_text())
    cards = {row["id"]: row for row in (*first["cards"], *review["cards"])}
    require(set(cards) == set(NAMES), "CATALOG_15_CARD_ID_MISMATCH")
    acceptance = json.loads((ROOT / "docs/catalog/issue89-acceptance-matrix.json").read_text())
    require(acceptance["release"].startswith("BLOCKED"), "OWNER_89_RELEASE_FALSE")
    require({x["id"] for x in acceptance["cards"]} == set(NAMES),
            "OWNER_89_INDEPENDENT_MATRIX_INCOMPLETE")
    require(all(x["release"] == "DRAFT_NOT_APPROVED" and
                x["figure_overlay"].startswith("BLOCKED") and
                x["real_device_pinmap"].startswith("BLOCKED")
                for x in acceptance["cards"]), "OWNER_89_NORMATIVE_FALSE_PASS")
    files, result = {}, {}
    roles = {"resistor": ("A", "B", "W"), "fuse": ("A", "B"),
             "transistor": None, "diode": ("A", "K")}
    for identifier in NAMES:
        sym_path, part_path = _symbol_paths(identifier)
        require(sym_path.is_file() and part_path.is_file(), f"MISSING_REAL_PAIR_{identifier}")
        symbol, part = load_symbol(sym_path), load_part(part_path)
        require(symbol.identifier == part.identifier == part.symbol_id == identifier,
                f"PART_SYMBOL_ID_MISMATCH_{identifier}")
        require(symbol.status == SymbolStatus.DRAFT, f"FALSE_APPROVAL_{identifier}")
        pin_numbers = tuple(p.number for p in part.pins)
        require(pin_numbers == tuple(p.number for p in symbol.pins),
                f"PIN_NUMBER_MISMATCH_{identifier}")
        require(len(set(pin_numbers)) == len(pin_numbers), f"PIN_DUPLICATE_{identifier}")
        family = identifier.split(".")[0]
        expected = roles[family]
        if family == "transistor":
            expected = ("B", "C", "E") if ".bjt_" in identifier else ("G", "D", "S")
        require(tuple(p.name for p in part.pins) == expected,
                f"PHYSICAL_ROLE_MISMATCH_{identifier}")
        trace = inspect_conductor_topology(symbol)
        require(trace.valid, f"CONDUCTOR_TOPOLOGY_BAD_{identifier}")
        require(trace.pin_islands == tuple((number,) for number in pin_numbers),
                f"CONDUCTIVE_SHORT_{identifier}")
        row = cards[identifier]
        if "release_acceptance" in row:
            require(row["release_acceptance"].startswith("BLOCKED"),
                    f"NORM_PREMATURE_ACCEPTANCE_{identifier}")
            require(row["manufacturer_pinout"] == "UNVERIFIED_ABSTRACT_NUMBERING",
                    f"VENDOR_ID_FALSE_CLAIM_{identifier}")
        else:
            require(str(row.get("approval", "DRAFT")).upper() == "DRAFT",
                    f"FIRST_BATCH_FALSE_APPROVAL_{identifier}")
        if ".with_case" in identifier:
            require(sum(isinstance(g, Circle) for g in symbol.graphics) == 1,
                    f"CASE_CIRCLE_MISSING_{identifier}")
        elif family == "transistor":
            require(not any(isinstance(g, Circle) for g in symbol.graphics),
                    f"UNEXPECTED_CASE_{identifier}")
        if ".bjt_npn" in identifier:
            require(any("EXPERIMENTAL_DERIVED" in t for t in symbol.standard_refs),
                    f"NPN_SOURCE_FIGURE_MISREPRESENTED_{identifier}")
        if family == "diode":
            require(len(part.pins) == 2 and tuple(p.label for p in symbol.pins)
                    == ("A", "K"), f"DIODE_PIN_ROLES_{identifier}")
            require(len(symbol.conductor_topology.conductor_indices) == 2,
                    f"PHOTON_AS_CONDUCTOR_{identifier}")
        ref = "R1" if family == "resistor" else ("FU1" if family == "fuse" else
              ("VT1" if family == "transistor" else "VD1"))
        for angle in (0, 90, 180, 270):
            for mirror in (False, True):
                trans = Transform(angle, mirror)
                instance = ComponentInstance(ref, identifier, Point(100000, 90000), trans)
                points = instance.pin_positions(symbol)
                require(len(points) == len(part.pins) == len(set(points.values())),
                        f"D4_PIN_COLLISION_{identifier}")
                require(all(points[p.number] == trans.apply(p.at) + instance.origin
                            for p in symbol.pins), f"D4_PINREF_CHANGED_{identifier}")
        component = ComponentInstance(ref, identifier)
        circuit = Circuit((component,), tuple(Net(
            f"N_{i}", (PinRef(ref, pin),)) for i, pin in enumerate(pin_numbers)))
        require(not [d for d in validate_circuit(
            circuit, {identifier: part}, {identifier: symbol})
            if d.severity.value == "error"], f"E3_CIRCUIT_REJECTED_{identifier}")
        # Corrupt the real semantic conductor graph; the validator must fail.
        wire = Line(symbol.pins[0].at, symbol.pins[1].at)
        damaged = replace(
            symbol, graphics=(*symbol.graphics, wire),
            conductor_topology=replace(symbol.conductor_topology,
                conductor_indices=(*symbol.conductor_topology.conductor_indices,
                                   len(symbol.graphics))))
        require(not inspect_conductor_topology(damaged).valid,
                f"PHANTOM_SHORT_ACCEPTED_{identifier}")
        for view in (False, True):
            stem = identifier + ("-diagnostic" if view else "-clean")
            svg = render_symbol_svg(symbol, review_overlay=view)
            data, wh = _save_svg_png(svg, output, stem, count=5)
            files.update(data)
            xml = ET.fromstring(svg)
            if view:
                circles = xml.findall(f".//{SVG}circle")
                require(len(circles) == len(part.pins), f"SVG_PINS_{identifier}")
            result[stem] = {"physical_contacts": list(pin_numbers),
                            "roles": list(expected), "raster_wh": wh,
                            "normative_acceptance": "BLOCKED"}
    require(len(result) == 30 and len(files) == 60, "INCOMPLETE_15_UGO_GALLERY")
    return {"pair_count": 15, "views": result, "files": files}


def _port_fixture(paint, count, style, metrics, word, transform):
    from math import ceil

    content = paint.IcFieldContent(
        function=word, main_rows=("ЛОГИКА_УПРАВЛЕНИЯ", "STATUS"),
        left_rows=("AUX",), right_rows=("READY",),
    )
    pins = []
    half = count // 2
    for i in range(count):
        left = i < half
        row = i + 1 if left else i - half + 1
        pins.append(paint.ResolvedIcPin(
            f"DD1.{i+1}", str(i+1),
            f"ВХОД_{i+1}" if left else f"OUT_{i+1}",
            Side.LEFT if left else Side.RIGHT,
            row, Point(0, 0), role="in" if left else "out",
        ))
    base = tuple(pins)
    p90 = paint.propose_ic_dimensions(content, base, style, metrics,
                                      function_rotation=90)
    p0 = paint.propose_ic_dimensions(content, base, style, metrics,
                                     function_rotation=0)
    pitch = max(p90.row_pitch_um, p0.row_pitch_um)
    width = max(p90.width_um, p0.width_um)
    width = ceil(width / 2500) * 2500
    height = ceil(max(p90.height_um, p0.height_um,
                      width + 2*pitch) / pitch) * pitch
    origin = Point(150000, 130000)
    pins = []
    for p in base:
        frame = Point(0 if p.side == Side.LEFT else width,
                      p.row * pitch + pitch // 2)
        transformed = transform.apply(frame) + origin
        direction = SIDE_VECTORS[transform.side(p.side)]
        pins.append(replace(p, anchor=Point(
            transformed.x + direction.x * p90.lead_length_um,
            transformed.y + direction.y * p90.lead_length_um,
        )))
    return paint.IcResolvedUnit(
        "DD1", Box(0, 0, width, height), tuple(pins), content, origin,
        transform, typography_profile=paint.IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
    )


def ic_text_gallery(output, font):
    from examples.review_ic_cycle7 import synthetic_ic
    from gost_schematic.electrical.ic import IcKind, IcTextAngle
    from gost_schematic.electrical.ic_graphic_revision import revise_ic_text_orientation
    from gost_schematic.rendering import ic_rectangular as paint

    face = inspect_type_a_font(font, h_um=2500)
    measurer = PillowTextMeasurer()
    imgs, cases = {}, {}
    require(face.style.font_sha256 == hashlib.sha256(Path(font).read_bytes()).hexdigest(),
            "OPENGOST_HASH_MISMATCH")
    for count in (8, 14, 40, 64):
        for word in ("PWM_CONTROLLER", "КОНТРОЛЛЕР_ШИМ"):
            for angle in (0, 90, 180, 270):
                for mirror in (False, True):
                    trans = Transform(angle, mirror)
                    primary = _port_fixture(paint, count, face.style, measurer, word, trans)
                    flipped = replace(primary, function_rotation=0)
                    a = paint.render_resolved_ic(primary, face.style, measurer,
                                                  glyph_detail=True)
                    b = paint.render_resolved_ic(flipped, face.style, measurer,
                                                  glyph_detail=True)
                    require(a.body_world == b.body_world and
                            a.pin_anchors == b.pin_anchors, "TEXT_TOGGLE_MOVED_COPPER")
                    require(len(a.pin_anchors) == count, "TEXT_TOGGLE_LOST_CONTACT")
                    ax, bx = ET.fromstring(a.svg), ET.fromstring(b.svg)
                    for layer in ("ic-outline", "ic-physical-pin-leads"):
                        one = ax.find(f".//{SVG}g[@data-layer='{layer}']")
                        two = bx.find(f".//{SVG}g[@data-layer='{layer}']")
                        require(one is not None and ET.tostring(one) == ET.tostring(two),
                                f"TEXT_TOGGLE_CHANGED_{layer}")
                    va = ax.find(f".//{SVG}text[@data-kind='function']")
                    vb = bx.find(f".//{SVG}text[@data-kind='function']")
                    require(va is not None and vb is not None and
                            va.text == vb.text == word, "TEXT_TOGGLE_LOST_FUNCTION")
                    require(va.attrib.get("transform", "").startswith("matrix(")
                            and not vb.attrib.get("transform"), "TEXT_TOGGLE_ROTATION_WRONG")
                    require(a.glyph_ink and b.glyph_ink, "NO_REAL_GLYPH_INK")
                    label = f"ic-{count}-{word.replace('_', '-')}-{angle}-m{int(mirror)}"
                    cases[label] = {"function_90": True, "same_pinref": True,
                                    "same_body": True, "d4": [angle, mirror]}
                    if angle == 0 and not mirror:
                        for tag, rendered in (("portrait-90", a), ("horizontal-0", b)):
                            stem = label + "-" + tag
                            f, wh = _save_svg_png(rendered.svg, output, stem, count=20)
                            imgs.update(f)
                            cases[label][tag+"_raster"] = wh
                    bad = replace(primary.pins[0],
                                  anchor=Point(primary.pins[0].anchor.x + 1,
                                               primary.pins[0].anchor.y))
                    try:
                        paint.render_resolved_ic(
                            replace(primary, pins=(bad, *primary.pins[1:])),
                            face.style, measurer)
                    except ValueError as exc:
                        require("IC_PIN_ANCHOR_MISMATCH" in str(exc),
                                "ONE_UM_WRONG_DIAGNOSTIC")
                    else:
                        raise AssertionError("ONE_UM_PIN_WAS_ACCEPTED")
        # Real typed owner profile is serializable, but not proof of integrated text.
        record = synthetic_ic(count, IcKind.DIGITAL)
        revised = revise_ic_text_orientation(record, IcTextAngle.VERTICAL)
        require(record.device == revised.device and
                record.placements == revised.placements,
                "IC_GRAPHIC_REVISION_PHYSICAL_IDENTITY_CHANGED")
        from gost_schematic.electrical.ic import resolve_ic_pin_positions
        require(resolve_ic_pin_positions(record.device, record.specs,
                                          record.placements) ==
                resolve_ic_pin_positions(revised.device, revised.specs,
                                          revised.placements), "IC_TEXT_REVISION_PINREF_MOVED")
        # #97's real typed cross-owner adapter must not modify physical nets.
        from gost_schematic.electrical.ic_paint_bridge import (
            bind_ic_paint_text_only,
            propose_ic_paint_binding,
        )
        from gost_schematic.electrical.ic import resolve_ic_pin_positions
        source_binding = propose_ic_paint_binding(record, face.style, measurer)
        before_points = resolve_ic_pin_positions(
            source_binding.record.device, source_binding.record.specs,
            source_binding.record.placements,
        )
        proposed = revise_ic_text_orientation(
            source_binding.record, IcTextAngle.VERTICAL,
        )
        rebound = bind_ic_paint_text_only(source_binding, proposed)
        rebound.verify_endpoints()
        assert source_binding.record.device == rebound.record.device
        assert all(a.body == b.body for a, b in
                   zip(source_binding.record.specs, rebound.record.specs, strict=True))
        after_points = resolve_ic_pin_positions(
            rebound.record.device, rebound.record.specs,
            rebound.record.placements,
        )
        require(before_points == after_points, "IC_TYPED_BRIDGE_MOVED_PHYSICAL_PINREF")
        assert all(a.pin_anchors == b.pin_anchors for a, b in zip(
            (paint.render_resolved_ic(v, face.style, measurer)
             for v in source_binding.views),
            (paint.render_resolved_ic(v, face.style, measurer)
             for v in rebound.views), strict=True
        ))
    return {"cases": len(cases), "real_font_sha256": face.style.font_sha256,
            "files": imgs, "visual_default": "EXPLICIT_PORTRAIT_V2_ONLY",
            "global_default": "BLOCKED_LEGACY_HORIZONTAL"}


def netref_gallery(output, font):
    import importlib

    from examples.review_net_continuations_cycle7 import (
        sheet_svg,
        specimen,
        specimen_three_sheet,
    )
    from gost_schematic.electrical.netrefs import validate_net_continuations
    from gost_schematic.electrical.netrefs_serde import netrefs_from_json, netrefs_to_json

    importlib.import_module("gost_schematic.rendering.svg")
    files = {}
    for namespace in ("", "alt", "svg"):
        ET.register_namespace(namespace, SVG[1:-1])
        for project in (specimen(), specimen_three_sheet()):
            require(not validate_net_continuations(project), "NETREF_INVALID")
            serialized = netrefs_to_json(project)
            require(netrefs_from_json(serialized, project.circuit) == project,
                    "NETREF_JSON_NOT_LOSSLESS")
            for sheet in project.sheets:
                svg = sheet_svg(project, sheet.id, font_path=font, review_overlay=True)
                xml = ET.fromstring(svg)
                require(xml.tag == SVG + "svg", "NETREF_XML_NAMESPACE_INVALID")
                require(len(project.circuit.nets) == 1, "NETREF_PHANTOM_NET")
                require(not xml.findall(f".//{SVG}circle[@data-role='junction']"),
                        "NETREF_PHANTOM_JUNCTION")
                require(xml.attrib["data-approval"].startswith("DRAFT_"),
                        "NETREF_FALSE_GOST_APPROVAL")
                if namespace == "" and len(project.sheets) == 2:
                    stem = f"netrefs-sheet-{sheet.number}"
                    sha, _wh = _save_svg_png(svg, output, stem, count=15)
                    files.update(sha)
    p = specimen()
    corrupted = replace(p, endpoints=(
        replace(p.endpoints[0], net_id="INVALID_NET"), *p.endpoints[1:]))
    require(any(x.code == "E3_CONT_NET_ID_UNKNOWN" for x in
                validate_net_continuations(corrupted)),
            "NETREF_UNKNOWN_NET_NOT_REJECTED")
    return {"source_nets": 1, "artifacts": files,
            "namespace_aliases": 3, "pairs": "real two- and three-sheet"}


def project_cold_reopen():
    from gost_schematic.agent_project import ProjectError, ProjectService
    from gost_schematic.agent_project.trusted_import import import_six_part

    pid = "11111111-1111-4111-8111-111111111111"
    idem = "22222222-2222-4222-8222-222222222222"
    with tempfile.TemporaryDirectory(prefix="qa-c7-current-p11-") as root:
        workspace = Path(root) / "safe"
        initial = import_six_part(workspace, project_id=pid, idempotency_key=idem)
        svc = ProjectService.for_workspace(workspace)
        restored = svc.open_project(pid, initial.head.revision)
        require(len(restored.project.circuit.components) == 6, "PROJECT_COMPONENT_LOSS")
        require(len(restored.project.graph.segments) == 16, "PROJECT_WIRE_LOSS")
        require(len(restored.project.graph.junctions) == 3, "PROJECT_JUNCTION_LOSS")
        require(restored.project.revision == initial.head.revision,
                "PROJECT_SHA_DIFFERENT")
        rendered = svc.render_project(pid, initial.head.revision)
        require(rendered.png.startswith(b"\x89PNG\r\n\x1a\n"), "PROJECT_INVALID_PNG")
        require(rendered.svg.startswith("<svg") or "<svg" in rendered.svg[:300],
                "PROJECT_INVALID_SVG")
        try:
            svc.open_project("../escape")
        except (ProjectError, ValueError):
            pass
        else:
            raise AssertionError("PROJECT_PATH_ESCAPE_ACCEPTED")
        code = """
import builtins, sys
orig = builtins.__import__
def protected(name, *args, **kwargs):
    if name == 'examples' or name.startswith('examples.'):
        raise AssertionError('fresh process imported source fixture')
    return orig(name,*args,**kwargs)
builtins.__import__=protected
from pathlib import Path
from gost_schematic.agent_project import ProjectService
s=ProjectService.for_workspace(Path(sys.argv[1]))
p=s.open_project(sys.argv[2],sys.argv[3])
assert len(p.project.circuit.components)==6
assert len(p.project.graph.segments)==16
assert len(p.project.circuit.nets)==5
assert s.render_project(sys.argv[2],sys.argv[3]).png[:8]==b'\\x89PNG\\r\\n\\x1a\\n'
"""
        completed = subprocess.run(
            [sys.executable, "-c", code, str(workspace), pid, initial.head.revision],
            check=False, text=True, capture_output=True, timeout=50)
        require(completed.returncode == 0, "PROJECT_COLD_REOPEN_FAIL "+completed.stderr)
    return {"cold_reopen": True, "original_components": 6,
            "physical_nets": 5, "segments": 16, "junctions": 3,
            "multi_unit_ic_reopen": "BLOCKED_UNSUPPORTED_SCHEMATIC_PROJECT_V1"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"issue": 92, "owner_commits": OWNER, "draft_only": True,
              "real_production_code_staged_ephemerally": True, "gates": {}}
    # Stagewise assertions intentionally fail the workflow on any real regression.
    for label, action in (
        ("provenance_eskd", provenance),
        ("catalog_15", lambda: catalog_gallery(args.output_dir)),
        ("ic_function_90_0", lambda: ic_text_gallery(args.output_dir, args.font_file)),
        ("netrefs_real", lambda: netref_gallery(args.output_dir, args.font_file)),
        ("project_p11", project_cold_reopen),
    ):
        try:
            report["gates"][label] = {"status": "PASS", "evidence": action()}
        except Exception as exc:
            report["gates"][label] = {"status": "FAIL", "error": repr(exc)}
            (args.output_dir / "qa-cycle7-current-matrix.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
            raise
        print("INDEPENDENT_QA_GATE", label, "PASS", flush=True)
    (args.output_dir / "qa-cycle7-current-matrix.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
    print("QA_CYCLE7_INDEPENDENT_COMPLETE", json.dumps(
        {k: v["status"] for k, v in report["gates"].items()}))


if __name__ == "__main__":
    main()
