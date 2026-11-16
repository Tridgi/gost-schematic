import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui" / "integration"))
from project_wire_bridge import BridgeError, apply_snapshot, model, to_snapshot


def fixture(name):
    return json.loads((ROOT / "ui" / "fixtures" / name).read_text(encoding="utf-8"))


class ProjectWireBridgeTests(unittest.TestCase):
    def test_full_e695_unrouted_and_identity(self):
        doc = fixture("tl494-source-e695-v2.gscad.json")
        snap = to_snapshot(doc)
        self.assertEqual((len(snap["components"]), len(snap["nets"]),
                          sum(len(n["members"]) for n in snap["nets"]), len(snap["wires"])),
                         (23, 15, 62, 0))
        original = model.digest(doc)
        out = apply_snapshot(doc, snap, expected_sha=original)
        self.assertEqual(model.digest(out), original)
        self.assertEqual(len(out["project"]["sheets"][0]["graphics"]), 2)

    def test_toy_roundtrip(self):
        doc = fixture("toy-v2.gscad.json")
        out = apply_snapshot(doc, to_snapshot(doc), expected_sha=model.digest(doc))
        self.assertEqual(model.digest(out), model.digest(doc))

    def test_stale_sha_denied(self):
        doc = fixture("toy-v2.gscad.json")
        with self.assertRaisesRegex(BridgeError, "STALE_PROJECT_SHA"):
            apply_snapshot(doc, to_snapshot(doc), expected_sha="0"*64)

    def test_wrong_net_member_denied_without_modifying_source(self):
        doc = fixture("toy-v2.gscad.json")
        initial = model.digest(doc)
        snap = to_snapshot(doc)
        snap["nets"][0]["members"].reverse()
        with self.assertRaisesRegex(BridgeError, "SOURCE_TOPOLOGY_CHANGED"):
            apply_snapshot(doc, snap, expected_sha=initial)
        self.assertEqual(model.digest(doc), initial)

    def test_physical_pin_drift_1um_denied(self):
        doc = fixture("toy-v2.gscad.json")
        snap = to_snapshot(doc)
        snap["components"][0]["pins"][0]["local_at_um"][0] += 1
        with self.assertRaisesRegex(BridgeError, "SOURCE_TOPOLOGY_CHANGED"):
            apply_snapshot(doc, snap, expected_sha=model.digest(doc))

    def test_wrong_original_name_denied(self):
        doc = fixture("tl494-source-e695-v2.gscad.json")
        snap = to_snapshot(doc)
        snap["nets"][0]["literal_source_name"] = "FAKE_SOURCE_NET"
        with self.assertRaisesRegex(BridgeError, "SOURCE_TOPOLOGY_CHANGED"):
            apply_snapshot(doc, snap, expected_sha=model.digest(doc))

    def test_unknown_sheet_denied(self):
        with self.assertRaisesRegex(BridgeError, "UNKNOWN_SHEET"):
            to_snapshot(fixture("toy-v2.gscad.json"), sheet_id="missing")


if __name__ == "__main__":
    unittest.main()
