"""One-sheet native GOST Engine PAINT+catalog integration (DRAFT, PARTIAL).

Real stock power-stage UGO and native ExternalWireGraph + real PAINT PR#93
TL494CN with 16 physical pins and real editor targets. All sheet geometry is
from two engine renderers, NOT manually drawn SVG shapes.

An IC-sized adapter SymbolDefinition reserves geometry for the native sheet
layout, then its visual ink is REPLACED with real render_resolved_ic() output.
Physical pin positions and PinRef identities must match exactly before merge.

Only a traced core subset has connected electrical nets. This is a real
integration proof, NOT the complete 23-item photo circuit or approved E3.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_native_rework import build as build_power, source_graph, P
from examples.tl494_ic_paint_reference import build as build_paint_ic
from gost_schematic.core.geometry import Box, Line, Point, Rectangle
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.core.transforms import Transform
from gost_schematic.rendering.ic_rectangular import render_resolved_ic
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph, WireSegment, validate_external_wires,
)
from gost_schematic.validation.symbol_checks import validate_symbol
from gost_schematic.core.units import format_mm


URI="http://www.w3.org/2000/svg"
ET.register_namespace("",URI)
TAG="{"+URI+"}"


def attach_catalog_ic(font_file:Path):
    baseline,style,measure,policy,inspection,targets,part = build_paint_ic(font_file)
    target_origin=P(65,87)
    dx=target_origin.x-baseline.origin.x
    dy=target_origin.y-baseline.origin.y
    moved_pins=tuple(replace(
        pin,anchor=Point(pin.anchor.x+dx,pin.anchor.y+dy),
    ) for pin in baseline.pins)
    unit=replace(baseline,origin=target_origin,pins=moved_pins)
    newtargets=tuple(replace(t,anchor=Point(t.anchor.x+dx,t.anchor.y+dy))
                     for t in targets)
    body=unit.body
    # GRAPHIC ADAPTER: physical layout contract only. Its ink is never included
    # in the final exported SVG: output is from PAINT.render_resolved_ic.
    geometry=[Rectangle(body)]
    for pin in unit.pins:
        end=Point(pin.anchor.x-unit.origin.x,pin.anchor.y-unit.origin.y)
        start=Point(
            body.min_x if pin.side.value=="left" else body.max_x,
            end.y,
        )
        geometry.append(Line(start,end))
    graph_pins=tuple(
        GraphicPin(pin.number,
                   Point(pin.anchor.x-unit.origin.x,pin.anchor.y-unit.origin.y),
                   pin.side,pin.label) for pin in unit.pins
    )
    symbol=SymbolDefinition(
        identifier=part.identifier,
        revision=1,
        graphics=tuple(geometry),pins=graph_pins,
        body_keepout=body,line_width_um=policy.line_width_um,
        status=SymbolStatus.DRAFT,
        standard_refs=(
            "RENDER_SURROGATE_ONLY: all final IC ink comes from PAINT PR#93",
            "Each catalog GraphicPin position is derived from PAINT resolved physical pin",
        ),
    )
    errors=[d for d in validate_symbol(symbol) if d.severity.value=="error"]
    if errors:
        raise AssertionError("PAINT-to-sheet symbol adapter invalid: "+str(errors))
    instance=ComponentInstance("DA1",part.identifier,unit.origin)
    reference=instance.pin_positions(symbol)
    for pin in unit.pins:
        if reference[pin.number]!=pin.anchor:
            raise AssertionError(f"IC adapter changed PAINT physical PinRef DA1.{pin.number}")
    return unit,newtargets,part,symbol,instance,style,measure,policy,inspection


def S(net:str,a:Point,b:Point) -> WireSegment:
    if a==b or (a.x!=b.x and a.y!=b.y):
        raise AssertionError(f"Unrouted or nonorthogonal wire {net}: {a}→{b}")
    return WireSegment(a,b,net)


def generate(output:Path,font_file:Path):
    power,parts,symbols,power_pins=build_power()
    unit,targets,part,symbol,instance,style,measure,policy,font=attach_catalog_ic(font_file)
    parts[part.identifier]=part
    symbols[part.identifier]=symbol
    part_r8=parts["resistor.fixed"]
    r8=ComponentInstance(
        "R8","resistor.fixed",P(150,183),
        Transform(rotation=90),Quantity.from_unit("10",Unit.OHM),
    )
    power_component_names={x.reference for x in power.components}
    if "R8" in power_component_names or "DA1" in power_component_names:
        raise AssertionError("Duplicate owner")
    components=(*power.components,instance,r8)
    def add(net, pin_refs):
        return Net(net,tuple(pin_refs))
    updated=[]
    for net in power.nets:
        if net.name=="COMMON":
            updated.append(add(net.name,(*net.members,
                PinRef("DA1","7"),PinRef("DA1","1"),
                PinRef("DA1","16"),PinRef("R8","2"),
            )))
        else:
            updated.append(net)
    updated.append(add("GATE_DRIVE",(
        PinRef("DA1","9"),PinRef("DA1","10"),
        PinRef("VT1","1"),PinRef("R8","1"),
    )))
    circuit=Circuit(components,tuple(updated))
    # Authoritative world coordinates, never inferred from graphic ink
    pose={}
    for comp in components:
        physical=parts[comp.part_id]
        sym=symbols[physical.symbol_id]
        if {p.number for p in physical.pins}!={p.number for p in sym.pins}:
            raise AssertionError(comp.reference+" physical/graphic pin mapping drift")
        pose[comp.reference]=comp.pin_positions(sym)
    def pt(ref,number):return pose[ref][number]
    refground=pt("DA1","7")
    # DA1 left-side pin1, pin16 and GND share ground in the source picture.
    common_x=P(42,0).x
    common_y=P(220,0).y
    groundpins=[pt("DA1",num) for num in ("7","1","16")]
    copper=[]
    for pin in groundpins:
        copper.append(S("COMMON",pin,Point(common_x,pin.y)))
    copper.append(S("COMMON",Point(common_x,min(p.y for p in groundpins)),
                    Point(common_x,common_y)))
    copper.append(S("COMMON",pt("R8","2"),Point(pt("R8","2").x,common_y)))
    # Power COMMON original segment from X1.2 to return and from MOSFET S to return.
    # All additional stubs attach with explicitly declared junctions.
    E1=pt("DA1","9")
    E2=pt("DA1","10")
    Gate=pt("VT1","1")
    R8A=pt("R8","1")
    gate_x=R8A.x
    if E1.x>=gate_x or E2.x>=gate_x:
        raise AssertionError("Gate corridor must be right of PAINT external pins")
    copper.extend([
        S("GATE_DRIVE",E1,Point(gate_x,E1.y)),
        S("GATE_DRIVE",E2,Point(gate_x,E2.y)),
        S("GATE_DRIVE",Gate,Point(gate_x,Gate.y)),
        S("GATE_DRIVE",Point(gate_x,Gate.y),R8A),
    ])
    original=source_graph()
    graph=ExternalWireGraph(
        segments=(*original.segments,*copper),
        junctions=(*original.junctions,
            Point(common_x,common_y),
            Point(pt("R8","2").x,common_y),
            Point(gate_x,E1.y),Point(gate_x,E2.y),
        ),
    )
    electrical=validate_external_wires(circuit,graph,parts,symbols)
    erc=validate_circuit(circuit,parts,symbols)
    bypart={pid:symbols[part.symbol_id] for pid,part in parts.items()}
    output.mkdir(parents=True,exist_ok=True)
    variants={}
    for diagnostic in (False,True):
        sheet=render_external_wire_sheet(
            circuit,graph,bypart,style,measure,
            diagnostic=diagnostic,strict_layout=False,
        )
        ic=render_resolved_ic(
            unit,style,measure,policy=policy,
            editor_targets=targets,editor_overlay=diagnostic,
        )
        expected=tuple((p.pin_id,p.anchor) for p in unit.pins)
        if ic.pin_anchors!=expected:
            raise AssertionError("PAINT moved physical endpoints during sheet composition")
        svg=ET.fromstring(sheet.svg)
        placeholder=svg.find(f"./{TAG}g[@data-reference='DA1']")
        if placeholder is None:
            raise AssertionError("Native sheet does not have the DRAFT IC placeholder")
        svg.remove(placeholder)
        icroot=ET.fromstring(ic.svg)
        group=ET.SubElement(svg,TAG+"g",{
            "data-owner":"DA1",
            "data-ink-source":"native-PAINT-PR93",
            "data-pin-source":"real-physical-TL494CN",
        })
        for element in list(icroot):
            if element.tag==TAG+"title":continue
            group.append(element)
        # Huge sheet viewBox gives 10 mm white breathing room.
        x,y,w,h=map(float,svg.get("viewBox").split())
        x0=min(x,unit.origin.x/1000-15)-8
        y0=min(y,unit.origin.y/1000-15)-8
        x1=max(x+w,unit.origin.x/1000+unit.body.max_x/1000+17)+8
        y1=max(y+h,unit.origin.y/1000+unit.body.max_y/1000+12)+8
        svg.set("viewBox",f"{x0} {y0} {x1-x0} {y1-y0}")
        svg.set("width",f"{x1-x0}mm")
        svg.set("height",f"{y1-y0}mm")
        svg.set("data-composition","native-sheet-svg-plus-native-PAINT")
        svg.set("data-approval-status","DRAFT_INCOMPLETE_CONTROLLER")
        svg.insert(0,ET.Element(TAG+"title"))
        svg[0].text="Native catalogue / real PAINT TL494CN unified sheet DRAFT"
        result=ET.tostring(svg,encoding="unicode")+"\n"
        ET.fromstring(result)
        name=f"TL494_connected_{'diagnostic' if diagnostic else 'clean'}.svg"
        (output/name).write_text(result,encoding="utf-8")
        variants[name]={
            "native_layout_valid":sheet.layout.valid,
            "wire_count":len(graph.segments),
            "full_circuit_components":len(circuit.components),
            "physical_tl494_ports":len(ic.pin_anchors),
            "source_ic": "PAINT PR#93 real renderer",
        }
    report={
        "status":"DRAFT_REAL_INTEGRATED_ENGINE_PARTIAL",
        "not_full_e3":True,
        "source":"native Circuit/PinRef + catalogue UGO + real PAINT IC drawing",
        "component_count":len(circuit.components),
        "TL494_connected_pin_numbers":["1","7","9","10","16"],
        "TL494_unconnected_physical_pins":sorted(
            set(str(i) for i in range(1,17)) - {"1","7","9","10","16"},key=int,
        ),
        "segment_count":len(graph.segments),
        "font_sha256":style.font_sha256,
        "font_family":font.reported_face[0],
        "wire_diagnostics":[{"code":d.code,"severity":d.severity.value,
                             "message":d.message} for d in electrical],
        "erc_diagnostics":[{"code":d.code,"severity":d.severity.value,
                            "message":d.message} for d in erc],
        "variants":variants,
        "next_requirement":"Integrate 10 remaining control elements and source a/b continuations",
    }
    (output/"TL494_connected_manifest.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "count":len(circuit.components),
        "pin_count":len(ic.pin_anchors),
        "wires":len(graph.segments),
        "wire_errors":sum(d.severity.value=="error" for d in electrical),
        "erc_errors":sum(d.severity.value=="error" for d in erc),
        "layout":variants["TL494_connected_clean.svg"]["native_layout_valid"],
    }))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--font-file",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    generate(a.output,a.font_file)

if __name__=="__main__":
    main()
