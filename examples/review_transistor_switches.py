"""Native JFET and IGBT review matrices, three aligned views."""
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_pin_labels import add_pin_label
from gost_schematic.catalog.transistor_switches import SwitchKind, switch_review_variants
from gost_schematic.rendering.svg import render_symbol_svg

SVG = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", SVG[1:-1])


def generate(output: Path, kind: SwitchKind) -> int:
    output.mkdir(parents=True, exist_ok=True)
    variants = switch_review_variants(kind)
    for view in ("clean", "diagnostic", "protection"):
        root = ET.Element(SVG + "svg", {
            "width": "92mm", "height": "177mm", "viewBox": "0 0 92 177",
        })
        ET.SubElement(root, SVG + "rect", {
            "width": "92", "height": "177", "fill": "white",
        })

        def text(parent, x, y, value, size="2.6"):
            ET.SubElement(parent, SVG + "text", {
                "x": str(x), "y": str(y), "font-size": size,
                "font-family": "sans-serif", "text-anchor": "middle",
            }).text = value

        text(root, 46, 7, f"{kind.value.upper()} / {view} / DRAFT", "3.6")
        text(root, 23, 15, "case")
        text(root, 69, 15, "bare")
        for i, variant in enumerate(variants):
            symbol = variant.symbol
            x, y = 23 + (i % 2) * 46, 34 + (i // 2) * 40
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
                 f"{variant.spec.upper_exit.value.upper()}/"
                 f"{variant.spec.lower_exit.value.upper()}")
        (output / f"switch-{view}.svg").write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8",
        )
    return len(variants)


if __name__ == "__main__":
    for kind in SwitchKind:
        count = generate(Path("output/transistor-switches") / kind.value, kind)
        print(f"Rendered {count} layouts: {kind.value}")
