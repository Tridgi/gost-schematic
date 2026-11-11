import pytest

from gost_schematic.core.units import format_mm, mm


def test_unit_conversion_is_exact():
    assert mm("0.001") == 1
    assert mm(-2.5) == -2500
    assert format_mm(2501) == "2.501"


@pytest.mark.parametrize("invalid", [True, "nan", "infinity", "0.0001", "oops"])
def test_unit_conversion_rejects_ambiguous_values(invalid):
    with pytest.raises(ValueError):
        mm(invalid)
