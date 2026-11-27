"""Generate editor winding definitions from the actual Python catalog.

No hand-transcribed coil shapes. Output is a build input, not a second catalog.
Required constant annotations are preserved with their first source anchor.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.core.geometry import Circle, Line, Rectangle, Semicircle, Side, StyledLine

SOURCE = ROOT / "src" / "gost_schematic" / "catalog" / "inductors"
TARGET = ROOT / "ui" / "editor" / "src" / "authoring" / "windings.generated.json"

NAMES = {
    "choke.air_core": "Дроссель без магнитопровода",
    "choke.ferrite": "Дроссель с ферритовым магнитопроводом",
    "choke.ferromagnetic": "Дроссель с ферромагнитным магнитопроводом",
    "inductor.air_core": "Катушка без магнитопровода",
    "inductor.double_sliding": "Катушка с двумя скользящими контактами",
    "inductor.double_tapped": "Катушка с двумя отводами",
    "inductor.ferrite": "Катушка с ферритовым магнитопроводом",
    "inductor.ferromagnetic": "Катушка с ферромагнитным магнитопроводом",
    "inductor.gapped_core": "Катушка с зазором в магнитопроводе",
    "inductor.magnetodielectric": "Катушка с магнитодиэлектрическим магнитопроводом",
    "inductor.sliding_contact": "Катушка со скользящим контактом",
    "inductor.tapped": "Катушка с отводом",
    "inductor.trim_copper": "Катушка подстроечная с медным сердечником",
    "inductor.trim_magnetodielectric": "Катушка подстроечная магнитодиэлектрическая",
    "inductor.variable": "Катушка переменной индуктивности",
}


def point(p):
    return [p.x, p.y]


def primitive(shape, width):
    def item(kind, points, stroke=width):
        return {"kind": kind, "points_um": points, "stroke_um": stroke}

    if isinstance(shape, Semicircle):
        x, y, r = shape.center.x, shape.center.y, shape.radius
        if shape.bulge == Side.TOP:
            points = [[x-r, y], [x, y-r], [x+r, y]]
        elif shape.bulge == Side.BOTTOM:
            points = [[x-r, y], [x, y+r], [x+r, y]]
        elif shape.bulge == Side.LEFT:
            points = [[x, y-r], [x-r, y], [x, y+r]]
        else:
            points = [[x, y-r], [x+r, y], [x, y+r]]
        return [item("semicircle", points)]
    if isinstance(shape, Circle):
        x, y = shape.center.x, shape.center.y
        return [item("circle", [[x,y],[x+shape.radius,y]])]
    if isinstance(shape, Rectangle):
        b = shape.box
        return [item("rect", [[b.min_x,b.min_y],[b.max_x,b.max_y]])]
    if isinstance(shape, StyledLine):
        a,b = point(shape.start),point(shape.end)
        if not shape.dash_pattern_um:
            return [item("line",[a,b],shape.stroke_width_um)]
        # Python SVG dash semantics: butt-ended dash/gap from the start.
        # Existing source uses horizontal lines; reject unexpected diagonal dashes.
        dx,dy = b[0]-a[0],b[1]-a[1]
        if dx and dy:
            raise ValueError("Unsupported diagonal dashed core")
        length = abs(dx)+abs(dy)
        vx,vy = (dx>0)-(dx<0),(dy>0)-(dy<0)
        position,index,segments = 0,0,[]
        pattern = shape.dash_pattern_um
        while position < length:
            end = min(length,position+pattern[index % len(pattern)])
            if index % 2 == 0:
                segments.append(item("line",[
                    [a[0]+vx*position,a[1]+vy*position],
                    [a[0]+vx*end,a[1]+vy*end]],shape.stroke_width_um))
            position,index = end,index+1
        return segments
    if isinstance(shape, Line):
        return [item("line",[point(shape.start),point(shape.end)])]
    raise TypeError(type(shape).__name__)


def generate():
    entries = []
    for filename in sorted(SOURCE.glob("*.json")):
        definition = load_inductor(filename)
        s,p = definition.symbol,definition.part
        if s.identifier not in NAMES:
            raise ValueError("Unclassified winding: "+s.identifier)
        symbol_id = "symbol/"+s.identifier
        annotations = []
        for key, text in s.constant_annotations:
            slot = next(slot for slot in s.annotation_slots if slot.key == key)
            anchor = slot.candidates[0]
            annotations.append({"key":key,"text":text,"at_um":point(anchor.at),
                                "height_um":3500,"horizontal":anchor.horizontal.value,
                                "vertical":anchor.vertical.value})
        entries.append({
            "part": {"id":p.identifier,"reference_prefix":p.reference_prefix,
                     "symbol_ids":[symbol_id],"physical_pins":[
                         {"number":pin.number,"name":pin.name,"electrical_type":pin.electrical_type.value}
                         for pin in p.pins]},
            "symbol": {"id":symbol_id,"part_id":p.identifier,"revision":s.revision,
                       "status":s.status.value,"standard_refs":list(s.standard_refs),
                       "pins":[{"physical_pin_number":pin.number,"at_um":point(pin.at),"side":pin.side.value}
                               for pin in s.pins],
                       "graphics":[g for shape in s.graphics for g in primitive(shape,s.line_width_um)],
                       **({"constant_annotations":annotations} if annotations else {})},
            "name":NAMES[s.identifier],
            "category":"Дроссели" if s.identifier.startswith("choke.") else "Катушки индуктивности",
        })
    if len(entries)!=len(NAMES):
        raise ValueError(f"Unexpected winding inventory: {len(entries)}")
    return entries


if __name__ == "__main__":
    data = generate()
    TARGET.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Generated {len(data)} exact winding symbols and required constant annotations.")
