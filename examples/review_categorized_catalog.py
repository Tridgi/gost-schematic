"""Three aligned native catalog views, partitioned by actual symbol family.

No re-drawing: artwork and overlay primitives come from render_symbol_svg.
The protection-only view deliberately omits all functional artwork and notes.
"""
import json
from collections import defaultdict
from math import ceil
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.units import format_mm
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])
VIEWS = ("clean", "diagnostic", "protection")
TITLES = {
    "clean": "Чистые УГО",
    "diagnostic": "УГО, контакты и защитные зоны",
    "protection": "Только контакты и защитные зоны",
}
CATEGORIES = {
    "resistor": "Резисторы",
    "capacitor": "Конденсаторы",
    "inductor": "Катушки индуктивности",
    "choke": "Дроссели",
    "transformer": "Трансформаторы",
    "transductor": "Трансдукторы",
    "magnetic_amplifier": "Магнитные усилители",
    "reactor": "Реакторы",
    "diode": "Диоды",
    "rectifier": "Выпрямители",
    "transistor": "Транзисторы",
    "fuse": "Предохранители",
    "arrester": "Разрядники",
    "sensor": "Датчики",
    "acoustic": "Акустические приборы",
    "hall": "Датчики Холла",
}


def text(parent, x, y, value, *, size=2.5, **attrs):
    ET.SubElement(parent, SVG + "text", {
        "x": str(x), "y": str(y), "font-size": str(size),
        "font-family": "DejaVu Sans, sans-serif", **attrs,
    }).text = value


def extent(symbol):
    # Symmetric extent around the actual symbol origin, with conservative
    # space for review pin labels and authored constant annotation anchors.
    box = symbol.stroked_bounds
    rx = max(abs(box.min_x), abs(box.max_x)) / 1000 + 4
    ry = max(abs(box.min_y), abs(box.max_y)) / 1000 + 4
    for key, value in symbol.constant_annotations:
        slot = next(s for s in symbol.annotation_slots if s.key == key)
        at = slot.candidates[0].at
        rx = max(rx, abs(at.x) / 1000 + len(value) * 2.5 + 2)
        ry = max(ry, abs(at.y) / 1000 + 5)
    return rx, ry


def generate(output: Path) -> dict:
    catalog = CatalogResolver()
    by_family = defaultdict(list)
    for identifier, symbol in sorted(catalog.symbols.items()):
        if not inspect_conductor_topology(symbol).valid:
            raise ValueError(f"Invalid conductor topology: {identifier}")
        by_family[identifier.split(".", 1)[0]].append(identifier)
    manifest = {"schema_version": 1, "symbol_count": len(catalog.symbols),
                "views": list(VIEWS), "categories": []}
    for family, ids in sorted(by_family.items()):
        symbols = [catalog.symbols[identifier] for identifier in ids]
        rx = max(extent(symbol)[0] for symbol in symbols)
        ry = max(extent(symbol)[1] for symbol in symbols)
        cell_w = max(70, ceil(rx * 2 + 8), max(len(i) for i in ids) * 2 + 4)
        cell_h = max(40, ceil(ry * 2 + 15))
        columns = min(3, len(ids))
        rows_per_page = max(1, min(6, 650 // cell_h))
        capacity = columns * rows_per_page
        family_entry = {"id": family, "title": CATEGORIES.get(family, family),
                        "count": len(ids), "pages": []}
        manifest["categories"].append(family_entry)
        for start in range(0, len(ids), capacity):
            page = ids[start:start + capacity]
            rows = ceil(len(page) / columns)
            width, height = columns * cell_w + 12, rows * cell_h + 29
            stem = f"{family}-{start // capacity + 1:02d}"
            record = {"symbols": page, "files": {}}
            family_entry["pages"].append(record)
            for view in VIEWS:
                root = ET.Element(SVG + "svg", {
                    "width": f"{width}mm", "height": f"{height}mm",
                    "viewBox": f"0 0 {width} {height}",
                    "data-category": family, "data-view": view,
                })
                ET.SubElement(root, SVG + "rect", {"width": str(width),
                              "height": str(height), "fill": "white"})
                text(root, 6, 8, family_entry["title"], size=4.2)
                text(root, 6, 14, TITLES[view] + " / DRAFT", size=3)
                text(root, 6, 20, f"{start + 1}–{start + len(page)} / {len(ids)}")
                for i, identifier in enumerate(page):
                    symbol = catalog.symbols[identifier]
                    x = 6 + (i % columns + 0.5) * cell_w
                    y = 25 + (i // columns) * cell_h + ry
                    group = ET.SubElement(root, SVG + "g", {
                        "transform": f"translate({x} {y})",
                        "data-symbol-id": identifier, "data-view": view,
                    })
                    native = ET.fromstring(render_symbol_svg(
                        symbol, review_overlay=view != "clean",
                    ))
                    for child in native:
                        if view != "protection" or child.tag in (SVG + "rect", SVG + "circle"):
                            group.append(child)
                    if view != "protection":
                        for key, value in symbol.constant_annotations:
                            slot = next(s for s in symbol.annotation_slots if s.key == key)
                            at = slot.candidates[0]
                            text(group, format_mm(at.at.x), format_mm(at.at.y), value, **{
                                "text-anchor": {"left": "start", "center": "middle",
                                                "right": "end"}[at.horizontal.value],
                                "dominant-baseline": {"top": "hanging", "center": "central",
                                                      "bottom": "auto"}[at.vertical.value],
                                "data-note": key,
                            })
                    if view != "clean":
                        for pin in symbol.pins:
                            text(group, format_mm(pin.at.x + 800),
                                 format_mm(pin.at.y - 800), pin.number, size=1.8,
                                 fill="#148a74", **{"data-pin": pin.number})
                    text(group, 0, ry + 5, identifier,
                         size=2.4, **{"text-anchor": "middle", "data-label": "id"})
                    text(group, 0, ry + 9, f"R{symbol.revision} | {len(symbol.pins)} pins",
                         size=2.1, **{"text-anchor": "middle", "data-label": "revision"})
                relative = f"{view}/{stem}.svg"
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
                record["files"][view] = relative
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(f"Categorized {generate(Path('output/catalog-categorized'))['symbol_count']} symbols")
