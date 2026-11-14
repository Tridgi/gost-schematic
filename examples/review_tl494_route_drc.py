"""Issue #108: frozen TL494 23/15/91 geometry DRC from source e695c415.

Source fixture is byte-derived from the named photo SVG and typed TRACED_NETS,
not from visual OCR or invented electrical connections. The original reference
branch is NOT imported into integration. A source-ink-only audit cannot certify
native symbol clearance or measured font text; coverage flags remain false.

Usage: python -m examples.review_tl494_route_drc --output-dir output/tl494-drc
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment
from gost_schematic.validation.route_drc import audit_route_drc

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "tests" / "fixtures"
_SOURCE = _FIXTURES / "tl494-routing-source-e695c415.json"
_SVG = _FIXTURES / "tl494-routing-source-e695c415.svg"
_URI = "http://www.w3.org/2000/svg"
_NS = "{" + _URI + "}"


def load_frozen_source() -> tuple[Circuit, ExternalWireGraph, dict]:
    """Preserve true referenced PinRefs, exact net names and 91 source lines."""
    source = json.loads(_SOURCE.read_text("utf-8"))
    if source["source_head_sha"] != "e695c415fdced164b0e0c39c5249d030795a0aa6":
        raise ValueError("DRC_SNAPSHOT_SOURCE_REVISION_MISMATCH")
    if source["source_svg_blob_sha"] != "69fa5d18f0844b080d8f1574c686e5c1156ae1f9":
        raise ValueError("DRC_SNAPSHOT_SVG_SOURCE_MISMATCH")
    components = tuple(
        ComponentInstance(ref, "source-photo-snapshot." + ref)
        for ref in source["part_refs"]
    )
    circuit = Circuit(
        components,
        tuple(Net(name, tuple(PinRef(*p.rsplit(".", 1)) for p in members))
              for name, members in source["net_members"].items()),
    )
    wires = tuple(WireSegment(
        Point(*w["start_um"]), Point(*w["end_um"]), w["net"],
    ) for w in source["wires"])
    junctions = tuple(Point(*p) for p in source["junctions_um"])
    graph = ExternalWireGraph(wires, junctions)
    if (len(circuit.components), len(circuit.nets), len(graph.segments)) != (23, 15, 91):
        raise ValueError("DRC_SNAPSHOT_23_15_91_INVARIANT_BROKEN")
    if {int(p.number) for n in circuit.nets for p in n.members
            if p.reference == "DA1"} != set(range(1, 17)):
        raise ValueError("DRC_TL494_PHYSICAL_PIN_INVENTORY_BROKEN")
    if not any(p == PinRef("DA1", "7") for n in circuit.nets
               if n.name == "COMMON" for p in n.members):
        raise ValueError("DRC_COMMON_NOT_AUTHORED_NET")
    if len(graph.junctions) != 37:
        raise ValueError("DRC_SNAPSHOT_AUTHORED_JUNCTIONS_CHANGED")
    source_svg = _SVG.read_text("utf-8")
    root = ET.fromstring(source_svg)
    lines = root.findall(f".//{_NS}line[@data-layer='wires']")
    if len(lines) != 91 or root.tag != _NS + "svg":
        raise ValueError("DRC_FROZEN_SVG_91_WIRES_REQUIRED")
    for index, (item, wire) in enumerate(zip(lines, wires, strict=True)):
        attrs = {name: item.get(name) for name in ("x1", "y1", "x2", "y2")}
        expected = {
            "x1": wire.start.x, "y1": wire.start.y,
            "x2": wire.end.x, "y2": wire.end.y,
        }
        if item.get("data-wire-index") != str(index) or (
            item.get("data-net") != wire.net_name
        ):
            raise ValueError("DRC_FROZEN_SVG_NET_ID_NOT_SOURCE_BOUND")
        if any(round(float(attrs[k]) * 1000) != val
               for k, val in expected.items()):
            raise ValueError("DRC_FROZEN_SVG_CHANGED_SOURCE_COORDINATES")
    return circuit, graph, source


def report() -> dict:
    circuit, graph, source = load_frozen_source()
    audit = audit_route_drc(circuit, graph, stroke_um=300)
    record = audit.as_dict()
    record.update({
        "source_revision": source["source_head_sha"],
        "source_branch": source["source_branch"],
        "original_svg_width_mm": source["original_svg"]["width_mm"],
        "original_svg_height_mm": source["original_svg"]["height_mm"],
        "source_photo_reference": source["source_script"],
        "source_continuation_b": "existing v2 named continuation; output negative partial span",
        "source_pin_inventory": source["net_members"],
        "source_junction_positions_um": source["junctions_um"],
        "source_lines_um": source["wires"],
        "groups": {
            "left_input": ["X1", "L1"],
            "upper_power": ["C1", "C2", "VD1", "L2", "FU1", "X2"],
            "central_pwm": ["DA1"],
            "left_lower_control": ["R1", "R2", "R3", "R4", "R5", "R6", "R7",
                                   "C3", "C4", "C7"],
            "right_driver": ["R8", "VT1"],
            "bottom_common": ["COMMON"],
        },
        "known_limitation": (
            "Source reference branch is independent of integration. This frozen "
            "wire-graph report measures all 91 real displayed source wires but "
            "does not substitute real native symbol/Type-A measured text objects. "
            "checked_symbol_geometry=false and checked_measured_text=false "
            "therefore WHOLE-SHEET PASS cannot be claimed."
        ),
        "recommended_format": (
            "A1 landscape (841x594mm) minimum by current 679.3mm source width, "
            "subject to real border/title/print margins. Re-layout/A3 split "
            "is preferred after joint source/ESKD acceptance."
        ),
        "top_error_kinds": dict(Counter(
            f.code for f in audit.findings if f.severity == "error"
        )),
    })
    # This is a PARTIAL score; NOT a false claim that all labels/UGO passed.
    record["full_3_2_1mm_sheet_certified"] = False
    return record


def make_review_svg(source: dict, *, max_highlights: int = 120) -> str:
    root = ET.fromstring(_SVG.read_text("utf-8"))
    if root.tag != _NS + "svg":
        raise ValueError("DRC_SOURCE_SVG_NAMESPACE")
    layer = ET.SubElement(root, _NS + "g", {
        "data-layer": "editor-route-drc",
        "data-print": "false",
        "data-status": "NONNORMATIVE_DIAGNOSTIC",
        "stroke": "none", "fill": "none",
    })
    strokes = root.findall(f".//{_NS}line[@data-layer='wires']")
    marked: set[int] = set()
    for issue in source["findings"]:
        if issue["severity"] != "error":
            continue
        for ident in (issue["first"], issue["second"]):
            if not isinstance(ident, str) or not ident.startswith("W"):
                continue
            try:
                idx = int(ident[1:])
            except ValueError:
                continue
            if idx in marked or idx >= len(strokes) or len(marked) >= max_highlights:
                continue
            marked.add(idx)
            line = strokes[idx]
            e = ET.SubElement(layer, _NS + "line", {
                "data-source-wire-index": str(idx),
                "data-kind": "drc-error-conductor",
                "x1": line.get("x1"), "y1": line.get("y1"),
                "x2": line.get("x2"), "y2": line.get("y2"),
                "stroke": "#d93025",
                "stroke-width": "0.55", "stroke-dasharray": "1,0.7",
                "opacity": "0.85",
            })
            ET.SubElement(e, _NS + "title").text = "DRC error at authored wire " + str(idx)
    summary = ET.SubElement(root, _NS + "metadata", {
        "data-layer": "route-drc-report",
        "data-print": "false",
    })
    summary.text = json.dumps({
        "error_count": source["error_count"],
        "warning_count": source["warning_count"],
        "parallel_pairs_checked": len(source["parallel_measurements"]),
        "highlighted_source_wires": sorted(marked),
        "source_wires_untouched": 91,
        "not_normatively_approved": True,
    }, sort_keys=True)
    # The existing printer requires exactly one default SVG namespace.
    # ET otherwise chooses ns0:svg in this standalone diagnostic entrypoint.
    ET.register_namespace("", _URI)
    return ET.tostring(root, encoding="unicode") + "\n"


def generate(output_dir: Path) -> dict:
    result = report()
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = _SVG.read_text("utf-8")
    reviewed = make_review_svg(result)
    (output_dir / "TL494-routing-source-clean.svg").write_text(clean, "utf-8")
    (output_dir / "TL494-routing-drc-diagnostic.svg").write_text(reviewed, "utf-8")
    (output_dir / "TL494-routing-drc.json").write_text(
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        "utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output_dir)
    print(json.dumps({
        "source": result["source_revision"],
        "components": result["component_count"],
        "nets": result["net_count"],
        "wires": result["wire_count"],
        "total_length_mm": round(result["total_wire_length_um"] / 1000, 3),
        "parallel_pairs": len(result["parallel_measurements"]),
        "errors": result["error_count"],
        "warnings": result["warning_count"],
        "whole_sheet_certified": result["full_3_2_1mm_sheet_certified"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
