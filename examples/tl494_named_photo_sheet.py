"""23-element photo-traced TL494CN: native types + PAINT, full authored wires.

Research DRAFT. Electrical behavior / normative approval NOT claimed.
Follows actual source 640x290; copies NO hand-drawn UGO artwork.
Core 13 come from proven native stage; 10 source control parts joined here.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_connected_native import attach_catalog_ic, S, P, TAG
from examples.tl494_native_rework import build as build_power, source_graph
from examples.tl494_full_native_model import TRACED_NETS
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.netrefs import (
    ContinuationAddressBinding, ContinuationAddressKind, ContinuationDirection,
    ContinuationPair, ContinuationScope, ContinuationSheet, ContinuationStub,
    NetContinuationEndpoint, NetContinuationProject, NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.ic_rectangular import render_resolved_ic
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph, WireSegment, validate_external_wires,
)


def M(x: float, y: float) -> Point:
    """Typed 1 micron integer coordinates, including quarter-mm IC rows."""
    return Point(round(x * 1000), round(y * 1000))


def full_components(power_components, ic_instance):
    """New positions are editorial; PartDefinitions are the installed catalogue."""
    def part(ref, part_id, x, y, value, unit, rot=0):
        return ComponentInstance(
            ref, part_id, M(x, y), Transform(rotation=rot),
            Quantity.from_unit(value, unit),
        )
    added = (
        part("R8", "resistor.fixed", 150, 183, "10", Unit.OHM, 90),
        part("C3", "capacitor.polarized", -135, 105, "47", Unit.MICROFARAD, 90),
        part("R1", "resistor.fixed", -95, 105, "1", Unit.OHM, 90),
        part("R2", "resistor.fixed", -55, 105, "620", Unit.OHM, 90),
        part("R3", "resistor.fixed", -85, 141, "10", Unit.KOHM, 0),
        part("R4", "resistor.fixed", -135, 161, "6.8", Unit.KOHM, 90),
        part("R5", "resistor.variable", -135, 193, "1", Unit.KOHM, 90),
        part("R6", "resistor.fixed", -85, 183, "1", Unit.OHM, 90),
        part("R7", "resistor.fixed", 0, 183, "680", Unit.KOHM, 90),
        part("C4", "capacitor.fixed", -118, 141, "10", Unit.NANOFARAD, 0),
        part("C7", "capacitor.fixed", -40, 183, "1", Unit.NANOFARAD, 90),
    )
    result=tuple(power_components)+(ic_instance,)+added
    if len(result)!=23 or len({c.reference for c in result})!=23:
        raise AssertionError("Photo BOM must contain 23 distinct positions")
    return result


def photo_nets():
    """Physically typed nets from source-photo binding, not arbitrary SVG paths."""
    rename={
        "a_INPUT_PLUS":"INPUT_POS",
        "b_NEGATIVE_OUTPUT":"OUTPUT_NEG",
        "TRANSFER":"ENERGY_TRANSFER",
    }
    result=tuple(Net(rename.get(name,name),tuple(
        PinRef(ref,num) for ref,num in members
    )) for name,members in TRACED_NETS.items())
    if len(result)!=15:
        raise AssertionError("Source photo full network count changed")
    return result


def on_segment(wire:WireSegment, p:Point)->bool:
    a,b=wire.start,wire.end
    return ((b.x-a.x)*(p.y-a.y)==(b.y-a.y)*(p.x-a.x)
            and min(a.x,b.x)<=p.x<=max(a.x,b.x)
            and min(a.y,b.y)<=p.y<=max(a.y,b.y))


def explicit_same_net_junctions(wires:tuple[WireSegment,...], base=()):
    """Mark only authored, same-net T contacts. X crossings never infer a Net.

    Endpoints are known from physically typed PinRef route graph. We do not
    use geometry to create semantic Net membership.
    """
    explicit=set(base)
    candidates={p for w in wires for p in (w.start,w.end)}
    for p in candidates:
        hits=[w for w in wires if on_segment(w,p)]
        nets={w.net_name for w in hits}
        if len(hits)>1 and len(nets)==1:
            if (len(hits)>2 or
                any(p not in (w.start,w.end) for w in hits)):
                explicit.add(p)
    return tuple(sorted(explicit,key=lambda p:(p.x,p.y)))


def compose_circuit(font_file:Path):
    power,parts,symbols,_=build_power()
    unit,targets,ic_part,ic_symbol,ic_instance,style,measure,policy,font=(
        attach_catalog_ic(font_file)
    )
    # The source photo places PWM vertically within its own central field.
    # PAINT has already reserved both angles; no physical anchor can move.
    unit=replace(unit,function_rotation=90)
    parts[ic_part.identifier]=ic_part
    symbols[ic_symbol.identifier]=ic_symbol
    components=full_components(power.components,ic_instance)
    circuit=Circuit(components,photo_nets())
    pose={}
    for comp in components:
        part=parts[comp.part_id]
        symbol=symbols[part.symbol_id]
        if {p.number for p in part.pins}!={p.number for p in symbol.pins}:
            raise AssertionError(f"{comp.reference}: model/graphic pin mismatch")
        pose[comp.reference]=comp.pin_positions(symbol)

    def pin(ref,num):
        return pose[ref][str(num)]
    wires=list(source_graph().segments)
    base_junctions=source_graph().junctions

    def route(net,*points):
        for a,b in zip(points,points[1:]):
            wires.append(S(net,a,b))
    def q(x,y):return M(x,y)

    # Existing 13-piece unit: faithfully connect physical Gate and a.
    common_x=42000
    return_y=220000
    grounds=[pin("DA1",n) for n in ("7","1","16")]
    for p in grounds:
        route("COMMON",p,Point(common_x,p.y))
    route("COMMON",Point(common_x,min(p.y for p in grounds)),Point(common_x,return_y))
    route("COMMON",pin("R8","2"),Point(pin("R8","2").x,return_y))

    e1,e2,g=pin("DA1","9"),pin("DA1","10"),pin("VT1","1")
    r8a=pin("R8","1")
    gx=r8a.x
    route("GATE_DRIVE",e1,Point(gx,e1.y))
    route("GATE_DRIVE",e2,Point(gx,e2.y))
    route("GATE_DRIVE",g,Point(gx,g.y),r8a)

    a12,a8,a11=(pin("DA1",n) for n in ("12","8","11"))
    ax=M(145,0).x
    route("INPUT_POS",q(50,45),q(50,75),q(145,75),Point(ax,a11.y))
    for p in (a12,a8,a11):
        route("INPUT_POS",p,Point(ax,p.y))

    # Reference rail from DA1.14 and DA1.15 to C3/R1/R2.
    a14,a15=pin("DA1","14"),pin("DA1","15")
    route("CONTROL_REFERENCE",q(-135,86),q(140,86),Point(140000,a14.y))
    route("CONTROL_REFERENCE",a14,Point(140000,a14.y))
    route("CONTROL_REFERENCE",a15,Point(140000,a15.y))
    for ref in ("C3","R1","R2"):
        p=pin(ref,"1")
        route("CONTROL_REFERENCE",p,Point(p.x,M(0,86).y))

    # Soft start: C3 minus / R1 bottom / R6 top / DA1.4.
    d4=pin("DA1","4")
    route("SOFT_START",pin("C3","2"),q(-135,117),q(51,117))
    route("SOFT_START",pin("R1","2"),q(-95,117))
    route("SOFT_START",pin("R6","1"),q(-105,175),q(-105,117))
    route("SOFT_START",d4,Point(51000,d4.y),q(51,117))

    # First error amplifier: R2 bottom / C4 left / R4 top / DA1.2.
    d2=pin("DA1","2")
    route("ERROR_INPUT",q(-135,125),q(45,125),Point(45000,d2.y),d2)
    for ref,num in (("R2","2"),("R4","1"),("C4","1")):
        p=pin(ref,num)
        route("ERROR_INPUT",p,Point(p.x,M(0,125).y))

    # RC compensation, feedback, divider and variable resistor wiper strap.
    route("RC_CORRECTION",pin("C4","2"),pin("R3","1"))
    d3=pin("DA1","3")
    route("FEEDBACK",pin("R3","2"),q(53,141),Point(53000,d3.y),d3)
    route("ADJUSTED_DIVIDER",pin("R4","2"),pin("R5","1"))
    route("ADJUSTED_DIVIDER",pin("R5","1"),q(-135,176),
          q(-105,176),q(-105,193),pin("R5","3"))

    # Two independent timing networks, one end grounded.
    d5=pin("DA1","5")
    route("OSCILLATOR_CT",pin("C7","1"),q(-40,149),q(46,149),
          Point(46000,d5.y),d5)
    d6=pin("DA1","6")
    route("OSCILLATOR_RT",pin("R7","1"),q(0,169),q(-5,169),q(-5,55),
          q(59,55),Point(59000,d6.y),d6)

    # Common return: R6, C7, R7, and source control pin13.
    route("COMMON",q(-85,220),q(30,220))
    for ref in ("R6","C7","R7"):
        route("COMMON",pin(ref,"2"),Point(pin(ref,"2").x,return_y))
    d13=pin("DA1","13")
    route("COMMON",d13,Point(138000,d13.y),q(138,82),
          q(-185,82),q(-185,212),q(-85,212),q(-85,220))

    # Source label b: physical output-negative continuation to R5 lower
    # contact. For now this is a long board-level DRAFT jumper; validated
    # as electrical connectivity, NOT claimed to be the source's wire shape.
    # Source b is a local named continuation, NOT a 700 mm conductor.
    route("OUTPUT_NEG",pin("R5","2"),q(-135,214))

    graph=ExternalWireGraph(
        tuple(wires),
        explicit_same_net_junctions(tuple(wires),base_junctions),
    )
    b=next(net for net in circuit.nets if net.name=="OUTPUT_NEG")
    source=NetContinuationEndpoint(
        "b-X2", "N-b", "S1", 1, "X2.1", "R5.2",
        q(445,45), "b", ContinuationDirection.SOURCE,
    )
    target=NetContinuationEndpoint(
        "b-R5", "N-b", "S1", 1, "R5.2", "X2.1",
        q(-135,214), "b", ContinuationDirection.TARGET,
    )
    pair=NetContinuationProject(
        circuit,
        (NetIdentity("N-b", b.name, b.members),),
        (ContinuationSheet("S1",1),),
        (source,target),
        (ContinuationPair("PAIR-b","b-X2","b-R5",ContinuationScope.SHEET_LOCAL),),
        (
            ContinuationStub("WIRE-X2-b","b-X2",PinRef("X2","1"),
                             pin("X2","1"),source.anchor),
            ContinuationStub("WIRE-R5-b","b-R5",PinRef("R5","2"),
                             pin("R5","2"),target.anchor),
        ),
        schema_version=2,
        address_bindings=(
            ContinuationAddressBinding(
                source.id,ContinuationAddressKind.ELEMENT_PIN,
                "X2",PinRef("X2","1"),
            ),
            ContinuationAddressBinding(
                target.id,ContinuationAddressKind.ELEMENT_PIN,
                "R5",PinRef("R5","2"),
            ),
        ),
    )
    provenance=validate_net_continuations(
        pair,physical_pin_anchors={
            PinRef("X2","1"):pin("X2","1"),
            PinRef("R5","2"):pin("R5","2"),
        },
    )
    if provenance:
        raise AssertionError(
            "SOURCE b continuation rejected: "+
            ";".join(x.code for x in provenance)
        )
    return circuit,graph,parts,symbols,pose,unit,targets,style,measure,policy,font,pair


def generate(output:Path,font_file:Path,*,strict:bool=False):
    circuit,graph,parts,symbols,pose,unit,targets,style,measure,policy,font,b_pair=(
        compose_circuit(font_file)
    )
    electrical=validate_external_wires(circuit,graph,parts,symbols)
    erc=validate_circuit(circuit,parts,symbols)
    # Raw ExternalWireGraph is intentionally unaware of typed E3 named
    # continuations; accept only the documented b split and its end marker,
    # after independent NetContinuationProject validation above.
    expected={
        ("WIRE_NET_DISCONNECTED","OUTPUT_NEG"),
        ("WIRE_DANGLING_END","-135000,214000"),
    }
    def justified_continuation(d):
        if d.code=="WIRE_NET_DISCONNECTED":
            return (d.code,d.subject) in expected
        return (d.code=="WIRE_DANGLING_END"
                and "-135000,214000" in d.message)
    errors=[d for d in electrical
            if d.severity.value=="error" and not justified_continuation(d)]
    errors+=[d for d in erc if d.severity.value=="error"]
    output.mkdir(parents=True,exist_ok=True)
    report={
        "status":"DRAFT_FULL_PHOTO_RECONSTRUCTION_NOT_APPROVED",
        "photo_component_count":len(circuit.components),
        "photo_net_count":len(circuit.nets),
        "wire_count":len(graph.segments),
        "junctions_um":[[p.x,p.y] for p in graph.junctions],
        "font_name":font.reported_face[0],
        "font_sha256":style.font_sha256,
        "TL494_connected_physical_pins":sorted(
            [p.number for n in circuit.nets for p in n.members if p.reference=="DA1"],
            key=int,
        ),
        "source_a":["X1.1","DA1.12","DA1.8","DA1.11"],
        "pwm_function_rotation_degrees":90,
        "source_b":["FU1.2","X2.1","R5.2"],
        "wire_diagnostics":[{"code":d.code,"severity":d.severity.value,
                             "message":d.message} for d in electrical],
        "erc_diagnostics":[{"code":d.code,"severity":d.severity.value,
                            "message":d.message} for d in erc],
        "not_approved":True,
        "not_electrically_verified":True,
        "source_photo_crossovers_are_NOT_solder_junctions":True,
        "b_wire_continuation":"real NetContinuationProject v2, same-sheet b pair",
        "continuation_valid":True,
        "expected_raw_wire_diagnostics":[
            {"code":d.code,"message":d.message}
            for d in electrical
            if d.severity.value=="error" and justified_continuation(d)
        ],
        "unexpected_wire_errors":[{"code":d.code,"message":d.message} for d in errors],
        "long_b_jumper_not_photo_ink":False,
        "variants":{},
    }
    if len(report["TL494_connected_physical_pins"])!=16:
        raise AssertionError("Missing or duplicated TL494 physical contact")
    bypart={pid:symbols[p.symbol_id] for pid,p in parts.items()}
    for diagnostic in (False,True):
        sheet=render_external_wire_sheet(
            circuit,graph,bypart,style,measure,
            diagnostic=diagnostic,strict_layout=False,
        )
        report["variants"]["diagnostic" if diagnostic else "clean"]={
            "layout_valid":sheet.layout.valid,
            "layout_diagnostics":[
                {"code":d.code,"severity":d.severity.value,
                 "message":d.message} for d in sheet.layout.diagnostics
            ],
        }
        if strict and (errors or not sheet.layout.valid):
            continue
        ic=render_resolved_ic(
            unit,style,measure,policy=policy,
            editor_targets=targets,editor_overlay=diagnostic,
        )
        if len(ic.pin_anchors)!=16:
            raise AssertionError("Physical IC endpoints lost")
        source=ET.fromstring(sheet.svg)
        ghost=source.find(f"./{TAG}g[@data-reference='DA1']")
        if ghost is None:
            raise AssertionError("Native sheet IC placeholder not found")
        source.remove(ghost)
        group=ET.SubElement(source,TAG+"g",{
            "data-owner":"DA1",
            "data-ink-source":"actual-PAINT-PR93",
            "data-physical-pin-count":"16",
        })
        xml=ET.fromstring(ic.svg)
        for element in list(xml):
            if element.tag==TAG+"title":continue
            group.append(element)
        # Visual review marks are OWNED by validated typed #90 continuations.
        # These nonphysical SVG marks never alter native Circuit.Net membership.
        for marker in b_pair.endpoints:
            xx=marker.anchor.x/1000
            yy=marker.anchor.y/1000
            ET.SubElement(source,TAG+"circle",{
                "cx":str(xx),"cy":str(yy),"r":"0.65","fill":"#fff",
                "stroke":"#000","stroke-width":"0.3",
                "data-nonphysical-net-continuation":marker.id,
            })
            mark=ET.SubElement(source,TAG+"text",{
                "x":str(xx),"y":str(yy-4),
                "font-family":style.font_family,
                "font-size":str(style.em_height_um/1000),
                "text-anchor":"middle","fill":"#000","stroke":"none",
                "data-source":"typed-net-continuation-v2",
            })
            mark.text=marker.label
        x,y,w,h=map(float,source.attrib["viewBox"].split())
        # Source control devices extend to x=-185; preserve generous margins.
        x0=min(x,unit.origin.x/1000-16)-6
        y0=min(y,unit.origin.y/1000-16)-6
        x1=max(x+w,unit.origin.x/1000+unit.body.max_x/1000+17)+6
        y1=max(y+h,unit.origin.y/1000+unit.body.max_y/1000+15)+6
        source.attrib.update({
            "width":f"{x1-x0}mm","height":f"{y1-y0}mm",
            "viewBox":f"{x0} {y0} {x1-x0} {y1-y0}",
            "data-photo-source":"640x290 user image",
            "data-status":"DRAFT",
        })
        name=f"TL494_named_photo_{'diagnostic' if diagnostic else 'clean'}.svg"
        (output/name).write_text(
            ET.tostring(source,encoding="unicode")+"\n",encoding="utf-8"
        )
    (output/"TL494_named_photo_manifest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    summary={
        "components":len(circuit.components),
        "nets":len(circuit.nets),
        "wires":len(graph.segments),
        "connected_DA1_pins":len(report["TL494_connected_physical_pins"]),
        "unexpected_wire_errors":sum(
            d.severity.value=="error" and not justified_continuation(d)
            for d in electrical
        ),
        "justified_b_continuation_diagnostics":sum(
            d.severity.value=="error" and justified_continuation(d)
            for d in electrical
        ),
        "erc_errors":sum(d.severity.value=="error" for d in erc),
        "layout_valid":report["variants"].get("clean",{}).get("layout_valid"),
    }
    print(json.dumps(summary,ensure_ascii=False))
    if strict and (errors or not report["variants"]["clean"]["layout_valid"]):
        raise AssertionError(
            "Fail-closed DRAFT full sheet: "
            + "; ".join(d.code+":"+d.message for d in errors)
        )
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--font-file",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--strict",action="store_true")
    args=parser.parse_args()
    generate(args.output,args.font_file,strict=args.strict)
