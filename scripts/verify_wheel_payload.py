"""Check built, non-editable wheel includes normative and catalog data.

Editable imports can hide an omitted package-data entry. This distribution
smoke test inspects the actual wheel, not the local source tree.
"""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

_PREFIX = "gost_schematic/"
_SYMBOLS = {
    "catalog/symbols/resistors/fixed.json",
    "catalog/symbols/capacitors/fixed.json",
    "catalog/symbols/capacitors/polarized.json",
    "catalog/symbols/capacitors/electrolytic.json",
    "catalog/symbols/diodes/general.json",
    "catalog/symbols/diodes/zener.json",
    "catalog/symbols/resistors/variable.json",
    "catalog/symbols/resistors/trimmer.json",
    "catalog/symbols/fuses/general.json",
    "catalog/symbols/transistors/bjt_npn.json",
    "catalog/symbols/transistors/bjt_npn_with_case.json",
    "catalog/symbols/transistors/bjt_pnp.json",
    "catalog/symbols/transistors/bjt_pnp_with_case.json",
    "catalog/symbols/transistors/mosfet_n_enh.json",
    "catalog/symbols/transistors/mosfet_n_enh_with_case.json",
    "catalog/symbols/transistors/mosfet_p_enh.json",
    "catalog/symbols/transistors/mosfet_p_enh_with_case.json",
    "catalog/symbols/diodes/schottky.json",
    "catalog/symbols/diodes/led.json",
    "catalog/symbols/diodes/photodiode.json",
    "catalog/symbols/diodes/varicap.json",
}
_PARTS = {
    "catalog/parts/resistors/fixed.json",
    "catalog/parts/capacitors/fixed.json",
    "catalog/parts/capacitors/polarized.json",
    "catalog/parts/capacitors/electrolytic.json",
    "catalog/parts/diodes/general.json",
    "catalog/parts/diodes/zener.json",
    "catalog/parts/resistors/variable.json",
    "catalog/parts/resistors/trimmer.json",
    "catalog/parts/fuses/general.json",
    "catalog/parts/transistors/bjt_npn.json",
    "catalog/parts/transistors/bjt_npn_with_case.json",
    "catalog/parts/transistors/bjt_pnp.json",
    "catalog/parts/transistors/bjt_pnp_with_case.json",
    "catalog/parts/transistors/mosfet_n_enh.json",
    "catalog/parts/transistors/mosfet_n_enh_with_case.json",
    "catalog/parts/transistors/mosfet_p_enh.json",
    "catalog/parts/transistors/mosfet_p_enh_with_case.json",
    "catalog/parts/diodes/schottky.json",
    "catalog/parts/diodes/led.json",
    "catalog/parts/diodes/photodiode.json",
    "catalog/parts/diodes/varicap.json",
}
_REQUIREMENTS = "standards/requirements_2026_ru.json"
_AI_FROZEN = "agent_project/data/tl494_ic97_frozen_source.json"
_AI_OWNER_LOCK = "agent_project/data/tl494_cycle12_owner_locks.json"
_AI_FROZEN_BLOB = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
_INSTALLED_AI_CLI = {
    "examples/agent_tl494_cycle11_pipeline.py",
    "examples/agent_tl494_cycle13_quickstart.py",
    "examples/agent_tl494_cycle16_owner_proof.py",
}


def verify_wheel(wheel: Path) -> dict[str, int]:
    """Fail closed if any normative or UGO data is absent or mislabelled."""
    with ZipFile(wheel) as archive:
        missing_cli = _INSTALLED_AI_CLI - set(archive.namelist())
        if missing_cli:
            raise ValueError(f"Wheel missing runnable AI CLI: {sorted(missing_cli)}")
        payload = {
            path.removeprefix(_PREFIX)
            for path in archive.namelist() if path.startswith(_PREFIX)
        }
        missing = (_SYMBOLS | _PARTS | {_REQUIREMENTS, _AI_FROZEN, _AI_OWNER_LOCK,
                                        "agent_project/cycle16_owner_proof.py"}) - payload
        if missing:
            raise ValueError(f"Wheel missing required data: {sorted(missing)}")
        inductors = {
            name for name in payload
            if name.startswith("catalog/inductors/") and name.endswith(".json")
        }
        if len(inductors) != 15:
            raise ValueError(f"Expected exactly 15 versioned inductors, got {len(inductors)}")
        frozen = archive.read(_PREFIX + _AI_FROZEN)
        blob = b"blob " + str(len(frozen)).encode("ascii") + b"\x00" + frozen
        if hashlib.sha1(blob).hexdigest() != _AI_FROZEN_BLOB:
            raise ValueError("Wheel changed the signed frozen TL494 source")
        owner_lock = json.loads(archive.read(_PREFIX + _AI_OWNER_LOCK))
        if (
            owner_lock["schema_version"] != 1
            or owner_lock["frozen_source_git_sha"]
            != "e695c415fdced164b0e0c39c5249d030795a0aa6"
            or owner_lock["file_locks"]["ic_frozen_fixture"]["git_blob_sha1"]
            != _AI_FROZEN_BLOB
            or owner_lock["constraints"]["complete_15_net_route_accepted"] is not False
            or owner_lock["constraints"]["autonomous_write_mcp_available"] is not False
        ):
            raise ValueError("Wheel changed Cycle12 pinned owner/API constraints")
        data = json.loads(archive.read(_PREFIX + _REQUIREMENTS))
        if data.get("profile_id") != "eskd-ru-2026-11":
            raise ValueError("Wheel contains an unexpected ESKD requirements edition")
        for name in _SYMBOLS:
            symbol = json.loads(archive.read(_PREFIX + name))
            if symbol.get("status", "draft") != "draft":
                raise ValueError(f"Unreviewed {name} must remain DRAFT")
        for name in inductors:
            winding = json.loads(archive.read(_PREFIX + name))
            if winding.get("schema_version") != 1 or winding.get("revision", 0) < 1:
                raise ValueError(f"Malformed draft winding: {name}")
            if winding.get("status", "draft") != "draft":
                raise ValueError(f"Unreviewed winding is not DRAFT: {name}")
    return {
        "symbol_files": len(_SYMBOLS),
        "physical_part_files": len(_PARTS),
        "winding_profiles": len(inductors),
        "normative_profiles": 1,
        "installed_readonly_ai_cli_modules": len(_INSTALLED_AI_CLI),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel_dir", type=Path)
    args = parser.parse_args(argv)
    wheels = sorted(args.wheel_dir.glob("gost_schematic-*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"Expected one GOST Schematic wheel, found {len(wheels)}")
    print(f"Wheel payload verified: {verify_wheel(wheels[0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
