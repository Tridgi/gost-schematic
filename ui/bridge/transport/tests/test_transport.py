"""Transport-level negative tests independent of UI/model availability."""
import importlib.util
import json
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
        for op in ["source_snapshot", "position_edit", "verify_net", "render_svg", "export_png"]:
            with self.subTest(op=op):
                self.assertEqual(worker.process(json.dumps(request(op=op)).encode())["error"]["code"], "NOT_WIRED")
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


if __name__ == "__main__":
    unittest.main()
