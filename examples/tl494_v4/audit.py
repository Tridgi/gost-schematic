"""TL494 v4 phase-one source/UGO/IC/geometry audit, NO drawing export.

The first gate tests the actual 23/15 baseline. Deliberately does not
overwrite or post-process SVG/PNG before geometric DRC is introduced.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.tl494_named_photo_sheet import compose_circuit as compose_original
from examples.tl494_v4.engine_adapter import (
    attach_catalog_ic_v4, build_power_v4,
)
from examples.tl494_v4.model_contract import frozen_inventory
from examples.tl494_v4.wire_drc import analyze_wire_graph
from gost_schematic.model.pins import ElectricalType


def _write(path:Path, data:dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(
        json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf-8",
    )


def run(font_file:Path,output:Path) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    inventory=frozen_inventory()
    _write(output/"source_inventory.json",inventory)

    circuit,graph,parts,symbols,pose,unit,targets,*rest=compose_original(font_file)
    physical={(p.reference,p.number) for n in circuit.nets for p in n.members}
    expected={(ref,num) for pins in inventory["source_nets"].values()
              for item in pins for ref,num in [item.split(".",1)]}
    if physical!=expected or len(circuit.components)!=23 or len(circuit.nets)!=15:
        raise AssertionError("P0: baseline Net or PinRef inventory changed")
    report=analyze_wire_graph(graph)
    _write(output/"baseline_geometric_drc.json",report)
    power,source_parts,source_symbols,positions=build_power_v4()
    if source_symbols["transistor.mosfet_n_enh"].identifier!=(
        "transistor.mosfet_n_enh"
    ):
        raise AssertionError("P1: not catalog MOSFET")
    upgraded,targets_v4,part_v4,sym_v4,instance,*tail=attach_catalog_ic_v4(font_file)
    if upgraded.function_rotation!=270:
        raise AssertionError("P3: PWM is not bottom-to-top")
    if {p.number for p in part_v4.pins}!=set(inventory["pin_display_aliases"]):
        raise AssertionError("P2: manufacturer physical pin loss")
    if next(x for x in part_v4.pins if x.number=="3").electrical_type is not ElectricalType.INPUT:
        raise AssertionError("P2: FEEDBACK pin must be INPUT")
    aliases={p.number:p.label for p in upgraded.pins}
    if aliases!=inventory["pin_display_aliases"]:
        raise AssertionError("P2: display aliases not source-pinned")
    if tuple((p.pin_id,p.anchor) for p in upgraded.pins)!=(
        tuple((p.pin_id,p.anchor) for p in unit.pins)
    ):
        raise AssertionError("P3: port moved with PWM text")
    real_terms={p.number:p.name for p in part_v4.pins}
    if real_terms!=inventory["pin_manufacturer_functions"]:
        raise AssertionError("P2: manufacturer metadata was truncated")
    output_size=None
    baseline_path=Path("examples/tl494_named_truth_output/TL494_named_photo_clean.svg")
    if baseline_path.exists():
        doc=ET.parse(baseline_path).getroot()
        values=[float(x) for x in doc.get("viewBox").split()]
        output_size={
            "width_mm":values[2],
            "height_mm":values[3],
            "stroke_px_at_640px":round(0.3*640/values[2],4),
            "A3_landscape_width_mm":420.0,
            "fits_A3_landscape_unscaled":values[2]<=420,
        }
    _write(output/"ic_model_gate.json",{
        "status":"PASS_TYPED_SOURCE_MODEL_ONLY",
        "pin_3":"INPUT",
        "physical_pin_count":16,
        "full_manufacturer_names":real_terms,
        "display_aliases":aliases,
        "PWM_reading":"bottom_to_top",
        "PWM_function_rotation_degrees":270,
        "lead_coordinates_unchanged":True,
        "catalog_mosfet_modified":False,
        "true_catalog_core_UGO":True,
        "source_sheet":output_size,
        "warning":"Geometry from PAINT 270 is experimental pending #110 owner acceptance",
    })
    blockers={
        "status":"BLOCKED_PRINT_EXPORT",
        "issues":{
            "107":"Symbol normative review and print-scale image parity pending",
            "108":"True geometry-aware global router and complete wire-vs-UGO/text DRC absent",
            "109":"Normative COMMON/PE/chassis typed view marker not yet present in integration",
            "110":"270 function direction requires isolated PAINT patch, not in integration",
        },
        "raw_wire_drc":{
            "parallel_violations":report["parallel_violation_count"],
            "unmarked_crossings":report["distinct_net_x_crossings"],
        },
        "do_not_claim":"No SVG/PNG v4 until full source/UGO/DRC gates pass",
    }
    _write(output/"blockers.json",blockers)
    print(json.dumps({
        "baseline_components":23,
        "baseline_nets":15,
        "baseline_segments":len(graph.segments),
        "baseline_crossings":report["distinct_net_x_crossings"],
        "baseline_parallel_failures":report["parallel_violation_count"],
        "PWM_physical_anchors":16,
        "model_gate":"PASSED",
        "print_gate":"BLOCKED",
    },ensure_ascii=False))
    return blockers


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--font-file",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    run(args.font_file,args.output)
