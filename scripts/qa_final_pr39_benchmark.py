"""Bounded repeatable runtime probes for frozen PR39 router; no SLA assumed.

CI hardware is shared and varies; use elapsed times as observations only.
Never derive certification or theoretical worst-case from a few samples.
"""
from statistics import median
from time import perf_counter

from examples.review_end_to_end_circuit import definitions
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle
from scripts.qa_final_pr39_loader import load_frozen_pr39


def scenarios():
    low, sheet = load_frozen_pr39()
    parts, symbols = definitions()
    circuit = Circuit(
        (
            ComponentInstance("R1", "resistor.fixed", Point(8000, -14000)),
            ComponentInstance("R3", "resistor.fixed", Point(8000, 0)),
            ComponentInstance("R2", "resistor.fixed", Point(8000, 14000)),
        ),
        (Net("LINK", (PinRef("R1", "1"), PinRef("R2", "1"))),),
    )
    remote = Box(10**9, 10**9, 10**9 + 1000, 10**9 + 1000)
    foreign = WireObstacle(
        "thick-ink", Line(Point(5000, -1000), Point(5000, 1000)),
        stroke_um=1000, net_name="B",
    )
    return {
        "remote_1mm": lambda: low.route_two_pins(
            Point(0, 0), Point(1000, 0),
            keepouts=(remote,), max_cells=1000,
        ),
        "local_detour_30mm": lambda: low.route_two_pins(
            Point(0, 0), Point(30000, 0),
            keepouts=(Box(10000, -4000, 14000, 4000),),
            max_cells=25000,
        ),
        "printed_1mm_foreign_10mm": lambda: low.route_two_pins(
            Point(0, 0), Point(10000, 0),
            foreign_wires=(foreign,), grid_um=100,
            stroke_um=300, clearance_um=400, max_cells=15000,
        ),
        "real_pin_safe_adapter": lambda: sheet.route_circuit_two_pins(
            circuit, parts, symbols, PinRef("R1", "1"), PinRef("R2", "1"),
            net_name="LINK", max_cells=25000,
        ),
    }


def benchmark(*, repeats=3):
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("Bounded sample count must be 1..5")
    result = {}
    for label, routine in scenarios().items():
        samples_ms = []
        route_points = None
        for _ in range(repeats):
            started = perf_counter()
            route = routine()
            samples_ms.append(round((perf_counter() - started) * 1000, 3))
            if not route.ok:
                raise AssertionError((label, route.diagnostics))
            if route_points is None:
                route_points = route.points
            elif route_points != route.points:
                raise AssertionError(f"Non-deterministic geometry: {label}")
        result[label] = {
            "samples_ms": samples_ms,
            "median_ms": round(median(samples_ms), 3),
            "segments": len(route_points) - 1,
        }
    return result
