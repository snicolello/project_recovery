"""Read, refresh, assemble: the R1 recovery recipe over QMD.

refresh   builds or updates the derived QMD index, reads every indexed document back
          through QMD, checks it against the source bytes and records the generation.
assemble  reads the manifest's declared fields through QMD's read tools, cites each
          line with a receipt validated against the source bytes, and returns a
          bounded packet (recovery contract sections 1 to 3, 5 and 6).

Release R2 (owner ruling B): a note whose frontmatter says ``status: accepted`` is a
decision candidate. It becomes an accepted decision only when the acceptance record it
cites is read and verified under the manifest's authority policy (``authority.py``).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import authority as au
import packet as pk
from qmd_client import REPO, McpSession, QmdError, index_cli, installed_version
from receipts import (SourceError, make_receipt, normalize_text, read_source, safe_resolve, sha256_hex,
                      span_bytes, validate_receipt)

CONTRACT_VERSION = "0.1"
RECIPE_VERSION = "r2"
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
AUTHORITY_NOTE = ("local_claim: the governing record's status is read from a local note; "
                  "R2 verifies decision acceptance records, not the governing record")


class RecipeError(RuntimeError):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# Manifest ------------------------------------------------------------------

@dataclass
class Project:
    name: str
    collection: str
    root: str            # directory relative to the vault root ("." allowed)
    baseline_note: str   # path relative to the project root
    fields: dict
    authority: dict
    decision_statuses: list

    def source(self, rel: str) -> str:
        return rel if self.root == "." else f"{self.root}/{rel}"

    def qmd_path(self, rel: str) -> str:
        return f"{self.collection}/{rel}"


@dataclass
class Manifest:
    path: Path
    name: str
    vault_root: Path
    state_dir: Path
    projects: dict
    search_limit: int
    max_tokens: int
    raw: dict


REQUIRED_FIELDS = ("objective", "current_state", "blockers", "next_action", "accepted_decisions")
AUTHORITY_KEYS = frozenset({"record", "record_key", "record_label", "approver_labels", "approvals"})


def validate_manifest(raw: dict) -> list[str]:
    errors = []
    for key in ("manifest_version", "name", "vault", "index", "budget", "projects", "authority_policy"):
        if key not in raw:
            errors.append(f"missing key: {key}")
    if errors:
        return errors
    if raw["index"].get("engine") != "qmd" or raw["index"].get("version") != "2.8.3":
        errors.append("index must be qmd 2.8.3")
    search = raw["index"].get("search", {})
    if search.get("type") != "lex" or search.get("rerank") is not False:
        errors.append("index.search must be lexical with rerank false")
    errors.extend(au.validate_policy(raw["authority_policy"], list(raw["projects"])))
    for name, proj in raw["projects"].items():
        for key in ("collection", "root", "baseline_note", "fields", "authority", "decision_statuses"):
            if key not in proj:
                errors.append(f"projects.{name}: missing {key}")
        for field in REQUIRED_FIELDS:
            if field not in proj.get("fields", {}):
                errors.append(f"projects.{name}.fields: missing {field}")
        spec = proj.get("authority")
        if not isinstance(spec, dict):
            continue
        # A misspelt key must never fall back silently to the frontmatter ``status`` default.
        extra = sorted(set(spec) - AUTHORITY_KEYS)
        if extra:
            errors.append(f"projects.{name}.authority: unknown key(s) {extra}")
        # One mapping per governing record: a label never falls back to frontmatter, and
        # configuring both is refused rather than ranked (project_recovery #17).
        if "record_key" in spec and "record_label" in spec:
            errors.append(f"projects.{name}.authority: record_key and record_label are exclusive; configure one")
        for key in ("record_key", "record_label"):
            if key in spec and (not isinstance(spec[key], str) or not spec[key].strip()):
                errors.append(f"projects.{name}.authority.{key} must be a non-empty string")
    return errors


def load_manifest(path: Path, vault_root: Path | None = None, state_dir: Path | None = None) -> Manifest:
    path = path.resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_manifest(raw)
    if errors:
        raise RecipeError("invalid manifest: " + "; ".join(errors))
    root = (vault_root or (path.parent / raw["vault"]["root"])).resolve()
    if not root.is_dir():
        raise RecipeError(f"vault root not found: {root}")
    if state_dir is None:
        tag = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()[:8]
        state_dir = REPO / ".qmd" / f"{raw['name']}-{tag}"
    state_dir = state_dir.resolve()
    check_state_dir(state_dir, root)
    projects = {
        name: Project(name, p["collection"], p["root"], p["baseline_note"], p["fields"],
                      p["authority"], list(p["decision_statuses"]))
        for name, p in raw["projects"].items()
    }
    for proj in projects.values():
        safe_resolve(root, proj.source(proj.baseline_note))  # allowlist check on declared paths
    return Manifest(path, raw["name"], root, state_dir, projects,
                    int(raw["index"]["search"].get("limit", 10)), int(raw["budget"]["max_tokens"]), raw)


# Derived index location --------------------------------------------------

STATE_BASE = REPO / ".qmd"
STATE_MARKER = ".project-recovery-state"
# Everything the recipe or QMD creates in a state directory; nothing else is ever deleted.
STATE_ENTRIES = frozenset({STATE_MARKER, "generation.json", "index.sqlite", "index.sqlite-wal",
                           "index.sqlite-shm", "index.sqlite-journal", "config", "xdg-config",
                           "xdg-cache", "mcp-stderr.log"})


def _within(child: Path, parent: Path) -> bool:
    c, p = os.path.normcase(str(child)), os.path.normcase(str(parent))
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def check_state_dir(state_dir: Path, vault_root: Path) -> None:
    """The derived index must sit strictly inside <repo>/.qmd/ and share no path with the vault."""
    base = Path(os.path.realpath(STATE_BASE))
    state = Path(os.path.realpath(state_dir))
    root = Path(os.path.realpath(vault_root))
    if not _within(state, base) or os.path.normcase(str(state)) == os.path.normcase(str(base)):
        raise RecipeError("state dir must be a subdirectory of <repo>/.qmd/")
    if _within(state, root) or _within(root, state):
        raise RecipeError("state dir must not equal, contain, or sit inside the vault root")


def clear_state(state_dir: Path) -> None:
    """Delete a state directory only if this tool created it and it holds only tool files."""
    if not state_dir.exists():
        return
    if not (state_dir / STATE_MARKER).is_file():
        raise RecipeError(f"refusing to rebuild: {state_dir.name} lacks the {STATE_MARKER} marker")
    unknown = sorted(p.name for p in state_dir.iterdir() if p.name not in STATE_ENTRIES)
    if unknown:
        raise RecipeError(f"refusing to rebuild: unexpected entries in state dir: {unknown}")
    for p in state_dir.iterdir():
        if p.name == STATE_MARKER:
            continue
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
    (state_dir / STATE_MARKER).unlink()
    state_dir.rmdir()


# Refresh -------------------------------------------------------------------

# QMD 2.8.3 skips a Markdown file whose text, read as UTF-8, is empty after JavaScript's
# String.prototype.trim() (dist/cli/qmd.js, indexFiles: ``if (!content.trim())``): it is
# never indexed or served. These are the code points trim() removes in the Node that runs
# QMD (ECMAScript WhiteSpace and LineTerminator), confirmed exhaustively by
# evidence/qmd-blank-notes-2026-10-14/. Python's str.isspace() differs (U+0085, U+001C to
# U+001F), so it is not used.
JS_WHITESPACE = frozenset("\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003"
                          "\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff")


def indexable(data: bytes) -> bool:
    """Whether QMD 2.8.3 indexes a file with these bytes. Like Node's UTF-8 read, decoding
    keeps a byte-order mark and turns invalid bytes into U+FFFD, which is not whitespace."""
    return any(ch not in JS_WHITESPACE for ch in data.decode("utf-8", errors="replace"))


def disk_scan(m: Manifest, proj: Project) -> dict[str, tuple[str, bool]]:
    """source path -> (SHA-256 of the bytes on disk, whether QMD indexes them), for every
    Markdown file in the project root, from one read of each file. Links (symlinks,
    junctions) are skipped; they are outside the allowlist."""
    base = safe_resolve(m.vault_root, proj.root) if proj.root != "." else m.vault_root
    out = {}
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base).as_posix()
        try:
            data = safe_resolve(m.vault_root, proj.source(rel)).read_bytes()
        except SourceError:
            continue
        out[proj.source(rel)] = (sha256_hex(data), indexable(data))
    return out


def disk_files(m: Manifest, proj: Project) -> dict[str, str]:
    """source path -> SHA-256 of the bytes on disk, for every Markdown file in the project
    root, indexable or not."""
    return {source: sha for source, (sha, _) in disk_scan(m, proj).items()}


def indexed_sources(record: dict) -> set:
    """The sources QMD serves at a recorded generation: every recorded file except those
    recorded as present, not indexable. A record written before that field existed could
    hold no blank file (refresh refused one), so its absence means none."""
    return set(record["files"]) - set(record.get("not_indexable", []))


def generation_path(m: Manifest) -> Path:
    return m.state_dir / "generation.json"


def refresh(m: Manifest, rebuild: bool = False) -> dict:
    """Build or update the index, then record a content-derived generation."""
    check_state_dir(m.state_dir, m.vault_root)
    if rebuild:
        clear_state(m.state_dir)
    if installed_version() != "2.8.3":
        raise RecipeError("QMD 2.8.3 not installed; run install_qmd.py")
    if m.state_dir.exists() and not (m.state_dir / STATE_MARKER).is_file() and any(m.state_dir.iterdir()):
        raise RecipeError(f"state dir {m.state_dir.name} exists but was not created by this tool")
    m.state_dir.mkdir(parents=True, exist_ok=True)
    (m.state_dir / STATE_MARKER).write_text("project-recovery derived index; safe to delete\n", encoding="utf-8")
    if not (m.state_dir / "index.sqlite").exists():
        for proj in m.projects.values():
            base = m.vault_root if proj.root == "." else safe_resolve(m.vault_root, proj.root)
            index_cli(m.state_dir, ["collection", "add", str(base), "--name", proj.collection])
    index_cli(m.state_dir, ["update"])
    files: dict[str, str] = {}
    not_indexable: list[str] = []
    verified_empty: list[str] = []
    with McpSession(m.state_dir) as session:
        status = session.status()
        indexed_roots = {c["name"]: os.path.normcase(c["path"]) for c in status.get("collections", [])}
        for proj in m.projects.values():
            base = m.vault_root if proj.root == "." else safe_resolve(m.vault_root, proj.root)
            # A missing or renamed root scans as empty; it must never be verified empty. safe_resolve
            # has already rejected a root reached through a link or junction.
            if not base.is_dir():
                raise RecipeError(f"project root {proj.root!r} for collection {proj.collection} "
                                  "does not exist as a directory")
            # Every Markdown file is hashed and accounted for; QMD serves exactly the indexable ones.
            scan = disk_scan(m, proj)
            disk = {source: sha for source, (sha, _) in scan.items()}
            expected = {source: sha for source, (sha, ok) in scan.items() if ok}
            served = {proj.source(q[len(proj.collection) + 1:]): sha256_hex(t.encode("utf-8"))
                      for q, t in session.multi_get(f"{proj.collection}/**/*.md").items()}
            if proj.collection not in indexed_roots:
                # QMD's status omits a collection with no indexed document, so its root cannot
                # be read back. It is verified empty only when its root exists as a directory
                # (checked above), the disk scan proves there is nothing to serve and QMD serves
                # nothing for it.
                if expected or served:
                    raise RecipeError(f"collection {proj.collection} is not in the index although "
                                      f"{len(expected)} indexable note(s) are in the manifest root")
                verified_empty.append(proj.collection)
            elif indexed_roots[proj.collection] != os.path.normcase(str(base)):
                raise RecipeError(f"collection {proj.collection} does not point at the manifest root")
            if served != expected:
                emptied = sorted(s for s in served if s in disk and s not in expected)
                if emptied:
                    raise RecipeError(
                        f"index for {proj.collection} still serves earlier content for {len(emptied)} note(s) "
                        f"now blank on disk ({', '.join(emptied[:3])}): QMD 2.8.3 keeps a note's last indexed "
                        "content when the note is emptied; run refresh with --rebuild")
                raise RecipeError(f"index for {proj.collection} does not match source bytes after refresh")
            files.update(disk)
            not_indexable.extend(s for s in disk if s not in expected)
    # The generation is derived from every file's bytes; whether a file is indexable follows from them.
    canonical = json.dumps(sorted(files.items()), separators=(",", ":")).encode("utf-8")
    record = {
        "generation": "qmd-2.8.3:" + hashlib.sha256(canonical).hexdigest()[:16],
        "files": dict(sorted(files.items())),
        "not_indexable": sorted(not_indexable),
        "verified_empty": sorted(verified_empty),
        "refreshed_at": now(),
        "engine": {"name": "qmd", "version": installed_version(), "search": "lex", "rerank": False},
    }
    generation_path(m).write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def load_generation(m: Manifest) -> dict:
    try:
        return json.loads(generation_path(m).read_text(encoding="utf-8"))
    except OSError:
        raise RecipeError("no recorded generation; run the refresh step first") from None


def generation_gap(m: Manifest, proj: Project, record: dict) -> list[dict]:
    disk = disk_files(m, proj)
    prefix = proj.source("")
    recorded = {k: v for k, v in record["files"].items() if proj.root == "." or k.startswith(prefix)}
    gap = []
    for source in sorted(set(disk) | set(recorded)):
        if source not in disk:
            gap.append({"source": source, "change": "removed_since_refresh"})
        elif source not in recorded:
            gap.append({"source": source, "change": "added_since_refresh"})
        elif disk[source] != recorded[source]:
            gap.append({"source": source, "change": "modified_since_refresh"})
    return gap


# Assembly ------------------------------------------------------------------

@dataclass
class Line:
    number: int
    text: str


def parse_note(text: str) -> dict:
    lines = [Line(i + 1, raw.rstrip("\r")) for i, raw in enumerate(text.split("\n"))]
    front: dict[str, Line] = {}
    front_lines: dict[str, list[Line]] = {}  # every line per key; ``front`` keeps the last
    body_start = 1
    if lines and lines[0].text == "---":
        for line in lines[1:]:
            if line.text == "---":
                body_start = line.number + 1
                break
            key, sep, _ = line.text.partition(":")
            if sep:
                front[key.strip()] = line
                front_lines.setdefault(key.strip(), []).append(line)
    body = [ln for ln in lines if ln.number >= body_start and ln.text.strip()]
    statement = next((ln for ln in body if not ln.text.startswith("#")), None)
    return {"front": front, "front_lines": front_lines, "body": body, "statement": statement,
            "visible": visible_lines(text)}


def visible_lines(text: str) -> list[str]:
    """Each line of ``text`` with fenced code blocks and HTML comments blanked to spaces, so
    line numbers are kept. The same patterns ``authority.approval_markers`` strips, applied in
    the same order (fences, then comments); an unclosed fence or comment blanks the rest."""
    plain = text.replace("\r\n", "\n")

    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    return au.HTML_COMMENT.sub(blank, au.FENCE.sub(blank, plain)).split("\n")


def front_value(line: Line) -> str:
    return line.text.partition(":")[2].strip()


def label_lines(note: dict, label: str) -> list[Line]:
    """The body lines of a parsed note that start with ``label``, in order, outside fenced
    code blocks and HTML comments (an example or commented-out line states nothing). The
    one labelled-line reader: labelled fields and approvals cite the first, a labelled
    governing record requires exactly one. The raw line is what gets cited."""
    return [ln for ln in note["body"] if note["visible"][ln.number - 1].startswith(label)]


def stated_value(text: str) -> str:
    """A cited value without surrounding whitespace, quotes, backticks, colons or emphasis
    markers."""
    return text.strip().strip("*_:\"'` \t")


def states_unknown(text: str) -> bool:
    return stated_value(text).upper().startswith("UNKNOWN")


def shared_notes(m: "Manifest", project: str) -> dict[str, dict]:
    """Every note, read from disk, in ``project`` and in every project that shares one of its
    allowlisted repositories: the scope of the one-note-per-record rule."""
    repos = [r for r in m.raw["authority_policy"].get("repositories", []) if project in r.get("projects", [])]
    names = {project} | {q for r in repos for q in r.get("projects", []) if q in m.projects}
    notes: dict[str, dict] = {}
    for name in sorted(names):
        for src in disk_files(m, m.projects[name]):
            try:
                notes[src] = parse_note(read_source(m.vault_root, src).decode("utf-8"))
            except (SourceError, UnicodeDecodeError):
                continue
    return notes


def decision_title(note: dict) -> str | None:
    """A decision's displayed title, from its hashed bytes only: the title line, else the
    permalink. None when neither exists (such a note is never promoted)."""
    for key in ("title", "permalink"):
        line = note["front"].get(key)
        if line and front_value(line):
            return front_value(line)
    return None


def decision_lines(policy: dict, note: dict) -> list[int]:
    """The lines a decision entry cites, in order: status, statement, acceptance reference.
    Assembly cites exactly these; validate requires exactly these."""
    lines = [note["front"]["status"].number] if note["front"].get("status") else []
    if note["statement"]:
        lines.append(note["statement"].number)
    ref = au.reference_line(policy, note)
    if ref is not None:
        lines.append(ref.number)
    return lines


def mismatch_conflict(source: str, v: dict) -> dict:
    """Conflict for a record whose approval text does not bind this note's current bytes
    (``approved_text_mismatch``) or is not approver-authored (``approval_text_not_approver_authored``)."""
    return {"field": "decisions", "kind": v["conflict"], "source": source,
            "reference": v.get("reference"), "revision": v.get("revision"),
            "approved_digest": v.get("approved_digest"), "current_digest": v.get("note_digest"),
            "reason": v.get("reason", "the acceptance record does not approve this decision; not accepted")}


class Assembler:
    def __init__(self, m: Manifest, proj: Project, session: McpSession, record: dict, verifier: au.Verifier):
        self.m, self.proj, self.session = m, proj, session
        self.generation, self.recorded = record["generation"], record["files"]
        self.verifier, self.policy = verifier, m.raw["authority_policy"]
        self.conflicts: list[dict] = []
        self.unknowns: list[dict] = []
        self._docs: dict[str, str | None] = {}

    def doc(self, rel: str) -> str | None:
        if rel not in self._docs:
            self._docs[rel] = self.session.get(self.proj.qmd_path(rel))
        return self._docs[rel]

    def cite(self, field: str, rel: str, start: int, end: int) -> dict | None:
        """Fetch a line range through QMD and return a receipted item, or record a conflict."""
        source = self.proj.source(rel)
        text = self.session.get(self.proj.qmd_path(rel), start, end - start + 1)
        if text is None:
            self.conflicts.append({"field": field, "kind": "span_unavailable", "source": source,
                                   "span": [start, end], "reason": "QMD returned no document"})
            return None
        cited = text.encode("utf-8")
        receipt = make_receipt(source, start, end, cited, self.generation, now())
        ok, why = validate_receipt(receipt, self.m.vault_root, cited)
        if not ok:
            self.conflicts.append({"field": field, "kind": "receipt_validation_failed", "source": source,
                                   "span": [start, end], "claimed_sha": receipt["content_sha"], "reason": why})
            return None
        return {"text": normalize_text(cited), "receipt": receipt}

    def node(self, field: str, items: list, reason: str) -> dict:
        items = [i for i in items if i]
        if items:
            return {"status": "established", "items": items}
        self.unknowns.append({"field": field, "reason": reason})
        return {"status": "unknown", "reason": reason, "items": []}

    def labelled(self, field: str, rel: str, labels: list[str]) -> list[dict]:
        text = self.doc(rel)
        if text is None:
            return []
        note = parse_note(text)
        out = []
        for label in labels:
            lines = label_lines(note, label)
            if lines:
                out.append(self.cite(field, rel, lines[0].number, lines[0].number))
        return out

    def label_field(self, field: str) -> dict:
        labels = self.proj.fields[field]
        return self.node(field, self.labelled(field, self.proj.baseline_note, labels),
                         f"no line labelled {labels} in the baseline note")

    def approval(self, path: str, spec: dict) -> dict:
        rel = spec["note"]
        if self.doc(rel) is None:
            self.unknowns.append({"field": path, "reason": f"declared note {spec['note']!r} not found in scope"})
            return {"status": "unknown", "reason": "declared note not found; no locator recorded", "items": []}
        items = [i for i in self.labelled(path, rel, [spec["label"]]) if i]
        if not items:
            return self.node(path, [], f"no line labelled {spec['label']!r}")
        if states_unknown(items[0]["text"][len(spec["label"]):]):
            self.unknowns.append({"field": path, "reason": "source states UNKNOWN"})
            return {"status": "unknown", "reason": "source states UNKNOWN", "items": [], "evidence": items}
        return {"status": "established", "items": items}

    def governing_record(self, spec: dict, rel: str, text: str | None) -> dict:
        """The governing record's status line, under exactly one configured mapping: a
        frontmatter key (``record_key``, default ``status``) or, when ``record_label`` is
        set, a body line starting with that label, read by ``label_lines``. A label never
        falls back to frontmatter (project_recovery #17). Fails closed: no matching line,
        more than one, or a cited value that is empty or starts with UNKNOWN leaves
        authority unknown; matching lines that do not establish it are kept as evidence."""
        if text is None:
            return self.node("authority", [], "no governing record found")
        note = parse_note(text)
        label = spec.get("record_label")
        if label is not None:
            lines, mapping = label_lines(note, label), f"line labelled {label!r}"
            absent = f"no {mapping} in the governing record"
        else:
            key = spec.get("record_key", "status")
            lines, mapping, absent = note["front_lines"].get(key, []), f"frontmatter key {key!r}", \
                "no governing record found"
        if not lines:
            return self.node("authority", [], absent)
        items = [i for i in (self.cite("authority", rel, ln.number, ln.number) for ln in lines) if i]
        if len(lines) > 1:
            reason = f"{len(lines)} lines match the governing record's {mapping}; ambiguous, not resolved"
            self.conflicts.append({"field": "authority", "kind": "authority_ambiguous",
                                   "source": self.proj.source(rel), "reason": reason})
        elif not items:
            return self.node("authority", [], "the governing record's line failed receipt validation")
        else:
            cited = items[0]["text"]
            # Classify the visible body value; comments cannot supply a status or hide
            # UNKNOWN. Keep the original cited bytes for evidence and its receipt.
            value = stated_value(note["visible"][lines[0].number - 1][len(label):]
                                 if label is not None else front_value(Line(0, cited)))
            if value and not states_unknown(value):
                return {"status": "established", "items": items}
            reason = "source states UNKNOWN" if value else f"the governing record's {mapping} states no value"
        self.unknowns.append({"field": "authority", "reason": reason})
        return {"status": "unknown", "reason": reason, "items": [], "evidence": items}

    def authority(self) -> dict:
        spec = self.proj.authority
        rel = spec.get("record", self.proj.baseline_note)
        text = self.doc(rel)
        node = self.governing_record(spec, rel, text)
        node["authority_state"] = "local_only"
        node["verification"] = AUTHORITY_NOTE
        approver_items = self.labelled("authority.approver", rel, spec.get("approver_labels", [])) if text else []
        node["approver"] = self.node("authority.approver", approver_items,
                                     "no record in scope names who may change the governing record")
        node["approvals"] = {a["name"]: self.approval(f"authority.approvals.{a['name']}", a)
                             for a in spec.get("approvals", [])}
        return node

    def decisions(self, listing: dict[str, str]) -> tuple[dict, dict, dict]:
        """Split decision notes into verified accepted decisions, candidates and others.

        Values that carry no receipt of their own (title, reference, binding) are parsed
        only from listing bytes that equal both the bytes on disk and the recorded
        generation; a note whose listing bytes do not is dropped with a conflict.
        ``local_status`` is read from the cited, receipt-validated status line."""
        accepted, candidates, other = [], [], []
        citations = au.record_citations(self.policy, shared_notes(self.m, self.proj.name))
        prefix = self.proj.source("")
        for key, sources in citations.items():
            if len(sources) > 1 and any(src.startswith(prefix) for src in sources):
                host, repo, kind, number, record_id = key
                self.conflicts.append({"field": "decisions", "kind": "acceptance_record_replayed",
                                       "reference": f"{host}/{repo} {kind} {number}" + (f" #{record_id}" if record_id else ""),
                                       "sources": sources,
                                       "reason": "one acceptance record is cited by several notes; none is accepted"})
        for qpath in sorted(listing):
            rel = qpath[len(self.proj.collection) + 1:]
            source = self.proj.source(rel)
            note = parse_note(listing[qpath])
            status_line = note["front"].get("status")
            if not status_line or front_value(status_line) not in self.proj.decision_statuses:
                continue
            served = sha256_hex(listing[qpath].encode("utf-8"))
            try:
                disk = sha256_hex(safe_resolve(self.m.vault_root, source).read_bytes())
            except (SourceError, OSError):
                disk = None
            if served != disk or served != self.recorded.get(source):
                self.conflicts.append({"field": "decisions", "kind": "decision_source_unvalidated", "source": source,
                                       "reason": "served note bytes differ from the source or the recorded "
                                                 "generation; not used as a decision source"})
                continue
            is_claim = front_value(status_line) == "accepted"
            field = "decision_candidates" if is_claim else "other_decisions"
            status_item = self.cite(field, rel, status_line.number, status_line.number)
            items = [status_item]
            if note["statement"]:
                items.append(self.cite(field, rel, note["statement"].number, note["statement"].number))
            entry = {"title": decision_title(note), "source": source,
                     "local_status": front_value(Line(0, status_item["text"])) if status_item else "unknown"}
            if is_claim:
                ref_line = au.reference_line(self.policy, note)
                ref_item = self.cite(field, rel, ref_line.number, ref_line.number) if ref_line else None
                items.append(ref_item)
                if ref_line and not ref_item:
                    v = {**self.verifier.verify(None, self.proj.name, None), "result": "invalid",
                         "reason": "the reference line failed receipt validation"}
                else:  # the reference is read from the cited, receipt-validated text
                    v = au.verify_decision(self.verifier, note, source, self.proj.name, served, citations,
                                           reference_text=ref_item["text"] if ref_item else None)
                if v.get("conflict"):
                    self.conflicts.append(mismatch_conflict(source, v))
                entry.update({"authority_state": au.state_for(v["result"]), "verification": v})
            else:
                entry["authority_state"] = "local_only"
            entry.update(self.node(f"{field}:{rel}", items, "decision lines failed validation"))
            if is_claim and entry["verification"]["result"] == "verified" and entry["status"] == "established":
                accepted.append(entry)
            elif is_claim:
                if entry["authority_state"] == "verified":  # record verified but local evidence failed
                    entry["authority_state"] = "unverified"
                candidates.append(entry)
            else:
                other.append(entry)
        # Baseline "Accepted decision:" lines are local claims about decisions. The baseline
        # note is not bound to any acceptance record, so its lines are never attached to a
        # decision entry (verified or not): each stays its own local_only candidate.
        for item in self.labelled("decision_candidates", self.proj.baseline_note,
                                  self.proj.fields["accepted_decisions"]):
            if item:
                candidates.append({"title": None, "source": item["receipt"]["source"],
                                   "local_status": "stated_in_baseline", "authority_state": "local_only",
                                   "verification": self.verifier.verify(None, self.proj.name, None),
                                   "status": "established", "items": [item]})
        if any(d["status"] == "established" for d in accepted):
            acc = {"status": "established", "basis": "verified acceptance records only", "decisions": accepted}
        else:
            tally: dict[str, int] = {}
            for d in candidates:
                tally[d["verification"]["result"]] = tally.get(d["verification"]["result"], 0) + 1
            reason = "no decision has verified acceptance evidence"
            if candidates:
                reason += f"; {len(candidates)} candidate(s): " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items()))
            self.unknowns.append({"field": "accepted_decisions", "reason": reason})
            acc = {"status": "unknown", "basis": "verified acceptance records only", "reason": reason,
                   "decisions": accepted}
        cand = {"status": "candidate", "basis": "local claims; not accepted until verified", "decisions": candidates}
        return acc, cand, {"decisions": other}

    def query_hits(self, query: str) -> list[dict]:
        hits = []
        prefix = self.proj.collection + "/"
        for rank, hit in enumerate(self.session.query(query, self.proj.collection, self.m.search_limit), 1):
            path = hit.get("file", "")
            if not path.startswith(prefix):
                self.conflicts.append({"field": "query_hits", "kind": "scope_violation", "source": path,
                                       "reason": "result outside the declared collection; dropped"})
                continue
            rel = path[len(prefix):]
            try:
                safe_resolve(self.m.vault_root, self.proj.source(rel))
            except SourceError as exc:
                self.conflicts.append({"field": "query_hits", "kind": "scope_violation", "source": path,
                                       "reason": str(exc)})
                continue
            text = self.doc(rel)
            body = parse_note(text)["body"] if text is not None else []
            items = [self.cite("query_hits", rel, body[0].number, body[-1].number)] if body else []
            entry = {"rank": rank, "source": self.proj.source(rel), "title": hit.get("title")}
            entry.update(self.node(f"query_hits:{self.proj.source(rel)}", items, "hit could not be cited"))
            hits.append(entry)
        return hits

    def missing_links(self, packet: dict, listing: dict[str, str]) -> list[dict]:
        stems = {Path(q[len(self.proj.collection) + 1:]).stem for q in listing}
        linked: dict[str, set] = {}
        for _, node in pk.iter_nodes(packet):
            for key in ("items", "evidence"):
                for item in node.get(key, []):
                    for target in WIKILINK.findall(item["text"]):
                        linked.setdefault(target.strip(), set()).add(item["receipt"]["source"])
        return [{"link": t, "linked_from": sorted(src), "result": "not found in scope; no locator recorded"}
                for t, src in sorted(linked.items()) if t not in stems]


def make_verifier(m: Manifest, transport: str | None = None, snapshot_dir: Path | None = None) -> au.Verifier:
    """The manifest's verifier; ``transport`` (offline, snapshot, gh) and ``snapshot_dir`` override it."""
    return au.build_verifier(m.raw["authority_policy"], m.path.parent, transport, snapshot_dir)


def make_rechecker(m: Manifest, project: str, verifier: au.Verifier):
    """``recheck(entry) -> (ok, reason)`` for packet.audit: re-derive the cited acceptance
    reference and binding from the decision's source bytes and verify them again."""
    proj = m.projects[project]
    policy = m.raw["authority_policy"]
    prefix = proj.source("")

    def recheck(entry: dict) -> tuple[bool, str]:
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith(prefix):
            return False, "decision source outside the project root"
        try:
            data = read_source(m.vault_root, source)
            note = parse_note(data.decode("utf-8"))
        except (SourceError, UnicodeDecodeError) as exc:
            return False, f"decision source unreadable: {exc}"
        status = note["front"].get("status")
        if not status or front_value(status) != "accepted":
            return False, "decision source does not claim status accepted"
        # The entry must be exactly what assembly produces for this note: its title from the
        # hashed bytes, and its items exactly the status, statement and reference lines, with
        # no other cited content anywhere inside the entry.
        title = decision_title(note)
        if title is None:
            return False, "the note's bytes carry no title or permalink; it cannot be promoted"
        if entry.get("title") != title:
            return False, "entry title differs from its source note"
        if "evidence" in entry or any(node is not entry for _, node in pk.iter_nodes(entry)):
            return False, "entry carries cited content outside its own items"
        items = entry.get("items") if isinstance(entry.get("items"), list) else []
        got = [(((i.get("receipt") or {}).get("source")), list((i.get("receipt") or {}).get("span") or []),
                (i.get("receipt") or {}).get("content_sha")) if isinstance(i, dict) else None for i in items]
        want = [(source, [n, n], sha256_hex(span_bytes(data, n, n))) for n in decision_lines(policy, note)]
        if any(g and g[0] != source for g in got):
            return False, "entry cites items from a note other than its own source"
        if got != want:
            return False, "entry items are not exactly the status, statement and reference lines of its source note"
        v = au.verify_decision(verifier, note, source, proj.name, sha256_hex(data),
                               au.record_citations(policy, shared_notes(m, project)))
        if v.get("conflict"):
            return False, v["reason"], v["conflict"]
        claimed = entry.get("verification") or {}
        if v["result"] != "verified":
            return False, f"re-verification {v['result']}: {v['reason']}"
        if (v["reference"], v["revision"]) != (claimed.get("reference"), claimed.get("revision")):
            return False, "re-verified record differs from the packet's reference or revision"
        return True, "ok"
    return recheck


def assemble(m: Manifest, project: str, query: str, session: McpSession, max_tokens: int | None = None,
             verifier: au.Verifier | None = None, omitted_hits: int = 0, hidden_from_rank: int | None = None,
             history=None) -> dict:
    """The packet for ``project`` and ``query``. ``omitted_hits`` and ``hidden_from_rank`` are
    used only by validate's replay mode (``rederive.py``): the count of hits trimmed before the
    replay that it cannot cite (added to ``budget.omitted``), and the rank from which replayed
    results are cited and read for ``missing_sources``, then left out as trimming would."""
    if project not in m.projects:
        raise RecipeError(f"project not in manifest: {project}")
    proj = m.projects[project]
    verifier = verifier or make_verifier(m)
    record = load_generation(m)
    gap = generation_gap(m, proj, record)
    a = Assembler(m, proj, session, record, verifier)
    listing = session.multi_get(f"{proj.collection}/**/*.md")
    accepted, candidates, other = a.decisions(listing)
    fields = {
        "objective": a.label_field("objective"),
        "authority": a.authority(),
        "accepted_decisions": accepted,
        "decision_candidates": candidates,
        "other_decisions": other,
        "current_state": a.label_field("current_state"),
        "blockers": a.label_field("blockers"),
        "next_action": a.label_field("next_action"),
    }
    hits = a.query_hits(query)
    # Freshness is re-checked after assembly: a source edited, or a new generation
    # recorded, while the packet was being assembled makes it incomplete, by name.
    during = [dict(g, detected="during_assembly") for g in generation_gap(m, proj, record) if g not in gap]
    try:
        after = load_generation(m)["generation"]
    except RecipeError:
        after = None
    if after != record["generation"]:
        during.append({"source": None, "change": f"recorded generation changed to {after!r}",
                       "detected": "during_assembly"})
    gap = gap + during
    results: dict[str, int] = {}
    for d in accepted["decisions"] + candidates["decisions"]:
        results[d["verification"]["result"]] = results.get(d["verification"]["result"], 0) + 1
    summary = verifier.summary()
    unread = results.get("unavailable", 0)
    if unread:
        statement = (f"{unread} acceptance record(s) could not be read ({summary['transport']}); the decisions "
                     "citing them are unverified candidates, not accepted decisions")
    elif summary["requests"]:
        statement = f"every cited acceptance record that passed the policy was read serially ({summary['transport']})"
    else:
        statement = f"no acceptance record was read ({summary['transport']})"
    out = {
        "contract_version": CONTRACT_VERSION,
        "recipe_version": RECIPE_VERSION,
        "project": project,
        "scope": {"collection": proj.collection, "root": proj.root},
        "query": query,
        "status": "incomplete" if gap else "complete",
        "assembled_at": now(),
        "freshness": {
            "generation": record["generation"],
            "refreshed_at": record["refreshed_at"],
            "generation_gap": gap,
            "statement": (f"assembled from generation {record['generation']}; "
                          + ("sources changed after it was recorded; run the refresh step" if gap
                             else "every source in scope matches it")),
        },
        "authority_verification": {**summary, "results": dict(sorted(results.items())), "statement": statement},
        "fields": fields,
        "query_hits": hits,
        "missing_sources": [],
        "conflicts": a.conflicts,
        "unknowns": a.unknowns,
    }
    out["missing_sources"] = a.missing_links(out, listing)
    if history is not None:
        # Read-only historical context is separate from every current decision result.
        out["last_checked"] = history.read(m, project)
    if hidden_from_rank is not None:
        out["query_hits"] = [h for h in hits if h["rank"] < hidden_from_rank]
        omitted_hits += len(hits) - len(out["query_hits"])
    return pk.bound(out, max_tokens or m.max_tokens, omitted_hits)
