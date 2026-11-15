"""Synthetic-only physical E3 IC package and split-view reference, Cycle 7.

This example is NOT a manufacturer pinout, a footprint, or a GOST approved UGO.
PAINT must measure real font and supply validated sizes before rendering.
"""

import argparse
from pathlib import Path

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.electrical.ic import (
    IcDeviceDefinition,
    IcKind,
    IcPackage,
    IcPhysicalPin,
    IcPinRow,
    IcPinType,
    IcSymbolSpec,
    IcUnit,
    IcUnitPlacement,
    PinoutOrigin,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_to_json


def synthetic_ic(
    count: int, kind: IcKind = IcKind.DIGITAL,
    split: bool | None = None,
) -> IcLibraryRecord:
    """Clearly synthetic 2/4/8/14/40/64-pin reference; no real IC claims."""
    if count not in (2, 4, 8, 14, 40, 64):
        raise ValueError("Only explicitly designed synthetic fixture sizes allowed")
    if not isinstance(kind, IcKind):
        raise TypeError("Kind must be typed")
    split = (count >= 14) if split is None else split
    pins = []
    for n in range(1, count + 1):
        kind_of_pin = (
            IcPinType.NC if n == count and count > 4 else
            IcPinType.POWER_INPUT if n == count - 1 and count > 4 else
            IcPinType.OPEN_COLLECTOR if n == count - 2 and count > 4 else
            IcPinType.INPUT if n % 2 else IcPinType.OUTPUT
        )
        pins.append(IcPhysicalPin(
            str(n),
            f"СИНТЕТИЧЕСКАЯ_ФУНКЦИЯ_ВЫВОДА_{n}"
            if n in (1, 10, 40) else f"ТЕСТ_{n}",
            f"Synthetic pin role {n}", kind_of_pin,
        ))
    pack = IcPackage(
        package_id=f"TEST_PACKAGE_{count}", family="SYNTHETIC-NOT-FOOTPRINT",
        pin_count=count, origin=PinoutOrigin.SYNTHETIC,
    )
    groups = (
        (tuple(str(x) for x in range(1, count // 2 + 1)),
         tuple(str(x) for x in range(count // 2 + 1, count + 1)))
        if split else (tuple(str(x) for x in range(1, count + 1)),)
    )
    units = tuple(
        IcUnit(f"U{idx}", f"Synthetic functional unit {idx}", members)
        for idx, members in enumerate(groups, 1)
    )
    device = IcDeviceDefinition(
        f"TEST_IC_{kind.value.upper()}_{count}",
        kind, pack, tuple(pins), units,
    )
    specs = []
    placements = []
    for unit_idx, unit in enumerate(units):
        # Dimensions are declared explicitly as an input to PAINT.
        # They are NOT font-derived and are NOT production drawing dimensions.
        rows = []
        side_height = (len(unit.pin_numbers) + 2) * 4000
        body = Box(0, 0, 60000, side_height)
        for idx, number in enumerate(unit.pin_numbers):
            side = Side.LEFT if (idx % 2 == 0) else Side.RIGHT
            x = -4000 if side is Side.LEFT else 64000
            row_index = idx // 2
            # Explicit stable port rows, no collision; names never choose size.
            y = 5000 + idx * 4000
            rows.append(IcPinRow(
                number, side, Point(x, y), f"functional-row-{row_index}",
                label=f"VIEW_{number}", visual_row=idx + 1,
            ))
        specs.append(IcSymbolSpec(
            device_id=device.identifier, unit_id=unit.id,
            body=body, main_field=f"{kind.value.upper()} TEST FUNCTION",
            rows=tuple(rows), aux_left="IN", aux_right="OUT",
        ))
        placements.append(IcUnitPlacement(
            component_ref=kind.reference_prefix + "1",
            device_id=device.identifier, unit_id=unit.id,
            origin=Point(unit_idx * 500000, 0),
        ))
    return IcLibraryRecord(device, tuple(specs), tuple(placements))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for count in (2, 4, 8, 14, 40, 64):
        for kind in (IcKind.ANALOG, IcKind.DIGITAL):
            record = synthetic_ic(count, kind)
            filename = f"TEST_IC_{kind.value.upper()}_{count}.json"
            (args.output_dir / filename).write_text(
                ic_to_json(record), encoding="utf-8",
            )
            print(f"DRAFT synthetic physical IC only: {filename}")


if __name__ == "__main__":
    main()
