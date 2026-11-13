"""Immutable Issue #35 archival SVG against the live post-PR62 C3 circuit.

The archive is tests/fixtures/electrical-cycle3/end-to-end-*.svg, *never* a
derivation by moving the present-day C3 backwards. The live diagram comes from
authored_specimen() unchanged, with validated 16 segment wires and 3 junctions.
"""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.core.geometry import Point
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.annotations import TextStyle
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import validate_external_wires

_SVG = "{http://www.w3.org/2000/svg}"
_ARCHIVE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "electrical-cycle3"
)
_ARCHIVE_SOURCE = "tests/fixtures/electrical-cycle3/end-to-end-"


def _wires(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(root.findall(f".//{_SVG}line[@data-layer='wires']"))


def _junctions(root: ET.Element) -> tuple[ET.Element, ...]:
    return tuple(root.findall(f".//{_SVG}circle[@data-kind='authored-junction']"))


def _pin_endpoints(root: ET.Element) -> tuple[tuple[str, str], ...]:
    c3 = root.find(f".//{_SVG}g[@data-reference='C3']")
    if c3 is None:
        raise ValueError("Archive has no C3 symbol")
    lines = c3.findall(f"./{_SVG}line")
    if len(lines) < 2:
        raise ValueError("Archive C3 lacks its two catalog lead primitives")
    return ((lines[0].get("x1"), lines[0].get("y1")),
            (lines[1].get("x2"), lines[1].get("y2")))


def archive_c3_svg(*, diagnostic: bool = False) -> ET.Element:
    """Read-only historical fixture. Fail if it was silently regenerated."""
    name = "end-to-end-review.svg" if diagnostic else "end-to-end-clean.svg"
    root = ET.fromstring((_ARCHIVE / name).read_text(encoding="utf-8"))
    if root.tag != _SVG + "svg" or len(_wires(root)) != 18:
        raise ValueError("Issue #35 archive must retain 18 source wire segments")
    if len(_junctions(root)) != 3:
        raise ValueError("Issue #35 archive must retain three authored nodes")
    if _pin_endpoints(root) != (("91", "75"), ("109", "75")):
        raise ValueError("Issue #35 C3 archive pins are not at y=75 mm")
    if not any(
        line.get("x1") == "84" and line.get("x2") == "84"
        and line.get("y1") == "80" and line.get("y2") == "75"
        for line in _wires(root)
    ):
        raise ValueError("The Issue #35 dogleg is missing from the archival fixture")
    return root


def current_c3_geometry():
    """The accepted PR #62 authored circuit, never translated or patched."""
    circuit, graph = authored_specimen()
    c3 = next(item for item in circuit.components if item.reference == "C3")
    if c3.part_id != "capacitor.electrolytic" or c3.origin != Point(100000, 80000):
        raise ValueError("Live PR62 C3 origin differs; update review contract")
    expected_tail = (
        ((40000, 40000), (40000, 80000), "TOP"),
        ((40000, 80000), (91000, 80000), "TOP"),
        ((120000, 40000), (120000, 80000), "RIGHT"),
        ((120000, 80000), (109000, 80000), "RIGHT"),
    )
    observed = tuple(
        ((item.start.x, item.start.y), (item.end.x, item.end.y), item.net_name)
        for item in graph.segments[-4:]
    )
    if observed != expected_tail:
        raise ValueError("Live C3 graph no longer matches accepted PR62")
    if len(graph.segments) != 16 or len(graph.junctions) != 3:
        raise ValueError("Live C3 graph no longer has 16 wires/3 authored junctions")
    return circuit, graph


def _crop(root: ET.Element, kind: str, *, diagnostic: bool) -> str:
    """An explicitly labelled comparison-only crop, never a page export."""
    root.set("width", "55mm")
    root.set("height", "36mm")
    root.set("viewBox", "76 57 55 36")
    root.set("data-c3-review-kind", kind)
    root.set("data-c3-preview-crop", "true")
    root.set("data-approval-status", "DRAFT")
    root.set("data-view", "diagnostic" if diagnostic else "clean")
    label = "ARCHIVE Issue #35 (18 wires)" if kind == "archived-issue35" else (
        "CURRENT post-PR62 (16 wires)"
    )
    ET.SubElement(root, _SVG + "title").text = (
        "C3 " + label + " — archival comparison only, not a routing proposal"
    )
    return ET.tostring(root, encoding="unicode") + "\n"


def generate_c3_comparison(output_dir: Path, style: TextStyle) -> dict:
    """Emit archived vs current SVG without ever mutating the live Circuit."""
    circuit, graph = current_c3_geometry()
    unchanged = (circuit, graph)
    parts, symbols = definitions()
    issues = validate_external_wires(circuit, graph, parts, symbols)
    if issues:
        raise ValueError("Current C3 wires are invalid: " + str(
            [(item.code, item.subject) for item in issues]
        ))
    errors = [
        item for item in validate_circuit(circuit, parts, symbols)
        if item.severity.value == "error"
    ]
    if errors:
        raise ValueError("Current C3 ERC errors: " + str([item.code for item in errors]))
    by_part = {key: symbols[part.symbol_id] for key, part in parts.items()}
    c3 = next(item for item in circuit.components if item.reference == "C3")
    symbol = by_part[c3.part_id]
    part = parts[c3.part_id]
    if symbol.identifier != "capacitor.electrolytic" or symbol.revision != 1:
        raise ValueError("C3 symbol catalog ID/revision must be audited")
    if [(pin.number, pin.polarity.value) for pin in part.pins] != [
        ("1", "positive"), ("2", "negative")
    ]:
        raise ValueError("C3 physical polarity/contacts unexpectedly changed")
    for diagnostic in (False, True):
        old_svg = archive_c3_svg(diagnostic=diagnostic)
        new_render = render_external_wire_sheet(
            circuit, graph, by_part, style, PillowTextMeasurer(),
            diagnostic=diagnostic,
        )
        if not new_render.layout.valid:
            raise ValueError("Current C3 annotation layout is invalid")
        current_svg = ET.fromstring(new_render.svg)
        if len(_wires(current_svg)) != 16 or len(_junctions(current_svg)) != 3:
            raise ValueError("Current C3 SVG lost physical authored wires/junctions")
        # Archive has labels rendered with old source font, deliberately retained.
        for kind, svg in (
            ("archived-issue35", old_svg), ("current", current_svg)
        ):
            name = f"c3-{kind}-{'diagnostic' if diagnostic else 'clean'}.svg"
            (output_dir / name).write_text(
                _crop(svg, kind, diagnostic=diagnostic), encoding="utf-8",
            )
    if authored_specimen() != unchanged:
        raise ValueError("Comparison unexpectedly modified authoritative circuit")
    pins = c3.pin_positions(symbol)
    result = {
        "status": "DRAFT_ARCHIVE_VS_ACCEPTED_PR62",
        "archive_source": _ARCHIVE_SOURCE + "{clean,review}.svg",
        "archive_provenance": "Issue #35 historical vector fixture, read-only",
        "current_source": "examples/review_end_to_end_circuit.py::authored_specimen",
        "current_provenance": "accepted PR #62; no additional C3 placement",
        "symbol": {"id": symbol.identifier, "revision": symbol.revision,
                   "status": symbol.status.value},
        "physical_part": part.identifier,
        "archive_origin_um": [100000, 75000],
        "current_origin_um": [c3.origin.x, c3.origin.y],
        "archive_pins_um": {"1": [91000, 75000], "2": [109000, 75000]},
        "current_pins_um": {
            number: [point.x, point.y] for number, point in pins.items()
        },
        "archive_wire_count": 18,
        "current_wire_count": len(graph.segments),
        "archive_junctions_um": [[40000, 20000], [40000, 40000],
                                 [120000, 40000]],
        "current_junctions_um": [[p.x, p.y] for p in graph.junctions],
        "net_names": [net.name for net in circuit.nets],
        "note": (
            "Historical Issue #35 only: archived SVG was NOT recreated from "
            "or imposed onto the live accepted 16-segment authored circuit."
        ),
    }
    (output_dir / "c3-comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
