"""Native UGO gallery for reference batch 02; technical text is a review overlay."""
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.units import format_mm
from gost_schematic.rendering.svg import render_symbol_svg

IDS = (
    "reactor.current_limiting",
    "acoustic.loudspeaker",
    "acoustic.piezo_laryngophone",
    "resistor.thermistor_ptc",
    "resistor.thermistor_ntc",
    "resistor.thermistor_reference",
    "resistor.strain_linear",
    "resistor.strain_nonlinear",
    "resistor.photo",
    "resistor.varistor",
    "resistor.varistor_reference",
    "resistor.thermistor_ptc_vertical",
    "resistor.thermistor_ntc_vertical",
    "resistor.thermistor_reference_vertical",
    "resistor.strain_linear_vertical",
    "resistor.strain_nonlinear_vertical",
    "resistor.photo_vertical",
    "resistor.varistor_vertical",
    "resistor.varistor_reference_vertical",
    "resistor.magnetic",
    "resistor.magnetic_reference",
    "sensor.hall",
    "sensor.hall_with_case",
    "arrester.vacuum",
    "arrester.gas_filled",
)
SVG = "{http://www.w3.org/2000/svg}"


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    catalog = CatalogResolver()
    for review in (False, True):
        mode = "diagnostic" if review else "clean"
        height = 20 + ((len(IDS) + 3) // 4) * 40
        root = ET.Element("svg", {"xmlns": SVG[1:-1], "width": "200mm",
                                 "height": f"{height}mm", "viewBox": f"0 0 200 {height}"})
        ET.SubElement(root, "rect", {"width": "200", "height": str(height), "fill": "white"})
        for i, identifier in enumerate(IDS):
            symbol = catalog.symbols[identifier]
            native = ET.fromstring(render_symbol_svg(symbol, review_overlay=review))
            # Keep original native geometry and contacts; add declared note/pin text for review.
            native.attrib.update({"viewBox": "-23 -18 46 36", "width": "46mm",
                                  "height": "36mm"})
            for key, value in symbol.constant_annotations:
                anchor = next(slot for slot in symbol.annotation_slots if slot.key == key)
                at = anchor.candidates[0]
                ET.SubElement(native, SVG + "text", {
                    "x": format_mm(at.at.x), "y": format_mm(at.at.y),
                    "font-size": "2.5", "font-family": "sans-serif",
                    "text-anchor": {"left": "start", "center": "middle", "right": "end"}[
                        at.horizontal.value],
                    "dominant-baseline": {"top": "hanging", "center": "central",
                                          "bottom": "auto"}[at.vertical.value],
                    "data-note": key,
                }).text = value
            if review:
                for pin in symbol.pins:
                    ET.SubElement(native, SVG + "text", {
                        "x": format_mm(pin.at.x + 800), "y": format_mm(pin.at.y - 800),
                        "font-size": "1.7", "fill": "#148a74", "data-pin": pin.number,
                    }).text = pin.number
            ET.register_namespace("", SVG[1:-1])
            (output / f"{identifier}-{mode}.svg").write_text(
                ET.tostring(native, encoding="unicode") + "\n", encoding="utf-8")
            x, y = 25 + (i % 4) * 50, 24 + (i // 4) * 40
            group = ET.SubElement(root, "g", {"transform": f"translate({x} {y})",
                                             "data-symbol-id": identifier})
            for child in native:
                for node in child.iter():
                    node.tag = node.tag.rsplit("}", 1)[-1]
                group.append(child)
            ET.SubElement(root, "text", {"x": str(x), "y": str(y + 16),
                                         "font-size": "2", "text-anchor": "middle",
                                         "font-family": "sans-serif"}).text = identifier
        (output / f"gallery-{mode}.svg").write_text(
            ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate(Path("output/resistor-batch02"))
