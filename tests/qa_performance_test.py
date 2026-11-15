"""Non-gating cycle-4 benchmark observations, printed in CI warning summaries.

Each scale is measured ONCE in the standard suite. For better medians, run the
standalone script with --repeat 3 on an otherwise idle runner.
"""

import json
import warnings

from scripts.qa.benchmark_cycle4 import benchmark


def test_bounded_real_symbol_wire_and_svg_measurements_recorded_in_ci():
    report = benchmark(sizes=(10, 50, 200, 500), repeat=1)
    assert report["schema_version"] == 1
    assert [row["size"] for row in report["results"]] == [10, 50, 200, 500]
    for row in report["results"]:
        assert row["wire_segment_count"] == row["size"]
        assert row["svg_component_count"] == row["size"]
        assert row["sheet_svg"]["output_bytes"] > 0
        for key in ("wire_validation", "sheet_svg"):
            assert row[key]["samples"] == 1
            assert row[key]["median_ms"] >= 0
            assert row[key]["max_tracemalloc_peak_kib"] >= 0
    compact = [
        {
            "n": row["size"],
            "wire_ms": row["wire_validation"]["median_ms"],
            "wire_peak_kib": row["wire_validation"]["max_tracemalloc_peak_kib"],
            "svg_ms": row["sheet_svg"]["median_ms"],
            "svg_peak_kib": row["sheet_svg"]["max_tracemalloc_peak_kib"],
        }
        for row in report["results"]
    ]
    warnings.warn(
        "QA-CYCLE4 measured (single sample; no SLA) "
        + report["environment"]["python"]
        + ": " + json.dumps(compact, separators=(",", ":")),
        UserWarning,
        stacklevel=1,
    )
