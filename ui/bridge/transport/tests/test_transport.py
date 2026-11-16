"""Transport-level negative tests independent of UI/model availability."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cad_transport", ROOT / "worker.py")
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def request(id="a", op="hello", args=None):
    return {"v": 1, "id": id, "op": op, "args": args if args is not None else {}}


def exchange_raw(payload: bytes):
    proc = subprocess.run([sys.executable, "-u", str(ROOT / "worker.py")], input=payload,
                          capture_output=True, timeout=8, check=True)
    return [json.loads(line) for line in proc.stdout.splitlines()], proc.stderr


class TransportTests(unittest.TestCase):
    def test_correlated_stream(self):
        items = [request("first"), request("second", "unit_roundtrip", {"x_um": "1", "y_um": "-2"}), request("third")]
        got, stderr = exchange_raw(b"".join(json.dumps(x).encode() + b"\n" for x in items))
        self.assertEqual([x["id"] for x in got], ["first", "second", "third"])
        self.assertEqual(got[1]["result"]["y_um"], "-2")
        self.assertEqual(stderr, b"")

    def test_int64_and_invalid_numeric(self):
        a = worker.process(json.dumps(request(args={}, op="unit_roundtrip")).encode())
        self.assertEqual(a["error"]["code"], "INVALID_UNIT")
        maxes = {"x_um": "9223372036854775807", "y_um": "-9223372036854775808"}
        good = worker.process(json.dumps(request(op="unit_roundtrip", args=maxes)).encode())
        self.assertEqual(good["result"], maxes)
        for bad in ["-0", "01", "+1", "1.0", " 1", True, 1, "9223372036854775808", "9"*5000]:
            with self.subTest(bad=repr(bad)[:30]):
                got = worker.process(json.dumps(request(op="unit_roundtrip", args={"x_um": bad, "y_um": "1"})).encode())
                self.assertFalse(got["ok"])

    def test_invalid_utf8_and_duplicate_members(self):
        samples = [b"\xff", b'{"v":1,"v":1,"id":"x","op":"hello","args":{}}',
                   b'{"v":1,"id":"x","op":"hello","args":{"a":1,"a":2}}',
                   b'{"v":1,"id":"x","op":"unit_roundtrip","args":{"x_um":NaN}}']
        for body in samples:
            with self.subTest(body=body):
                self.assertEqual(worker.process(body)["error"]["code"], "INVALID_JSON")

    def test_version_bool_and_unknown_keys(self):
        for v in [True, 1.0, 0, 2]:
            with self.subTest(version=v):
                x = request(); x["v"] = v
                self.assertEqual(worker.process(json.dumps(x).encode())["error"]["code"], "UNSUPPORTED_VERSION")
        x = request(); x["extra"] = 5
        self.assertEqual(worker.process(json.dumps(x).encode())["error"]["code"], "INVALID_REQUEST")

    def test_traversal_and_shell_rejection(self):
        for path in ["../../secret.json", "C:\\secret.json", "foo\\bar.json", "x/../y.json", "/etc/passwd"]:
            with self.subTest(path=path):
                x = worker.process(json.dumps(request(op="render_symbol", args={"symbol": path})).encode())
                self.assertEqual(x["error"]["code"], "INVALID_SYMBOL")
        x = worker.process(json.dumps(request(op="shell", args={"cmd": "rm -rf /"})).encode())
        self.assertEqual(x["error"]["code"], "UNKNOWN_OPERATION")

    def test_not_falsely_wired(self):
        for op in ["position_edit", "render_svg", "export_png"]:
            with self.subTest(op=op):
                self.assertEqual(worker.process(json.dumps(request(op=op)).encode())["error"]["code"], "NOT_WIRED")
        for op in ["validate_document", "source_snapshot", "verify_net", "engine_projection"]:
            self.assertEqual(
                worker.process(json.dumps(request(op=op)).encode())["error"]["code"],
                "INVALID_REQUEST",
            )
        self.assertFalse(worker.process(json.dumps(request()).encode())["result"]["project_write"])

    def test_edit_cas_and_source_lock(self):
        rev_a, rev_b = "a" * 64, "b" * 64
        worker.validate_edit_guard(base_revision=rev_a, current_revision=rev_a,
                                   expected_topology_hash=rev_b, actual_topology_hash=rev_b)
        with self.assertRaises(worker.ProtocolError) as err:
            worker.validate_edit_guard(base_revision=rev_a, current_revision=rev_b,
                                       expected_topology_hash=rev_b, actual_topology_hash=rev_b)
        self.assertEqual(err.exception.code, "REVISION_CONFLICT")
        with self.assertRaises(worker.ProtocolError) as err:
            worker.validate_edit_guard(base_revision=rev_a, current_revision=rev_a,
                                       expected_topology_hash=rev_a, actual_topology_hash=rev_b)
        self.assertEqual(err.exception.code, "SOURCE_LOCKED")

    def test_oversize_line_recovers_framing(self):
        payload = b"x" * (worker.MAX_REQUEST + 31) + b"\n" + json.dumps(request("next")).encode() + b"\n"
        replies, _ = exchange_raw(payload)
        self.assertEqual([x["error"]["code"] if not x["ok"] else x["id"] for x in replies],
                         ["PAYLOAD_TOO_LARGE", "next"])

    def test_bad_line_does_not_kill_worker(self):
        replies, _ = exchange_raw(b"not json\n" + json.dumps(request("next")).encode() + b"\n")
        self.assertEqual(replies[0]["error"]["code"], "INVALID_JSON")
        self.assertTrue(replies[1]["ok"])

    def test_real_engine_gate(self):
        got = worker.process(json.dumps(request(op="check_symbol", args={"symbol": "resistors/fixed.json"})).encode())
        self.assertTrue(got["ok"] or got["error"]["code"] in {"ENGINE_UNAVAILABLE", "UNKNOWN_SYMBOL", "ENGINE_FAILURE"})


    def _fixture(self):
        """Only true #122 imported source is acceptable as an integration fixture."""
        filename = ROOT.parents[2] / "ui" / "fixtures" / "tl494-source-e695-v2.gscad.json"
        if not filename.is_file():
            if os.environ.get("GSCAD_REQUIRE_V2") == "1":
                self.fail("required ProjectFileV2 source fixture missing")
            self.skipTest("shared #122 model and source fixture not yet imported into this checkout")
        return json.loads(filename.read_text(encoding="utf-8"))

    def test_real_v2_source_snapshot_and_no_false_routed_claim(self):
        doc = self._fixture()
        payload = json.dumps(request("src1", "source_snapshot", {"document": doc})).encode()
        self.assertLess(len(payload), worker.MAX_REQUEST)
        result = worker.process(payload)
        self.assertTrue(result["ok"], result)
        data = result["result"]
        self.assertEqual(data["model"], "gscad-project")
        self.assertEqual(data["format_version"], 2)
        self.assertEqual(data["inventory"]["components"], 23)
        self.assertEqual(data["inventory"]["nets"], 15)
        self.assertEqual(data["inventory"]["memberships"], 62)
        self.assertEqual(data["inventory"]["wires"], 0)
        self.assertEqual(data["inventory"]["non_electrical_b"], 2)
        self.assertEqual(data["declared_routes"]["unrouted"], 15)
        self.assertFalse(data["electrical_approval"])
        self.assertFalse(data["project_write"])
        self.assertEqual(data["source_sha"], "e695c415fdced164b0e0c39c5249d030795a0aa6")

    def test_real_v2_net_reachability_and_workspace_hash(self):
        doc = self._fixture()
        snapshot = worker.process(json.dumps(
            request("src2", "validate_document", {"document": doc})
        ).encode())
        self.assertTrue(snapshot["ok"], snapshot)
        net = next(net for net in doc["project"]["nets"] if len(net["members"]) >= 2)
        verified = worker.process(json.dumps(request(
            "net1", "verify_net", {"document": doc, "net_id": net["id"]}
        )).encode())
        self.assertTrue(verified["ok"], verified)
        self.assertFalse(verified["result"]["reachability_complete"])
        self.assertFalse(verified["result"]["export_approved"])
        self.assertEqual(verified["result"]["declared_route_status"], "unrouted")
        doc["workspace"]["selected_ids"] = []
        doc["workspace"]["zoom_milli"] = 1750
        after = worker.process(json.dumps(
            request("src3", "source_snapshot", {"document": doc})
        ).encode())
        self.assertTrue(after["ok"], after)
        self.assertEqual(
            snapshot["result"]["project_sha256"], after["result"]["project_sha256"]
        )
        self.assertEqual(
            snapshot["result"]["source_topology_sha256"],
            after["result"]["source_topology_sha256"],
        )

    def test_real_v2_invalid_source_and_anchor_rejected(self):
        doc = self._fixture()
        doc["project"]["nets"][0]["members"][0]["physical_pin_number"] = "99999"
        bad = worker.process(json.dumps(request(
            "negative1", "source_snapshot", {"document": doc}
        )).encode())
        self.assertFalse(bad["ok"])
        self.assertIn(
            bad["error"]["code"],
            {"INVALID_PINREF", "SOURCE_TOPOLOGY_DRIFT", "SCHEMA_INVALID"},
        )
        self.assertNotIn("99999", bad["error"]["message"])
        self.assertEqual(bad["id"], "negative1")
        doc = self._fixture()
        first = next(iter(doc["project"]["nets"]))
        result = worker.process(json.dumps(request(
            "negative2", "verify_net", {"document": doc, "net_id": first["id"] + "_unknown"}
        )).encode())
        self.assertEqual(result["error"]["code"], "UNKNOWN_NET")


    def test_real_v2_wire_snapshot_and_cas_candidate_without_disk_write(self):
        doc = self._fixture()
        original = worker.process(json.dumps(
            request("v2snapshot", "wire_snapshot", {"document": doc})
        ).encode())
        self.assertTrue(original["ok"], original)
        snapshot = original["result"]["wiring_snapshot"]
        self.assertEqual(len(snapshot["components"]), 23)
        self.assertEqual(len(snapshot["nets"]), 15)
        self.assertEqual(len(snapshot["wires"]), 0)
        self.assertEqual(
            snapshot["source_topology_hash"],
            original["result"]["source_topology_sha256"],
        )
        self.assertFalse(original["result"]["committed"])
        params = {
            "document": doc, "candidate": snapshot,
            "expected_project_sha256": original["result"]["project_sha256"],
        }
        proposal = worker.process(json.dumps(
            request("v2candidate", "validate_wire_candidate", params)
        ).encode())
        self.assertTrue(proposal["ok"], proposal)
        self.assertFalse(proposal["result"]["committed"])
        self.assertEqual(
            proposal["result"]["project_sha256"], original["result"]["project_sha256"]
        )
        self.assertEqual(
            proposal["result"]["validated_document"]["project"]["provenance"],
            doc["project"]["provenance"],
        )

    def test_real_v2_wire_candidate_rejects_stale_sha_and_net_spoof(self):
        doc = self._fixture()
        original = worker.process(json.dumps(
            request("v2snapshot", "wire_snapshot", {"document": doc})
        ).encode())
        self.assertTrue(original["ok"], original)
        snapshot = original["result"]["wiring_snapshot"]
        params = {
            "document": doc,
            "candidate": snapshot,
            "expected_project_sha256": "0" * 64,
        }
        stale = worker.process(json.dumps(
            request("v2stale", "validate_wire_candidate", params)
        ).encode())
        self.assertEqual(stale["error"]["code"], "STALE_PROJECT_SHA")
        snapshot["nets"][0]["literal_source_name"] = "FORGED_NET"
        params["expected_project_sha256"] = original["result"]["project_sha256"]
        forged = worker.process(json.dumps(
            request("v2forged", "validate_wire_candidate", params)
        ).encode())
        self.assertEqual(forged["error"]["code"], "SOURCE_TOPOLOGY_CHANGED")
        self.assertEqual(doc["project"]["provenance"]["source_sha"],
                         "e695c415fdced164b0e0c39c5249d030795a0aa6")



    def test_ambiguous_model_dsu_vertex_ids_rejected_before_model_import(self):
        # Both triples are distinct, but the old #122 colon-joined DSU key is
        # 's:a:b:c' for BOTH. This negative test does not need jsonschema.
        doc = {"project": {"sheets": [
            {"id": "s", "wires": [
                {"id": "a:b", "vertices": [{"id": "c"}]},
                {"id": "a", "vertices": [{"id": "b:c"}]},
            ]},
        ]}}
        rejected = worker.process(json.dumps(request(
            "collision1", "verify_net", {"document": doc, "net_id": "N"}
        )).encode())
        self.assertEqual(rejected["id"], "collision1")
        self.assertEqual(rejected["error"]["code"], "AMBIGUOUS_VERTEX_ID")
        doc["project"]["sheets"][0]["wires"][1]["vertices"][0]["id"] = "safe"
        worker._reject_ambiguous_wire_vertices(doc)



    def test_project_v2_to_existing_python_engine_projection_is_read_only(self):
        doc = self._fixture()
        engine_adapter = ROOT.parents[2] / "ui" / "editor" / "src" / "model" / "engine_adapter.py"
        if not engine_adapter.is_file():
            if os.environ.get("GSCAD_REQUIRE_E3") == "1":
                self.fail("required canonical E3 engine adapter missing")
            self.skipTest("PR #134 E3 projection adapter not imported by MASTER")
        response = worker.process(json.dumps(
            request("e3projection", "engine_projection", {"document": doc})
        ).encode())
        self.assertTrue(response["ok"], response)
        projected = response["result"]
        self.assertEqual(projected["model"], "gscad-project")
        self.assertEqual(projected["component_count"], 23)
        self.assertEqual(projected["net_count"], 15)
        self.assertEqual(projected["authored_segment_count"], 0)
        self.assertEqual(projected["source_b_graphic_count"], 2)
        self.assertEqual(projected["incomplete_net_counts"], [15])
        self.assertTrue(projected["geometry_complete"])
        self.assertFalse(projected["rendering_catalog_verified"])
        self.assertFalse(projected["render_allowed"])
        self.assertFalse(projected["project_write"])



    def test_fixed_path_engine_module_registered_and_bad_source_fails_closed(self):
        """Regression: dataclass module resolution requires sys.modules at exec."""
        from dataclasses import is_dataclass

        doc = self._fixture()
        adapter = ROOT.parents[2] / "ui" / "editor" / "src" / "model" / "engine_adapter.py"
        if not adapter.is_file():
            if os.environ.get("GSCAD_REQUIRE_E3") == "1":
                self.fail("required engine adapter absent")
            self.skipTest("engine adapter not yet integrated")
        response = worker.process(json.dumps(request(
            "module-registered", "engine_projection", {"document": doc}
        )).encode())
        self.assertTrue(response["ok"], response)
        module = sys.modules.get("_gscad_engine_projection")
        self.assertIsNotNone(module, "fixed-path module must exist for dataclass")
        self.assertEqual(pathlib.Path(module.__file__).resolve(), adapter.resolve())
        self.assertTrue(is_dataclass(module.EngineProjectProjection))
        self.assertFalse(response["result"]["render_allowed"])
        self.assertFalse(response["result"]["project_write"])

        bad = json.loads(json.dumps(doc))
        bad["project"]["nets"][0]["members"][0]["physical_pin_number"] = "999"
        denied = worker.process(json.dumps(request(
            "source-forgery", "engine_projection", {"document": bad}
        )).encode())
        self.assertFalse(denied["ok"], denied)
        self.assertIn(denied["error"]["code"],
                      {"INVALID_PINREF", "SOURCE_TOPOLOGY_DRIFT", "SCHEMA_INVALID"})
        self.assertNotEqual(denied["error"]["code"], "INTERNAL")
        self.assertEqual(sys.modules["_gscad_engine_projection"].__file__, str(adapter))


    def test_native_blob_parser_uses_strict_real_v2_model_and_no_paths(self):
        doc = self._fixture()
        serialized = json.dumps(doc, ensure_ascii=False)
        response = worker.process(json.dumps(request(
            "native-open", "parse_document_blob", {"blob": serialized}
        )).encode())
        self.assertTrue(response["ok"], response)
        self.assertEqual(response["result"]["document"], doc)
        self.assertEqual(response["result"]["project_id"], doc["project"]["id"])
        self.assertEqual(response["result"]["source_sha"],
                         "e695c415fdced164b0e0c39c5249d030795a0aa6")
        self.assertFalse(response["result"]["project_write"])
        self.assertEqual(len(response["result"]["project_sha256"]), 64)
        bad_samples = [
            '{"format":"gscad-project","format":"sneaky"}',
            '{"project":{"id":"one","\\u0069d":"two"}}',
            serialized.replace('"format_version": 2', '"format_version": 2.0', 1),
            serialized.replace('"format_version": 2', '"format_version": NaN', 1),
        ]
        for bad in bad_samples:
            with self.subTest(payload=bad[:60]):
                denied = worker.process(json.dumps(request(
                    "native-denied", "parse_document_blob", {"blob": bad}
                )).encode())
                self.assertFalse(denied["ok"], denied)
                self.assertNotEqual(denied["error"]["code"], "INTERNAL")
        no_path = worker.process(json.dumps(request(
            "path-injection", "parse_document_blob",
            {"blob": serialized, "path": "C:\\\\Windows\\\\system.ini"}
        )).encode())
        self.assertEqual(no_path["error"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
