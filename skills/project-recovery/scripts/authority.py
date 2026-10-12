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
    if not isinstance(kinds, list) or not all(isinstance(k, dict) and k.get("kind") in KINDS
                                              and isinstance(k.get("body_marker"), str) and k["body_marker"]
                                              for k in kinds):
        errors.append(f"authority_policy.acceptance_records: each entry needs kind in {KINDS} and a body_marker")
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
        return self.fetch_path(ref.host, ref.api_path)

    def fetch_path(self, host: str, api_path: str) -> dict:
        """One serial request per distinct API path per run."""
        key = (host, api_path)
        if key in self._cache:
            cached = self._cache[key]
            if isinstance(cached, Unavailable):
                raise cached
            return cached
        if not self._lock.acquire(blocking=False):
            raise ConcurrentRequest("verification requests run serially; a request is already in flight")
        start = time.perf_counter_ns()
        try:
            body = self.transport.get(host, api_path)
            self.requests.append((api_path, start, time.perf_counter_ns(), "read"))
            self._cache[key] = body
            return body
        except Unavailable as exc:
            self.requests.append((api_path, start, time.perf_counter_ns(), "unavailable"))
            self._cache[key] = exc
            raise
        finally:
            self._lock.release()

    def verify(self, reference_text: str | None, project: str, binding: str | None,
               note_names: tuple = (), note_digest: str | None = None) -> dict:
        """Verification result for the reference text cited by a decision note (null keys omitted).

        The record must be bound to the citing note: a pull merge or review must name the
        note's declared ``binding`` (``source_revision``) as its subject revision; an issue
        comment must contain the acceptance marker followed by one of ``note_names`` (the
        note's permalink or title). A record that satisfies everything else but is not bound
        to this note is ``invalid``.

        Content binding (owner review 2026-10-12): the approval text itself must carry
        ``<marker> <note name> sha256:<digest>``, where the digest is SHA-256 of the citing
        note's exact bytes. The approval text is the comment body, the review body, or, for a
        merge, the merge commit message (read with a second serial request). A changed note,
        a different note, or a missing digest makes the result ``invalid`` with
        ``mismatch`` set (reported as ``approved_text_mismatch``)."""
        return {k: v for k, v in self._verify(reference_text, project, binding, tuple(note_names),
                                              note_digest).items() if v is not None}

    def approval_text(self, ref: Reference, body: dict, rec: dict) -> str | None:
        """The approver-authored text that names what was accepted, or None if unreadable."""
        if ref.kind == "issue_comment":
            return rec.get("body", "")
        if ref.kind == "pull_review":
            return body.get("body") or ""
        sha = rec.get("revision")
        if not sha:
            return None
        commit = self.fetch_path(ref.host, f"repos/{ref.repo}/git/commits/{sha}")
        if not isinstance(commit, dict) or commit.get("sha") != sha:
            return None
        return commit.get("message") or ""

    def _verify(self, reference_text: str | None, project: str, binding: str | None, note_names: tuple,
                note_digest: str | None) -> dict:
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
        if ref.kind != "issue_comment" and rec.get("accepted") is not True:
            problems.append("pull request not merged" if ref.kind == "pull_merge" else "review state is not APPROVED")
        if rec.get("actor") not in repo["approvers"]:
            problems.append(f"actor {rec.get('actor')!r} is not an approver for {ref.repo}")
        if not rec.get("revision"):
            problems.append("record carries no revision")
        if ref.kind != "issue_comment":
            if binding is None:
                problems.append("the note declares no source_revision, so the record cannot be bound to it")
            elif rec.get("subject_revision") != binding:
                problems.append(f"record subject revision {rec.get('subject_revision')!r} differs from the note's {binding!r}")
        base.update({"revision": rec.get("revision"), "actor": rec.get("actor")})
        if problems:
            return {**base, "result": "invalid", "reason": "; ".join(problems)}
        # Content binding: only checked once the record is otherwise a valid acceptance.
        try:
            text = self.approval_text(ref, body, rec)
        except Unavailable as exc:
            return {**base, "result": "unavailable", "reason": f"approval text unreadable: {exc}"}
        marker = rule.get("body_marker") or ""
        approved = [(m.group(1).strip(), m.group(2)) for m in
                    re.finditer(re.escape(marker) + r" +(.+?) +sha256:([0-9a-f]{64})(?![0-9a-f])", text or "")] \
            if marker else []
        names = [n for n in note_names if n]
        if not any(name in names and digest == note_digest for name, digest in approved):
            shown = [f"{n} sha256:{d[:12]}" for n, d in approved] or ["no marker with a digest"]
            current = f"{names} sha256:{(note_digest or 'unknown')[:12]}"
            return {**base, "result": "invalid", "mismatch": True,
                    "approved_digest": next((d for n, d in approved if n in names), approved[0][1] if approved else None),
                    "note_digest": note_digest,
                    "reason": (f"approved_text_mismatch: the record approves {shown}; this note is {current}; "
                               "the record is not bound to this note's content")}
        return {**base, "result": "verified", "verified_at": now(), "approved_digest": note_digest,
                "reason": f"{ref.kind} read from {ref.host}/{ref.repo} at revision {rec['revision']}; "
                          f"approves this note's bytes (sha256:{note_digest[:12]})"}

    def summary(self) -> dict:
        overlaps = any(b[1] < a[2] for a, b in zip(self.requests, self.requests[1:]))
        return {"transport": self.transport_name, "serial": True, "requests": len(self.requests),
                "overlapping_requests": overlaps,
                "unavailable": sum(1 for r in self.requests if r[3] == "unavailable")}


# The binding rule -----------------------------------------------------------
# The one place that decides when an acceptance record is bound to a decision note.
# recipe.Assembler.decisions (assembly) and recipe.make_rechecker (validate) both call
# verify_decision; SKILL.md and the manifest notes point here instead of restating it.
# ``note`` is a parsed note: {"front": {key: line}, "body": [line]}, each line with
# ``.text`` and ``.number``.

def _value(line) -> str:
    return line.text.partition(":")[2].strip()


def reference_line(policy: dict, note: dict):
    """The line that names a note's acceptance record: the policy's frontmatter key, else the
    first body line starting with one of its labels."""
    spec = policy.get("reference", {})
    key = spec.get("frontmatter_key")
    if key and key in note["front"]:
        return note["front"][key]
    for label in spec.get("body_labels", []):
        for line in note["body"]:
            if line.text.startswith(label):
                return line
    return None


def binding_value(policy: dict, note: dict) -> str | None:
    """The note's declared subject revision (``source_revision``), if any."""
    key = (policy.get("binding") or {}).get("frontmatter_key")
    line = note["front"].get(key) if key else None
    return _value(line) if line else None


def note_names(note: dict, source: str) -> tuple[str, ...]:
    """Names the approval text may use for the note: permalink and title (else the file stem)."""
    names = [_value(note["front"][k]) for k in ("permalink", "title")
             if k in note["front"] and _value(note["front"][k])]
    return tuple(names) or (Path(source).stem,)


def record_citations(policy: dict, notes: dict[str, dict]) -> dict[str, list[str]]:
    """Acceptance record URL -> every note (source) in the project whose reference line cites it."""
    out: dict[str, list[str]] = {}
    for source, note in sorted(notes.items()):
        line = reference_line(policy, note)
        ref = parse_reference(line.text) if line else None
        if ref is not None:
            out.setdefault(ref.url, []).append(source)
    return out


def verify_decision(verifier: "Verifier", note: dict, source: str, project: str, note_digest: str | None,
                    citations: dict[str, list[str]], reference_text: str | None = None) -> dict:
    """When is a record bound to a decision? All of these must hold:

    1. the note cites exactly one record (``reference_line``), from a repository allowlisted
       for ``project``, of a configured kind, made by an approver, and accepting
       (merged, APPROVED, or an approver's comment);
    2. for a pull merge or review, the note declares ``source_revision`` and it equals the
       record's subject revision;
    3. the record's approval text (comment body, review body, or merge commit message)
       contains ``<body_marker> <note permalink or title> sha256:<note_digest>``, where
       ``note_digest`` is SHA-256 of the note's current, validated bytes; otherwise
       ``invalid`` with ``mismatch`` (``approved_text_mismatch``);
    4. no other note in the project cites the same record (``citations``); otherwise
       ``invalid`` for every citing note.

    ``reference_text`` overrides the reference line's text (assembly passes the cited,
    receipt-validated text). Requests go through the serial ``Verifier``."""
    line = reference_line(verifier.policy, note)
    text = reference_text if reference_text is not None else (line.text if line else None)
    v = verifier.verify(text, project, binding_value(verifier.policy, note), note_names(note, source), note_digest)
    others = [c for c in citations.get(v.get("reference"), []) if c != source]
    if not others or v["result"] == "not_referenced":
        return v
    return {**v, "result": "invalid",
            "reason": f"the record is also cited by {others}; one acceptance record binds one note"}


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
