"""Circle is exact ProjectV2 artwork, not electrical geometry."""
import json
from pathlib import Path

import pytest

from ui.editor.src.model.contract import ContractError, digest, validate

FIXTURE = Path(__file__).resolve().parents[1] / "ui/fixtures/toy-v2.gscad.json"


@pytest.mark.parametrize("points", (
    [[0, 0], [0, 0]],
    [[0, 0], [-5000, 0]],
    [[0, 0], [5000, 1]],
    [[0, 0], [5000, 0], [0, 5000]],
    [[0, 999999999], [5000, 999999999]],
))
def test_invalid_circle_fails_even_if_definition_is_unplaced(points):
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc["project"]["symbol_definitions"][0]["graphics"].append({
        "kind": "circle", "points_um": points, "stroke_um": 300,
    })
    with pytest.raises(ContractError):
        validate(doc)


def test_native_circle_roundtrip_preserves_netlist_and_digest():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    before = doc["project"]["nets"]
    doc["project"]["symbol_definitions"][0]["graphics"].append({
        "kind": "circle", "points_um": [[1000, 2000], [6000, 2000]], "stroke_um": 300,
    })
    validate(doc)
    restored = json.loads(json.dumps(doc))
    validate(restored)
    assert digest(restored) == digest(doc)
    assert restored["project"]["nets"] == before
