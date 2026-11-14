"""Real TL494CN 16-physical-pin Type-A render using PAINT PR #93 (DRAFT).

No synthetic pinout: pin numbering and functions from TI TL494 datasheet.
Pins/targets are materialized once; a 0/90-degree text switch does not change
anchors or physical identities. PR #93 is fetched into isolated CI for rendering;
the branch is NOT merged with integration.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box, Point, Side, SIDE_VECTORS
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import PhysicalPin, ElectricalType
from gost_schematic.rendering.ic_rectangular import (
    IcFieldContent, IcRenderingPolicy, IcResolvedUnit, IcTypographyProfile,
    ResolvedIcPin, propose_ic_dimensions, render_resolved_ic,
)
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.standards.type_a_font import inspect_type_a_font

PINS = {
    "1":("1IN+",ElectricalType.INPUT),
    "2":("1IN−",ElectricalType.INPUT),
    "3":("FEEDBACK",ElectricalType.OUTPUT),
    "4":("DTC",ElectricalType.INPUT),
    "5":("CT",ElectricalType.UNSPECIFIED),
    "6":("RT",ElectricalType.UNSPECIFIED),
    "7":("GND",ElectricalType.POWER_INPUT),
    "8":("C1",ElectricalType.OPEN_COLLECTOR),
    "9":("E1",ElectricalType.OUTPUT),
    "10":("E2",ElectricalType.OUTPUT),
    "11":("C2",ElectricalType.OPEN_COLLECTOR),
    "12":("VCC",ElectricalType.POWER_INPUT),
    "13":("OUTPUT CTRL",ElectricalType.INPUT),
    "14":("REF",ElectricalType.POWER_OUTPUT),
    "15":("2IN−",ElectricalType.INPUT),
    "16":("2IN+",ElectricalType.INPUT),
}
SOURCE_PHOTO_LEFT=("2","4","3","5","6","7","1","16")
SOURCE_PHOTO_RIGHT=("12","15","14","13","8","11","9","10")


def build(font_file: Path):
    inspection=inspect_type_a_font(
        font_file,h_um=3500,family="OpenGost Type A TT",require_family_match=True,
    )
    style=inspection.style
    measurer=PillowTextMeasurer()
    policy=IcRenderingPolicy()
    physical=PartDefinition(
        identifier="reference.tl494cn",reference_prefix="DA",
        symbol_id="reference.tl494cn",
        pins=tuple(PhysicalPin(num,PINS[num][0],PINS[num][1])
                   for num in sorted(PINS,key=int)),
    )
    content=IcFieldContent(function="PWM",analog=True)
    template=[]
    for side,numbers in ((Side.LEFT,SOURCE_PHOTO_LEFT),(Side.RIGHT,SOURCE_PHOTO_RIGHT)):
        for row,num in enumerate(numbers,1):
            # The PHOTO places some logical inputs on the right.
            # Label physical electrical type separately from the E3 presentation role.
            role="power" if num in ("7","12","14") else (
                "passive" if num == "3" else "in" if side is Side.LEFT else "out"
                if num in ("3","8","9","10","11") else "passive"
            )
            template.append(ResolvedIcPin(
                f"DA1.P{num}",num,PINS[num][0],side,row,
                Point(100000+int(num)*109,200000+int(num)*213),role,
            ))
    template=tuple(template)
    plans={
        angle: propose_ic_dimensions(
            content,template,style,measurer,policy,function_rotation=angle,
        ) for angle in (0,90)
    }
    pitch=plans[0].row_pitch_um
    lead=plans[0].lead_length_um
    if plans[90].lead_length_um!=lead:
        raise ValueError("Physical lead revision between typography angles")
    if plans[90].row_pitch_um!=pitch:
        raise ValueError("Portrait typography cannot be switched without body revision")
    width=max(x.width_um for x in plans.values())
    height=max(x.height_um for x in plans.values())
    origin=Point(35000,30000)
    resolved=[]
    for pin in template:
        start=Point(
            origin.x + (0 if pin.side is Side.LEFT else width),
            origin.y + pin.row*pitch + pitch//2,
        )
        vector=SIDE_VECTORS[pin.side]
        resolved.append(replace(
            pin,anchor=Point(
                start.x + vector.x*lead,
                start.y + vector.y*lead,
            )
        ))
    resolved=tuple(resolved)
    baseline=IcResolvedUnit(
        reference="DA1",body=Box(0,0,width,height),
        pins=resolved,content=content,origin=origin,
        typography_profile=IcTypographyProfile.LEGACY_V1,
        function_rotation=0,
    )
    targets=tuple(IcConnectionTarget(
        pin_id=pin.pin_id,pin_ref=PinRef("DA1",pin.number),
        anchor=pin.anchor,connectable=True,
        net_id=None,
    ) for pin in resolved)
    assert {int(x.number) for x in resolved}==set(range(1,17))
    assert {x.number for x in physical.pins}=={x.number for x in resolved}
    circuit=Circuit((ComponentInstance("DA1",physical.identifier),),())
    assert circuit.components[0].reference=="DA1"
    return baseline,style,measurer,policy,inspection,targets,physical


def generate(output: Path,font_file: Path):
    base,style,measurer,policy,inspection,targets,part=build(font_file)
    output.mkdir(parents=True,exist_ok=True)
    manifest={
        "status":"DRAFT_REAL_TL494_PHYSICAL_IC_PAINT_PR93",
        "hardware":"Texas Instruments TL494CN",
        "native_paint_head":"79ddb2ae57efd9ea621d64914a324988b343061d",
        "physical_pin_count":len(part.pins),
        "font_sha256":style.font_sha256,
        "font_face":list(inspection.reported_face),
        "text_h_um":inspection.measured_cap_height_um,
        "real_pin_names":{k:v[0] for k,v in PINS.items()},
        "physical_pin_anchors_um":{
            pin.number:[pin.anchor.x,pin.anchor.y] for pin in base.pins
        },
        "net_assignment_verified":False,
        "source_photo_pin_order":{"left":SOURCE_PHOTO_LEFT,"right":SOURCE_PHOTO_RIGHT},
        "variants":{},
    }
    for deg in (0,90):
        unit=replace(base,function_rotation=deg)
        for diagnostic in (False,True):
            result=render_resolved_ic(
                unit,style,measurer,policy=policy,
                editor_targets=targets,editor_overlay=diagnostic,
                review_overlay=False,
            )
            if result.pin_anchors!=tuple((p.pin_id,p.anchor) for p in base.pins):
                raise AssertionError("PAINT mutated physical pin anchor")
            key=f"PWM_angle_{deg}_{'diagnostic' if diagnostic else 'clean'}"
            svg=output/f"TL494CN_{key}.svg"
            svg.write_text(result.svg,encoding="utf-8")
            ET.fromstring(result.svg)
            if not diagnostic and any(
                marker in result.svg for marker in (
                    "#148645","#8b1e27",'data-layer="editor-connection-targets"'
                )):
                raise AssertionError("Diagnostic colors leaked into clean SVG")
            if diagnostic and 'data-layer="editor-connection-targets"' not in result.svg:
                raise AssertionError("PAINT lost the 16 verified editor endpoints")
            manifest["variants"][key]={
                "svg":svg.name,"real_anchors":len(result.pin_anchors),
                "font":result.font_sha256,"ink_boxes":len(result.ink),
            }
    (output/"TL494CN_ic_manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "pins":16,"font":inspection.reported_face[0],
        "mode":"real PAINT PR93, exact TL494 physical pins",
        "variants":len(manifest["variants"]),
    },ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--font-file",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    generate(args.output,args.font_file)


if __name__=="__main__":
    main()
