"""Bounded cycle-4 measurements of real-catalog wire validation and sheet SVG.

Run: python scripts/qa/benchmark_cycle4.py --sizes 10 50 200 500 --repeat 3
Results are observations, NOT CI performance SLA or claims of normative approval.
"""

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from functools import partial
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
    validate_external_wires,
)

_SVG = "{http://www.w3.org/2000/svg}"


def _source():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    part = load_part(root / "parts/resistors/fixed.json")
    symbol = load_symbol(root / "symbols/resistors/fixed.json")
    assert part.symbol_id == symbol.identifier
    return part, symbol


def _instance(ref, part, pin, target, rotation=0):
    tx = Transform(rotation)
    return ComponentInstance(ref, part.identifier, target - tx.apply(pin.at), tx)


def _wire_fixture(size, part, symbol):
    pin = next(item for item in symbol.pins if item.number == "1")
    step, y = 4000, -12_000
    end_x = step * (size - 2)
    first = _instance("R1", part, pin, Point(0, 0), 180)
    last = _instance("R2", part, pin, Point(end_x, 0))
    circuit = Circuit(
        (first, last),
        (Net("SIG", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    segments = [WireSegment(Point(0, 0), Point(0, y), "SIG")]
    segments.extend(
        WireSegment(Point(i * step, y), Point((i + 1) * step, y), "SIG")
        for i in range(size - 2)
    )
    segments.append(WireSegment(Point(end_x, y), Point(end_x, 0), "SIG"))
    assert len(segments) == size
    return circuit, ExternalWireGraph(tuple(segments))


def _sheet_fixture(size, part):
    circuit = Circuit(
        tuple(ComponentInstance(f"R{i + 1}", part.identifier, Point(i * 30_000, 0))
              for i in range(size)),
        (),
    )
    return circuit, SheetLayout((), ())


def _sample(operation, repeats):
    observations = []
    result = None
    for _ in range(repeats):
        gc.collect()
        tracemalloc.start()
        start = time.perf_counter_ns()
        try:
            result = operation()
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            peak_kib = tracemalloc.get_traced_memory()[1] / 1024
        finally:
            tracemalloc.stop()
        observations.append((elapsed_ms, peak_kib))
    return result, {
        "median_ms": round(statistics.median(value[0] for value in observations), 3),
        "min_ms": round(min(value[0] for value in observations), 3),
        "max_ms": round(max(value[0] for value in observations), 3),
        "max_tracemalloc_peak_kib": round(max(value[1] for value in observations), 1),
        "samples": len(observations),
    }


def benchmark(sizes=(10, 50, 200, 500), repeat=3):
    if type(repeat) is not int or not 1 <= repeat <= 5:
        raise ValueError("repeat must be an integer from 1 through 5")
    if not sizes or any(type(n) is not int or not 4 <= n <= 500 for n in sizes):
        raise ValueError("sizes must be bounded integer counts from 4 through 500")
    part, symbol = _source()
    records = []
    for size in sizes:
        wire_circuit, graph = _wire_fixture(size, part, symbol)
        sheet_circuit, sheet_layout = _sheet_fixture(size, part)
        parts = {part.identifier: part}
        symbols = {symbol.identifier: symbol}

        check_wire = partial(validate_external_wires, wire_circuit, graph, parts, symbols)
        check_svg = partial(render_sheet_svg, sheet_circuit, symbols, sheet_layout)

        diagnostics, wire_stats = _sample(check_wire, repeat)
        if diagnostics:
            raise AssertionError(f"Expected connected graph at size {size}: {diagnostics}")
        svg, svg_stats = _sample(check_svg, repeat)
        root = ET.fromstring(svg)
        if len(root.findall(f".//{_SVG}g[@data-layer='symbols']")) != size:
            raise AssertionError(f"Missing SVG instances at size {size}")
        records.append({
            "size": size,
            "wire_segment_count": len(graph.segments),
            "svg_component_count": len(sheet_circuit.components),
            "wire_validation": wire_stats,
            "sheet_svg": {**svg_stats, "output_bytes": len(svg.encode("utf-8"))},
        })
    return {
        "schema_version": 1,
        "seed": 3604,
        "scope": "real resistor.fixed; no font, no layout or routing, no timing SLA",
        "environment": {
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "cpu_count_reported": os.cpu_count(),
            "memory_metric": "tracemalloc peak of measured operation, not RSS",
        },
        "results": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 50, 200, 500])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = benchmark(tuple(args.sizes), args.repeat)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
