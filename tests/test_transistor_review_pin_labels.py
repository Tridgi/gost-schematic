"""Regression: vertical S/E/C labels must not sit on the conductor."""
from xml.etree import ElementTree as ET

import pytest

from examples.review_bipolar_layouts import generate as bipolar
from examples.review_mosfet_layouts import generate as mosfet
from examples.review_transistor_switches import generate as switches
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Side

SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("view", ("diagnostic", "protection"))
def test_all_112_layouts_have_readable_contact_labels(tmp_path, view):
    from gost_schematic.catalog.transistor_switches import SwitchKind

    bipolar(tmp_path / "bjt")
    for dep in (False, True):
        for body in (False, True):
            mosfet(tmp_path / f"mos-{dep}-{body}", depletion=dep, separate_body=body)
    mosfet(tmp_path / "diode", body_diode=True)
    for kind in SwitchKind:
        switches(tmp_path / kind.value, kind)
    resolver = CatalogResolver()
    seen = set()
    for path in tmp_path.rglob(f"*-{view}.svg"):
        for group in ET.parse(path).getroot().findall(SVG + "g"):
            ident = group.get("data-symbol-id")
            if not ident:
                continue
            _, symbol = resolver.resolve(ident)
            seen.add(ident)
            labels = group.findall(f"{SVG}text[@data-pin-label]")
            assert len(labels) == len(symbol.pins)
            bounds = []
            for pin in symbol.pins:
                label = next(t for t in labels if t.get("data-pin-label") == pin.number)
                assert label.text == pin.label
                x, y = float(label.get("x")), float(label.get("y"))
                px, py = pin.at.x / 1000, pin.at.y / 1000
                anchor = label.get("text-anchor")
                width = len(pin.label) * 1.8  # conservative upper bound for these Latin labels
                left = x if anchor == "start" else x - width / 2
                box = (left, y - 1.8, left + width, y + 0.5)
                if pin.side in (Side.TOP, Side.BOTTOM):
                    assert anchor == "start" and x - px >= 1.5
                    assert abs(y - py) <= 0.7
                else:
                    assert anchor == "middle" and abs(x - px) < 0.001
                    assert py - y >= 1.5
                # All text fits in a cell, above its layout caption (y=16).
                assert -21 < box[0] < box[2] < 21
                assert -16 < box[1] < box[3] < 15
                for other in bounds:
                    assert (box[2] <= other[0] or box[0] >= other[2] or
                            box[3] <= other[1] or box[1] >= other[3])
                bounds.append(box)
    assert seen == set(resolver.transistor_layout_ids())
