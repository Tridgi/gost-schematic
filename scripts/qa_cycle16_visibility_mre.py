"""Cycle16 independent actual NET _visibility_path() regression and physical DRC.

Run only against a separate, SHA-pinned NET #114 checkout. This is NOT a
replacement router, does not write owner files and does not approve a partial
TL494 sheet. --expect-known-defect is an explicitly non-release negative
baseline mode; --require-fixed is the strict forward-looking acceptance mode.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path


def require(condition: bool, error: str) -> None:
    if not condition:
        raise AssertionError(error)


def verify(net_root: Path, expected_head: str, *, expect_known_defect: bool) -> dict:
    root = net_root.resolve(strict=True)
    require(len(expected_head) == 40 and
            all(c in "0123456789abcdef" for c in expected_head),
            "QA_C16_INVALID_EXPECTED_NET_SHA")
    actual_sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True, encoding="utf-8",
    ).strip()
    require(actual_sha == expected_head, "QA_C16_NET_SOURCE_HEAD_DRIFT")
    module = (root / "src/gost_schematic/engines/multiterminal_router.py")
    require(module.is_file(), "QA_C16_NOT_ACTUAL_NET_ROUTER")
    src_root = str(root / "src")
    sys.path.insert(0, src_root)

    from gost_schematic.validation.route_drc import candidate_wire_clearance

    from gost_schematic.core.geometry import Box, Point
    from gost_schematic.engines import multiterminal_router as router
    from gost_schematic.validation.external_wire_checks import (
        ExternalWireGraph,
        WireSegment,
    )

    require(Path(router.__file__).resolve() == module.resolve(),
            "QA_C16_IMPORTED_NONOWNER_ROUTER")
    start = Point(125000, 146250)
    target = Point(120000, 146250)
    trunk = WireSegment(
        Point(124699, 131250), Point(124699, 226699), "OSCILLATOR_CT",
    )
    full = WireSegment(start, target, "COMMON")
    verdict = candidate_wire_clearance(full, trunk)
    require(verdict.valid and not verdict.errors and
            "DRC_UNMARKED_DIFFERENT_NET_X" in verdict.warnings,
            "QA_C16_GENUINE_CONTINUOUS_UNMARKED_X_REJECTED_BY_DRC")
    xpoint = Point(124699, 146250)
    # A drawn dot at a FOREIGN cross is not a valid electrical connection.
    with_foreign_dot = candidate_wire_clearance(
        full, trunk, explicit_junctions=frozenset({xpoint}),
    )
    require(not with_foreign_dot.valid and
            "DRC_FOREIGN_NET_AUTHORED_X_JUNCTION" in with_foreign_dot.errors,
            "QA_C16_FOREIGN_X_FALSE_ELECTRICAL_DOT_ACCEPTED")

    # The tiny leg created by the irrelevant search-only lattice point is
    # physically invalid as a STANDALONE endpoint, unlike the full X segment.
    ghost_leg = WireSegment(start, Point(124702, 146250), "COMMON")
    ghost_verdict = candidate_wire_clearance(ghost_leg, trunk)
    require(not ghost_verdict.valid and ghost_verdict.errors,
            "QA_C16_VIRTUAL_ENDPOINT_MISCLASSIFIED_AS_REAL_X")

    own_tee = candidate_wire_clearance(
        WireSegment(Point(50000, 120000), Point(55000, 120000), "SOFT_START"),
        WireSegment(Point(55000, 118000), Point(55000, 124000), "SOFT_START"),
    )
    require(not own_tee.valid and
            "DRC_SAME_NET_T_NO_DOT" in own_tee.errors,
            "QA_C16_OWN_T_WITHOUT_AUTHORED_DOT_WAS_ACCEPTED")
    foreign_tee = candidate_wire_clearance(
        WireSegment(Point(50000, 120000), Point(55000, 120000), "COMMON"),
        WireSegment(Point(55000, 118000), Point(55000, 124000), "SOFT_START"),
    )
    require(not foreign_tee.valid and
            "DRC_FOREIGN_NET_ENDPOINT_CONTACT" in foreign_tee.errors,
            "QA_C16_FOREIGN_PIN_TOUCH_WAS_ACCEPTED")

    empty = ExternalWireGraph((trunk,))
    paper = Box(100000, 100000, 150000, 235000)
    far = Box(124700, 170000, 124701, 170001)
    # Irrelevant 1um obstacle is 23.75 mm away from the candidate's y.
    require(far.min_y - start.y == 23750, "QA_C16_OFFPATH_TEST_CHANGED")
    on = Box(122500, 146249, 122501, 146251)

    def search(boxes: tuple[Box, ...]) -> tuple[tuple[Point, ...], str | None]:
        return router._visibility_path(
            start, Point(-1, 0), (target,),
            net_name="COMMON", occupied=empty, tree=(),
            existing_dots=(), goal_pin_normals={}, ink_obstacles=(),
            authorized_pins=frozenset(), boxes=boxes, page=paper,
            stroke_um=300, search_node_cap=1000,
            grid_um=5000, max_detour_ratio=3,
        )

    clean, clean_reason = search(())
    require(tuple(clean) == (start, target) and clean_reason is None,
            "QA_C16_BASELINE_REAL_ROUTE_UNEXPECTED")

    mutated, mutated_reason = search((far,))
    observed_defect = (not mutated and mutated_reason is not None)
    if expect_known_defect:
        require(observed_defect, "QA_C16_KNOWN_DEFECT_BASELINE_NO_LONGER_REPRODUCES")
    else:
        require(tuple(mutated) == (start, target) and mutated_reason is None,
                "QA_C16_REAL_NET_OFFPATH_1UM_FALSE_NO_ROUTE_UNFIXED")

    physically_on, on_reason = search((on,))
    for a, b in itertools.pairwise(physically_on):
        require((a.x == b.x) != (a.y == b.y),
                "QA_C16_ONPATH_CANDIDATE_NON_ORTHOGONAL")
        if a.y == b.y and on.min_y < a.y < on.max_y:
            require(max(min(a.x, b.x), on.min_x) >=
                    min(max(a.x, b.x), on.max_x),
                    "QA_C16_REAL_ONPATH_OBSTACLE_CROSSED")
        if a.x == b.x and on.min_x < a.x < on.max_x:
            require(max(min(a.y, b.y), on.min_y) >=
                    min(max(a.y, b.y), on.max_y),
                    "QA_C16_REAL_ONPATH_OBSTACLE_CROSSED")

    report = {
        "schema": "QA_CYCLE16_REAL_OWNER_VISIBILITY_MRE_V1",
        "net_head": actual_sha,
        "actual_router_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "frozen_tl494_source_sha": "e695c415fdced164b0e0c39c5249d030795a0aa6",
        "scope": "ACTUAL_NET_METHOD_AND_DRC_MICROCASE_NOT_15NET_ROUTE",
        "original_continuous_unmarked_foreign_x": "PASS",
        "real_foreign_authored_junction_negative": "REJECTED",
        "real_virtual_endpoint_foreign_contact_negative": "REJECTED",
        "real_same_net_T_without_dot_negative": "REJECTED",
        "real_foreign_net_T_negative": "REJECTED",
        "one_um_offpath_box_um": [far.min_x, far.min_y, far.max_x, far.max_y],
        "one_um_offpath_reproduced_false_negative": observed_defect,
        "offpath_new_route": [[p.x, p.y] for p in mutated],
        "offpath_search_reason": mutated_reason,
        "actual_onpath_candidate": [[p.x, p.y] for p in physically_on],
        "actual_onpath_reason": on_reason,
        "test_mode": "KNOWN_NEGATIVE_BASELINE" if expect_known_defect else
                     "STRICT_FIXED_ROUTER_ACCEPTANCE",
        "full_TL494_release": "BLOCKED_NOT_ASSESSED_BY_MICROCASE",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--net-root", required=True, type=Path)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--expect-known-defect", action="store_true")
    modes.add_argument("--require-fixed", action="store_true")
    args = parser.parse_args()
    report = verify(
        args.net_root, args.expected_head,
        expect_known_defect=args.expect_known_defect,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n", encoding="utf-8",
    )
    print("QA_CYCLE16_ACTUAL_NET_VISIBILITY " +
          json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
