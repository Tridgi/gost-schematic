"""Read-only real RECON Cycle15 TL494 route+PAINT proof consumer (wheel CLI).

Usage:
  python -m examples.agent_tl494_cycle16_owner_proof --owner-c15-dir PATH --out NEW_DIR

Without an external owner directory, emits a truthful blocked handoff. No
source inference, netlist change, MCP writer, or print permission is possible.
"""
from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path

from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.cycle16_owner_proof import review_c15_owner_proof
from gost_schematic.agent_project.owner_source_contract import verify_frozen_owner_fixture

from .agent_tl494_cycle11_pipeline import _request
from .agent_tl494_cycle13_quickstart import _json_bytes, _safe_new_output


def run(output: Path, owner_c15_dir: Path | None = None) -> dict:
    source = verify_frozen_owner_fixture(
        files("gost_schematic").joinpath(
            "agent_project", "data", "tl494_ic97_frozen_source.json",
        ).read_bytes(),
        CatalogResolver(),
    )
    request = _request(source)
    proof = review_c15_owner_proof(request, owner_c15_dir)
    dest = _safe_new_output(output)
    (dest / "source-c16-owner-candidate-proof.json").write_bytes(_json_bytes(proof))
    return proof


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--owner-c15-dir", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = run(args.out, args.owner_c15_dir)
    except ProjectError as error:
        print(json.dumps({
            "status": "REJECTED", "code": error.code,
            "read_only": True, "mutated": False, "print_ready": False,
        }, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
