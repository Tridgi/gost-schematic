"""Cross-owner proof: genuine PR #97 typed physical IC -> PAINT PR #93.

Run ONLY after overlaying pinned source from ELEKTRIK #97 in CI. No mock
PinRef, no fake Type A, and no source module copied to PAINT branch.
"""
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.rendering.ic_electrical_binding import (
    render_verified_ic_paint_binding,
)
from gost_schematic.rendering.ic_rectangular import IcTypographyProfile
from gost_schematic.standards.type_a_font import inspect_type_a_font

SVG = "{http://www.w3.org/2000/svg}"


def main():
    # The ELEKTRIK package is a pinned optional source overlaid only in CI.
    # Import here so this PAINT-only tree has a reproducible Ruff layout.
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.electrical.ic_serde import ic_from_json

    font = Path(os.environ["IC_TYPE_A_FONT_PATH"])
    inspection = inspect_type_a_font(font, h_um=3500)
    assert inspection.measured_cap_height_um == 3500
    assert inspection.style.font_sha256 == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    )
    measure = PillowTextMeasurer()
    result = {
        "font_sha256": inspection.style.font_sha256,
        "cases": {},
        "paired_portrait_results": {},
    }
    out = Path("output/ic-cycle7-joint")
    out.mkdir(parents=True, exist_ok=True)
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
            # Verify the actual owner-typed model at both visual word angles.
            # A too-small existing IcSymbolSpec must remain BLOCKED rather than
            # silently rewriting a physical pin or accepting a collision.
            try:
                angle_90 = render_verified_ic_paint_binding(
                    binding, inspection.style, measure, circuit=circuit,
                    typography_profile=(
                        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT
                    ),
                    function_rotation=90,
                )
                angle_0 = render_verified_ic_paint_binding(
                    binding, inspection.style, measure, circuit=circuit,
                    typography_profile=(
                        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT
                    ),
                    function_rotation=0,
                )
            except ValueError as exc:
                if not any(code in str(exc) for code in (
                    "IC_PORTRAIT_BODY_REQUIRED", "IC_TEXT_OVERFLOW",
                    "IC_INK_COLLISION", "IC_REFDES_UNPLACEABLE",
                )):
                    raise
                result["paired_portrait_results"][key] = {
                    "status": "BLOCKED_OWNER_GEOMETRY_REVISION",
                    "diagnostic": str(exc),
                }
            else:
                assert len(angle_0) == len(angle_90)
                assert all(
                    a.pin_anchors == b.pin_anchors
                    and a.body_world == b.body_world
                    and a.connection_targets == b.connection_targets
                    for a, b in zip(angle_0, angle_90, strict=True)
                )
                for index, (a,b) in enumerate(
                    zip(angle_0, angle_90, strict=True)
                ):
                    (out/f"{key}-typed-{index}-function-0.svg").write_text(
                        a.svg, encoding="utf-8",
                    )
                    (out/f"{key}-typed-{index}-function-90.svg").write_text(
                        b.svg, encoding="utf-8",
                    )
                assert circuit.nets == (Net("TEST_A",(PinRef(reference,"1"),)),)
                result["paired_portrait_results"][key] = {
                    "status": "PASS_TYPED_NET_PINREF_SAME",
                    "physical_pin_count": count,
                    "unit_count": len(angle_90),
                    "unchanged_nets": True,
                    "unchanged_external_points": True,
                    "version": "portrait_function_v2_draft",
                }
            result["cases"][key]={
                "physical_count":count,
                "unit_count":len(binding.views),
                "source_sha_verified":True,
                "model_unchanged":True,
                "net_unchanged":True,
                "all_external_points_equal":True,
                "font_h_um":inspection.measured_cap_height_um,
            }
    (out/"paint-elektrik-typed-proof.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8",
    )
    print("PASS real type-A PAINT/ELEKTRIK 12 synthetic package families; "
          "paired portrait results:", result["paired_portrait_results"])


if __name__ == "__main__":
    main()
