"""Render actual installed symbols using the native SVG renderer."""
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.rendering.svg import render_symbol_svg

IDS = (
    "resistor.fixed",
    "resistor.variable",
    "resistor.trimmer",
    "resistor.fixed_power_0p05",
    "resistor.fixed_power_0p125",
    "resistor.fixed_power_0p25",
    "resistor.fixed_power_0p5",
    "resistor.fixed_power_1",
    "resistor.fixed_power_2",
    "resistor.fixed_power_5",
    "resistor.tap_center",
    "resistor.tap_offset",
    "resistor.tap_two_same",
    "resistor.tap_two_opposite",
    "resistor.rheostat",
    "resistor.trimmer_rheostat",
    "resistor.variable_side_wiper",
    "resistor.trimmer_top_wiper",
    "resistor.heater",
    "resistor.shunt_kelvin",
)


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    catalog = CatalogResolver()
    for review in (False, True):
        mode = "diagnostic" if review else "clean"
        svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                                 "width": "180mm", "height": "210mm",
                                 "viewBox": "0 0 180 210"})
        ET.SubElement(svg, "rect", {"width": "180", "height": "210", "fill": "white"})
        for i, identifier in enumerate(IDS):
            symbol = catalog.symbols[identifier]
            native = render_symbol_svg(symbol, review_overlay=review)
            (output / f"{identifier}-{mode}.svg").write_text(native, encoding="utf-8")
            item = ET.fromstring(native)
            x, y = 22.5 + (i % 4) * 45, 20 + (i // 4) * 40
            group = ET.SubElement(svg, "g", {"transform": f"translate({x} {y})"})
            for child in item:
                for node in child.iter():
                    node.tag = node.tag.rsplit("}", 1)[-1]
                group.append(child)
            ET.SubElement(svg, "text", {"x": str(x), "y": str(y + 16),
                                        "font-size": "2", "text-anchor": "middle"}).text = identifier
        (output / f"gallery-{mode}.svg").write_text(
            ET.tostring(svg, encoding="unicode") + "\n", encoding="utf-8",
        )


if __name__ == "__main__":
    generate(Path("output/resistor-batch01"))
