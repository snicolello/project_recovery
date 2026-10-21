"""McpSession start and cleanup (project_recovery #14, #25). No Node or QMD needed: a missing
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

    def assert_pipes_closed(self, proc):
        self.assertTrue(proc.stdin.closed, "the server's stdin pipe was left open")
        self.assertTrue(proc.stdout.closed, "the server's stdout pipe was left open")

    def assert_no_resource_warning(self, caught):
        self.assertEqual([str(w.message) for w in caught if issubclass(w.category, ResourceWarning)], [])

    def track_popen(self) -> list:
        """Start real processes as usual, keeping each one so its pipes can be checked after cleanup."""
        started: list = []
        real_popen = qmd_client.subprocess.Popen

        def tracking_popen(*a, **k):
            started.append(real_popen(*a, **k))
            return started[-1]

        patcher = mock.patch.object(qmd_client.subprocess, "Popen", tracking_popen)
        patcher.start()
        self.addCleanup(patcher.stop)
        return started

    def fake_proc(self) -> mock.Mock:
        proc = mock.Mock()
        proc.stdin = io.StringIO()
        proc.stdout = io.StringIO("")
        return proc

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
        proc.kill.assert_called_once()
        proc.stdin.close.assert_called_once()
        self.assertTrue(proc.stdout.closed)
        self.assert_no_open_handle(session)

    def test_failing_pipe_cleanup_does_not_mask_the_start_failure(self):
        proc = self.fake_proc()
        proc.stdin = mock.Mock()
        proc.stdin.close.side_effect = OSError("cannot close stdin")
        session = qmd_client.McpSession(self.state, timeout=0.2)
        with mock.patch.object(qmd_client, "_command", return_value=[sys.executable]), \
                mock.patch.object(qmd_client.subprocess, "Popen", return_value=proc):
            with self.assertRaisesRegex(qmd_client.QmdError, "timeout waiting for initialize"):
                session.__enter__()
        proc.stdin.close.assert_called_once()
        self.assertTrue(proc.stdout.closed, "stdout is released even when closing stdin fails")
        self.assert_no_open_handle(session)

    def test_pipes_close_when_the_reader_never_started(self):
        proc = self.fake_proc()
        original = RuntimeError("can't start new thread")
        session = qmd_client.McpSession(self.state)
        with mock.patch.object(qmd_client, "_command", return_value=[sys.executable]), \
                mock.patch.object(qmd_client.subprocess, "Popen", return_value=proc), \
                mock.patch.object(qmd_client.threading.Thread, "start", side_effect=original):
            with self.assertRaises(RuntimeError) as ctx:
                session.__enter__()
        self.assertIs(ctx.exception, original)
        self.assert_pipes_closed(proc)
        self.assert_no_open_handle(session)

    def test_broken_stdin_on_close_is_not_an_error(self):
        proc = self.fake_proc()
        proc.stdin = mock.Mock()
        proc.stdin.close.side_effect = BrokenPipeError("server gone")
        tools = {"tools": [{"name": n} for n in sorted(qmd_client.ALLOWED_TOOLS)]}
        session = qmd_client.McpSession(self.state)
        with mock.patch.object(qmd_client, "_command", return_value=[sys.executable]), \
                mock.patch.object(qmd_client.subprocess, "Popen", return_value=proc), \
                mock.patch.object(qmd_client.McpSession, "_rpc", return_value=tools), \
                mock.patch.object(qmd_client.McpSession, "_send"):
            with session:
                pass
        proc.stdin.close.assert_called_once()
        self.assertTrue(proc.stdout.closed)
        self.assert_no_open_handle(session)

    def test_close_kills_when_terminate_fails_and_still_closes_the_log(self):
        proc = mock.Mock()
        proc.terminate.side_effect = OSError("cannot terminate")
        proc.kill.side_effect = OSError("cannot kill")
        session = qmd_client.McpSession(self.state)
        session._proc = proc
        session._stderr = open(self.state.parent / "log.txt", "a", encoding="utf-8")
        log = session._stderr
        with self.assertRaisesRegex(OSError, "cannot kill"):
            session.close()
        proc.kill.assert_called_once()
        self.assertTrue(log.closed)
        self.assert_no_open_handle(session)

    def test_disallowed_tools_close_session(self):
        started = self.track_popen()
        session = qmd_client.McpSession(self.state, timeout=20)
        with mock.patch.object(qmd_client, "_command", return_value=self.fake_server(
                sorted(qmd_client.ALLOWED_TOOLS) + ["write"])), \
                warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            with self.assertRaisesRegex(qmd_client.QmdError, "outside the read-only allowlist"):
                session.__enter__()
            self.assert_no_open_handle(session)
            [proc] = started
            self.assertIsNotNone(proc.poll(), "server stopped after the refused start")
            self.assert_pipes_closed(proc)
            del proc
            started.clear()
            gc.collect()
        self.assert_no_resource_warning(caught)

    def test_normal_entry_and_cleanup(self):
        session = qmd_client.McpSession(self.state, timeout=20)
        with mock.patch.object(qmd_client, "_command", return_value=self.fake_server(
                sorted(qmd_client.ALLOWED_TOOLS))), \
                warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            with session as s:
                self.assertIs(s, session)
                proc, log = s._proc, s._stderr
                self.assertIsNone(proc.poll(), "server running inside the session")
                self.assertFalse(log.closed)
                self.assertFalse(proc.stdin.closed)
                self.assertEqual(s.advertised, sorted(qmd_client.ALLOWED_TOOLS))
                self.assertEqual(s.status(), {"collections": []})
            self.assertIsNotNone(proc.poll(), "server stopped on exit")
            self.assertTrue(log.closed)
            self.assert_pipes_closed(proc)
            self.assertEqual(self.opened, [log])
            self.assert_no_open_handle(session)
            session.close()  # closing again is harmless
            self.assert_no_open_handle(session)
            del proc, s
            gc.collect()
        self.assert_no_resource_warning(caught)


if __name__ == "__main__":
    unittest.main()
