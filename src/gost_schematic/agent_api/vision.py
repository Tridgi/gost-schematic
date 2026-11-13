"""Immutable, bounded, read-only SVG viewport service for MCP visual feedback.

Coordinates are exact integer micrometres in the source model and decimal mm
at the public boundary. SVG is re-rasterized for every viewport; no PNG crops.
SVG is never parsed to determine net connectivity.
"""

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point
from gost_schematic.model.circuit import PinRef
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import validate_external_wires

from .specimen import Specimen, load_specimen, render_specimen_svg

MAX_DIMENSION = 4096
MAX_PIXELS = 12_000_000
MAX_PNG_BYTES = 8_000_000
SVG_NS = "http://www.w3.org/2000/svg"


class VisionError(ValueError):
    """Machine-readable fail-closed error at the read-only service boundary."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class View:
    png: bytes
    svg: str
    metadata: dict[str, Any]


def _decimal(value: Any, *, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise VisionError("INVALID_COORDINATE", f"{name} must be finite numeric mm")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise VisionError("INVALID_COORDINATE", f"Invalid {name}") from exc
    if not number.is_finite() or abs(number) > 1_000_000:
        raise VisionError("INVALID_COORDINATE", f"{name} is nonfinite or out of range")
    if number.as_tuple().exponent < -3 and number != number.quantize(Decimal("0.001")):
        raise VisionError("INVALID_COORDINATE", f"{name} must align with 1 micrometre")
    return number


def _micrometres(value: Any, name: str) -> int:
    scaled = _decimal(value, name=name) * 1000
    if scaled != scaled.to_integral_value():
        raise VisionError("INVALID_COORDINATE", f"{name} must align with 1 micrometre")
    return int(scaled)


def _box_from_mm(values: Any) -> Box:
    if not isinstance(values, (list, tuple)) or len(values) != 4:
        raise VisionError("INVALID_BBOX", "bbox_mm must be four coordinates [x1,y1,x2,y2]")
    coords = [_micrometres(value, f"bbox_mm[{i}]") for i, value in enumerate(values)]
    try:
        return Box(*coords)
    except ValueError as exc:
        raise VisionError("INVALID_BBOX", str(exc)) from exc


def _rect(values: list[Point], *, radius: int = 0) -> Box:
    if not values:
        raise VisionError("EMPTY_SELECTION", "No physical geometry matches selector")
    return Box(
        min(p.x for p in values) - max(radius, 1),
        min(p.y for p in values) - max(radius, 1),
        max(p.x for p in values) + max(radius, 1),
        max(p.y for p in values) + max(radius, 1),
    )


def _union(first: Box, second: Box) -> Box:
    return Box(
        min(first.min_x, second.min_x), min(first.min_y, second.min_y),
        max(first.max_x, second.max_x), max(first.max_y, second.max_y),
    )


def _intersect(first: Box, second: Box) -> Box:
    try:
        return Box(
            max(first.min_x, second.min_x), max(first.min_y, second.min_y),
            min(first.max_x, second.max_x), min(first.max_y, second.max_y),
        )
    except ValueError as exc:
        raise VisionError("REGION_OUTSIDE_SHEET", "Viewport does not intersect sheet") from exc


def _sheet_box(svg: str) -> Box:
    root = ET.fromstring(svg)
    view_box = root.get("viewBox")
    if not view_box:
        raise VisionError("SVG_VIEWBOX_MISSING", "Source renderer returned no viewBox")
    parts = view_box.split()
    if len(parts) != 4:
        raise VisionError("SVG_VIEWBOX_INVALID", "Source SVG has malformed viewBox")
    x, y, w, h = (_micrometres(v, "source viewBox") for v in parts)
    return Box(x, y, x + w, y + h)


def _model_metadata(scene: Specimen) -> dict[str, Any]:
    from importlib.resources import files

    # Hash actual shipped JSON bytes in deterministic path order, not Python repr()
    # (which can drift across interpreters or hash randomization).
    catalog_root = Path(str(files("gost_schematic").joinpath("catalog")))
    catalog_digest = hashlib.sha256()
    for path in sorted(catalog_root.rglob("*.json")):
        catalog_digest.update(path.relative_to(catalog_root).as_posix().encode())
        catalog_digest.update(b"\\x00")
        catalog_digest.update(path.read_bytes())
        catalog_digest.update(b"\\x00")
    catalog_hash = catalog_digest.hexdigest()
    canonical = json.dumps({
        "components": [
            [c.reference, c.part_id, c.origin.x, c.origin.y, repr(c.transform),
             repr(c.nominal)] for c in scene.circuit.components
        ],
        "nets": [[n.name, [[p.reference, p.number] for p in n.members]]
                 for n in scene.circuit.nets],
        "wires": [[w.start.x, w.start.y, w.end.x, w.end.y, w.net_name]
                  for w in scene.graph.segments],
        "junctions": [[p.x, p.y] for p in scene.graph.junctions],
        "catalog_sha256": catalog_hash,
    }, sort_keys=True, separators=(",", ":")).encode()
    try:
        engine_version = version("gost-schematic")
    except PackageNotFoundError:
        engine_version = "source-checkout"
    return {
        "project_ref": scene.reference,
        "project_revision": hashlib.sha256(canonical).hexdigest(),
        "catalog_sha256": catalog_hash,
        "engine_version": engine_version,
        "component_count": len(scene.circuit.components),
        "wire_segment_count": len(scene.graph.segments),
        "status": "DRAFT / experimental / not ESKD-approved",
        "font_provenance": "specimen reference labels: sans-serif (not verified OpenGost Type A)",
    }


def _diagnostic(item: Any, source: str) -> dict[str, Any]:
    return {
        "code": item.code, "severity": item.severity.value,
        "subject": item.subject, "message": item.message, "source": source,
    }


def diagnostics(project_ref: str = "six-part", check: str = "all") -> dict[str, Any]:
    if check not in ("all", "erc", "geometry", "labels"):
        raise VisionError("INVALID_CHECK", "check must be all, erc, geometry or labels")
    scene = _load(project_ref)
    entries: list[dict[str, Any]] = []
    if check in ("all", "geometry"):
        entries.extend(_diagnostic(x, "ExternalWireGraph") for x in
                       validate_external_wires(scene.circuit, scene.graph,
                                               scene.parts, scene.symbols))
    if check in ("all", "erc"):
        entries.extend(_diagnostic(x, "Circuit") for x in
                       validate_circuit(scene.circuit, scene.parts, scene.symbols,
                                        scenario=scene.scenario))
    entries.sort(key=lambda d: (d["source"], d["code"], d["subject"] or "", d["message"]))
    return {
        **_model_metadata(scene), "check": check, "diagnostics": entries,
        "labels_check_status": "not implemented" if check in ("all", "labels") else "not requested",
        "authoritative_sources": ["Circuit", "ExternalWireGraph"],
        "limitations": ["no net inference from SVG", "no ГОСТ conformity approval"],
    }


def _load(project_ref: str) -> Specimen:
    if not isinstance(project_ref, str) or len(project_ref) > 128:
        raise VisionError("UNKNOWN_PROJECT", "Invalid project reference")
    try:
        return load_specimen(project_ref)
    except ValueError as exc:
        raise VisionError("UNKNOWN_PROJECT", str(exc)) from exc


def _component_box(scene: Specimen, ref: str) -> Box:
    item = next((x for x in scene.circuit.components if x.reference == ref), None)
    if item is None:
        raise VisionError("UNKNOWN_COMPONENT", f"No component {ref!r}")
    symbol = scene.symbols[scene.parts[item.part_id].symbol_id]
    body = item.transform.box(symbol.body_keepout).translated(item.origin)
    pins = _rect(list(item.pin_positions(symbol).values()), radius=1)
    # Include specimen refdes and a conservative text glyph margin above body.
    label = Box(item.origin.x - 5000, body.min_y - 7000,
                item.origin.x + 5000, body.min_y + 1)
    return _union(_union(body, pins), label)


def _pin_position(scene: Specimen, ref: str, number: str) -> Point:
    item = next((x for x in scene.circuit.components if x.reference == ref), None)
    if item is None:
        raise VisionError("UNKNOWN_COMPONENT", f"No component {ref!r}")
    part = scene.parts[item.part_id]
    if not any(pin.number == number for pin in part.pins):
        raise VisionError("UNKNOWN_PIN", f"No physical pin {ref}.{number}")
    positions = item.pin_positions(scene.symbols[part.symbol_id])
    if number not in positions:
        raise VisionError("UNMAPPED_PIN", f"No graphic position for {ref}.{number}")
    return positions[number]


def _net_box(scene: Specimen, name: str) -> Box:
    net = next((n for n in scene.circuit.nets if n.name == name), None)
    if net is None:
        raise VisionError("UNKNOWN_NET", f"No declared electrical net {name!r}")
    points = [_pin_position(scene, p.reference, p.number) for p in net.members]
    for segment in scene.graph.segments:
        if segment.net_name == name:
            points.extend((segment.start, segment.end))
    return _rect(points, radius=2000)


def select_box(scene: Specimen, selector: dict[str, Any]) -> Box:
    if not isinstance(selector, dict) or len(selector) != 1:
        raise VisionError("INVALID_SELECTOR", "Exactly one selector kind is required")
    kind, value = next(iter(selector.items()))
    if kind == "reference" and isinstance(value, str):
        return _component_box(scene, value)
    if kind == "pin" and isinstance(value, dict) and set(value) == {"component", "number"}:
        ref, number = value["component"], value["number"]
        if not isinstance(ref, str) or not isinstance(number, str):
            raise VisionError("INVALID_SELECTOR", "pin component and number must be strings")
        point = _pin_position(scene, ref, number)
        return _rect([point], radius=3500)
    if kind == "net" and isinstance(value, str):
        return _net_box(scene, value)
    if kind == "bbox_mm":
        return _box_from_mm(value)
    raise VisionError("INVALID_SELECTOR", "Use reference, pin, net or bbox_mm")


def _render(
    scene: Specimen, box: Box | None, *, mode: str, dpi: int = 300,
    max_px: int = 1600, output_root: Path | None = None,
) -> View:
    if mode not in ("clean", "diagnostic"):
        raise VisionError("INVALID_MODE", "mode must be clean or diagnostic")
    svg = render_specimen_svg(scene, diagnostic=(mode == "diagnostic"))
    source_sha = hashlib.sha256(svg.encode()).hexdigest()
    sheet = _sheet_box(svg)
    bounds = sheet if box is None else _intersect(sheet, box)
    w_um, h_um = bounds.max_x - bounds.min_x, bounds.max_y - bounds.min_y
    if box is None:
        if type(max_px) is not int or not 64 <= max_px <= MAX_DIMENSION:
            raise VisionError("IMAGE_TOO_LARGE", "max_px must be 64..4096")
        scale = Decimal(max_px) / Decimal(max(w_um, h_um))
        width = max(1, int((Decimal(w_um) * scale).to_integral_value(ROUND_HALF_UP)))
        height = max(1, int((Decimal(h_um) * scale).to_integral_value(ROUND_HALF_UP)))
    else:
        if type(dpi) is not int or not 72 <= dpi <= 600:
            raise VisionError("INVALID_DPI", "target_dpi must be 72..600")
        factor = Decimal(dpi) / Decimal(25400)
        width = max(1, int((Decimal(w_um) * factor).to_integral_value(ROUND_HALF_UP)))
        height = max(1, int((Decimal(h_um) * factor).to_integral_value(ROUND_HALF_UP)))
    if max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
        raise VisionError("IMAGE_TOO_LARGE", f"Requested {width}x{height} exceeds viewport cap")
    root = ET.fromstring(svg)
    def mm(value: int) -> str:
        return format(Decimal(value) / Decimal(1000), "f")
    root.set("viewBox", " ".join((
        mm(bounds.min_x), mm(bounds.min_y), mm(w_um), mm(h_um),
    )))
    root.set("width", mm(w_um) + "mm")
    root.set("height", mm(h_um) + "mm")
    # Explicit white preview background avoids client-dependent transparency.
    root.insert(1, ET.Element(f"{{{SVG_NS}}}rect", {
        "x": mm(bounds.min_x), "y": mm(bounds.min_y),
        "width": mm(w_um), "height": mm(h_um), "fill": "#ffffff",
        "data-layer": "viewport-background",
    }))
    cropped_svg = ET.tostring(root, encoding="unicode") + "\n"
    backend = "resvg_py"
    try:
        import resvg_py
        # resvg_py 0.5 rejects physical "mm" lengths. Only the rasterizer
        # input uses pixel lengths; the saved SVG retains mm and viewBox.
        root.set("width", str(width))
        root.set("height", str(height))
        raster_svg = ET.tostring(root, encoding="unicode")
        png = resvg_py.svg_to_bytes(svg_string=raster_svg, width=width, height=height)
    except ImportError:
        backend = "CairoSVG"
        try:
            import cairosvg
            png = cairosvg.svg2png(
                bytestring=cropped_svg.encode("utf-8"),
                output_width=width, output_height=height,
            )
        except (ImportError, OSError) as exc:
            raise VisionError("RASTERIZER_UNAVAILABLE",
                              "Install 'gost-schematic[mcp]'; on Windows use resvg_py") from exc
        except Exception as exc:
            raise VisionError("RASTERIZATION_FAILED", type(exc).__name__) from exc
    except Exception as exc:
        raise VisionError("RASTERIZATION_FAILED", type(exc).__name__) from exc
    if len(png) > MAX_PNG_BYTES:
        raise VisionError("IMAGE_TOO_LARGE", "PNG exceeds 8 MB response limit")
    view_id = hashlib.sha256(json.dumps({
        "svg": source_sha, "bbox": [bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y],
        "px": [width, height], "mode": mode,
    }, sort_keys=True).encode()).hexdigest()[:24]
    metadata: dict[str, Any] = {
        **_model_metadata(scene),
        "view_id": view_id, "mode": mode,
        "geometry_sha256": source_sha,
        "view_svg_sha256": hashlib.sha256(cropped_svg.encode()).hexdigest(),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "bbox_mm": [mm(x) for x in (bounds.min_x, bounds.min_y, bounds.max_x, bounds.max_y)],
        "sheet_bbox_mm": [mm(x) for x in
                          (sheet.min_x, sheet.min_y, sheet.max_x, sheet.max_y)],
        "pixels": [width, height], "mime_type": "image/png",
        "effective_dpi": [round(width * 25400 / w_um, 3),
                          round(height * 25400 / h_um, 3)],
        "rasterizer": backend, "source_geometry": "existing render_sheet_svg",
        "font_warning": "specimen labels are sans-serif; OpenGost Type A not verified",
    }
    if output_root is not None:
        root_dir = output_root.resolve()
        # The supplied root is a trusted server config, never a tool parameter.
        review_dir = (root_dir / "artifacts" / "ai-mcp").resolve()
        if not review_dir.is_relative_to(root_dir):
            raise VisionError("WORKSPACE_VIOLATION", "Review artifacts outside configured workspace")
        review_dir.mkdir(parents=True, exist_ok=True)
        prefix = "view-" + view_id
        png_path, svg_path = review_dir / (prefix + ".png"), review_dir / (prefix + ".svg")
        png_path.write_bytes(png)
        svg_path.write_text(cropped_svg, encoding="utf-8")
        metadata["artifact_png"] = str(png_path)
        metadata["artifact_svg"] = str(svg_path)
    return View(png, cropped_svg, metadata)


def render_overview(project_ref: str = "six-part", mode: str = "clean",
                    max_px: int = 1600, output_root: Path | None = None) -> View:
    return _render(_load(project_ref), None, mode=mode, max_px=max_px,
                   output_root=output_root)


def inspect_region(project_ref: str, selector: dict[str, Any],
                   padding_mm: Any = 3, target_dpi: int = 300,
                   mode: str = "diagnostic", output_root: Path | None = None) -> View:
    scene = _load(project_ref)
    padding = _micrometres(padding_mm, "padding_mm")
    if not 2000 <= padding <= 10000:
        raise VisionError("INVALID_PADDING", "padding_mm must be 2..10")
    bounds = select_box(scene, selector).expanded(padding)
    result = _render(scene, bounds, mode=mode, dpi=target_dpi,
                     output_root=output_root)
    result.metadata["selector"] = selector
    return result


def inspect_component(project_ref: str, reference: str, padding_mm: Any = 3,
                      target_dpi: int = 300, mode: str = "diagnostic",
                      output_root: Path | None = None) -> View:
    return inspect_region(project_ref, {"reference": reference}, padding_mm, target_dpi,
                          mode, output_root)


def inspect_connection(project_ref: str, a: dict[str, str], b: dict[str, str],
                       padding_mm: Any = 3, target_dpi: int = 250,
                       mode: str = "diagnostic",
                       output_root: Path | None = None) -> View:
    scene = _load(project_ref)
    def make_ref(obj: dict[str, str]) -> PinRef:
        if not isinstance(obj, dict) or set(obj) != {"component", "number"}:
            raise VisionError("INVALID_PINREF", "Expected {component, number} for both contacts")
        if not isinstance(obj["component"], str) or not isinstance(obj["number"], str):
            raise VisionError("INVALID_PINREF", "Both contact fields must be strings")
        _pin_position(scene, obj["component"], obj["number"])
        return PinRef(obj["component"], obj["number"])
    first, second = make_ref(a), make_ref(b)
    shared = [n.name for n in scene.circuit.nets
              if first in n.members and second in n.members]
    if len(shared) != 1:
        raise VisionError("PINS_NOT_CONNECTED", "Contacts do not share exactly one declared net")
    net = shared[0]
    view = inspect_region(project_ref, {"net": net}, padding_mm, target_dpi,
                          mode, output_root)
    view.metadata["connection"] = {
        "a": f"{first.reference}.{first.number}",
        "b": f"{second.reference}.{second.number}",
        "declared_net": net,
        "related_segments": sum(w.net_name == net for w in scene.graph.segments),
        "diagnostics": diagnostics(project_ref, "geometry")["diagnostics"],
    }
    return view


def list_views(project_ref: str = "six-part") -> dict[str, Any]:
    scene = _load(project_ref)
    geometry_hash = hashlib.sha256(render_specimen_svg(scene).encode()).hexdigest()
    return {
        **_model_metadata(scene), "geometry_sha256": geometry_hash,
        "views": [
            {"kind": "overview", "mode": "clean|diagnostic"},
            {"kind": "region", "selector": "reference|pin|net|bbox_mm"},
            {"kind": "component", "references": [x.reference for x in scene.circuit.components]},
            {"kind": "connection", "pins": "physical PinRef pair sharing one declared net"},
        ],
    }
