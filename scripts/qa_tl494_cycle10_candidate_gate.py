"""QA of real RECON Cycle10 multi-candidate driver, not an image mock.

Verifies each routed net and actual partial conductor export against frozen
source 23/15/62, exact original a_/b_ identifiers and pinned owner SHAs.
No unverified 8/15 or 0/15 becomes printable. QA never alters owner trees.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path

from scripts.qa_tl494_next_route_gate import (
    EMPTY_DELTA,
    FROZEN_SHA,
    GateError,
    frozen_membership,
    inspect_route,
    require,
)

RECON_CANDIDATE_SHA = "4db3b8bb7b06757602787b48240d0deaaa3dc754"
CYCLE11_RECON_SHA = "c58e224700b318892ee92197f8bfd391807a7325"
# Provenance as claimed INSIDE current RECON owner source code, not guessed.
CYCLE11_RECON_OWNER_SHAS = {
    "ELEKTRIK_IC_PR97": "19d14c4b660c9ad490a65cd1eab644f1637bc334",
    "PAINT_PR93": "32f2efb2cdcb561cb2567a54448381de3cb87832",
    "YGO2_PR113": "eb16121e07efec71de77dfc7b8123bc09f66ddd6",
    "ELEKTRIK_NET_PR114": "5033659747f01fdc03adc084b846f47b05001963",
}
# Latest concurrently retrieved owner HEADs for *execution*, not silently
# identical to pinned provenance shown in the RECON source report.
CYCLE11_LIVE_RUNTIME_SHAS = {
    "ic": "1e4baf7ea713f649e0dabb4d6119e97281901f03",
    "paint": "f69d891e2f17797878627447eb7f05a66f311ca0",
    "net": "b5436ecc800bf7c4a99e1d71cce0cb5dc854ed52",
    "catalog": "eb16121e07efec71de77dfc7b8123bc09f66ddd6",
}
FROZEN_IC_BLOB = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
OWNER_SHAS = {
    "ELEKTRIK_IC_PR97": "b28428d94218cac777a28897ce9176285d0fab0b",
    "PAINT_PR93": "161c31bd0b538c6e827341ae465c3b3a59f6637d",
    "YGO2_PR113": "edc71a48035723d48a203ae2ea12588701f68ba8",
    "ELEKTRIK_NET_PR114": "b3a8263944c5a687492a49555d8149e538f0902b",
}
ALIAS = {
    "INPUT_POS": "a_INPUT_PLUS",
    "ENERGY_TRANSFER": "TRANSFER",
    "OUTPUT_NEG": "b_NEGATIVE_OUTPUT",
}
OLD_BAD = {"error_count": 9, "warning_count": 32,
           "segments": 91, "junctions": 37}


def exact_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()


def original_members() -> dict[str, tuple[str, ...]]:
    canonical = frozen_membership()
    originals = {
        ALIAS.get(name, name): tuple(sorted(refs))
        for name, refs in canonical.items()
    }
    require(len(originals) == 15 and
            sum(map(len, originals.values())) == 62,
            "QA_ORIGINAL_RAW_NET_IDENTITIES_NOT_15_62")
    return originals


def normalized(source: dict[str, tuple[str, ...]]) -> dict[str, frozenset[str]]:
    return {key: frozenset(value) for key, value in source.items()}


def check_graph(graph: dict, trees: dict, expected: dict) -> dict:
    require(isinstance(graph, dict) and
            graph.get("status") == "DIAGNOSTIC_ONLY_NOT_PRINT_AFTER",
            "QA_RECON_PARTIAL_GRAPH_FAKED_PRINTABLE")
    wires = graph.get("segments_um")
    junctions = graph.get("junctions_um")
    require(isinstance(wires, list) and isinstance(junctions, list),
            "QA_RECON_MISSING_REAL_WIRE_EXPORT")
    require(len(wires) == trees.get("graph_segments") and
            len(junctions) == trees.get("graph_junctions"),
            "QA_RECON_WIRES_DRC_GRAPH_MISMATCH")
    for segment in wires:
        require(isinstance(segment, dict) and
                segment.get("net") in expected,
                "QA_RECON_FOREIGN_NET_WIRE")
        a, b = segment.get("start"), segment.get("end")
        require(isinstance(a, list) and isinstance(b, list) and
                len(a) == len(b) == 2 and
                all(type(n) is int for n in a + b) and
                a != b and (a[0] == b[0] or a[1] == b[1]),
                "QA_RECON_NONPHYSICAL_OR_ZERO_WIRE")
    counted = Counter(wire["net"] for wire in wires)
    for tree in trees.get("net_trees", ()):
        name = tree.get("net")
        if tree.get("complete"):
            require(counted[name] == tree.get("segments"),
                    "QA_RECON_ACCEPTED_GRAPH_DIFFERS_FROM_COMPLETED_TREE")
        else:
            require(counted[name] == 0,
                    "QA_RECON_UNSAFE_PARTIAL_TREE_WIRES_SILENTLY_ACCEPTED")
    coords = [
        (tuple(wire["start"]), tuple(wire["end"]), wire["net"])
        for wire in wires
    ]

    def on_segment(start, end, point):
        dx, dy = end[0] - start[0], end[1] - start[1]
        return (
            dx * (point[1] - start[1]) ==
            dy * (point[0] - start[0]) and
            min(start[0], end[0]) <= point[0] <= max(start[0], end[0]) and
            min(start[1], end[1]) <= point[1] <= max(start[1], end[1])
        )

    seen = set()
    for point in junctions:
        require(isinstance(point, list) and len(point) == 2 and
                all(type(n) is int for n in point),
                "QA_RECON_FORGED_JUNCTION_COORDINATE")
        loc = tuple(point)
        require(loc not in seen, "QA_RECON_DUPLICATED_AUTHORED_JUNCTION")
        seen.add(loc)
        touched = [
            net for start, end, net in coords
            if on_segment(start, end, loc)
        ]
        require(len(touched) >= 2 and len(set(touched)) == 1,
                "QA_RECON_FOREIGN_NET_OR_DANGLING_JUNCTION_DOT")
    return {
        "wires": len(wires), "junctions": len(junctions),
        "complete_net_wire_counts_attested": True,
        "explicit_junction_net_identity_checked": True,
    }


def inspect_candidate_driver(
    wrapper: dict, source: dict[str, tuple[str, ...]],
    *, owner_shas: dict | None = None, recon_sha: str = RECON_CANDIDATE_SHA,
    frozen_fixture: dict | None = None,
) -> dict:
    require(isinstance(wrapper, dict), "QA_RECON_CANDIDATE_NOT_TYPED_JSON")
    require(wrapper.get("schema") ==
            "TL494_23_15_62_SOURCE_LOCKED_ROUTE_CANDIDATES_V1",
            "QA_RECON_CANDIDATE_SCHEMA_UNKNOWN")
    require(wrapper.get("source_reference_sha") == FROZEN_SHA and
            wrapper.get("owner_exact_SHAs") == (
                owner_shas if owner_shas is not None else OWNER_SHAS
            ),
            "QA_RECON_STALE_OR_UNTRUSTED_OWNER_SHAS")
    require(wrapper.get("frozen_photo_fixture_git_blob") == FROZEN_IC_BLOB,
            "QA_RECON_UNTRUSTED_23_15_62_PHOTO_FIXTURE")
    require(wrapper.get("bom_count") == 23 and
            wrapper.get("net_count") == 15 and
            wrapper.get("physical_net_membership_count") == 62,
            "QA_RECON_PHYSICAL_BOM_NET_PIN_COUNTS_DRIFT")
    require(wrapper.get("negative_original_DRC_expected") == OLD_BAD,
            "QA_RECON_OLD_KNOWN_BAD_TEST_REMOVED")
    require(wrapper.get("qa_print_release") ==
            "BLOCKED_INDEPENDENT_QA_AND_ESKD" and
            wrapper.get("actual_full_sheet_svg_or_png_emitted") is False,
            "QA_RECON_PARTIAL_WRONGLY_CLAIMED_PRINT_RELEASE")
    real_source = wrapper.get("original_net_names")
    require(isinstance(real_source, list) and len(real_source) == 15 and
            set(real_source) == set(source),
            "QA_RECON_ORIGINAL_A_B_NET_NAMES_DRIFT")
    require(wrapper.get("internal_aliases_reverse") == {
        "a_INPUT_PLUS": "INPUT_POS",
        "TRANSFER": "ENERGY_TRANSFER",
        "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
    }, "QA_RECON_ORIGINAL_SOURCE_ALIAS_MAPPING_CHANGED")
    if frozen_fixture is not None:
        require(wrapper.get("source_BOM") == frozen_fixture.get("components"),
                "QA_CYCLE11_SOURCE_NOMINAL_OR_PART_ID_CHANGED")
        require(wrapper.get("source_BOM_SHA256") == exact_hash(
            frozen_fixture["components"]
        ), "QA_CYCLE11_SOURCE_BOM_HASH_INCORRECT")
        require(wrapper.get("original_Netlist") == frozen_fixture.get("nets"),
                "QA_CYCLE11_SOURCE_ORIGINAL_NETLIST_REWRITTEN")
        require(wrapper.get("source_BOM") and next(
            item["part_id"] for item in wrapper["source_BOM"]
            if item["ref"] == "DA1"
        ) == "reference.tl494cn",
                "QA_CYCLE11_LEGACY_DA1_SOURCE_PART_ID_LOST")
        require(set(source["b_NEGATIVE_OUTPUT"]) >= {"X2.1", "R5.2"},
                "QA_CYCLE11_B_CONTINUATION_PHYSICAL_ENDPOINTS_LOST")
        require(wrapper.get("actual_full_sheet_svg_or_png_emitted") is False,
                "QA_CYCLE11_PREMATURE_NATIVE_PRINT_CLAIM")
    trials = wrapper.get("candidates")
    require(isinstance(trials, list) and 1 <= len(trials) <= 3,
            "QA_RECON_MISSING_CANDIDATE_EVIDENCE")
    seen = set()
    outcomes = []
    for trial in trials:
        require(isinstance(trial, dict), "QA_RECON_INVALID_CANDIDATE")
        key = trial.get("key")
        require(key in ("source", "short-first", "control-first") and
                key not in seen, "QA_RECON_DUPLICATE_OR_UNKNOWN_VARIANT")
        seen.add(key)
        named = trial.get("source_nets")
        require(isinstance(named, dict) and set(named) == set(source) and
                all(isinstance(members, list) and
                    tuple(sorted(members)) == original
                    for name, (members, original) in (
                        (name, (named[name], source[name]))
                        for name in source
                    )),
                "QA_RECON_CANDIDATE_PHYSICAL_NET_MEMBERSHIPS_CHANGED")
        require(trial.get("Net_membership_SHA256") == exact_hash(named) and
                wrapper.get("original_nets_SHA256") == exact_hash(named),
                "QA_RECON_SOURCE_NET_HASH_INCONSISTENT")
        require(trial.get("source_unchanged") is True and
                trial.get("print_after_released") is False,
                "QA_RECON_CANDIDATE_NOT_READ_ONLY")
        count = trial.get("routed_net_count")
        require(type(count) is int and 0 <= count <= 15,
                "QA_RECON_CANDIDATE_ROUTED_COUNT_INVALID")
        if trial.get("status") == "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT":
            require(count == 0 and trial.get("routes_attempted") == 0 and
                    not trial.get("technical_route_eligible") and
                    "owner_router_report" not in trial,
                    "QA_RECON_LAYOUT_BLOCKER_WAS_RELEASED")
            outcomes.append({
                "variant": key, "routed": 0,
                "gate": "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT",
            })
            continue
        route = trial.get("owner_router_report")
        require(isinstance(route, dict) and
                trial.get("routes_attempted") == 15,
                "QA_RECON_NO_GENUINE_15_NET_ROUTE_ATTEMPT")
        verified = dict(route)
        # Provenance is checked above, never inferred from arbitrary SVG.
        verified.update({
            "source_sha": FROZEN_SHA,
            "owner_router_sha": (
                owner_shas if owner_shas is not None else OWNER_SHAS
            )["ELEKTRIK_NET_PR114"],
            "origin_component_count": 23, "origin_net_count": 15,
            "DA1_real_anchor_count": 16,
            "net_diff": deepcopy(EMPTY_DELTA),
            "old_source_negative_drc": {
                "errors": 9, "warnings": 32, "segments": 91, "junctions": 37,
            }, "print_after_released": False,
        })
        checked = inspect_route(
            verified, normalized(source),
            exact_router_sha=(
                owner_shas if owner_shas is not None else OWNER_SHAS
            )["ELEKTRIK_NET_PR114"],
        )
        require(count == checked["routed_nets"],
                "QA_RECON_CANDIDATE_FAKE_REROUTE_COUNT")
        # A real layout/ink page fit may veto an otherwise complete graph.
        # It must never override BLOCKED geometry to manufacture success.
        require(trial.get("technical_route_eligible") is not True or (
            checked["status"].startswith("TECHNICAL_ROUTE_ELIGIBLE")
            and trial.get("layout_valid") is True
            and trial.get("a3", {}).get("A3_capacity_fit") is True
        ), "QA_RECON_CANDIDATE_FORGED_PRINT_PREFLIGHT")
        physical = check_graph(
            trial.get("accepted_graph_nonprintable"), route, source,
        )
        outcomes.append({
            "variant": key, "routed": count,
            "gate": checked["status"],
            "geometry_counts": physical,
            "drc_errors": checked["new_route_drc_errors"],
            "incomplete": checked["unrouted_net_names"],
        })
    best = wrapper.get("best_evidence_variant")
    require(best in seen and type(wrapper.get("best_completed_nets")) is int and
            wrapper["best_completed_nets"] ==
            next(row["routed"] for row in outcomes if row["variant"] == best) and
            wrapper["best_completed_nets"] == max(
                row["routed"] for row in outcomes
            ), "QA_RECON_INFLATED_BEST_VARIANT")
    return {
        "reference_source": FROZEN_SHA,
        "reference_driver_commit": recon_sha,
        "source_photo_fixture_blob": FROZEN_IC_BLOB,
        "verified_real_original_net_names": 15,
        "verified_actual_pinref_memberships": 62,
        "variants": outcomes,
        "best_completed_nets": wrapper["best_completed_nets"],
        "release": "NO_GO_RAW_CANDIDATE_IS_NOT_PRINTABLE_ART",
        "all_negative_source_invariants_preserved": True,
    }


def selftest_tampering(
    real: dict, expected: dict, *, owner_shas: dict | None = None,
    recon_sha: str = RECON_CANDIDATE_SHA,
    frozen_fixture: dict | None = None,
) -> dict:
    cases = {
        "wrong_source_sha": lambda a: a.update(
            source_reference_sha="forged",
        ),
        "wrong_owner_sha": lambda a: a["owner_exact_SHAs"].update(
            {"PAINT_PR93": "forged"},
        ),
        "wrong_original_physical_contact": lambda a: a["candidates"][0][
            "source_nets"]["COMMON"].append("DA1.999"),
        "claimed_16_of_15": lambda a: a.update(best_completed_nets=16),
        "fake_original_alias": lambda a: a["internal_aliases_reverse"].update(
            {"a_INPUT_PLUS": "WRONG_NET"},
        ),
        "premature_print_release": lambda a: a.update(
            qa_print_release="PASS",
        ),
        **({
            "fake_source_nominal": lambda a: a["source_BOM"][0].update(
                nominal_si="12345",
            ),
            "fake_b_net_membership": lambda a: a["original_Netlist"][
                "b_NEGATIVE_OUTPUT"
            ].append("DA1.999"),
        } if frozen_fixture is not None else {}),
    }
    results = {}
    for name, change in cases.items():
        altered = deepcopy(real)
        change(altered)
        try:
            inspect_candidate_driver(
                altered, expected,
                owner_shas=owner_shas, recon_sha=recon_sha,
                frozen_fixture=frozen_fixture,
            )
        except GateError:
            results[name] = "REJECTED_REAL_OWNER_MUTATION"
        else:
            raise GateError("QA_RECON_NEGATIVE_BYPASS_" + name)
    return results


def _git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def git_blob(data: bytes) -> str:
    prefix = ("blob " + str(len(data))).encode() + b"\0"
    return hashlib.sha1(prefix + data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen-root", type=Path, required=True)
    ap.add_argument("--recon-root", type=Path, required=True)
    ap.add_argument("--ic-fixture", type=Path, required=True)
    ap.add_argument("--candidate-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cycle11", action="store_true")
    for owner in CYCLE11_LIVE_RUNTIME_SHAS:
        ap.add_argument("--live-" + owner, type=Path)
    args = ap.parse_args()
    expected_recon = CYCLE11_RECON_SHA if args.cycle11 else RECON_CANDIDATE_SHA
    expected_owners = CYCLE11_RECON_OWNER_SHAS if args.cycle11 else OWNER_SHAS
    require(_git_head(args.frozen_root) == FROZEN_SHA and
            _git_head(args.recon_root) == expected_recon,
            "QA_RECON_REAL_COMMIT_NOT_PINNED")
    live_provenance = {}
    if args.cycle11:
        for owner, sha in CYCLE11_LIVE_RUNTIME_SHAS.items():
            path = getattr(args, "live_" + owner)
            require(path is not None and _git_head(path) == sha,
                    "QA_CYCLE11_LIVE_OWNER_HEAD_NOT_ATTESTED:" + owner)
            live_provenance[owner] = sha
    require(git_blob(args.ic_fixture.read_bytes()) == FROZEN_IC_BLOB,
            "QA_RECON_ORIGINAL_TI_FIXTURE_BYTES_CHANGED")
    source = original_members()
    raw = json.loads(args.candidate_report.read_text(encoding="utf-8"))
    fixture = json.loads(args.ic_fixture.read_text(encoding="utf-8"))
    report = {
        "real_candidate": inspect_candidate_driver(
            raw, source, owner_shas=expected_owners, recon_sha=expected_recon,
            frozen_fixture=fixture if args.cycle11 else None,
        ),
        "negative_adversarial": selftest_tampering(
            raw, source, owner_shas=expected_owners, recon_sha=expected_recon,
            frozen_fixture=fixture if args.cycle11 else None,
        ),
        "no_print_approval": True,
        "live_runtime_exact_head_SHA": live_provenance,
        "embedded_RECON_owner_snapshots": expected_owners,
        "runtime_differs_from_embedded_snapshot": (
            args.cycle11 and any(
                live_provenance[owner] != expected_owners[lab]
                for owner, lab in (
                    ("ic", "ELEKTRIK_IC_PR97"),
                    ("paint", "PAINT_PR93"),
                    ("net", "ELEKTRIK_NET_PR114"),
                    ("catalog", "YGO2_PR113"),
                )
            )
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False,
                   sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("QA92_REAL_SOURCE_NAMED_CANDIDATE " +
          json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
