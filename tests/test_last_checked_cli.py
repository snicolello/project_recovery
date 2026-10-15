"""CLI seams for synthetic last-checked evidence; GhTransport.get never uses network."""
import contextlib
import importlib.util
import io
import json
import unittest
from unittest import mock

from reliance_cases import QUERY, REPO, make_env
import authority as au
import last_checked
import packet as pk
import recover
import recipe
import rederive

SPEC = importlib.util.spec_from_file_location("capture_last_checked_cli", REPO / "scripts/capture_last_checked.py")
capture_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture_cli)


class LastCheckedCliTests(unittest.TestCase):
    def setUp(self):
        self.env = make_env(packets=False)
        self.addCleanup(self.env.close)
        self.m = self.env.m
        self.bundle = self.m.state_dir / "capture.json"

    def capture(self, output=None):
        snapshots = au.SnapshotTransport(REPO / "fixtures/github-snapshots")
        with mock.patch.object(au.GhTransport, "get", lambda _, host, path: snapshots.get(host, path)):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = capture_cli.main(["--manifest", str(self.m.path), "--vault-root", str(self.env.root),
                                         "--project", "cobalt", "--out", str(output or self.bundle)])
        return code, json.loads(stdout.getvalue())

    def test_capture_cli_creates_new_bundle_and_prints_independent_pin(self):
        code, result = self.capture()
        self.assertEqual(code, 0, result)
        self.assertEqual(result["decisions"], 1)
        history = last_checked.Replay(self.bundle, result["bundle_sha256"])
        self.assertEqual(history.read(self.m, "cobalt")["status"], "historical")
        before = self.bundle.read_bytes()
        code, result = self.capture()
        self.assertEqual(code, 1)
        self.assertIn("already exists", result["error"])
        self.assertEqual(self.bundle.read_bytes(), before)

    def test_invalid_capture_destination_is_refused_before_network(self):
        with mock.patch.object(au.GhTransport, "get", side_effect=AssertionError("unexpected network")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = capture_cli.main(["--manifest", str(self.m.path), "--vault-root", str(self.env.root),
                                         "--project", "cobalt", "--out", str(self.env.root / "capture.json")])
        self.assertEqual(code, 1)
        self.assertIn("outside source roots", json.loads(stdout.getvalue())["error"])
        self.assertFalse((self.env.root / "capture.json").exists())

    def test_assemble_and_validate_cli_use_their_own_history_and_pin(self):
        code, captured = self.capture()
        self.assertEqual(code, 0)
        common = ["--manifest", str(self.m.path), "--vault-root", str(self.env.root),
                  "--state-dir", str(self.m.state_dir), "--verifier", "offline",
                  "--last-checked", str(self.bundle), "--last-checked-sha256", captured["bundle_sha256"]]
        with mock.patch.object(recover, "McpSession", lambda _: rederive.VaultSession(self.m, "cobalt", [])):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = recover.main(["assemble", *common, "--project", "cobalt", "--query", QUERY])
        self.assertEqual(code, 0)
        packet = json.loads(stdout.getvalue())
        self.assertEqual(packet["fields"]["accepted_decisions"]["decisions"], [])
        self.assertEqual(packet["last_checked"]["status"], "historical")
        path = self.m.state_dir / "packet.json"
        path.write_bytes(pk.compact(packet))
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = recover.main(["validate", *common, "--packet", str(path), "--hits", "packet"])
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["result"], "equal_to_rederived")

    def test_cli_requires_bundle_and_pin_together(self):
        for flag, value in (("--last-checked", str(self.bundle)), ("--last-checked-sha256", "0" * 64)):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
                recover.main(["assemble", "--manifest", str(self.m.path), "--project", "cobalt",
                              "--query", QUERY, flag, value])
            self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
