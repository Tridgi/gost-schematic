"""Native matrix of 16 BJT layouts, with three matching view modes."""
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_pin_labels import add_pin_label
from gost_schematic.catalog.transistors import bipolar_review_variants
from gost_schematic.rendering.svg import render_symbol_svg

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def generate(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    variants = bipolar_review_variants()
    for view in ("clean", "diagnostic", "protection"):
        root = ET.Element(SVG + "svg", {
            "width": "184mm", "height": "177mm", "viewBox": "0 0 184 177",
        })
        ET.SubElement(root, SVG + "rect", {
            "width": "184", "height": "177", "fill": "white",
        })

        def text(parent, x, y, value, size="2.6"):
            ET.SubElement(parent, SVG + "text", {
                "x": str(x), "y": str(y), "font-size": size,
                "font-family": "sans-serif", "text-anchor": "middle",
            }).text = value

        text(root, 92, 7, f"BJT layout matrix / {view} / DRAFT", "3.6")
        for i, name in enumerate(("NPN case", "PNP case", "NPN bare", "PNP bare")):
            text(root, 23 + 46 * i, 15, name)
        for i, variant in enumerate(variants):
            symbol = variant.symbol
            x, y = 23 + (i % 4) * 46, 34 + (i // 4) * 40
            group = ET.SubElement(root, SVG + "g", {
                "transform": f"translate({x} {y})",
                "data-symbol-id": symbol.identifier, "data-view": view,
            })
            native = ET.fromstring(render_symbol_svg(
                symbol, review_overlay=view != "clean",
            ))
            for child in native:
                if view != "protection" or child.tag in (SVG + "rect", SVG + "circle"):
                    group.append(child)
            if view != "clean":
                for pin in symbol.pins:
                    add_pin_label(group, pin)
            text(root, x, y + 16,
                 f"C:{variant.spec.collector_exit.value.upper()} "
                 f"E:{variant.spec.emitter_exit.value.upper()}")
        (output / f"bjt-{view}.svg").write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8",
        )
    return len(variants)


if __name__ == "__main__":
    print(f"Rendered {generate(Path('output/bipolar-layouts'))} BJT review variants")
