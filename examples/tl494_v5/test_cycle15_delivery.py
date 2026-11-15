"""Cycle15 one-command source model + true blocked paper preflight."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from examples.tl494_v5.cycle15_delivery import produce_delivery
from examples.tl494_v5.route_candidate_driver import REAL_SOURCE_NAMES, SOURCE_SHA


def _font() -> Path:
    return Path(os.environ["TL494_TYPE_A_FONT"])


def test_unmoved_C1_refdes_blocks_before_any_route_and_svg(tmp_path: Path):
    record = produce_delivery(
        tmp_path, _font(), component_moves=(),
        node_cap=1500, physical_ripup_attempts=2,
    )
    assert record["schema"] == "GOST_TL494_CYCLE15_SOURCE_FRAME_BLOCKED_V1"
    assert record["source_sha"] == SOURCE_SHA
    assert set(record["source_original_net_names"]) == set(REAL_SOURCE_NAMES)
    assert len(record["source_original_62_pinrefs"]) == 15
    assert sum(len(v) for v in record["source_original_62_pinrefs"].values()) == 62
    assert record["full_SVG_PNG300_release"] == "BLOCKED_SOURCE_TEXT_FRAME"
    assert record["route_not_invoked"] is True
    assert record["completed_original_nets"] == 0
    v = record["real_measured_text_frame_violations"]
    assert len(v) == 1 and v[0]["owner"] == "C1"
    assert v[0]["bounds_um"][1] == 9100
    assert not list(tmp_path.rglob("*.svg"))
    assert not list(tmp_path.rglob("*.png"))
    saved = json.loads(
        (tmp_path/"C15_REAL_TL494_DELIVERY.json").read_text(encoding="utf8")
    )
    assert saved == record


@pytest.mark.parametrize(
    ("format_name", "node_cap", "ripup", "error"),
    [
        ("A0", 1500, 1, "C15_INVALID_PAPER_OR_SEARCH_BUDGET"),
        ("A3", 99, 1, "C15_INVALID_PAPER_OR_SEARCH_BUDGET"),
        ("A3", 100001, 1, "C15_INVALID_PAPER_OR_SEARCH_BUDGET"),
        ("A3", 1500, -1, "C15_UNBOUNDED_RIPUP"),
        ("A3", 1500, 6, "C15_UNBOUNDED_RIPUP"),
    ],
)
def test_noncanonical_paper_budget_and_ripup_rejected_before_source(
    tmp_path: Path, format_name: str, node_cap: int,
    ripup: int, error: str,
):
    with pytest.raises(ValueError, match=error):
        produce_delivery(
            tmp_path, Path("/forged/missing/type-a-font.ttf"),
            page_format=format_name, node_cap=node_cap,
            physical_ripup_attempts=ripup,
        )
    assert not list(tmp_path.iterdir())
