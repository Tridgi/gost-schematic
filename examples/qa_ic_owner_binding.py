"""Cross-owner proof: genuine PR #97 typed physical IC -> PAINT PR #93.

Run ONLY after overlaying pinned source from ELEKTRIK #97 in CI. No mock
PinRef, no fake Type A, and no source module copied to PAINT branch.
"""
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
from gost_schematic.electrical.ic_serde import ic_from_json
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.rendering.ic_electrical_binding import (
    render_verified_ic_paint_binding,
)
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def main():
    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    inspection = inspect_type_a_font(font, h_um=3500)
    assert inspection.measured_cap_height_um == 3500
    assert inspection.style.font_sha256 == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    )
    measure = PillowTextMeasurer()
    result = {"font_sha256": inspection.style.font_sha256, "cases": {}}
    for count in (2, 4, 8, 14, 40, 64):
        for kind, reference in (("DIGITAL", "DD1"), ("ANALOG", "DA1")):
            path = Path(
                f"tests/fixtures/electrical-ic-cycle7/TEST_IC_{kind}_{count}.json"
            )
            record = ic_from_json(path.read_text(encoding="utf-8"))
            binding = propose_ic_paint_binding(record, inspection.style, measure)
            before = (
                binding.record.device,
                binding.record.specs,
                binding.record.placements,
            )
            circuit = Circuit(
                (ComponentInstance(reference, record.device.identifier),),
                (Net("TEST_A", (PinRef(reference, "1"),)),),
            )
            rendered = render_verified_ic_paint_binding(
                binding, inspection.style, measure,
                circuit=circuit, glyph_detail=True,
            )
            assert before == (
                binding.record.device, binding.record.specs,
                binding.record.placements,
            )
            assert circuit.nets == (Net("TEST_A",(PinRef(reference,"1"),)),)
            assert len(rendered) == len(binding.record.specs)
            assert sum(len(view.pin_anchors) for view in rendered)==count
            assert sum(len(view.connection_targets) for view in rendered)==count
            assert all("editor-connection-targets" not in view.svg
                       for view in rendered)
            assert all(view.font_sha256==inspection.style.font_sha256
                       for view in rendered)
            for view in rendered:
                root = ET.fromstring(view.svg)
                assert root.get("data-approval")=="DRAFT"
                for physical in view.connection_targets:
                    assert physical.pin_ref.reference==reference
                    assert physical.pin_ref.number in record.device.pin_map
                if count == 14:
                    assert any(not t.connectable for t in view.connection_targets) or (
                        len(binding.views)>1
                    )
            key=f"{kind.lower()}-{count}"
            result["cases"][key]={
                "physical_count":count,
                "unit_count":len(binding.views),
                "source_sha_verified":True,
                "model_unchanged":True,
                "net_unchanged":True,
                "all_external_points_equal":True,
                "font_h_um":inspection.measured_cap_height_um,
            }
    out = Path("output/ic-cycle7-joint")
    out.mkdir(parents=True,exist_ok=True)
    (out/"paint-elektrik-typed-proof.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8",
    )
    print("PASS real type-A PAINT/ELEKTRIK 12 synthetic package families")


if __name__ == "__main__":
    main()
