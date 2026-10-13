"""Run one synthetic, read-only transition rehearsal with isolated derived state.

This is advance preparation for owner review, not an R4/R5 release gate. It copies
the hash-pinned fixture notes into a throwaway pilot vault, builds a QMD index in
``.qmd/``, assembles and requery-validates one packet, and records the checks in a
JSON report. The recovery surface remains read-only: only the index-maintenance
allowlist writes, and it writes outside the source root.

Usage: python -I scripts/rehearse_transition.py --run-id NAME
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
PRODUCT_SCRIPTS = REPO / "skills" / "project-recovery" / "scripts"
sys.path.insert(0, str(PRODUCT_SCRIPTS))

import packet as pk  # noqa: E402
import qmd_client  # noqa: E402
import recipe  # noqa: E402
import rederive  # noqa: E402
from qmd_client import ALLOWED_TOOLS, McpSession, QmdError, installed_version  # noqa: E402
from receipts import SourceError, safe_resolve  # noqa: E402

FIXTURE_ROOT = REPO / "fixtures" / "synthetic-vault"
FIXTURE_HASHES = REPO / "fixtures" / "synthetic-vault-hashes.json"
MANIFEST = REPO / "manifest" / "fixture-vault.json"
SNAPSHOTS = REPO / "fixtures" / "github-snapshots"
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MUTATING_TOOLS = ("write", "edit", "move", "delete", "shell", "update", "embed")


class RehearsalError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_hashes(path: Path = FIXTURE_HASHES) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise RehearsalError("fixture hash manifest must be a non-empty object")
    return {str(name).replace("\\", "/"): str(digest) for name, digest in raw.items()}


def verify_tree(root: Path, expected: dict[str, str]) -> dict[str, str]:
    actual = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(name for name in set(actual) & set(expected) if actual[name] != expected[name])
        raise RehearsalError(
            f"source tree differs from fixture manifest; missing={missing}, extra={extra}, changed={changed}"
        )
    return actual


def _within(child: Path, parent: Path) -> bool:
    child_text = os.path.normcase(os.path.realpath(child))
    parent_text = os.path.normcase(os.path.realpath(parent))
    return child_text == parent_text or child_text.startswith(parent_text.rstrip(os.sep) + os.sep)


def assert_isolated(vault: Path, state: Path, output: Path) -> None:
    paths = {"vault": vault.resolve(), "state": state.resolve(), "output": output.resolve()}
    for left_name, left in paths.items():
        for right_name, right in paths.items():
            if left_name >= right_name:
                continue
            if _within(left, right) or _within(right, left):
                raise RehearsalError(f"{left_name} and {right_name} paths overlap")
    cache = state / "xdg-cache"
    index = state / "index.sqlite"
    if _within(cache, vault) or _within(index, vault):
        raise RehearsalError("QMD index or cache overlaps the source root")


def repository_path(path: Path) -> str:
    """Return a stable repository-relative path for retained public evidence."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO.resolve()).as_posix()
    except ValueError as exc:
        raise RehearsalError("rehearsal evidence path is outside the repository") from exc


def run_paths(run_id: str) -> dict[str, Path]:
    return {
        "output": REPO / ".scratch" / "transition-rehearsal" / run_id,
        "vault": REPO / "runtime-vaults" / "transition-rehearsal" / run_id,
        "state": recipe.STATE_BASE / f"transition-rehearsal-{run_id}",
    }


def require_fresh_run_paths(paths: dict[str, Path]) -> None:
    existing = sorted(name for name, path in paths.items() if path.exists())
    if existing:
        raise RehearsalError(
            "run paths already exist; preserve them and choose a fresh --run-id: " + ", ".join(existing)
        )


def copy_verified_vault(source: Path, destination: Path, expected: dict[str, str]) -> None:
    if destination.exists():
        raise RehearsalError(f"pilot vault already exists; choose a fresh --run-id: {destination}")
    verify_tree(source, expected)
    destination.mkdir(parents=True)
    for locator, digest in expected.items():
        source_file = safe_resolve(source, locator)
        destination_file = destination.joinpath(*locator.split("/"))
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        destination_file.write_bytes(source_file.read_bytes())
        if sha256_file(destination_file) != digest:
            raise RehearsalError(f"copy verification failed: {locator}")
    verify_tree(destination, expected)


def trust_root_probes(output: Path) -> dict:
    root = output / "trust-probe" / "root"
    outside = output / "trust-probe" / "outside"
    root.mkdir(parents=True)
    outside.mkdir(parents=True)
    (outside / "outside.md").write_text("synthetic outside content\n", encoding="utf-8")

    try:
        safe_resolve(root, "../outside/outside.md")
    except SourceError:
        traversal = "rejected"
    else:
        raise RehearsalError("parent traversal escaped the trust root")

    link = root / "escape"
    link_kind = "symlink"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        if sys.platform != "win32":
            link_result = "not_available"
        else:
            import _winapi

            link_kind = "junction"
            try:
                _winapi.CreateJunction(str(outside), str(link))
            except OSError:
                link_result = "not_available"
            else:
                link_result = "created"
    else:
        link_result = "created"

    if link_result == "created":
        try:
            safe_resolve(root, "escape/outside.md")
        except SourceError:
            link_result = "rejected"
        else:
            raise RehearsalError(f"{link_kind} escaped the trust root")
    return {"parent_traversal": traversal, "link_kind": link_kind, "link_escape": link_result}


def state_directory_probe(vault: Path, state: Path) -> dict[str, str]:
    try:
        recipe.check_state_dir(state, vault)
    except recipe.RecipeError as exc:
        return {"result": "rejected", "error": str(exc)}
    return {"result": "accepted"}


def configuration_probes(output: Path) -> dict:
    # Both paths are beneath .qmd, so only the vault-overlap rule can reject this
    # candidate. This avoids a false pass caused by the broader .qmd boundary rule.
    overlap_vault = recipe.STATE_BASE / "transition-overlap-probes" / output.name / "vault"
    overlap_vault.mkdir(parents=True)
    inside_source = overlap_vault / "derived-state"
    state_in_source = state_directory_probe(overlap_vault, inside_source)
    expected_state_error = "state dir must not equal, contain, or sit inside the vault root"
    if state_in_source != {"result": "rejected", "error": expected_state_error}:
        raise RehearsalError(
            "vault-overlap state probe did not return the required rejection: "
            f"{state_in_source!r}"
        )
    if inside_source.exists():
        raise RehearsalError("rejected in-source state probe wrote to the source root")

    hook_state = output / "hook-probe"
    (hook_state / "config").mkdir(parents=True)
    (hook_state / "config" / "index.yml").write_text(
        "collections:\n  atlas:\n    path: synthetic\n    update: forbidden-command\n", encoding="utf-8"
    )
    try:
        qmd_client.check_no_hooks(hook_state)
    except QmdError as exc:
        update_hook = {"result": "rejected", "error": str(exc)}
    else:
        raise RehearsalError("QMD update hook was accepted")
    expected_hook_error = "QMD config defines an update hook; refusing to run: index.yml"
    if update_hook != {"result": "rejected", "error": expected_hook_error}:
        raise RehearsalError(f"update-hook probe returned an unexpected rejection: {update_hook!r}")
    return {
        "state_dir_inside_source": state_in_source,
        "state_probe_vault": repository_path(overlap_vault),
        "update_hook": update_hook,
    }


def poisoned_advertisement_probe(output: Path) -> dict:
    class FakeProcess:
        stdin = None
        stdout = []

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            return None

    class PoisonedSession(McpSession):
        def _rpc(self, method: str, params: dict | None = None) -> dict:
            if method == "tools/list":
                names = sorted(qmd_client.ALLOWED_TOOLS | {"write"})
                return {"tools": [{"name": name} for name in names]}
            return {}

        def _send(self, msg: dict) -> None:
            return None

    state = output / "poisoned-advertisement-probe"
    with mock.patch.object(qmd_client, "_command", return_value=["qmd-probe-stub"]), \
            mock.patch.object(qmd_client.subprocess, "Popen", return_value=FakeProcess()), \
            mock.patch.object(qmd_client.threading, "Thread", FakeThread):
        try:
            with PoisonedSession(state) as session:
                advertised = sorted(session.advertised)
        except QmdError as exc:
            error = str(exc)
            prefix = "QMD advertises tools outside the read-only allowlist:"
            if not error.startswith(prefix) or "write" not in error:
                raise RehearsalError(f"poisoned advertisement returned an unexpected rejection: {error}") from exc
            return {"result": "rejected", "error": error}
    return {"result": "accepted", "advertised": advertised}


def reject_mutating_tools(session: McpSession) -> list[str]:
    refused = []
    calls_before = list(session.calls)
    for name in MUTATING_TOOLS:
        try:
            session.call_tool(name, {})
        except QmdError:
            refused.append(name)
        else:
            raise RehearsalError(f"mutating tool was callable: {name}")
    if session.calls != calls_before:
        raise RehearsalError("refused tool names reached the MCP transport")
    return refused


def _tree_observation(path: Path, label: str) -> dict:
    """Observe metadata without persisting home-directory names or contents."""
    if not path.exists():
        return {"path": label, "exists": False, "entries": 0, "bytes": 0, "fingerprint": None}
    digest = hashlib.sha256()
    entries = 0
    total_bytes = 0

    def visit(directory: Path, prefix: str = "") -> None:
        nonlocal entries, total_bytes
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise RehearsalError(
                f"cannot observe default QMD path metadata: {label}: {type(exc).__name__}"
            ) from exc
        for child in children:
            relative = f"{prefix}/{child.name}" if prefix else child.name
            try:
                metadata = child.stat(follow_symlinks=False)
                is_directory = child.is_dir(follow_symlinks=False)
                is_file = child.is_file(follow_symlinks=False)
            except OSError as exc:
                raise RehearsalError(
                    f"cannot observe default QMD path metadata: {label}: {type(exc).__name__}"
                ) from exc
            kind = "directory" if is_directory else "file" if is_file else "other"
            digest.update(f"{relative}\0{kind}\0{metadata.st_size}\0{metadata.st_mtime_ns}\n".encode())
            entries += 1
            total_bytes += metadata.st_size if is_file else 0
            if is_directory:
                visit(Path(child.path), relative)

    visit(path)
    return {
        "path": label,
        "exists": True,
        "entries": entries,
        "bytes": total_bytes,
        "fingerprint": digest.hexdigest(),
    }


def observe_default_home(home: Path | None = None) -> dict[str, dict]:
    root = Path.home() if home is None else home
    return {
        "cache": _tree_observation(root / ".cache" / "qmd", "~/.cache/qmd"),
        "config": _tree_observation(root / ".config" / "qmd", "~/.config/qmd"),
    }


def assert_default_home_unchanged(before: dict[str, dict], after: dict[str, dict]) -> dict:
    changed = sorted(name for name in before if before.get(name) != after.get(name))
    if changed:
        raise RehearsalError("default QMD home paths changed: " + ", ".join(changed))
    return {"result": "pass", "targets": sorted(before)}


def observe_isolated_storage(state: Path, vault: Path) -> dict:
    targets = {
        "index": state / "index.sqlite",
        "cache": state / "xdg-cache",
        "config": state / "config",
    }
    if not targets["index"].is_file():
        raise RehearsalError("isolated QMD index is missing")
    if not targets["cache"].is_dir():
        raise RehearsalError("isolated QMD cache directory is missing")
    if not targets["config"].is_dir():
        raise RehearsalError("isolated QMD config directory is missing")
    for name, path in targets.items():
        if not _within(path, state):
            raise RehearsalError(f"isolated QMD {name} is outside the state root")
        if _within(path, vault) or _within(vault, path):
            raise RehearsalError(f"isolated QMD {name} overlaps the vault root")
    return {
        "result": "pass",
        "state": repository_path(state),
        "index": {"path": "index.sqlite", "exists": True, "bytes": targets["index"].stat().st_size},
        "cache": _tree_observation(targets["cache"], "xdg-cache"),
        "config": _tree_observation(targets["config"], "config"),
    }


def snippet_line_probe(hits: list[dict], vault: Path) -> dict:
    target = next((hit for hit in hits if hit.get("file") == "atlas/Queue Archive.md"), None)
    if target is None:
        return {"result": "not_observed", "reason": "Queue Archive was not returned"}
    rows = []
    for rendered in str(target.get("snippet", "")).splitlines():
        match = re.match(r"^(\d+): (.*)$", rendered.rstrip("\r"))
        if match:
            rows.append((int(match.group(1)), match.group(2)))
    heading = next(((label, text) for label, text in rows if text == "# Queue Archive"), None)
    source_lines = (vault / "atlas" / "Queue Archive.md").read_text(encoding="utf-8").splitlines()
    actual_heading = next((number for number, text in enumerate(source_lines, 1) if text == "# Queue Archive"), None)
    match_line = next((number for number, text in enumerate(source_lines, 1)
                       if "Atlas queue originally used Redis" in text), None)
    if heading is None or actual_heading is None or match_line is None:
        return {"result": "not_observed", "reason": "expected synthetic lines were absent"}
    return {
        "result": "reproduced" if heading[0] != actual_heading else "not_reproduced",
        "file": target["file"],
        "match_line_field": target.get("line"),
        "actual_match_line": match_line,
        "rendered_heading_label": heading[0],
        "actual_heading_line": actual_heading,
        "snippet": target.get("snippet"),
    }


def run(run_id: str) -> tuple[int, dict]:
    if not RUN_ID.fullmatch(run_id):
        raise RehearsalError("--run-id must be 1-64 letters, digits, dots, underscores or hyphens")
    paths = run_paths(run_id)
    output, vault, state = paths["output"], paths["vault"], paths["state"]
    require_fresh_run_paths(paths)
    assert_isolated(vault, state, output)

    started = time.perf_counter()
    report: dict = {
        "schema": "project-recovery-transition-rehearsal-v1",
        "status": "failed",
        "advance_preparation_only": True,
        "run_id": run_id,
        "started_at": utc_now(),
        "source_revision": os.environ.get("PROJECT_RECOVERY_REVISION", "record-with-git-rev-parse"),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
            "node_qmd_required": "Node 24; QMD 2.8.3",
        },
        "paths": {
            "fixture_root": repository_path(FIXTURE_ROOT),
            "pilot_vault": repository_path(vault),
            "state": repository_path(state),
            "index": repository_path(state / "index.sqlite"),
            "cache": repository_path(state / "xdg-cache"),
            "output": repository_path(output),
        },
        "checks": {},
    }
    expected = expected_hashes()
    fixture_before = verify_tree(FIXTURE_ROOT, expected)
    default_home_before = observe_default_home()
    output.mkdir(parents=True)
    try:
        report["checks"]["fixture_before"] = {"result": "pass", "files": len(fixture_before)}
        copy_verified_vault(FIXTURE_ROOT, vault, expected)
        pilot_before = verify_tree(vault, expected)
        report["checks"]["isolated_paths"] = "pass"
        report["checks"]["trust_root"] = trust_root_probes(output)
        report["checks"]["configuration"] = configuration_probes(output)
        poisoned_probe = poisoned_advertisement_probe(output)
        report["checks"]["poisoned_mcp_advertisement"] = poisoned_probe
        if poisoned_probe["result"] != "rejected":
            raise RehearsalError("MCP session accepted a poisoned tool advertisement")
        if installed_version() != "2.8.3":
            raise RehearsalError(f"expected existing QMD 2.8.3, found {installed_version()!r}")

        manifest = recipe.load_manifest(MANIFEST, vault_root=vault, state_dir=state)
        refresh_started = time.perf_counter()
        generation = recipe.refresh(manifest)
        # A lexical-only run may not populate a cache. Materialize the redirected
        # cache root so the retained report can still prove its isolated location.
        (state / "xdg-cache").mkdir(parents=True, exist_ok=True)
        storage_observation = observe_isolated_storage(state, vault)
        report["timings_seconds"] = {"refresh": round(time.perf_counter() - refresh_started, 3)}
        assemble_started = time.perf_counter()
        with McpSession(state) as session:
            refused = reject_mutating_tools(session)
            snippet_probe = snippet_line_probe(session.query("Atlas queue", "atlas", 10), vault)
            verifier = recipe.make_verifier(manifest, "snapshot", SNAPSHOTS)
            packet = recipe.assemble(manifest, "atlas", "Atlas project", session, None, verifier)
            advertised = session.advertised
            calls = session.calls
        report["timings_seconds"]["assemble"] = round(time.perf_counter() - assemble_started, 3)
        packet_path = output / "atlas-packet.json"
        packet_bytes = pk.compact(packet) + b"\n"
        packet_path.write_bytes(packet_bytes)

        validate_started = time.perf_counter()
        validation = rederive.validate(manifest, packet_bytes, "snapshot", SNAPSHOTS, "requery")
        report["timings_seconds"]["validate_requery"] = round(time.perf_counter() - validate_started, 3)
        if validation.get("result") != "equal_to_rederived" or validation.get("failures") != 0:
            raise RehearsalError("validate --hits requery did not return equal_to_rederived")

        pilot_after = verify_tree(vault, expected)
        if pilot_before != pilot_after:
            raise RehearsalError("pilot source changed during the recovery run")
        report["generation"] = generation["generation"]
        report["documents"] = len(generation["files"])
        report["packet"] = {
            "path": repository_path(packet_path),
            "sha256": hashlib.sha256(packet_bytes).hexdigest(),
            "status": packet.get("status"),
            "accepted_decisions": len(packet["fields"]["accepted_decisions"]["decisions"]),
        }
        report["checks"].update({
            "pilot_source_unchanged": {"result": "pass", "files": len(pilot_after)},
            "isolated_storage": storage_observation,
            "mcp_advertised_tools": advertised,
            "mcp_calls": calls,
            "mutating_tools_refused": refused,
            "qmd_snippet_line_labels": snippet_probe,
            "validation": {"result": validation["result"], "failures": validation["failures"],
                           "hits": "requery"},
        })
        if set(advertised) != ALLOWED_TOOLS:
            raise RehearsalError("advertised MCP surface differs from the read-only allowlist")
        report["status"] = "pass"
        code = 0
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    finally:
        report["checks"]["default_home_before"] = default_home_before
        try:
            default_home_after = observe_default_home()
            report["checks"]["default_home_after"] = default_home_after
            report["checks"]["default_home_unchanged"] = assert_default_home_unchanged(
                default_home_before, default_home_after
            )
        except Exception as exc:
            report["checks"]["default_home_unchanged"] = {"result": "fail", "error": str(exc)}
            report["status"] = "failed"
            code = 1
        try:
            fixture_after = verify_tree(FIXTURE_ROOT, expected)
            report["checks"]["fixture_after"] = {"result": "pass", "files": len(fixture_after)}
        except Exception as exc:
            report["checks"]["fixture_after"] = {"result": "fail", "error": str(exc)}
            report["status"] = "failed"
            code = 1
        report["finished_at"] = utc_now()
        report.setdefault("timings_seconds", {})["total"] = round(time.perf_counter() - started, 3)
        output.mkdir(parents=True, exist_ok=True)
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return code, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="unique label for retained rehearsal artifacts")
    args = parser.parse_args(argv)
    try:
        code, report = run(args.run_id)
    except Exception as exc:
        report = {"schema": "project-recovery-transition-rehearsal-v1", "status": "failed",
                  "advance_preparation_only": True, "error": f"{type(exc).__name__}: {exc}"}
        code = 1
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
