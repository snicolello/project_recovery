"""McpSession start and cleanup (project_recovery #14). No Node or QMD needed: a missing
QMD is simulated by pointing the client at a path that does not exist, and a successful
start uses a minimal stand-in MCP server written to a temporary directory.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import gc
import io
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import qmd_client  # noqa: E402

FAKE_SERVER = r'''
import json, sys
tools = sys.argv[1].split(",")
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2025-11-25", "capabilities": {}, "serverInfo": {"name": "fake"}}
    elif msg["method"] == "tools/list":
        result = {"tools": [{"name": n} for n in tools]}
    else:
        result = {"structuredContent": {"collections": []}}
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
'''


class Boom(RuntimeError):
    pass


class SessionStartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state"
        self.opened: list = []
        real_open = open

        def tracking_open(*a, **k):
            f = real_open(*a, **k)
            self.opened.append(f)
            return f

        patcher = mock.patch.object(qmd_client, "open", tracking_open, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for f in self.opened:
            f.close()
        self.tmp.cleanup()

    def assert_no_open_handle(self, session: qmd_client.McpSession):
        self.assertIsNone(session._stderr)
        self.assertIsNone(session._proc)
        self.assertTrue(all(f.closed for f in self.opened), "an acquired stderr handle was left open")

    def fake_server(self, tools: list[str]) -> list[str]:
        script = Path(self.tmp.name) / "fake_mcp.py"
        script.write_text(FAKE_SERVER, encoding="utf-8")
        return [sys.executable, "-I", str(script), ",".join(tools)]

    def test_absent_qmd_raises_original_error_and_leaves_no_handle(self):
        session = qmd_client.McpSession(self.state)
        with mock.patch.object(qmd_client, "QMD_BIN", Path(self.tmp.name) / "missing" / "qmd"), \
                warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            with self.assertRaisesRegex(qmd_client.QmdError, "QMD not installed"):
                with session:
                    self.fail("session entered without QMD")
            self.assert_no_open_handle(session)
            del session
            gc.collect()
        self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_raising_command_propagates_the_same_exception(self):
        session = qmd_client.McpSession(self.state)
        original = Boom("command discovery failed")
        with mock.patch.object(qmd_client, "_command", side_effect=original):
            with self.assertRaises(Boom) as ctx:
                session.__enter__()
        self.assertIs(ctx.exception, original)
        self.assert_no_open_handle(session)

    def test_failed_process_start_closes_handle_and_preserves_exception(self):
        session = qmd_client.McpSession(self.state)
        original = FileNotFoundError("node vanished")
        with mock.patch.object(qmd_client, "_command", return_value=[sys.executable]), \
                mock.patch.object(qmd_client.subprocess, "Popen", side_effect=original):
            with self.assertRaises(FileNotFoundError) as ctx:
                session.__enter__()
        self.assertIs(ctx.exception, original)
        self.assertEqual(len(self.opened), 1, "the stderr log is opened once the command resolves")
        self.assert_no_open_handle(session)

    def test_failing_cleanup_does_not_mask_the_start_failure(self):
        proc = mock.Mock()
        proc.stdout = io.StringIO("")
        proc.terminate.side_effect = OSError("cannot terminate")
        session = qmd_client.McpSession(self.state, timeout=0.2)
        with mock.patch.object(qmd_client, "_command", return_value=[sys.executable]), \
                mock.patch.object(qmd_client.subprocess, "Popen", return_value=proc):
            with self.assertRaisesRegex(qmd_client.QmdError, "timeout waiting for initialize"):
                session.__enter__()
        proc.terminate.assert_called_once()
        self.assert_no_open_handle(session)

    def test_disallowed_tools_close_session(self):
        session = qmd_client.McpSession(self.state, timeout=20)
        with mock.patch.object(qmd_client, "_command", return_value=self.fake_server(
                sorted(qmd_client.ALLOWED_TOOLS) + ["write"])):
            with self.assertRaisesRegex(qmd_client.QmdError, "outside the read-only allowlist"):
                session.__enter__()
        self.assert_no_open_handle(session)

    def test_normal_entry_and_cleanup(self):
        session = qmd_client.McpSession(self.state, timeout=20)
        with mock.patch.object(qmd_client, "_command", return_value=self.fake_server(
                sorted(qmd_client.ALLOWED_TOOLS))):
            with session as s:
                self.assertIs(s, session)
                proc, log = s._proc, s._stderr
                self.assertIsNone(proc.poll(), "server running inside the session")
                self.assertFalse(log.closed)
                self.assertEqual(s.advertised, sorted(qmd_client.ALLOWED_TOOLS))
                self.assertEqual(s.status(), {"collections": []})
        self.assertIsNotNone(proc.poll(), "server stopped on exit")
        self.assertTrue(log.closed)
        proc.stdin.close()  # the subprocess pipes are outside #14's scope
        proc.stdout.close()
        self.assertEqual(self.opened, [log])
        self.assert_no_open_handle(session)
        session.close()  # closing again is harmless
        self.assert_no_open_handle(session)


if __name__ == "__main__":
    unittest.main()
