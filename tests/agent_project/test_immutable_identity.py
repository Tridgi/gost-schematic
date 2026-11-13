"""Snapshot identity is immutable even when callers mutate exported dictionaries."""
import copy

import pytest

from gost_schematic.agent_project import CatalogResolver, SchematicProject
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "77777777-7777-4777-8777-777777777777"
KEY = "88888888-8888-4888-8888-888888888888"


def test_catalog_labels_are_deeply_frozen_and_export_is_independent(tmp_path):
    project = import_six_part(
        tmp_path, project_id=PID, idempotency_key=KEY
    ).project
    original_revision = project.revision
    with pytest.raises(TypeError):
        project.catalog_lock[0]["part_id"] = "malicious"
    with pytest.raises(TypeError):
        project.catalog_lock[0]["physical_pins"][0]["number"] = "999"
    with pytest.raises(TypeError):
        project.labels[0]["text"] = "fake"
    serialized = project.to_record()
    serialized["catalog_lock"][0]["physical_pins"][0]["name"] = "fake"
    serialized["labels"][0]["text"] = "fake"
    assert project.revision == original_revision
    assert project.to_record()["catalog_lock"][0]["physical_pins"][0]["name"] != "fake"


def test_component_ids_are_independent_of_future_rename_proposal(tmp_path):
    """Only verify data contract: no mutation operation is exposed to clients."""
    project = import_six_part(
        tmp_path, project_id=PID, idempotency_key=KEY
    ).project
    record = copy.deepcopy(project.to_record())
    before_uid = record["components"][0]["id"]
    original_refdes = record["components"][0]["reference"]
    record["components"][0]["reference"] = "R99"
    for row in record["labels"]:
        if row["component_id"] == before_uid:
            row["text"] = "R99"
    loaded = SchematicProject.from_record(record, CatalogResolver())
    assert loaded.component_ids[0] == before_uid
    assert loaded.circuit.components[0].reference == "R99"
    assert all(
        pin.reference != original_refdes
        for net in loaded.circuit.nets for pin in net.members
    )
    assert loaded.revision != project.revision
    assert project.circuit.components[0].reference == original_refdes
