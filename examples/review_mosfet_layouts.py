"""Native matrix of 16 enhancement MOSFET layouts, with three matching view modes."""
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.transistors import (
    mosfet_body_diode_variants,
    mosfet_extended_variants,
    mosfet_review_variants,
)
from gost_schematic.rendering.svg import render_symbol_svg

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def generate(output: Path, *, depletion: bool = False, separate_body: bool = False,
             body_diode: bool = False) -> int:
    output.mkdir(parents=True, exist_ok=True)
    variants = mosfet_extended_variants(depletion=depletion, separate_body=separate_body)
    if not depletion and not separate_body:
        variants = mosfet_review_variants()
    if body_diode:
        if depletion or separate_body:
            raise ValueError('Body diode gallery requires three-pin enhancement mode')
        variants = mosfet_body_diode_variants()
    mode = 'body diode' if body_diode else ('depletion' if depletion else 'enhancement')
    columns = 2 if body_diode else 4
    width = 46 * columns
    terminals = '4 pins' if separate_body else '3 pins'
    for view in ("clean", "diagnostic", "protection"):
        root = ET.Element(SVG + "svg", {
            "width": f"{width}mm", "height": "177mm", "viewBox": f"0 0 {width} 177",
        })
        ET.SubElement(root, SVG + "rect", {
            "width": str(width), "height": "177", "fill": "white",
        })

        def text(parent, x, y, value, size="2.6"):
            ET.SubElement(parent, SVG + "text", {
                "x": str(x), "y": str(y), "font-size": size,
                "font-family": "sans-serif", "text-anchor": "middle",
            }).text = value

        text(root, width / 2, 7, f"MOSFET {mode} / {terminals} / {view} / DRAFT", "3.6")
        names = ("N bare", "P bare") if body_diode else ("N case", "P case", "N bare", "P bare")
        for i, name in enumerate(names):
            text(root, 23 + 46 * i, 15, name)
        for i, variant in enumerate(variants):
            symbol = variant.symbol
            x, y = 23 + (i % columns) * 46, 34 + (i // columns) * 40
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
                    text(group, pin.at.x / 1000, pin.at.y / 1000 - 1.2,
                         pin.label, "1.8")
            text(root, x, y + 16,
                 f"D:{variant.spec.drain_exit.value.upper()} "
                 f"S:{variant.spec.source_exit.value.upper()}")
        (output / f"mosfet-{view}.svg").write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8",
        )
    return len(variants)


if __name__ == "__main__":
    for mode, depletion, separate in (
        ("enh3", False, False), ("enh4", False, True),
        ("dep3", True, False), ("dep4", True, True),
    ):
        output = Path("output/mosfet-layouts") / mode
        count = generate(output, depletion=depletion, separate_body=separate)
        print(f"Rendered {count} MOSFET review variants: {mode}")

    count = generate(Path("output/mosfet-layouts/diode3"), body_diode=True)
    print(f"Rendered {count} MOSFET review variants: diode3")
