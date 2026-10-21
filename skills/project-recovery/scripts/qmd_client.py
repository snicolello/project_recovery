"""Read-only access to a pinned QMD 2.8.3 install.

Two surfaces, both deliberately narrow:

* ``McpSession`` speaks MCP (Model Context Protocol) over stdio to ``qmd mcp`` and
  will only call the four read tools QMD advertises: query, get, multi_get, status.
  If the server advertises any other tool the session refuses to start.
* ``index_cli`` runs the two QMD CLI commands needed to build and refresh the
  derived index (``collection add`` and ``update``). They write only to the index
  and configuration under the instance's state directory, never to source roots.

Nothing here exposes write, edit, move, delete or shell capability to a caller.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[3]
QMD_BIN = REPO / "qmd-runtime" / "node_modules" / "@tobilu" / "qmd" / "bin" / "qmd"
QMD_PACKAGE = QMD_BIN.parent.parent / "package.json"

ALLOWED_TOOLS = frozenset({"query", "get", "multi_get", "status"})
COLLECTION_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
# QMD collection config keys that would make `qmd update` run shell commands.
HOOK_KEY = re.compile(r"^\s*(update|update_command|pull|pre_update|post_update)\s*:", re.MULTILINE)
PROTOCOL_VERSION = "2025-11-25"


class QmdError(RuntimeError):
    pass


def installed_version() -> str | None:
    try:
        return json.loads(QMD_PACKAGE.read_text(encoding="utf-8")).get("version")
    except OSError:
        return None


def _command() -> list[str]:
    node = shutil.which("node")
    if not node:
        raise QmdError("node not found on PATH (Node 24 required)")
    if not QMD_BIN.exists():
        raise QmdError("QMD not installed; run: python -I skills/project-recovery/scripts/install_qmd.py")
    return [node, str(QMD_BIN)]


def environment(state_dir: Path) -> dict[str, str]:
    """Isolated environment: config, index and caches under state_dir; offline; CPU only."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("QMD_") and k != "INDEX_PATH"}
    env.update({
        "QMD_CONFIG_DIR": str(state_dir / "config"),
        "INDEX_PATH": str(state_dir / "index.sqlite"),
        "XDG_CONFIG_HOME": str(state_dir / "xdg-config"),
        "XDG_CACHE_HOME": str(state_dir / "xdg-cache"),
        "QMD_FORCE_CPU": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "NO_COLOR": "1",
    })
    return env


def check_cli_args(args: list[str]) -> None:
    """Exact-argv allowlist: ``update`` alone, or ``collection add <abs dir> --name <name>``."""
    if args == ["update"]:
        return
    if (len(args) == 5 and args[:2] == ["collection", "add"] and args[3] == "--name"
            and not args[2].startswith("-") and Path(args[2]).is_absolute()
            and COLLECTION_NAME.match(args[4])):
        return
    raise QmdError(f"QMD CLI invocation not allowlisted: {args!r}")


def check_no_hooks(state_dir: Path) -> None:
    """Refuse to run when the instance config defines any per-collection update hook."""
    config = state_dir / "config" / "index.yml"
    if config.exists() and HOOK_KEY.search(config.read_text(encoding="utf-8", errors="replace")):
        raise QmdError(f"QMD config defines an update hook; refusing to run: {config.name}")


def index_cli(state_dir: Path, args: list[str], timeout: float = 120) -> str:
    """Run an allowlisted index-maintenance command; returns stdout."""
    check_cli_args(args)
    check_no_hooks(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        _command() + args, env=environment(state_dir), cwd=state_dir, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        raise QmdError(f"qmd {' '.join(args[:2])} failed ({result.returncode}): {result.stderr[-500:]}")
    return result.stdout


class McpSession:
    """Synchronous MCP stdio client restricted to QMD's four read tools."""

    def __init__(self, state_dir: Path, timeout: float = 60):
        self.state_dir = state_dir
        self.timeout = timeout
        self.calls: list[str] = []
        self.advertised: list[str] = []
        self._seq = 0
        self._responses: queue.Queue = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._stderr = None

    def __enter__(self) -> "McpSession":
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Resolve the command before acquiring anything: a missing Node or QMD raises here
        # with no handle open (project_recovery #14).
        command = _command() + ["mcp"]
        self._stderr = open(self.state_dir / "mcp-stderr.log", "a", encoding="utf-8")
        try:
            self._proc = subprocess.Popen(
                command, env=environment(self.state_dir), cwd=self.state_dir,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            reader = threading.Thread(target=self._read, args=(self._proc.stdout,), daemon=True)
            reader.start()
            self._reader = reader
            self._rpc("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                     "clientInfo": {"name": "project-recovery", "version": "0.1"}})
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = self._rpc("tools/list").get("tools", [])
            self.advertised = sorted(t["name"] for t in tools)
            if set(self.advertised) != ALLOWED_TOOLS:
                raise QmdError(f"QMD advertises tools outside the read-only allowlist: {self.advertised}")
        except BaseException:
            try:
                self.close()
            except Exception:  # noqa: BLE001 - the original failure is the one to report
                pass
            raise
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Stop the server, then release its pipes and the stderr log, each even if an earlier step fails."""
        try:
            if self._proc is not None:
                proc, self._proc = self._proc, None
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except OSError:
                    proc.kill()  # terminate failed: still try to stop it, then report why
                    raise
                finally:
                    self._close_pipes(proc)
        finally:
            if self._stderr is not None:
                stderr, self._stderr = self._stderr, None
                stderr.close()

    def _close_pipes(self, proc: subprocess.Popen) -> None:
        # project_recovery #25. The reader thread owns stdout and closes it at end of file:
        # closing it here could block on, or break, a read in progress.
        reader, self._reader = self._reader, None
        try:
            if proc.stdin is not None:
                try:
                    proc.stdin.close()
                except BrokenPipeError:
                    pass  # the server has gone; as in subprocess.Popen.__exit__
        finally:
            if reader is not None:
                reader.join(timeout=5)
            elif proc.stdout is not None:
                proc.stdout.close()  # no reader was started

    def _read(self, stdout) -> None:
        # The pipe is passed in: close() may clear self._proc before this thread first runs.
        with stdout:
            for line in stdout:
                try:
                    self._responses.put(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def _send(self, msg: dict) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._seq += 1
        msg = {"jsonrpc": "2.0", "id": self._seq, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
        while True:
            try:
                response = self._responses.get(timeout=self.timeout)
            except queue.Empty:
                raise QmdError(f"timeout waiting for {method}") from None
            if response.get("id") != self._seq:
                continue
            if "error" in response:
                raise QmdError(f"{method}: {response['error']}")
            return response.get("result", {})

    def call_tool(self, name: str, arguments: dict) -> dict:
        if name not in ALLOWED_TOOLS:
            raise QmdError(f"tool not in read-only allowlist: {name}")
        self.calls.append(name)
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    # Convenience wrappers -------------------------------------------------

    def status(self) -> dict:
        return self.call_tool("status", {}).get("structuredContent", {})

    def query(self, text: str, collection: str, limit: int = 10) -> list[dict]:
        """Lexical-only query scoped to one collection; reranking off."""
        result = self.call_tool("query", {
            "searches": [{"type": "lex", "query": text}],
            "collections": [collection], "limit": limit, "rerank": False,
        })
        return list(result.get("structuredContent", {}).get("results", []))

    def get(self, path: str, from_line: int | None = None, max_lines: int | None = None) -> str | None:
        """Raw text of a document or line range, or None when QMD reports it missing."""
        args: dict = {"file": path, "lineNumbers": False}
        if from_line is not None:
            args["fromLine"] = from_line
        if max_lines is not None:
            args["maxLines"] = max_lines
        result = self.call_tool("get", args)
        if result.get("isError"):
            return None
        for item in result.get("content", []):
            if item.get("type") == "resource":
                return item["resource"].get("text", "")
        return None

    def multi_get(self, pattern: str, max_bytes: int = 1_000_000) -> dict[str, str]:
        """Map of collection-relative path to raw text for every indexed document matching pattern."""
        result = self.call_tool("multi_get", {"pattern": pattern, "lineNumbers": False, "maxBytes": max_bytes})
        out: dict[str, str] = {}
        for item in result.get("content", []):
            if item.get("type") == "resource":
                uri = item["resource"].get("uri", "")
                path = unquote(uri[len("qmd://"):]) if uri.startswith("qmd://") else uri
                out[path] = item["resource"].get("text", "")
        return out
