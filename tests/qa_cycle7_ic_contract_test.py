"""PAINT #88 independent *real source* negative API tests, no simulated renderer.

Uses the exact owner .txt as executable production code; no font dependency in
these structural checks. Real OpenGost/Pillow+SVG/PNG acceptance is in the
dedicated qa_cycle7_ic_visual.py workflow. No manufacturer/pinout invented.
"""
from dataclasses import replace

import pytest
from qa_cycle7_support import BLOBS, ensure_verified, owner_renderer

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform


@pytest.fixture(scope="module")
def painter():
    ensure_verified()
    return owner_renderer()


def _pin(mod, number, *, side=Side.LEFT, row=1, at=None):
    return mod.ResolvedIcPin(
        pin_id=f"test_{number}", number=str(number),
        label=f"ДЛИННОЕ НАЗВАНИЕ ВЫВОДА {number}",
        side=side, row=row, anchor=at if at is not None else Point(0, 0),
        role="passive",
    )


def test_real_owner_ic_source_is_not_integrated_code_mock(painter):
    assert BLOBS["qa_cycle7_ic_owner88/ic_rectangular.txt"].startswith("0aeaf02e")
    assert painter.__file__.endswith(
        "tests/fixtures/qa_cycle7_ic_owner88/ic_rectangular.txt"
    )
    assert painter.ResolvedIcPin.__module__ == "_qa_cycle7_real_paint_88"
    assert painter.render_resolved_ic.__module__ == "_qa_cycle7_real_paint_88"


@pytest.mark.parametrize("n", (2, 8, 14, 40, 64))
def test_real_owner_ic_typed_pin_numbers_retain_64_distinct_roles(painter, n):
    pins = tuple(
        _pin(painter, i+1, row=i+1, at=Point(0, 4000 * (i+1)))
        for i in range(n)
    )
    box = Box(0, 0, 50000, 30000 + 4000 * n)
    unit = painter.IcResolvedUnit(
        "DD7", box, pins, painter.IcFieldContent(
            "ЛОГИЧЕСКАЯ СИСТЕМА", analog=False,
        )
    )
    assert len(unit.pins) == n
    assert [p.number for p in unit.pins] == [str(i+1) for i in range(n)]
    assert [p.label for p in unit.pins] == [
        f"ДЛИННОЕ НАЗВАНИЕ ВЫВОДА {i+1}" for i in range(n)
    ]
    assert len({p.anchor for p in unit.pins}) == n
    assert unit.reference == "DD7"
    # This test only verifies author-supplied typed pins; not vendor identities.


@pytest.mark.parametrize(
    ("wrong", "diagnostic"),
    [
        ({"row": 0}, "IC_PIN_ROW_INVALID"),
        ({"row": -1}, "IC_PIN_ROW_INVALID"),
        ({"role": "piezoelectric"}, "IC_PIN_ROLE_INVALID"),
        ({"number": ""}, "IC_PIN_ID_MISSING"),
        ({"pin_id": ""}, "IC_PIN_ID_MISSING"),
    ],
)
def test_real_owner_ic_bad_physical_record_rejected(painter, wrong, diagnostic):
    initial = _pin(painter, 12)
    with pytest.raises(ValueError, match=diagnostic):
        replace(initial, **wrong)


def test_real_owner_ic_duplicate_number_pin_id_anchor_row_each_fail_closed(painter):
    a = _pin(painter, 1, row=1, at=Point(0, 7500))
    b = _pin(painter, 2, row=2, at=Point(0, 12500))
    base = painter.IcResolvedUnit(
        "DA1", Box(0, 0, 50000, 40000), (a, b),
        painter.IcFieldContent("АЦП")
    )
    assert len(base.pins) == 2
    variants = [
        (replace(b, number=a.number), "IC_DUPLICATE_PHYSICAL_NUMBER"),
        (replace(b, pin_id=a.pin_id), "IC_DUPLICATE_PIN_ID"),
        (replace(b, anchor=a.anchor), "IC_DUPLICATE_RESOLVED_ANCHOR"),
        (replace(b, row=a.row), "IC_DUPLICATE_PIN_ROW"),
    ]
    for second, code in variants:
        with pytest.raises(ValueError, match=code):
            replace(base, pins=(a, second))


@pytest.mark.parametrize(
    ("opts", "msg"),
    [
        ({"module_um": 0}, "IC_POLICY_INVALID"),
        ({"pitch_modules": 0}, "IC_POLICY_INVALID"),
        ({"ink_padding_um": 0}, "IC_POLICY_INVALID"),
        ({"line_width_um": -10}, "IC_POLICY_INVALID"),
        ({"lead_length_um": 100, "ink_padding_um": 1000},
         "IC_POLICY_INVALID"),
    ],
)
def test_owner_real_ic_invalid_editorial_policy_rejected(painter, opts, msg):
    with pytest.raises(ValueError, match=msg):
        painter.IcRenderingPolicy(**opts)


def test_owner_real_ic_extra_fields_and_newline_are_not_silently_truncated(painter):
    fields = painter.IcFieldContent(
        function="КОНТРОЛЛЕР",
        main_rows=("UART + SPI + ADC", "ВТОРАЯ СТРОКА"),
        left_rows=("НАИМЕНОВАНИЕ ВХОДА ПОЛНОЕ",),
        right_rows=("OUTPUT BUFFER ENABLE",),
        analog=True,
    )
    assert fields.main_rows[1] == "ВТОРАЯ СТРОКА"
    assert fields.left_rows[0] == "НАИМЕНОВАНИЕ ВХОДА ПОЛНОЕ"
    with pytest.raises(ValueError, match="IC_TEXT_NEWLINE"):
        replace(fields, function="SHORT\nTRUNCATE")
    with pytest.raises(ValueError, match="IC_ZONE_ROW_INVALID"):
        replace(fields, left_zone_after=(-1,))


def test_owner_real_ic_unsupported_vertical_pin_direction_not_silently_mapped(
    painter,
):
    left = _pin(painter, 1)
    with pytest.raises(ValueError, match="IC_NONSTANDARD_INPUT_SIDE"):
        painter.IcResolvedUnit(
            "DD1", Box(0, 0, 50000, 40000),
            (replace(left, role="in", side=Side.RIGHT),),
            painter.IcFieldContent("BUS"),
        )
    with pytest.raises(ValueError, match="IC_NONSTANDARD_OUTPUT_SIDE"):
        painter.IcResolvedUnit(
            "DA1", Box(0, 0, 50000, 40000),
            (replace(left, role="out", side=Side.LEFT),),
            painter.IcFieldContent("AMP"),
        )
    assert Transform(rotation=90, mirror_x=True).side(Side.LEFT) != Side.LEFT
