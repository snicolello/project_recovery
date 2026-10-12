"""Serial GitHub acceptance verification (recovery contract section 4), release R2.

A decision note may cite one acceptance record: a pull request merge, a pull request
review, or an issue comment. The manifest's ``authority_policy`` names which
repositories are allowlisted for which project, which record kinds count, who may
accept, and how a note names its record. This module turns a cited reference into a
verification result:

    verified        the record was read, serially, and satisfies the policy;
                    ``revision`` and ``verified_at`` are recorded
    unavailable     the record could not be read now (offline, rate-limited,
                    permission, no snapshot); provenance is kept
    invalid         the reference or the record fails the policy
    not_referenced  the note cites no acceptance record

Only ``verified`` may promote a decision candidate to an accepted decision. Every
other result leaves the decision a candidate with ``authority_state`` ``unverified``
(a record is referenced) or ``local_only`` (none is).

Transports share one interface, ``get(host, api_path) -> dict``, and raise
``Unavailable`` when the record cannot be read:

    OfflineTransport   never reads anything; every referenced record is unavailable
    SnapshotTransport  reads fixed JSON files laid out as <dir>/<host>/<api_path>.json,
                       holding the same response bodies the GitHub REST API returns
    GhTransport        runs ``gh api <api_path>`` (read-only GET); optional, used only
                       by the live smoke test, never by the gates

Requests run one at a time: the verifier holds a non-reentrant lock around every
transport call and refuses a second concurrent request instead of queueing it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

RESULTS = ("verified", "unavailable", "invalid", "not_referenced")
STATES = frozenset({"verified", "unverified", "local_only", "superseded"})
KINDS = ("pull_merge", "pull_review", "issue_comment")
TRANSPORTS = ("offline", "snapshot", "gh")

REF = re.compile(
    r"https://(?P<host>[A-Za-z0-9.-]+)/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/"
    r"(?P<what>pull|issues)/(?P<number>\d+)"
    r"(?:#(?P<frag>pullrequestreview|issuecomment)-(?P<id>\d+))?(?![\w/#-])")


class Unavailable(RuntimeError):
    """The record could not be read now. Never a reason to promote."""


class ConcurrentRequest(RuntimeError):
    """A second verification request was attempted while one was in flight."""


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# References ----------------------------------------------------------------

@dataclass(frozen=True)
class Reference:
    url: str
    host: str
    repo: str          # owner/name
    kind: str
    number: int
    record_id: int | None

    @property
    def api_path(self) -> str:
        if self.kind == "pull_merge":
            return f"repos/{self.repo}/pulls/{self.number}"
        if self.kind == "pull_review":
            return f"repos/{self.repo}/pulls/{self.number}/reviews/{self.record_id}"
        return f"repos/{self.repo}/issues/comments/{self.record_id}"


def parse_reference(text: str) -> Reference | None:
    """The single acceptance-record URL in ``text``, or None (none, or more than one)."""
    found = list(REF.finditer(text))
    if len(found) != 1:
        return None
    m = found[0]
    if m.group("frag") == "pullrequestreview":
        if m.group("what") != "pull":
            return None
        kind = "pull_review"
    elif m.group("frag") == "issuecomment":
        kind = "issue_comment"
    else:
        if m.group("what") != "pull":
            return None  # a bare issue is not an acceptance record
        kind = "pull_merge"
    return Reference(m.group(0), m.group("host").lower(), f"{m.group('owner')}/{m.group('repo')}",
                     kind, int(m.group("number")), int(m.group("id")) if m.group("id") else None)


# Transports ----------------------------------------------------------------

class OfflineTransport:
    name = "offline"

    def get(self, host: str, api_path: str) -> dict:
        raise Unavailable("offline: no verifier transport configured for this run")


class SnapshotTransport:
    """Fixed response bodies on disk, one file per API path. Missing file = unavailable."""
    name = "snapshot"

    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()

    def get(self, host: str, api_path: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or ".." in api_path.split("/"):
            raise Unavailable("snapshot: invalid host or path")
        path = self.directory / host / (api_path + ".json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise Unavailable(f"snapshot: no record captured for {host}/{api_path}") from None
        except (OSError, ValueError) as exc:
            raise Unavailable(f"snapshot: unreadable record: {exc}") from None


class GhTransport:
    """Read-only ``gh api`` GET through the user's existing gh session. Optional; not used by gates."""
    name = "gh"

    def __init__(self, timeout: float = 30):
        self.timeout = timeout

    def get(self, host: str, api_path: str) -> dict:
        gh = shutil.which("gh")
        if not gh:
            raise Unavailable("gh: GitHub CLI not found")
        cmd = [gh, "api", "--method", "GET", api_path]
        if host != "github.com":
            cmd[2:2] = ["--hostname", host]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise Unavailable("gh: request timed out") from None
        if r.returncode != 0:
            detail = (r.stderr or r.stdout).strip().splitlines()
            raise Unavailable(f"gh: {detail[-1][:200] if detail else f'exit {r.returncode}'}")
        try:
            return json.loads(r.stdout)
        except ValueError:
            raise Unavailable("gh: response was not JSON") from None


def make_transport(kind: str, snapshot_dir: Path | None = None):
    if kind == "offline":
        return OfflineTransport()
    if kind == "snapshot":
        if snapshot_dir is None:
            raise ValueError("snapshot transport needs a snapshot directory")
        return SnapshotTransport(snapshot_dir)
    if kind == "gh":
        return GhTransport()
    raise ValueError(f"unknown verifier transport: {kind!r}")


# Normalization -------------------------------------------------------------

def _login(value) -> str | None:
    return value.get("login") if isinstance(value, dict) else None


def normalize(ref: Reference, body: dict) -> dict:
    """Reduce a REST response body to the fields the policy checks."""
    if not isinstance(body, dict):
        return {}
    if ref.kind == "pull_merge":
        return {"number": body.get("number"), "accepted": body.get("merged") is True,
                "actor": _login(body.get("merged_by")), "revision": body.get("merge_commit_sha"),
                "subject_revision": (body.get("head") or {}).get("sha") if isinstance(body.get("head"), dict) else None,
                "acted_at": body.get("merged_at"), "html_url": body.get("html_url")}
    if ref.kind == "pull_review":
        return {"number": ref.number if body.get("id") == ref.record_id else None,
                "accepted": body.get("state") == "APPROVED", "actor": _login(body.get("user")),
                "revision": body.get("node_id"), "subject_revision": body.get("commit_id"),
                "acted_at": body.get("submitted_at"), "html_url": body.get("html_url")}
    # issue_comment: the revision changes when the comment is edited.
    node, updated = body.get("node_id"), body.get("updated_at")
    issue_url = body.get("issue_url") or ""
    return {"number": ref.number if body.get("id") == ref.record_id and issue_url.endswith(f"/{ref.number}") else None,
            "accepted": None, "body": body.get("body") or "", "actor": _login(body.get("user")),
            "revision": f"{node}@{updated}" if node and updated else None, "subject_revision": None,
            "acted_at": updated, "html_url": body.get("html_url")}


# Policy --------------------------------------------------------------------

POLICY_KEYS = ("local_claims", "verifier", "acceptance_records", "repositories", "reference")


def validate_policy(policy: dict, projects: list[str]) -> list[str]:
    errors = []
    if not isinstance(policy, dict):
        return ["authority_policy must be an object"]
    for key in POLICY_KEYS:
        if key not in policy:
            errors.append(f"authority_policy: missing {key}")
    if errors:
        return errors
    if policy["local_claims"] != "decision_candidates":
        errors.append("authority_policy.local_claims must be decision_candidates (R2, ruling B)")
    v = policy["verifier"]
    if not isinstance(v, dict) or v.get("transport") not in TRANSPORTS or v.get("serial") is not True:
        errors.append(f"authority_policy.verifier needs transport in {TRANSPORTS} and serial true")
    kinds = policy["acceptance_records"]
    if not isinstance(kinds, list) or not all(isinstance(k, dict) and k.get("kind") in KINDS for k in kinds):
        errors.append(f"authority_policy.acceptance_records: each entry needs kind in {KINDS}")
    for i, r in enumerate(policy["repositories"] if isinstance(policy["repositories"], list) else [None]):
        if not (isinstance(r, dict) and isinstance(r.get("host"), str) and isinstance(r.get("repo"), str)
                and r["repo"].count("/") == 1 and isinstance(r.get("projects"), list)
                and isinstance(r.get("approvers"), list) and r["approvers"]):
            errors.append(f"authority_policy.repositories[{i}] needs host, owner/repo, projects, approvers")
            continue
        unknown = [p for p in r["projects"] if p not in projects]
        if unknown:
            errors.append(f"authority_policy.repositories[{i}]: unknown projects {unknown}")
    ref = policy["reference"]
    if not isinstance(ref, dict) or not (ref.get("frontmatter_key") or ref.get("body_labels")):
        errors.append("authority_policy.reference needs frontmatter_key or body_labels")
    return errors


@dataclass
class Verifier:
    """Checks acceptance references against the policy, one request at a time."""
    policy: dict
    transport: object
    requests: list = field(default_factory=list)   # (api_path, start_ns, end_ns, outcome)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _cache: dict = field(default_factory=dict)

    @property
    def transport_name(self) -> str:
        return getattr(self.transport, "name", type(self.transport).__name__)

    def repository(self, ref: Reference, project: str) -> dict | None:
        for r in self.policy.get("repositories", []):
            if r["host"].lower() == ref.host and r["repo"].lower() == ref.repo.lower() and project in r["projects"]:
                return r
        return None

    def kind_rule(self, kind: str) -> dict | None:
        return next((k for k in self.policy.get("acceptance_records", []) if k.get("kind") == kind), None)

    def fetch(self, ref: Reference) -> dict:
        """One serial request per distinct record per run."""
        key = (ref.host, ref.api_path)
        if key in self._cache:
            cached = self._cache[key]
            if isinstance(cached, Unavailable):
                raise cached
            return cached
        if not self._lock.acquire(blocking=False):
            raise ConcurrentRequest("verification requests run serially; a request is already in flight")
        start = time.perf_counter_ns()
        try:
            body = self.transport.get(ref.host, ref.api_path)
            self.requests.append((ref.api_path, start, time.perf_counter_ns(), "read"))
            self._cache[key] = body
            return body
        except Unavailable as exc:
            self.requests.append((ref.api_path, start, time.perf_counter_ns(), "unavailable"))
            self._cache[key] = exc
            raise
        finally:
            self._lock.release()

    def verify(self, reference_text: str | None, project: str, binding: str | None) -> dict:
        """Verification result for the reference text cited by a decision note (null keys omitted)."""
        return {k: v for k, v in self._verify(reference_text, project, binding).items() if v is not None}

    def _verify(self, reference_text: str | None, project: str, binding: str | None) -> dict:
        base = {"transport": self.transport_name, "reference": None, "kind": None,
                "revision": None, "verified_at": None, "actor": None}
        if reference_text is None:
            return {**base, "result": "not_referenced", "reason": "the note cites no acceptance record"}
        ref = parse_reference(reference_text)
        if ref is None:
            return {**base, "result": "invalid",
                    "reason": "reference is not exactly one pull, review or issue-comment URL"}
        base.update({"reference": ref.url, "kind": ref.kind})
        repo = self.repository(ref, project)
        if repo is None:
            return {**base, "result": "invalid",
                    "reason": f"{ref.host}/{ref.repo} is not allowlisted for project {project!r}; no request made"}
        rule = self.kind_rule(ref.kind)
        if rule is None:
            return {**base, "result": "invalid", "reason": f"record kind {ref.kind} is not configured; no request made"}
        try:
            body = self.fetch(ref)
        except Unavailable as exc:
            return {**base, "result": "unavailable", "reason": str(exc)}
        rec = normalize(ref, body)
        problems = []
        if rec.get("number") != ref.number:
            problems.append("record does not match the cited number or id")
        if ref.kind == "issue_comment":
            marker = rule.get("body_marker")
            if not marker or marker not in rec.get("body", ""):
                problems.append(f"comment does not contain the acceptance marker {marker!r}")
        elif rec.get("accepted") is not True:
            problems.append("pull request not merged" if ref.kind == "pull_merge" else "review state is not APPROVED")
        if rec.get("actor") not in repo["approvers"]:
            problems.append(f"actor {rec.get('actor')!r} is not an approver for {ref.repo}")
        if not rec.get("revision"):
            problems.append("record carries no revision")
        if binding is not None and rec.get("subject_revision") != binding:
            problems.append(f"record subject revision {rec.get('subject_revision')!r} differs from the note's {binding!r}")
        base.update({"revision": rec.get("revision"), "actor": rec.get("actor")})
        if problems:
            return {**base, "result": "invalid", "reason": "; ".join(problems)}
        return {**base, "result": "verified", "verified_at": now(),
                "reason": f"{ref.kind} read from {ref.host}/{ref.repo} at revision {rec['revision']}"}

    def summary(self) -> dict:
        overlaps = any(b[1] < a[2] for a, b in zip(self.requests, self.requests[1:]))
        return {"transport": self.transport_name, "serial": True, "requests": len(self.requests),
                "overlapping_requests": overlaps,
                "unavailable": sum(1 for r in self.requests if r[3] == "unavailable")}


def state_for(result: str) -> str:
    """Authority state of a decision given its verification result."""
    return {"verified": "verified", "not_referenced": "local_only"}.get(result, "unverified")


def build_verifier(policy: dict, base_dir: Path, transport: str | None = None,
                   snapshot_dir: Path | None = None) -> Verifier:
    """Verifier from the manifest policy; ``transport``/``snapshot_dir`` override it."""
    v = policy.get("verifier") or {}
    kind = transport or v.get("transport", "offline")
    snaps = snapshot_dir
    if snaps is None and v.get("snapshot_dir"):
        snaps = (base_dir / v["snapshot_dir"]).resolve()
    return Verifier(policy, make_transport(kind, snaps))
