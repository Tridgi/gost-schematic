"""Time observations, not rigid performance SLA / GitHub runner benchmark."""
import json
import warnings

from scripts.qa_final_pr39_benchmark import benchmark


def test_bounded_pr39_search_runtime_and_repeat_determinism():
    observations = benchmark(repeats=3)
    assert set(observations) == {
        "remote_1mm",
        "local_detour_30mm",
        "printed_1mm_foreign_10mm",
        "real_pin_safe_adapter",
    }
    assert all(len(data["samples_ms"]) == 3 for data in observations.values())
    assert all(data["segments"] >= 1 for data in observations.values())
    warnings.warn(
        "PR39 QA non-gating performance (milliseconds): "
        + json.dumps(observations, sort_keys=True),
        stacklevel=1,
    )
