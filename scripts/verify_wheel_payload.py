"""Check built, non-editable wheel includes normative and catalog data.

Editable imports can hide an omitted package-data entry. This distribution
smoke test inspects the actual wheel, not the local source tree.
"""

import argparse
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
}
_REQUIREMENTS = "standards/requirements_2026_ru.json"


def verify_wheel(wheel: Path) -> dict[str, int]:
    """Fail closed if any normative or UGO data is absent or mislabelled."""
    with ZipFile(wheel) as archive:
        payload = {
            path.removeprefix(_PREFIX)
            for path in archive.namelist() if path.startswith(_PREFIX)
        }
        missing = (_SYMBOLS | _PARTS | {_REQUIREMENTS}) - payload
        if missing:
            raise ValueError(f"Wheel missing required data: {sorted(missing)}")
        inductors = {
            name for name in payload
            if name.startswith("catalog/inductors/") and name.endswith(".json")
        }
        if len(inductors) != 15:
            raise ValueError(f"Expected exactly 15 versioned inductors, got {len(inductors)}")
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
