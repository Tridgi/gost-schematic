"""Exact-µm model-layer geometry DRC for authored TL494 E3 wires, Issue #108.

This is *not* a router and never changes circuit Nets or SVG ink. Does not
silently equate an X crossing with a conductive contact. Fail-closed evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from gost_schematic.core.geometry import Point
from gost_schematic.validation.external_wire_checks import WireSegment, ExternalWireGraph


@dataclass(frozen=True)
class ClearanceViolation:
    code: str
    wire_a: int
    wire_b: int
    net_a: str
    net_b: str
    clearance_um: int
    required_um: int
    location_um: tuple[int,int] | None = None

    def to_dict(self) -> dict:
        return {
            "code":self.code, "a":self.wire_a, "b":self.wire_b,
            "nets":[self.net_a,self.net_b],
            "clearance_mm":round(self.clearance_um/1000,6),
            "required_mm":round(self.required_um/1000,6),
            "location_mm":(
                [round(v/1000,6) for v in self.location_um]
                if self.location_um is not None else None
            ),
        }


def axis(wire:WireSegment) -> str:
    if wire.start.y==wire.end.y:
        return "H"
    if wire.start.x==wire.end.x:
        return "V"
    return "OTHER"


def _span(w:WireSegment,coord:str)->tuple[int,int]:
    a=getattr(w.start,coord)
    b=getattr(w.end,coord)
    return (min(a,b),max(a,b))


def pair_clearance(
    a:WireSegment,b:WireSegment,*,stroke_um:int=300,
) -> int | None:
    """True edge-to-edge clearance, only for overlapping parallel segments.

    None means not parallel or longitudinal spans do not overlap positively.
    Measured from both stroked line edges (stroke_um/2 on each side).
    """
    if stroke_um<=0:
        raise ValueError("P7: nonpositive stroke")
    direction=axis(a)
    if direction=="OTHER" or axis(b)!=direction:
        return None
    normal,along=("y","x") if direction=="H" else ("x","y")
    ax1,ax2=_span(a,along)
    bx1,bx2=_span(b,along)
    if min(ax2,bx2)<=max(ax1,bx1):
        return None
    return abs(getattr(a.start,normal)-getattr(b.start,normal))-stroke_um


def right_angle_crossing(a:WireSegment,b:WireSegment)->tuple[int,int] | None:
    """Unmarked X: report geometry only; never infer electrical continuity."""
    da,db=axis(a),axis(b)
    if {da,db}!={"H","V"}:
        return None
    h=a if da=="H" else b
    v=a if da=="V" else b
    x=v.start.x
    y=h.start.y
    if _span(h,"x")[0]<x<_span(h,"x")[1] and _span(v,"y")[0]<y<_span(v,"y")[1]:
        return x,y
    return None


def analyze_wire_graph(
    graph:ExternalWireGraph,*,stroke_um:int=300,required_parallel_um:int=3000,
)->dict:
    if required_parallel_um<0 or stroke_um<=0:
        raise ValueError("P7: invalid geometry tolerances")
    violations=[]
    crossings=[]
    count_by_net={}
    total_um=0
    for wire in graph.segments:
        if axis(wire)=="OTHER":
            raise ValueError(f"P7: diagonal segment in {wire.net_name}")
        count_by_net[wire.net_name]=count_by_net.get(wire.net_name,0)+1
        total_um+=abs(wire.end.x-wire.start.x)+abs(wire.end.y-wire.start.y)
    for (i,a),(j,b) in combinations(enumerate(graph.segments),2):
        if a.net_name==b.net_name:
            continue
        clearance=pair_clearance(a,b,stroke_um=stroke_um)
        if clearance is not None and clearance<required_parallel_um:
            violations.append(ClearanceViolation(
                "WIRE_PARALLEL_CLEARANCE",i,j,a.net_name,b.net_name,
                clearance,required_parallel_um,
            ))
        p=right_angle_crossing(a,b)
        if p is not None:
            if Point(*p) not in graph.junctions:
                crossings.append({
                    "a":i,"b":j,"nets":[a.net_name,b.net_name],
                    "at_mm":[round(v/1000,3) for v in p],
                    "classification":"UNMARKED_DISTINCT_NET_X",
                })
            else:
                violations.append(ClearanceViolation(
                    "UNAUTHORIZED_CROSS_NET_JUNCTION",i,j,
                    a.net_name,b.net_name,0,required_parallel_um,p,
                ))
    endpoints={}
    for w in graph.segments:
        for p in (w.start,w.end):
            endpoints.setdefault(w.net_name,set()).add((p.x,p.y))
    bends=0
    for net,points in endpoints.items():
        for px,py in points:
            orientations={
                axis(w) for w in graph.segments
                if w.net_name==net and (px,py) in (
                    (w.start.x,w.start.y),(w.end.x,w.end.y)
                )
            }
            if orientations=={"H","V"}:
                bends+=1
    return {
        "status":"FAIL" if violations or crossings else "PASS_PRELIMINARY",
        "wire_count":len(graph.segments),
        "distinct_nets_with_ink":len(count_by_net),
        "net_segments":count_by_net,
        "stroke_mm":stroke_um/1000,
        "required_parallel_edge_clearance_mm":required_parallel_um/1000,
        "total_wire_length_mm":round(total_um/1000,3),
        "estimated_orthogonal_bends":bends,
        "distinct_net_x_crossings":len(crossings),
        "crossings":crossings,
        "parallel_violation_count":sum(
            x.code=="WIRE_PARALLEL_CLEARANCE" for x in violations
        ),
        "violations":[x.to_dict() for x in violations],
        "limitations":[
            "P0: perpendicular crossing without junction is electrically separate, yet requires route/visual review",
            "P0: this module does not implement full symbol-stroke/text-ink clearance or automatic routing",
            "P0: an acceptable numeric parallel report alone cannot approve E3 or prove circuit functionality",
        ],
    }
