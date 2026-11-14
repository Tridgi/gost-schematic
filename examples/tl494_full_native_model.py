"""Typed 23-part TL494CN photo netlist, not a finished routed E3 drawing.

Uses the actual GOST Schematic Engine Circuit, Net, PinRef, ComponentInstance,
PartDefinition, SymbolDefinition, CatalogResolver and circuit validator.

Photo labels 'a' and 'b' are source-named continuation candidates; their
interpretation is recorded for engineering review. No "PASS" is assigned to
an unverified photo trace or to a manufacturer-unapproved symbol.
"""
from __future__ import annotations

import json
from pathlib import Path
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Point, Box, Rectangle, Line, Side
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import GraphicPin, PhysicalPin, ElectricalType
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.symbol_checks import validate_symbol
from examples.tl494_native_rework import contact_part

MANUFACTURER_PIN_MAP = {
    "1": ("1IN+", ElectricalType.INPUT),
    "2": ("1IN-", ElectricalType.INPUT),
    "3": ("FEEDBACK", ElectricalType.OUTPUT),
    "4": ("DTC", ElectricalType.INPUT),
    "5": ("CT", ElectricalType.UNSPECIFIED),
    "6": ("RT", ElectricalType.UNSPECIFIED),
    "7": ("GND", ElectricalType.POWER_INPUT),
    "8": ("C1", ElectricalType.OPEN_COLLECTOR),
    "9": ("E1", ElectricalType.OUTPUT),
    "10": ("E2", ElectricalType.OUTPUT),
    "11": ("C2", ElectricalType.OPEN_COLLECTOR),
    "12": ("VCC", ElectricalType.POWER_INPUT),
    "13": ("OUTPUT CTRL", ElectricalType.INPUT),
    "14": ("REF", ElectricalType.POWER_OUTPUT),
    "15": ("2IN-", ElectricalType.INPUT),
    "16": ("2IN+", ElectricalType.INPUT),
}
SOURCE_LEFT = ("2","4","3","5","6","7","1","16")
SOURCE_RIGHT = ("12","15","14","13","8","11","9","10")

SPEC = {
    **{f"C{x}": ("capacitor.electrolytic","220" if x in (1,2) else "47" if x==3 else "1000", Unit.MICROFARAD)
       for x in (1,2,3,5,6)},
    "C4":("capacitor.fixed","10",Unit.NANOFARAD),
    "C7":("capacitor.fixed","1",Unit.NANOFARAD),
    **{f"R{x}":("resistor.fixed",value,unit)
       for x,value,unit in (
          (1,"1",Unit.OHM),(2,"620",Unit.OHM),(3,"10",Unit.KOHM),
          (4,"6.8",Unit.KOHM),(6,"1",Unit.OHM),
          (7,"680",Unit.KOHM),(8,"10",Unit.OHM),
       )},
    "R5":("resistor.variable","1",Unit.KOHM),
    "VT1":("transistor.mosfet_n_enh",None,None),
    "VD1":("diode.schottky",None,None),
    "L1":("inductor.air_core","100",Unit.MICROHENRY),
    "L2":("inductor.air_core","100",Unit.MICROHENRY),
    "FU1":("fuse.general",None,None),
    "X1":("reference.connector.x1",None,None),
    "X2":("reference.connector.x2",None,None),
    "DA1":("reference.tl494cn",None,None),
}

# The ONLY source for circuit membership is a human reading of the 640px
# reference photo. Membership does not imply approved ERC operation.
TRACED_NETS = {
 "a_INPUT_PLUS":(("X1","1"),("L1","1"),("DA1","12"),("DA1","8"),("DA1","11")),
 "COMMON":(("X1","2"),("X2","2"),("VT1","3"),("VD1","1"),
           ("C5","1"),("C6","1"),("DA1","7"),("DA1","1"),("DA1","16"),
           ("DA1","13"),("R6","2"),("R7","2"),("R8","2"),("C7","2")),
 "SWITCH":(("L1","2"),("VT1","2"),("C1","1"),("C2","1")),
 "TRANSFER":(("C1","2"),("C2","2"),("VD1","2"),("L2","1")),
 "OUT_BEFORE_FUSE":(("L2","2"),("FU1","1"),("C5","2"),("C6","2")),
 "b_NEGATIVE_OUTPUT":(("FU1","2"),("X2","1"),("R5","2")),
 "CONTROL_REFERENCE":(("DA1","14"),("DA1","15"),("R1","1"),
                      ("R2","1"),("C3","1")),
 "SOFT_START":(("DA1","4"),("R1","2"),("C3","2"),("R6","1")),
 "ERROR_INPUT":(("DA1","2"),("R2","2"),("R4","1"),("C4","1")),
 "RC_CORRECTION":(("C4","2"),("R3","1")),
 "FEEDBACK":(("R3","2"),("DA1","3")),
 "ADJUSTED_DIVIDER":(("R4","2"),("R5","1"),("R5","3")),
 "OSCILLATOR_CT":(("C7","1"),("DA1","5")),
 "OSCILLATOR_RT":(("R7","1"),("DA1","6")),
 "GATE_DRIVE":(("DA1","9"),("DA1","10"),("R8","1"),("VT1","1")),
}

def physical_tl494():
    """Real numbering, with DRAFT graphical presentation, not an official UGO."""
    geometry=[Rectangle(Box(0,0,60000,92000))]
    graphic=[]
    for side,numbers in ((Side.LEFT,SOURCE_LEFT),(Side.RIGHT,SOURCE_RIGHT)):
        for row,number in enumerate(numbers):
            y=(row+1)*10000
            left,right=(-9000,0) if side is Side.LEFT else (60000,69000)
            geometry.append(Line(Point(left,y),Point(right,y)))
            graphic.append(GraphicPin(
                number,Point(left if side is Side.LEFT else right,y),
                side,MANUFACTURER_PIN_MAP[number][0],
            ))
    sym=SymbolDefinition(
        identifier="reference.tl494cn",revision=1,
        graphics=tuple(geometry),pins=tuple(graphic),
        body_keepout=Box(0,0,60000,92000),
        line_width_um=300,status=SymbolStatus.DRAFT,
        standard_refs=("Manufacturer TL494CN physical pinout verified",
                       "GRAPHIC_DRAFT: Use isolated PAINT PR#93 for actual IC presentation"),
    )
    part=PartDefinition(
        identifier="reference.tl494cn",
        reference_prefix="DA",symbol_id=sym.identifier,
        pins=tuple(
            PhysicalPin(number,name,elec)
            for number,(name,elec) in MANUFACTURER_PIN_MAP.items()
        ),
    )
    return part,sym

def build():
    resolver=CatalogResolver()
    parts=dict(resolver.parts)
    symbols=dict(resolver.symbols)
    for part,symbol in (contact_part(destination=False),
                        contact_part(destination=True),physical_tl494()):
        assert not any(e.severity.value=="error" for e in validate_symbol(symbol))
        parts[part.identifier]=part
        symbols[symbol.identifier]=symbol
    components=[]
    for index,(ref,(part_id,value,unit)) in enumerate(SPEC.items()):
        components.append(ComponentInstance(
            ref,part_id,Point((index%6)*80000,(index//6)*120000),
            nominal=Quantity.from_unit(value,unit) if value is not None else None,
        ))
    nets=tuple(
        Net(name,tuple(PinRef(ref,n) for ref,n in members))
        for name,members in TRACED_NETS.items()
    )
    circuit=Circuit(tuple(components),nets)
    names={component.reference for component in circuit.components}
    if len(names)!=23:raise AssertionError("Not all 23 source items modeled")
    seen={}
    for net in nets:
        for pin in net.members:
            if pin.reference not in names:
                raise AssertionError(f"Unknown element: {pin}")
            component=next(c for c in components if c.reference==pin.reference)
            part=parts[component.part_id]
            graphic=symbols[part.symbol_id]
            if {p.number for p in part.pins}!={p.number for p in graphic.pins}:
                raise AssertionError(f"Part/pin mismatch: {pin.reference}")
            if pin.number not in {p.number for p in part.pins}:
                raise AssertionError(f"Invalid physical pin: {pin}")
            if pin in seen:raise AssertionError(f"{pin} in both {seen[pin]} and {net.name}")
            seen[pin]=net.name
    return circuit,parts,symbols,seen

def write_report(directory:Path):
    circuit,parts,symbols,seen=build()
    diagnostics=validate_circuit(circuit,parts,symbols)
    out={
        "status":"PHOTO_TRACED_NATIVE_TYPED_MODEL_NOT_APPROVED",
        "full_component_count":len(circuit.components),
        "net_count":len(circuit.nets),
        "physical_pin_memberships":len(seen),
        "source_a_b_labels":"Interpreted a=input plus and b=negative output; confirm source semantics",
        "physical_type_numbering":"TI TL494CN, IRFZ44N G/D/S 1/2/3, 1N5822 A/K",
        "source_photo_origin":"uploaded original 640x290",
        "routed":False,
        "rendered_full_e3":False,
        "unverified_electrical_claims":(
            "Control reference and R5 jumper still need source enlargement",
            "R7=680kΩ and C7=1nF imply oscillator ≈1.47kHz by 1/(R*C), "
            "not ~100kHz listed in source BOM",
            "Schematics show a/b labels; not separately validated net continuation"
        ),
        "native_erc_diagnostics":[
            {"code":d.code,"severity":d.severity.value,"message":d.message}
            for d in diagnostics
        ],
        "elements":[
            {"ref":c.reference,"part_id":c.part_id,
             "nominal_si":str(c.nominal.si_value) if c.nominal is not None else None}
            for c in circuit.components
        ],
        "nets":{net.name:[f"{p.reference}.{p.number}" for p in net.members]
                for net in circuit.nets},
    }
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"TL494_full_typed_netlist.json").write_text(
        json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "real_components":len(circuit.components),
        "nets":len(circuit.nets),
        "duplicate_physical_pins":0,
        "erc_errors":sum(d.severity.value=="error" for d in diagnostics),
    },ensure_ascii=False))
    return out

if __name__=="__main__":
    write_report(Path("examples/tl494_model_output"))
