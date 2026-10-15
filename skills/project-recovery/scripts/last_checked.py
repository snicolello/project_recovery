"""Historical GitHub evidence, never current acceptance (project_recovery #17).

Capture is called only by the separate governed capture utility. Replay only reads a
bundle pinned by a digest supplied independently by the operator, not by the packet.
That pin provides integrity relative to operator-controlled evidence, not authenticity.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import authority as au
import shape
from receipts import SourceError, read_source

FORMAT = "recovery-last-checked-v1"
STATEMENT = "Historical context only; history establishes no current acceptance. Later GitHub changes are unknown."
TRUST = "operator-controlled bundle and separately retained SHA-256; not proof of GitHub authenticity"
RAW_BODY = shape.Scalar("a JSON response object or array", lambda v: isinstance(v, (dict, list)))
POLICY = shape.Scalar("a policy object", lambda v: isinstance(v, dict))
CAPTURE_DECISION = shape.Obj({
    "source": shape.STR, "note_digest": shape.SHA, "note_names": shape.ListOf(shape.STR),
    "binding": shape.STR_OR_NULL, "reference": shape.STR, "kind": shape.enum(*au.KINDS),
    "revision": shape.STR, "actor": shape.STR, "last_checked_at": shape.TS,
})
BUNDLE = shape.Obj({
    "format": shape.enum(FORMAT), "project": shape.STR, "captured_via": shape.enum("gh"),
    "captured_at": shape.TS, "policy": POLICY, "policy_sha256": shape.SHA,
    "decisions": shape.ListOf(CAPTURE_DECISION, "source"),
    "responses": shape.ListOf(shape.Obj({"host": shape.STR, "api_path": shape.STR, "body": RAW_BODY})),
})


def encoded(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def policy_digest(policy: dict) -> str:
    """Acceptance policy identity; reading transport/location is not an acceptance rule."""
    return digest(encoded({k: v for k, v in policy.items() if k != "verifier"}))


def check_bundle(bundle: dict) -> None:
    problems: list = []
    try:
        BUNDLE.check(bundle, "bundle", problems)
    except shape._ProblemLimitReached:
        raise ValueError("malformed capture bundle: too many structural errors") from None
    if problems:
        raise ValueError("malformed capture bundle: " + problems[0]["field"])
    policy = bundle["policy"]
    projects = {bundle["project"]}
    for repo in policy.get("repositories", []):
        if isinstance(repo, dict) and isinstance(repo.get("projects"), list):
            projects.update(p for p in repo["projects"] if isinstance(p, str))
    if au.validate_policy(policy, sorted(projects)) or policy["verifier"] != {"transport": "gh", "serial": True}:
        raise ValueError("capture policy is not a valid GitHub verification policy")
    if policy_digest(policy) != bundle["policy_sha256"]:
        raise ValueError("capture policy digest differs")
    if bundle["captured_at"] > au.now() or any(
            d["last_checked_at"] > bundle["captured_at"] for d in bundle["decisions"]):
        raise ValueError("capture times are in the future or out of order")


def capture(m, project: str, verifier: au.Verifier | None = None) -> dict:
    """Verify a project's accepted claims through GitHub and return a new capture.

    Nothing is written here. Tests replace GhTransport.get with synthetic responses;
    a snapshot reader (even one named 'gh') cannot be used to claim a live check.
    """
    import recipe

    if project not in m.projects:
        raise ValueError("project is not in the manifest")
    policy = copy.deepcopy(m.raw["authority_policy"])
    policy["verifier"] = {"transport": "gh", "serial": True}
    verifier = verifier or au.Verifier(policy, au.GhTransport())
    if type(verifier.transport) is not au.GhTransport or policy_digest(verifier.policy) != policy_digest(policy):
        raise ValueError("capture requires the manifest policy and the GitHub transport")
    if verifier.requests or verifier._cache:
        raise ValueError("capture requires a fresh verifier; prior reads cannot become a new check")
    notes = recipe.shared_notes(m, project)
    citations = au.record_citations(policy, notes)
    prefix = m.projects[project].source("")
    decisions = []
    originals = {}
    for source in sorted(notes):
        if not source.startswith(prefix):
            continue
        data = read_source(m.vault_root, source)
        note = recipe.parse_note(data.decode("utf-8"))
        if note != notes[source]:
            raise ValueError("source changed during capture")
        status = note["front"].get("status")
        if not status or recipe.front_value(status) != "accepted" or not recipe.decision_title(note):
            continue
        note_digest = digest(data)
        result = au.verify_decision(verifier, note, source, project, note_digest, citations)
        if result["result"] != "verified":
            continue
        originals[source] = data
        decisions.append({"source": source, "note_digest": note_digest,
                          "note_names": list(au.note_names(note, source)),
                          "binding": au.binding_value(policy, note),
                          **{k: result[k] for k in ("reference", "kind", "revision", "actor")},
                          "last_checked_at": result["verified_at"]})
    # Recheck the whole shared-note scope, including record-replay confounders.
    if policy_digest(m.raw["authority_policy"]) != policy_digest(policy):
        raise ValueError("acceptance policy changed during capture")
    if recipe.shared_notes(m, project) != notes or any(
            read_source(m.vault_root, src) != data for src, data in originals.items()):
        raise ValueError("source scope changed during capture")
    bundle = {"format": FORMAT, "project": project, "captured_via": "gh", "captured_at": au.now(),
              "policy": policy, "policy_sha256": policy_digest(policy), "decisions": decisions,
              "responses": [{"host": host, "api_path": path, "body": body}
                            for (host, path), body in sorted(verifier._cache.items())
                            if not isinstance(body, au.Unavailable)]}
    check_bundle(bundle)
    if len(encoded(bundle)) > shape.MAX_PACKET_BYTES:
        raise ValueError("capture bundle exceeds the size limit")
    return bundle


def output_path(m, path: Path) -> Path:
    """Validate the capture destination before live reads, and again before creation."""
    import recipe

    path, lane, vault = path.resolve(), recipe.STATE_BASE.resolve(), m.vault_root.resolve()
    if (path.suffix != ".json" or not path.is_relative_to(lane)
            or path.is_relative_to(vault) or vault.is_relative_to(path.parent)):
        raise ValueError("capture output must be a new .json file under .qmd outside source roots")
    if path.exists():
        raise FileExistsError("capture output already exists; choose a new file")
    return path


def write_capture(m, bundle: dict, path: Path) -> str:
    """Exclusive creation in the repository's derived .qmd lane, outside source roots."""
    check_bundle(bundle)
    path = output_path(m, path)
    data = encoded(bundle)
    if len(data) > shape.MAX_PACKET_BYTES:
        raise ValueError("capture bundle exceeds the size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as out:
        out.write(data)
    return digest(data)


class _CapturedResponses:
    name = "historical"

    def __init__(self, responses: list):
        self.records = {}
        for response in responses:
            key = (response["host"], response["api_path"])
            if key in self.records:
                raise ValueError("duplicate captured response")
            self.records[key] = response["body"]

    def get(self, host, api_path):
        if (host, api_path) not in self.records:
            raise au.Unavailable("capture lacks a required response")
        return self.records[(host, api_path)]


@dataclass(frozen=True)
class Replay:
    path: Path
    pin: str

    def read(self, m, project: str) -> dict:
        """Read historical context. No network, writes, or promotion of current acceptance."""
        import recipe

        out = {"status": "invalid", "reason": "", "replayed_at": au.now(),
               "bundle_sha256": self.pin if isinstance(self.pin, str) and shape.HEX64.fullmatch(self.pin) else "",
               "statement": STATEMENT, "trust_root": TRUST, "entries": []}
        try:
            if not isinstance(self.pin, str) or not shape.HEX64.fullmatch(self.pin):
                raise ValueError("a separately retained SHA-256 pin is required")
            if self.path.resolve().is_relative_to(m.vault_root.resolve()):
                raise ValueError("historical evidence must be outside source roots")
            try:
                with self.path.open("rb") as f:
                    data = f.read(shape.MAX_PACKET_BYTES + 1)
            except FileNotFoundError:
                return {**out, "status": "unavailable", "reason": "capture bundle is missing"}
            if digest(data) != self.pin:
                raise ValueError("capture bundle differs from the trusted digest")
            bundle = shape.parse(data)
            check_bundle(bundle)
            if bundle["project"] != project:
                raise ValueError("capture belongs to a different project")
            historical = au.Verifier(bundle["policy"], _CapturedResponses(bundle["responses"]))
            entries = []
            prefix = m.projects[project].source("")
            seen_refs = set()
            for d in bundle["decisions"]:
                source = d["source"]
                if (not source.startswith(prefix) or "\\" in source or source.startswith("/")
                        or any(p in ("", ".", "..") for p in source.split("/"))):
                    raise ValueError("capture source is outside the project's scope")
                ref = au.parse_reference(d["reference"])
                key = au.ref_key(ref) if ref else None
                if key is None or key in seen_refs:
                    raise ValueError("capture reuses or misstates an acceptance record")
                seen_refs.add(key)
                result = historical.verify(d["reference"], project, d["binding"],
                                           tuple(d["note_names"]), d["note_digest"])
                if result["result"] != "verified" or any(
                        result.get(k) != d[k] for k in ("reference", "kind", "revision", "actor")):
                    raise ValueError("captured approval does not verify under its recorded policy")
                applicability = "matches"
                try:
                    current = read_source(m.vault_root, source)
                    note = recipe.parse_note(current.decode("utf-8"))
                    line = au.reference_line(m.raw["authority_policy"], note)
                    current_ref = au.parse_reference(line.text) if line else None
                    if digest(current) != d["note_digest"]:
                        applicability = "note_changed"
                    if current_ref is None or au.ref_key(current_ref) != key:
                        applicability = "reference_changed"
                except (SourceError, OSError, UnicodeDecodeError):
                    applicability = "missing_source"
                if policy_digest(m.raw["authority_policy"]) != bundle["policy_sha256"]:
                    applicability = "policy_changed"
                entries.append({"source": source, **{k: d[k] for k in (
                    "reference", "revision", "actor", "last_checked_at")},
                    "approved_digest": d["note_digest"], "policy_sha256": bundle["policy_sha256"],
                    "applicability": applicability, "acceptance_effect": "none"})
            return {**out, "status": "historical", "reason": "captured checks replayed; no live verification",
                    "entries": entries}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, shape.ParseError) as exc:
            return {**out, "reason": str(exc)[:200]}
