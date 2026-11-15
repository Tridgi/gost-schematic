"""Boundary tests for actual-head blob manifest; never skip source-negative cases."""
import copy
import json

import pytest

from gost_schematic.agent_project.catalog import ProjectError
from gost_schematic.agent_project.owner_api_locks import (
    _PATHS,
    load_pinned_owner_lock_manifest,
    verify_pinned_owner_api_files,
)


def _as_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def test_real_cycle12_owner_lock_shape_is_snapshot_not_print_release():
    locked = load_pinned_owner_lock_manifest()
    assert locked["schema_version"] == 1
    assert locked["frozen_source_git_sha"] == (
        "e695c415fdced164b0e0c39c5249d030795a0aa6"
    )
    assert set(locked["file_locks"]) == set(_PATHS)
    assert set(locked["owner_heads"]) == {
        "IC97", "RECON115", "NET114", "PAINT93",
    }
    for name, row in locked["file_locks"].items():
        assert (row["owner"], row["path"]) == _PATHS[name]
        assert len(row["git_blob_sha1"]) == 40
    assert locked["file_locks"]["ic_frozen_fixture"]["git_blob_sha1"] == (
        "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
    )
    assert not locked["constraints"]["complete_15_net_route_accepted"]
    assert not locked["constraints"]["autonomous_write_mcp_available"]


@pytest.mark.parametrize(("mutation", "code"), [
    (lambda d: d.update(schema_version=True), "OWNER_LOCK_CONTRACT_DRIFT"),
    (lambda d: d.update(repository="evil/path"), "OWNER_LOCK_CONTRACT_DRIFT"),
    (lambda d: d["owner_heads"].update(IC97="deadbeef"), "OWNER_LOCK_HEAD_INVALID"),
    (lambda d: d["file_locks"]["ic_tl494"].update(
        path="../evil.py",
    ), "OWNER_LOCK_PATH_OR_OWNER_CHANGED"),
    (lambda d: d["file_locks"]["ic_tl494"].update(
        owner="NET114",
    ), "OWNER_LOCK_PATH_OR_OWNER_CHANGED"),
    (lambda d: d["file_locks"]["ic_frozen_fixture"].update(
        git_blob_sha1="f" * 40,
    ), "OWNER_LOCK_ORIGINAL_SOURCE_DRIFT"),
    (lambda d: d["file_locks"].pop("ic_tl494"), "OWNER_LOCK_FILE_SET_INVALID"),
    (lambda d: d["constraints"].update(
        complete_15_net_route_accepted=True,
    ), "OWNER_LOCK_CONTRACT_DRIFT"),
])
def test_mutated_snapshot_denied_before_owner_code(mutation, code):
    bad = copy.deepcopy(load_pinned_owner_lock_manifest())
    mutation(bad)
    with pytest.raises(ProjectError, match=code):
        load_pinned_owner_lock_manifest(_as_bytes(bad))


def test_bad_json_duplicate_keys_nan_injection_and_size_fail_closed():
    for payload, code in [
        (b'{"schema_version":1,"schema_version":2}', "OWNER_LOCK_DUPLICATE_KEY"),
        (b'{"a":NaN}', "OWNER_LOCK_INVALID_JSON"),
        (b'\xff', "OWNER_LOCK_INVALID_JSON"),
        (b" " * 12289, "OWNER_LOCK_MANIFEST_SIZE_INVALID"),
    ]:
        with pytest.raises(ProjectError, match=code):
            load_pinned_owner_lock_manifest(payload)


def test_unknown_owner_source_files_and_fake_current_blob_are_denied():
    with pytest.raises(ProjectError, match="OWNER_LOCK_ACTUAL_FILE_SET_INVALID"):
        verify_pinned_owner_api_files({})
    fake = {name: b"TI_DEVICE_ID = 'ti.tl494cn.pdip16'\n" for name in _PATHS}
    with pytest.raises(ProjectError, match="OWNER_LOCK_ACTUAL_BLOB_MISMATCH"):
        verify_pinned_owner_api_files(fake)
    fake["ic_frozen_fixture"] = "not bytes"
    with pytest.raises(ProjectError, match="OWNER_LOCK_ACTUAL_FILE_INVALID"):
        verify_pinned_owner_api_files(fake)
