"""Independent Cycle7 P0 editor-square release gate on real #93 + #97.

The original PAINT demonstration and actual ELEKTRIK IcPaintBinding are
executed in disposable CI on merged experimental integration. No source mocks.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import traceback
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import cairosvg
import fitz
import numpy as np
from PIL import Image

from gost_schematic.core.geometry import Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.rendering.ic_electrical_binding import (
    render_verified_ic_paint_binding,
)
from gost_schematic.rendering.ic_rectangular import render_resolved_ic
from gost_schematic.standards.type_a_font import inspect_type_a_font

ROOT = Path(__file__).resolve().parents[1]
NS = "{http://www.w3.org/2000/svg}"
COUNTS = (4, 8, 14, 40, 64)
EXPECTED = {
    "src/gost_schematic/rendering/ic_rectangular.py":
        "bff0caf982a14ebd2bacda15b419f9b4bcc16f70",
    "src/gost_schematic/rendering/ic_hotspots.py":
        "ca7fb0d481e32e66732606b56e315612fbbd9868",
    "src/gost_schematic/rendering/ic_electrical_binding.py":
        "126b591875d88afb236b4266290c0fc69145a0ac",
    "src/gost_schematic/electrical/ic.py":
        "879ced36cd11c2607bcac1db345bd75cae06e54a",
    "src/gost_schematic/electrical/ic_paint_bridge.py":
        "edf70d41f2833f8a9504d20632398eb8294ad2ea",
    "examples/review_ic_cycle7.py":
        "8aab4abb4774e989853fa74697411ca430c61216",
    "docs/standards/issue-91-deep-source-audit.json":
        "07b2ab53b64fe40fe35750f0a21b52db8ca66c30",
}
REQUIRED_FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def require(flag, code):
    if not flag:
        raise AssertionError(code)


def _git_blob(path):
    data = (ROOT / path).read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest()


def _um(attr):
    return Decimal(attr) * 1000


def _xml(svg):
    parsed = ET.fromstring(svg)
    require(parsed.tag == NS + "svg", "IC_BAD_XML_ROOT")
    return parsed


def _rects(root):
    return root.findall(
        f".//{NS}g[@data-layer='editor-connection-targets']/{NS}rect"
    )


def _lines(root):
    return root.findall(
        f".//{NS}g[@data-layer='ic-physical-pin-leads']/{NS}line"
    )


def _colored(image, kind):
    # PAINT authoritative RGB: green #148645, red NC #8b1e27.
    # Large 64-pin 300-DPI pages can exceed 20 million real pixels.
    # Vectorize the exact RGB mask; do not reduce resolution or invent ink.
    rgb = np.asarray(image.convert("RGB"))
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    if kind == "green":
        return int(np.count_nonzero(
            (r < 75) & (g > 80) & (g < 190) & (b < 125)
            & (g > r) & (g > b)
        ))
    return int(np.count_nonzero(
        (r > 95) & (r < 200) & (g < 90) & (b < 90)
        & (r * 10 > g * 14)
    ))


def _png(svg, destination):
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(destination),
        dpi=300,
    )
    with Image.open(destination) as img:
        require(img.width > 25 and img.height > 25, "IC_PNG_ZERO_SIZED")
        return {"wh": [img.width, img.height],
                "green_pixels": _colored(img, "green"),
                "red_pixels": _colored(img, "red")}


def _save(rendered, output, stem, *, clean):
    svg_file = output / (stem + ".svg")
    png_file = output / (stem + "-300dpi.png")
    svg_file.write_text(rendered, encoding="utf-8")
    metrics = _png(rendered, png_file)
    if clean:
        pdf_path = output / (stem + ".pdf")
        pdf_path.write_bytes(cairosvg.svg2pdf(bytestring=rendered.encode()))
        with fitz.open(pdf_path) as pdf:
            require(pdf.page_count == 1, "CLEAN_PDF_PAGE_COUNT")
            pix = pdf[0].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
            raster = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            require(_colored(raster, "green") == 0
                    and _colored(raster, "red") == 0,
                    "CLEAN_PDF_EDITOR_COLORS")
        require(metrics["green_pixels"] == 0
                and metrics["red_pixels"] == 0,
                "CLEAN_SVG_PNG_EDITOR_COLORS")
        require(not _rects(_xml(rendered)), "CLEAN_HAS_EDITOR_RECTS")
        require("editor-connection-targets" not in rendered,
                "CLEAN_HAS_EDITOR_LAYER")
        metrics["pdf_sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    else:
        metrics["contains_editor_layer"] = bool(_rects(_xml(rendered)))
    metrics["svg_sha256"] = hashlib.sha256(svg_file.read_bytes()).hexdigest()
    metrics["png_sha256"] = hashlib.sha256(png_file.read_bytes()).hexdigest()
    return metrics


def provenance():
    for path, expected in EXPECTED.items():
        require(_git_blob(path) == expected, "OWNER_SOURCE_SHA_CHANGED: " + path)
    data = json.loads((ROOT /
        "docs/standards/issue-91-deep-source-audit.json").read_text())
    require(data["totals"]["product_approved"] == 0,
            "ESKD_FALSE_APPROVED")
    return {"verified_git_blobs": EXPECTED,
            "original_paint_commit":
                "165017630dc911c3006eda35424d8293498db100",
            "original_ic_commit":
                "20bd39c794bc375937fe332c173e17955554d1e1",
            "experimental_integration":
                "1cdd11a3e72e467573d5d660db923b201be21df9"}


def actual_owner_gallery(output, font):
    """Read PAINT's ORIGINAL generate(), not a reauthored test specimen."""
    from examples.review_ic_cycle7 import generate

    owner_out = output / "paint-owner-original-gallery"
    generate(owner_out, font)
    table = {}
    missing = []
    for count in COUNTS:
        for flavor in ("horizontal", "vertical"):
            kind = "analog" if count == 8 else "digital"
            key = (f"ic-{count:02d}-{kind}"
                   if flavor == "horizontal"
                   else f"ic-{count:02d}-vertical")
            clean = (owner_out / (key + "-clean.svg")).read_text()
            diag = (owner_out / (key + "-diagnostic.svg")).read_text()
            rc, rd = _xml(clean), _xml(diag)
            leads = _lines(rd)
            boxes = _rects(rd)
            require(len(leads) == count,
                    "OWNER_GALLERY_PIN_LOSS_" + key)
            require(len(_rects(rc)) == 0, "OWNER_CLEAN_HAS_EDITOR_" + key)
            raster = _save(diag, output, key + "-actual-diagnostic", clean=False)
            _save(clean, output, key + "-actual-clean", clean=True)
            table[key] = {"physical_leads": len(leads),
                          "editor_squares": len(boxes),
                          "raster": raster}
            if len(boxes) != len(leads):
                missing.append(key)
    (output / "original-owner-gallery-matrix.json").write_text(
        json.dumps(table, indent=2, ensure_ascii=False) + "\n")
    require(not missing, "OWNER_GALLERY_DIAGNOSTIC_SQUARES_MISSING: " +
            ",".join(missing))
    return {"owner_generated": table, "missing": []}


def actual_electrical_binding(output, font):
    """Call genuine source-backed typed IcPaintBinding for all 10 packages."""
    from gost_schematic.electrical.ic import IcPinType
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.electrical.ic_serde import ic_from_json

    inspected = inspect_type_a_font(font, h_um=3500)
    require(inspected.measured_cap_height_um == 3500, "FONT_INK_METRICS_CHANGED")
    require(inspected.style.font_sha256 == REQUIRED_FONT_SHA, "FONT_HASH")
    style = inspected.style
    measure = PillowTextMeasurer()
    table = {}
    all_power, all_nc = 0, 0
    for count in COUNTS:
        for kind, ref in (("DIGITAL", "DD1"), ("ANALOG", "DA1")):
            fixture = (ROOT / "tests/fixtures/electrical-ic-cycle7" /
                       f"TEST_IC_{kind}_{count}.json")
            record = ic_from_json(fixture.read_text())
            require(record.device.package.pin_count == count, "PIN_COUNT_BAD")
            require(record.device.package.origin.value == "synthetic",
                    "FALSE_MANUFACTURER_PROVENANCE")
            binding = propose_ic_paint_binding(record, style, measure)
            binding.verify_endpoints()
            circuit = Circuit(
                (ComponentInstance(ref, record.device.identifier),),
                (Net("REAL_NET_1", (PinRef(ref, "1"),)),),
            )
            original_nets = circuit.nets
            original_device = binding.record.device
            results = render_verified_ic_paint_binding(
                binding, style, measure, circuit=circuit,
                glyph_detail=True, editor_overlay=True,
            )
            plain = render_verified_ic_paint_binding(
                binding, style, measure, circuit=circuit,
                glyph_detail=True,
            )
            require(circuit.nets == original_nets and
                    binding.record.device == original_device,
                    "EDITOR_DRAW_MUTATED_CIRCUIT")
            seen = set()
            drawn = []
            for idx, (view, result, clean) in enumerate(
                zip(binding.views, results, plain, strict=True)
            ):
                nodes = _rects(_xml(result.svg))
                lines = _lines(_xml(result.svg))
                require(len(nodes) == len(lines) == len(view.pins),
                        "EDITOR_MARKER_INVENTORY_" + kind + str(count))
                require(len(result.connection_targets) == len(view.pins),
                        "EDITOR_TARGET_COUNT_BAD")
                by_pin = {p.pin_id: p for p in view.pins}
                by_line = {n.attrib["data-pin-id"]: n for n in lines}
                require(len(by_line) == len(lines), "DUPLICATE_SVG_PIN_LINE")
                found = set()
                greens = 0
                reds = 0
                for node in nodes:
                    t_id = node.attrib["data-pin-id"]
                    require(t_id in by_pin and t_id not in found,
                            "EDITOR_GHOST_OR_DUPLICATE_MARKER")
                    found.add(t_id)
                    pin = by_pin[t_id]
                    physical = PinRef(ref, pin.number)
                    require(physical not in seen, "PHYSICAL_PINREF_REPEATED")
                    seen.add(physical)
                    require(node.attrib["data-pin-ref"] ==
                            f"{ref}.{pin.number}", "EDITOR_WRONG_PINREF")
                    require(pin.number in record.device.pin_map,
                            "EDITOR_FAKE_CONTACT_NUMBER")
                    require(Decimal(node.attrib["x"]) * 1000 +
                            Decimal(node.attrib["width"]) * 500 ==
                            pin.anchor.x, "EDITOR_MARKER_X_OFFSET")
                    require(Decimal(node.attrib["y"]) * 1000 +
                            Decimal(node.attrib["height"]) * 500 ==
                            pin.anchor.y, "EDITOR_MARKER_Y_OFFSET")
                    lead = by_line[t_id]
                    require(_um(lead.attrib["x2"]) == pin.anchor.x
                            and _um(lead.attrib["y2"]) == pin.anchor.y,
                            "EDITOR_NOT_ON_REAL_SVG_X2_Y2")
                    require(lead.attrib["data-pin-number"] == pin.number,
                            "EDITOR_WRONG_SVG_NUMBER")
                    require(not (
                        result.body_world.min_x <= pin.anchor.x
                        <= result.body_world.max_x
                        and result.body_world.min_y <= pin.anchor.y
                        <= result.body_world.max_y
                    ), "EDITOR_MARKER_INSIDE_BODY")
                    # Electrical source role, never a substring in VCC/GND/NC.
                    nc = (record.device.pin_map[pin.number].electrical_type
                          is IcPinType.NC)
                    expected = not nc
                    require(node.attrib["data-connectable"] ==
                            str(expected).lower(), "EDITOR_WRONG_ROLE_STATUS")
                    require((node.attrib["fill"] == "#148645") == expected,
                            "EDITOR_WRONG_GREEN")
                    require(node.attrib["fill"] ==
                            ("#8b1e27" if nc else "#148645"),
                            "EDITOR_WRONG_NC_COLOR")
                    require(node.attrib["data-net-id"] ==
                            ("REAL_NET_1" if pin.number == "1" else ""),
                            "EDITOR_FALSE_OR_MISSING_NET")
                    greens += int(expected)
                    reds += int(nc)
                    all_nc += int(nc)
                    all_power += int(
                        record.device.pin_map[pin.number].electrical_type in
                        (IcPinType.POWER_INPUT, IcPinType.POWER_OUTPUT)
                    )
                require(found == set(by_pin), "EDITOR_PIN_NOT_MARKED")
                key = f"bound-{kind.lower()}-{count}-unit{idx + 1}"
                metrics = _save(
                    result.svg, output, key + "-diagnostic", clean=False)
                _save(clean.svg, output, key + "-clean", clean=True)
                require(metrics["green_pixels"] > 0,
                        "GREEN_SQUARES_NOT_VISIBLE_300DPI")
                if reds:
                    require(metrics["red_pixels"] > 0,
                            "NC_RED_SQUARE_NOT_VISIBLE_300DPI")
                require(clean.pin_anchors == result.pin_anchors,
                        "CLEAN_VS_EDITOR_MOVED_ANCHORS")
                drawn.append({"unit": idx + 1, "physical_pins": len(view.pins),
                              "green": greens, "nc_red": reds,
                              "artifact": key, "raster": metrics})
            require(len(seen) == count, "PACKAGE_PHYSICAL_TERMINAL_LOSS")
            table[f"{kind}-{count}"] = drawn
    require(all_power > 0 and all_nc > 0,
            "NO_NC_OR_POWER_COVERAGE_IN_ORIGINAL_FIXTURES")
    return {"actual_synthetic_packages": table, "power_pins": all_power,
            "NC_pins": all_nc, "font_sha256": REQUIRED_FONT_SHA}


def negative_editor_contacts(font):
    """Exercise original engine's reject behavior; any bypass stays red."""
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.electrical.ic_serde import ic_from_json

    p = ROOT / "tests/fixtures/electrical-ic-cycle7/TEST_IC_DIGITAL_14.json"
    record = ic_from_json(p.read_text())
    face = inspect_type_a_font(font, h_um=3500)
    measure = PillowTextMeasurer()
    binding = propose_ic_paint_binding(record, face.style, measure)
    rendered = render_verified_ic_paint_binding(
        binding, face.style, measure, circuit=Circuit(
            (ComponentInstance("DD1", record.device.identifier),),
            (Net("REAL_NET_1", (PinRef("DD1", "1"),)),),
        ),
        editor_overlay=True,
    )
    unit = binding.views[0]
    targets = rendered[0].connection_targets
    require(len(targets) >= 3, "NEGATIVE_TEST_TOO_FEW_TARGETS")
    good = targets[0]
    bad_cases = {
        "wrong_pinref": (replace(good, pin_ref=PinRef("DD1", "900")),),
        "wrong_physical_number": (
            replace(good, pin_ref=PinRef("DD1", "999")),),
        "wrong_component": (
            replace(good, pin_ref=PinRef("DD_FAKE", good.pin_ref.number)),),
        "point_displaced_one_micrometre": (
            replace(good, anchor=Point(good.anchor.x + 1, good.anchor.y)),),
        "missing_authoritative_point": targets[:-1],
        "duplicate_authoritative_point": (targets[0], *targets),
        "wrong_net": (replace(
            good, net_id="FORGED_PHANTOM_NET"), *targets[1:]),
        "false_nc_on_active_pin": (replace(
            good, connectable=False, reason="NC"), *targets[1:]),
    }
    outcomes = {}
    for name, mutated in bad_cases.items():
        try:
            render_resolved_ic(
                unit, face.style, measure,
                editor_targets=mutated, editor_overlay=True,
            )
        except (ValueError, TypeError) as exc:
            outcomes[name] = {"status": "PASS_REJECTED", "error": str(exc)}
        else:
            outcomes[name] = {"status": "FAIL_ACCEPTED_UNSAFE"}
    # NC must never be colored green, even for an apparently powered pin.
    nc = next(t for t in (
        target for result in rendered
        for target in result.connection_targets
    ) if not t.connectable)
    nc_unit = next(view for view, result in zip(
        binding.views, rendered, strict=True
    ) if nc in result.connection_targets)
    try:
        render_resolved_ic(
            nc_unit, face.style, measure,
            editor_targets=(replace(nc, connectable=True, reason=None),),
            editor_overlay=True,
        )
    except ValueError as exc:
        outcomes["NC_falsely_green"] = {
            "status": "PASS_REJECTED", "error": str(exc)}
    else:
        outcomes["NC_falsely_green"] = {"status": "FAIL_ACCEPTED_UNSAFE"}

    require(all(v["status"] == "PASS_REJECTED" for v in outcomes.values()),
            "EDITOR_NEGATIVE_CONTRACT_BYPASS: " +
            ",".join(k for k, v in outcomes.items()
                     if v["status"] != "PASS_REJECTED"))
    return outcomes


def normative_power():
    """Distinguish a source permission from implemented graphic signoff."""
    data = json.loads((ROOT /
        "docs/standards/issue-91-deep-source-audit.json").read_text())
    sources = {s["standard"] for s in data["primary_sources"]}
    require("ГОСТ 2.743-91" in sources and "ГОСТ 2.759-82" in sources,
            "POWER_NORM_PRIMARY_NOT_PINNED")
    options = [
        {"key": "digital_power_left_right", "source":
         "2.743-91 §2.1.4, nonlogical pins left/right",
         "source_permission": "PASS", "actual_1to1_ugo": "BLOCKED"},
        {"key": "figure_6_a_common_control_block", "source":
         "2.743-91 §2.3.11 fig.6a", "source_permission": "PASS",
         "actual_1to1_ugo": "BLOCKED"},
        {"key": "figure_6_b_one_split_unit", "source":
         "2.743-91 §2.3.11 fig.6b", "source_permission": "PASS",
         "actual_1to1_ugo": "BLOCKED"},
        {"key": "figure_6_c_separate_power_contour", "source":
         "2.743-91 §2.3.11 fig.6c", "source_permission": "PASS",
         "actual_1to1_ugo": "BLOCKED"},
        {"key": "power_free_field_text", "source":
         "2.743-91 §2.3.11 free scheme field",
         "source_permission": "PASS", "actual_1to1_ugo": "BLOCKED"},
        {"key": "analog_U_OV", "source":
         "2.759-82 tab.4 §10/11 U, UD, OV",
         "source_permission": "PASS", "actual_1to1_ugo": "BLOCKED"},
        {"key": "editor_VCC_top_GND_bottom", "source":
         "EXPERIMENTAL, no confirmed 2.743-91 fig.6 top/bottom profile",
         "source_permission": "BLOCKED", "actual_1to1_ugo": "BLOCKED"},
    ]
    require(len(options) == 7 and all(
        row["actual_1to1_ugo"] == "BLOCKED" for row in options),
        "NORMATIVE_POWER_FALSE_APPROVAL")
    return {"rule_scope": options,
            "figure6_combination_note":
                "Within one design-document set: 6a+6b OR 6a+6c",
            "vendor_physical_pinout": "BLOCKED_SYNTHETIC_ONLY"}


def merged_integration_regressions():
    """Execute published merged implementation, not unmerged owner mocks."""
    from examples.review_net_continuations_cycle7 import specimen_three_sheet
    from gost_schematic.catalog.loader import load_symbol
    from gost_schematic.electrical.netrefs import validate_net_continuations

    symbols = sorted((ROOT / "src/gost_schematic/catalog/symbols").rglob("*.json"))
    winding = sorted((ROOT / "src/gost_schematic/catalog/inductors").glob("*.json"))
    require(len(symbols) == 21 and len(winding) == 15,
            "INTEGRATION_36_DRAFT_INVENTORY_CHANGED")
    for path in symbols:
        symbol = load_symbol(path)
        require(symbol.status.value == "draft",
                "INTEGRATION_FALSE_APPROVED_" + path.name)
    netrefs = specimen_three_sheet()
    require(len(netrefs.circuit.nets) == 3, "INTEGRATION_NET_LOSS")
    require(not validate_net_continuations(netrefs), "INTEGRATION_CONTINUATION_FAIL")
    from gost_schematic.agent_project import ProjectService
    from gost_schematic.agent_project.trusted_import import import_six_part

    with tempfile.TemporaryDirectory(prefix="qa92-merged-p11-") as folder:
        workspace = Path(folder) / "safe"
        original = import_six_part(
            workspace,
            project_id="11111111-1111-4111-8111-111111111111",
            idempotency_key="22222222-2222-4222-8222-222222222222",
        )
        svc = ProjectService.for_workspace(workspace)
        opened = svc.open_project(
            "11111111-1111-4111-8111-111111111111",
            original.head.revision,
        )
        require(len(opened.project.circuit.components) == 6,
                "INTEGRATION_PROJECT_COMPONENT_LOSS")
        require(len(opened.project.graph.segments) == 16,
                "INTEGRATION_PROJECT_CONDUCTOR_LOSS")
        code = (
            "import sys;"
            "from pathlib import Path;"
            "from gost_schematic.agent_project import ProjectService;"
            "p=ProjectService.for_workspace(Path(sys.argv[1]));"
            "v=p.open_project(sys.argv[2],sys.argv[3]);"
            "assert len(v.project.circuit.components)==6"
        )
        process = subprocess.run([
            sys.executable, "-c", code, str(workspace),
            "11111111-1111-4111-8111-111111111111",
            original.head.revision,
        ], capture_output=True, text=True, check=False, timeout=35)
        require(process.returncode == 0,
                "INTEGRATION_P11_COLD_REOPEN_FAIL: " + process.stderr)
    return {"catalog_static_DRAFT": len(symbols),
            "catalog_parameterized_DRAFT": len(winding),
            "approved": 0,
            "three_real_nets": len(netrefs.circuit.nets),
            "project_cold_open": True,
            "multi_unit_ic_persistence": "BLOCKED_NOT_IMPLEMENTED"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-file", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    options = ap.parse_args()
    out = options.output_dir
    out.mkdir(parents=True, exist_ok=True)
    gates = {}
    failures = []
    for name, fn in (
        ("P0_source_sha", provenance),
        ("P0_original_paint_gallery", lambda: actual_owner_gallery(
            out, options.font_file)),
        ("P0_typed_pinref_point_markers", lambda: actual_electrical_binding(
            out, options.font_file)),
        ("P0_negative_cases", lambda: negative_editor_contacts(
            options.font_file)),
        ("P1_power_norm_scope", normative_power),
        ("P3_merged_integration", merged_integration_regressions),
    ):
        try:
            gates[name] = {"status": "PASS", "evidence": fn()}
        except (
            AssertionError, ValueError, TypeError, KeyError, OSError,
            RuntimeError, ImportError, AttributeError, subprocess.SubprocessError,
        ) as error:
            traceback.print_exc()
            gates[name] = {"status": "FAIL", "diagnostic": str(error)}
            failures.append(name)
        print("QA92_EDITOR_SQUARE_GATE", name, gates[name]["status"], flush=True)
        (out / "qa92-editor-square-matrix.json").write_text(json.dumps(
            {"owner_paint": "165017630dc911c3006eda35424d8293498db100",
             "owner_ic": "20bd39c794bc375937fe332c173e17955554d1e1",
             "integration": "1cdd11a3e72e467573d5d660db923b201be21df9",
             "gates": gates,
             "all_release_checks_green": False},
            ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    if failures:
        raise SystemExit("QA92 P0 RED: " + ",".join(failures))
    print("QA92 P0 GREEN: all owner output/negative tests passed")


if __name__ == "__main__":
    main()
