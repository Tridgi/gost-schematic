from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.loader import load_symbol


@pytest.fixture
def resistor_path() -> Path:
    return Path(str(files("gost_schematic").joinpath(
        "catalog/symbols/resistors/fixed.json"
    )))


@pytest.fixture
def resistor(resistor_path):
    return load_symbol(resistor_path)
