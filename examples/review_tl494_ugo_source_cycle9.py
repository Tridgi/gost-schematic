"""Cycle 9: native TL494 photo UGO source-check gallery, no invented figure ink.

All component strokes are transformed original catalogue primitives. The
actual printed GOST diagrams are referenced by table/page in the HTML index,
not fabricated as SVG or misrepresented as a calibrated 1:1 overlay.
"""

import argparse
import hashlib
import html
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.source_profiles import (
    REQUIRED_REFERENCES,
    bind_tl494_source,
    load_catalog_pair,
    read_source_manifest,
)
from gost_schematic.core.geometry import Circle, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.rendering.svg import render_symbol_svg

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")
SHEET_MM = (288, 350)
D4_IDS = (
    "diode.general", "diode.schottky",
    "transistor.bjt_npn", "transistor.bjt_pnp",
    "transistor.bjt_npn.with_case", "transistor.bjt_pnp.with_case",
    "transistor.mosfet_n_enh", "transistor.mosfet_n_enh.with_case",
)
SOURCES = {
    "diode": ("https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf", 4),
    "transistor": ("https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf", 6),
    "capacitor": ("https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf", 7),
    "inductor": ("https://vkopilke.narod.ru/file68.pdf", 3),
    "resistor": ("https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf", 2),
    "fuse": ("https://www.nuvis.com.ua/GOST_2.727-68_ESKD.pdf", 3),
}


def _source_variant(symbol, ref):
    """Only the reference VL source metal junction is graphically dotted."""
    if ref != "VT1":
        return symbol
    # Existing working reference explicitly included this source/channel dot.
    # Local connection of two source strokes is at (0,+5) mm. Dot is ONLY ink.
    p = Point(0, 5000)
    if not any(
        getattr(item, "start", None) == p or getattr(item, "end", None) == p
        for item in symbol.graphics
    ):
        raise ValueError("VT1 reference dot does not sit on a source stroke end")
    if len(symbol.pins) != 3:
        raise ValueError("VT1 dot may not create a fourth pin")
    return replace(symbol, graphics=(*symbol.graphics, Circle(p, 250)))


def pose_symbol(symbol, transform: Transform):
    """Transform native D4 model, including each real GraphicPin and keepout."""
    return replace(
        symbol,
        graphics=tuple(transform.primitive(item) for item in symbol.graphics),
        pins=tuple(
            replace(pin, at=transform.apply(pin.at), side=transform.side(pin.side))
            for pin in symbol.pins
        ),
        body_keepout=transform.box(symbol.body_keepout),
    )


def _markers(root, posed, *, diagnostic):
    if not diagnostic:
        return
    body = posed.body_keepout
    ET.SubElement(root, SVG + "rect", {
        "x": str(body.min_x / 1000),
        "y": str(body.min_y / 1000),
        "width": str((body.max_x - body.min_x) / 1000),
        "height": str((body.max_y - body.min_y) / 1000),
        "stroke": "#c07c2a", "stroke-width": "0.15", "fill": "none",
        "stroke-dasharray": "0.7,0.5", "data-keepout": "true",
    })
    for pin in posed.pins:
        ET.SubElement(root, SVG + "rect", {
            "x": str((pin.at.x - 600) / 1000),
            "y": str((pin.at.y - 600) / 1000),
            "width": "1.2", "height": "1.2",
            "fill": "#14a56d", "stroke": "#096d42", "stroke-width": "0.12",
            "data-editor-target": "true", "data-physical-pin": pin.number,
        })


def _svg_bytes(root):
    return (ET.tostring(root, encoding="unicode") + "\n").encode("utf-8")


def _write_svg(path: Path, root):
    content = _svg_bytes(root)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _actual_root(symbol, reference, transform, *, diagnostic):
    posed = pose_symbol(_source_variant(symbol, reference), transform)
    root = ET.fromstring(render_symbol_svg(posed))
    root.attrib.update({
        "data-status": "DRAFT", "data-reference": reference,
        "data-symbol": symbol.identifier,
        "data-pose": str(transform.rotation),
        "data-mirror-x": str(transform.mirror_x).lower(),
        "data-view": "diagnostic" if diagnostic else "clean",
        "data-pins": ",".join(pin.number for pin in posed.pins),
        "data-real-pin-coordinates-um": ";".join(
            f"{pin.number}:{pin.at.x},{pin.at.y}" for pin in posed.pins
        ),
    })
    if reference == "VT1":
        root.set("data-source-dot", "PHOTO_MATCH_DRAFT_NOT_VENDOR_PIN")
    _markers(root, posed, diagnostic=diagnostic)
    return root, posed


def _pdf_link(identifier: str):
    family = identifier.split(".", 1)[0]
    url, page = SOURCES[family]
    if identifier == "diode.schottky":
        page = 4
    if identifier in ("transistor.bjt_npn", "transistor.bjt_pnp",
                      "transistor.bjt_npn.with_case",
                      "transistor.bjt_pnp.with_case"):
        page = 5
    if identifier.startswith("inductor."):
        page = 3
    return f"{url}#page={page}"


def _write_index(path, records):
    cells = []
    for item in records:
        ref = item["reference"]
        source = item["standard_figure"]
        link = _pdf_link(item["symbol_id"])
        file = ref + "-source-pose-clean.png"
        pins = ", ".join(item["physical_pin_refs"])
        cells.append(
            "<section><h2>" + html.escape(ref + " / " + item["symbol_id"])
            + "</h2><div class='pair'>"
            + "<article><h3>Оригинал (нормативный PDF)</h3>"
            + "<a href='" + html.escape(link, quote=True) + "'>"
            + html.escape(source) + " — открыть отсканированную таблицу</a>"
            + "<p>Точный вырезанный фрагмент источника пока не загружен. "
              "1:1 наложение заблокировано до независимой калибровки.</p>"
            + "</article><article><h3>Наш настоящий SVG → PNG 300 DPI</h3>"
            + "<img src='" + html.escape(file, quote=True) + "' alt='"
            + html.escape(ref, quote=True) + "'>"
            + "<p>PinRef: " + html.escape(pins) + "</p></article></div></section>"
        )
    html_text = (
        "<!doctype html><html lang='ru'><meta charset='utf-8'>"
        "<title>TL494 source-backed GOST DRAFT UGO review</title>"
        "<style>body{font:16px system-ui,sans-serif;margin:24px auto;"
        "max-width:1050px}section{border-bottom:1px solid #aaa;padding:18px 0}"
        ".pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}"
        "article{padding:12px;background:#f5f5f5}"
        "img{max-width:100%;object-fit:contain;background:white}"
        "h2{font-size:21px}h3{font-size:16px}</style>"
        "<h1>TL494CN: исходный ГОСТ ↔ настоящий векторный каталог, DRAFT</h1>"
        "<p>Ссылки ведут к подлинным страницам ГОСТ. Данные позиции"
        " закреплены, но независимое 1:1 изображение пока BLOCKED.</p>"
        + "".join(cells) + "</html>"
    )
    path.write_text(html_text, encoding="utf-8")


def generate(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    source = read_source_manifest()
    instances, parts, symbols = [], {}, {}
    for item in source["profiles"]:
        identifier = item["symbol_id"]
        symbol, part = load_catalog_pair(identifier)
        parts[identifier], symbols[identifier] = part, symbol
        origin = Point(*(round(value * 1000) for value in
                         item["source_layout_origin_mm"]))
        inst = ComponentInstance(
            item["reference"], identifier, origin,
            Transform(item["rotation"], item["mirror_x"]),
        )
        instances.append(inst)
    bindings = bind_tl494_source(instances, parts, symbols)
    result = {
        "source_sha": source["reference_sha"],
        "status": "DRAFT_NO_ESKD_1TO1",
        "source_bitmap_available": False,
        "gallery_count": len(REQUIRED_REFERENCES),
        "normative_approved": 0,
        "source_pin_positions_status": "PASS_REFERENCE_BRANCH_EDITORIAL_POSE",
        "source_1to1_status": "BLOCKED_NO_CALIBRATED_ORIGINAL_CROPS",
        "gallery_size_mm": list(SHEET_MM),
        "entries": [],
        "d4": [],
        "files": [],
    }
    for binding, entry in zip(bindings, source["profiles"], strict=True):
        expected = entry["source_pin_endpoints_mm"]
        real = binding.pin_positions
        if [list(p) for p in ((p.x // 1000, p.y // 1000) for p in real)] != expected:
            raise ValueError(f"{binding.reference}: source branch pin positions changed")
        card = {
            "reference": binding.reference, "symbol_id": binding.symbol.identifier,
            "standard_figure": entry["standard_figure"],
            "source_url": _pdf_link(binding.symbol.identifier),
            "physical_pin_refs": [
                f"{pin.reference}.{pin.number}" for pin in binding.pin_refs
            ],
            "source_absolute_pin_um": [
                [pin.x, pin.y] for pin in binding.pin_positions
            ],
            "physical_roles": list(entry["expected_physical_roles"]),
            "status": "DRAFT", "source_1to1": "BLOCKED",
            "svg_sha256": {},
        }
        transform = binding.instance.transform
        for diagnostic in (False, True):
            kind = "diagnostic" if diagnostic else "clean"
            root, _ = _actual_root(
                binding.symbol, binding.reference, transform, diagnostic=diagnostic
            )
            fname = f"{binding.reference}-source-pose-{kind}.svg"
            card["svg_sha256"][kind] = _write_svg(directory / fname, root)
            result["files"].append(fname)
        result["entries"].append(card)
    _write_index(directory / "index.html", result["entries"])
    for identifier in D4_IDS:
        symbol, part = load_catalog_pair(identifier)
        for mirror in (False, True):
            for angle in (0, 90, 180, 270):
                t = Transform(angle, mirror)
                ref = "VD" if identifier.startswith("diode.") else "VT"
                root, posed = _actual_root(
                    symbol, ref, t, diagnostic=False
                )
                serial = f"{identifier}-r{angle}-m{int(mirror)}"
                fname = f"{serial}-clean.svg"
                signature = _write_svg(directory / fname, root)
                result["files"].append(fname)
                result["d4"].append({
                    "id": identifier, "angle": angle, "mirror_x": mirror,
                    "file": fname, "svg_sha256": signature,
                    "pin_roles": [pin.name for pin in part.pins],
                    "physical_anchors_um": [
                        [p.at.x, p.at.y] for p in posed.pins
                    ],
                })
    # Two real SVG collection sheets. Do not embed any counterfeit GOST figure.
    for diagnostic in (False, True):
        mode = "diagnostic" if diagnostic else "clean"
        root = ET.Element(SVG + "svg", {
            "width": f"{SHEET_MM[0]}mm", "height": f"{SHEET_MM[1]}mm",
            "viewBox": f"0 0 {SHEET_MM[0]} {SHEET_MM[1]}",
            "data-status": "DRAFT", "data-mode": mode,
            "data-source": "actual-package-symbol-definition",
        })
        for idx, binding in enumerate(bindings):
            col, row = idx % 3, idx // 3
            px, py = col * 96 + 48, row * 70 + 35
            item = ET.SubElement(root, SVG + "g", {
                "data-reference": binding.reference,
                "data-symbol-id": binding.symbol.identifier,
                "data-pins": ",".join(pin.number for pin in binding.symbol.pins),
            })
            subroot, posed = _actual_root(
                binding.symbol, binding.reference,
                binding.instance.transform, diagnostic=diagnostic
            )
            bbox = posed.stroked_bounds
            cx = (bbox.min_x + bbox.max_x) / 2000
            cy = (bbox.min_y + bbox.max_y) / 2000
            geom = ET.SubElement(item, SVG + "g", {
                "transform": f"translate({px-cx:g},{py-cy:g})",
            })
            for child in subroot:
                if child.tag in (SVG + "g", SVG + "rect"):
                    geom.append(child)
            ET.SubElement(root, SVG + "text", {
                "x": str(px), "y": str(py + 25),
                "font-family": "OpenGost Type A", "text-anchor": "middle",
                "font-size": "3.4", "fill": "#000",
            }).text = f"{binding.reference}: {binding.symbol.identifier}"
            if diagnostic:
                ET.SubElement(root, SVG + "text", {
                    "x": str(px), "y": str(py + 30),
                    "font-family": "OpenGost Type A", "text-anchor": "middle",
                    "font-size": "2.8", "fill": "#0b7862",
                }).text = ",".join(
                    f"{p.number}:{p.name}" for p in binding.part.pins
                )
        fname = f"TL494-source-13-{mode}.svg"
        _write_svg(directory / fname, root)
        result["files"].append(fname)
    (directory / "TL494-UGO-cycle9-manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output_dir)
    print(f"Actual symbol SVG: {len(result['files'])}; "
          f"13 source selections, {len(result['d4'])} D4 cases; DRAFT")


if __name__ == "__main__":
    main()
