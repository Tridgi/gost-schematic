"""Side-by-side native artwork and diagnostic views for the installed catalog."""
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.units import format_mm
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def label(parent, x, y, value, **attrs):
    ET.SubElement(parent, SVG + "text", {
        "x": str(x), "y": str(y), "font-size": "2.8",
        "font-family": "sans-serif", **attrs,
    }).text = value


def generate(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    catalog = CatalogResolver()
    ids = sorted(catalog.symbols)
    # Fixed mm scale, paginated rather than squeezing artwork to fit.
    page_size, row_h, width = 16, 48, 230
    for start in range(0, len(ids), page_size):
        page = ids[start:start + page_size]
        height = 20 + row_h * len(page)
        root = ET.Element(SVG + "svg", {"width": f"{width}mm",
                                       "height": f"{height}mm",
                                       "viewBox": f"0 0 {width} {height}"})
        ET.SubElement(root, SVG + "rect", {"width": str(width), "height": str(height),
                                          "fill": "white"})
        label(root, 5, 7, "GOST schematic — installed catalog / DRAFT",
              **{"font-size": "4"})
        label(root, 90, 15, "Native SVG", **{"text-anchor": "middle"})
        label(root, 170, 15, "Native SVG + keepout and pins", **{"text-anchor": "middle"})
        for i, identifier in enumerate(page):
            symbol = catalog.symbols[identifier]
            y = 20 + i * row_h + row_h // 2
            if not inspect_conductor_topology(symbol).valid:
                raise ValueError(f"{identifier}: invalid conductor topology")
            label(root, 5, y - 4, identifier, **{"font-size": "2.3"})
            label(root, 5, y + 1, f"R{symbol.revision} | {len(symbol.pins)} pins")
            label(root, 5, y + 6, symbol.status.value.upper())
            for center, diagnostic in ((90, False), (170, True)):
                group = ET.SubElement(root, SVG + "g", {
                    "transform": f"translate({center} {y})",
                    "data-symbol-id": identifier,
                    "data-view": "diagnostic" if diagnostic else "clean",
                })
                rendered = ET.fromstring(render_symbol_svg(symbol, review_overlay=diagnostic))
                for child in rendered:
                    group.append(child)
                for key, value in symbol.constant_annotations:
                    slot = next(item for item in symbol.annotation_slots if item.key == key)
                    at = slot.candidates[0]
                    label(group, format_mm(at.at.x), format_mm(at.at.y), value, **{
                        "font-size": "2.5",
                        "text-anchor": {"left": "start", "center": "middle",
                                        "right": "end"}[at.horizontal.value],
                        "dominant-baseline": {"top": "hanging", "center": "central",
                                              "bottom": "auto"}[at.vertical.value],
                        "data-note": key,
                    })
                if diagnostic:
                    for pin in symbol.pins:
                        label(group, format_mm(pin.at.x + 800), format_mm(pin.at.y - 800),
                              pin.number, **{"font-size": "1.8", "fill": "#148a74",
                                             "data-pin": pin.number})
            ET.SubElement(root, SVG + "line", {"x1": "5", "x2": "225",
                          "y1": str(y + row_h // 2), "y2": str(y + row_h // 2),
                          "stroke": "#dedede", "stroke-width": ".15"})
        (output / f"catalog-{start // page_size + 1:02}.svg").write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return len(ids)


if __name__ == "__main__":
    print(f"Rendered {generate(Path('output/full-catalog-native'))} native symbols")
