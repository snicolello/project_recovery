"""Read, refresh, assemble: the R1 recovery recipe over QMD.

refresh   builds or updates the derived QMD index, reads every indexed document back
          through QMD, checks it against the source bytes and records the generation.
assemble  reads the manifest's declared fields through QMD's read tools, cites each
          line with a receipt validated against the source bytes, and returns a
          bounded packet (recovery contract sections 1 to 3, 5 and 6).

Authority verification is release R2: every decision is labelled ``local_only``.
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

import packet as pk
from qmd_client import REPO, McpSession, QmdError, index_cli, installed_version
from receipts import SourceError, make_receipt, normalize_text, safe_resolve, sha256_hex, validate_receipt

CONTRACT_VERSION = "0.1"
RECIPE_VERSION = "r1"
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
AUTHORITY_NOTE = ("not_performed: R1 labels every decision local_only; "
                  "GitHub acceptance verification is release R2")


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
    if raw["authority_policy"].get("local_claims") != "local_only":
        errors.append("authority_policy.local_claims must be local_only in R1")
    for name, proj in raw["projects"].items():
        for key in ("collection", "root", "baseline_note", "fields", "authority", "decision_statuses"):
            if key not in proj:
                errors.append(f"projects.{name}: missing {key}")
        for field in REQUIRED_FIELDS:
            if field not in proj.get("fields", {}):
                errors.append(f"projects.{name}.fields: missing {field}")
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

def disk_files(m: Manifest, proj: Project) -> dict[str, str]:
    """source path -> SHA-256 of the bytes on disk, for Markdown files in the project root.
    Links (symlinks, junctions) are skipped; they are outside the allowlist."""
    base = safe_resolve(m.vault_root, proj.root) if proj.root != "." else m.vault_root
    out = {}
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base).as_posix()
        try:
            out[proj.source(rel)] = sha256_hex(safe_resolve(m.vault_root, proj.source(rel)).read_bytes())
        except SourceError:
            continue
    return out


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
    with McpSession(m.state_dir) as session:
        status = session.status()
        indexed_roots = {c["name"]: os.path.normcase(c["path"]) for c in status.get("collections", [])}
        for proj in m.projects.values():
            base = m.vault_root if proj.root == "." else safe_resolve(m.vault_root, proj.root)
            if indexed_roots.get(proj.collection) != os.path.normcase(str(base)):
                raise RecipeError(f"collection {proj.collection} does not point at the manifest root")
            served = {proj.source(q[len(proj.collection) + 1:]): sha256_hex(t.encode("utf-8"))
                      for q, t in session.multi_get(f"{proj.collection}/**/*.md").items()}
            if served != disk_files(m, proj):
                raise RecipeError(f"index for {proj.collection} does not match source bytes after refresh")
            files.update(served)
    canonical = json.dumps(sorted(files.items()), separators=(",", ":")).encode("utf-8")
    record = {
        "generation": "qmd-2.8.3:" + hashlib.sha256(canonical).hexdigest()[:16],
        "files": dict(sorted(files.items())),
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
    body_start = 1
    if lines and lines[0].text == "---":
        for line in lines[1:]:
            if line.text == "---":
                body_start = line.number + 1
                break
            key, sep, _ = line.text.partition(":")
            if sep:
                front[key.strip()] = line
    body = [ln for ln in lines if ln.number >= body_start and ln.text.strip()]
    statement = next((ln for ln in body if not ln.text.startswith("#")), None)
    return {"front": front, "body": body, "statement": statement}


def front_value(line: Line) -> str:
    return line.text.partition(":")[2].strip()


class Assembler:
    def __init__(self, m: Manifest, proj: Project, session: McpSession, generation: str):
        self.m, self.proj, self.session, self.generation = m, proj, session, generation
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
        out = []
        for label in labels:
            for line in parse_note(text)["body"]:
                if line.text.startswith(label):
                    out.append(self.cite(field, rel, line.number, line.number))
                    break
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
        remainder = items[0]["text"][len(spec["label"]):].strip()
        if remainder.upper().startswith("UNKNOWN"):
            self.unknowns.append({"field": path, "reason": "source states UNKNOWN"})
            return {"status": "unknown", "reason": "source states UNKNOWN", "items": [], "evidence": items}
        return {"status": "established", "items": items}

    def authority(self) -> dict:
        spec = self.proj.authority
        rel = spec.get("record", self.proj.baseline_note)
        text = self.doc(rel)
        items = []
        if text is not None:
            line = parse_note(text)["front"].get(spec.get("record_key", "status"))
            if line:
                items.append(self.cite("authority", rel, line.number, line.number))
        node = self.node("authority", items, "no governing record found")
        node["authority_state"] = "local_only"
        node["verification"] = AUTHORITY_NOTE
        approver_items = self.labelled("authority.approver", rel, spec.get("approver_labels", [])) if text else []
        node["approver"] = self.node("authority.approver", approver_items,
                                     "no record in scope names who may change the governing record")
        node["approvals"] = {a["name"]: self.approval(f"authority.approvals.{a['name']}", a)
                             for a in spec.get("approvals", [])}
        return node

    def decisions(self, listing: dict[str, str]) -> tuple[dict, dict]:
        accepted, other = [], []
        by_stem = {}
        for qpath in sorted(listing):
            rel = qpath[len(self.proj.collection) + 1:]
            note = parse_note(listing[qpath])
            status_line = note["front"].get("status")
            if not status_line or front_value(status_line) not in self.proj.decision_statuses:
                continue
            status = front_value(status_line)
            field = "accepted_decisions" if status == "accepted" else "other_decisions"
            items = [self.cite(field, rel, status_line.number, status_line.number)]
            if note["statement"]:
                items.append(self.cite(field, rel, note["statement"].number, note["statement"].number))
            title_line = note["front"].get("title")
            entry = {"title": front_value(title_line) if title_line else Path(rel).stem,
                     "local_status": status, "authority_state": "local_only",
                     **self.node(f"{field}:{rel}", items, "decision lines failed validation")}
            (accepted if status == "accepted" else other).append(entry)
            by_stem[Path(rel).stem] = entry
        for item in self.labelled("accepted_decisions", self.proj.baseline_note,
                                  self.proj.fields["accepted_decisions"]):
            if not item:
                continue
            links = WIKILINK.findall(item["text"])
            target = next((by_stem[l] for l in links if l in by_stem and by_stem[l] in accepted), None)
            if target:
                target["items"].append(item)
            else:
                accepted.append({"title": None, "local_status": "stated_in_baseline",
                                 "authority_state": "local_only", "status": "established", "items": [item]})
        acc = {"status": "established", "decisions": accepted} if accepted else None
        if acc is None:
            reason = "no decision with local status accepted and no baseline statement"
            self.unknowns.append({"field": "accepted_decisions", "reason": reason})
            acc = {"status": "unknown", "reason": reason, "decisions": []}
        return acc, {"decisions": other}

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


def assemble(m: Manifest, project: str, query: str, session: McpSession, max_tokens: int | None = None) -> dict:
    if project not in m.projects:
        raise RecipeError(f"project not in manifest: {project}")
    proj = m.projects[project]
    record = load_generation(m)
    gap = generation_gap(m, proj, record)
    a = Assembler(m, proj, session, record["generation"])
    listing = session.multi_get(f"{proj.collection}/**/*.md")
    accepted, other = a.decisions(listing)
    fields = {
        "objective": a.label_field("objective"),
        "authority": a.authority(),
        "accepted_decisions": accepted,
        "other_decisions": other,
        "current_state": a.label_field("current_state"),
        "blockers": a.label_field("blockers"),
        "next_action": a.label_field("next_action"),
    }
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
            "statement": ("sources changed after the recorded generation; run the refresh step"
                          if gap else "every source in scope matches the recorded generation"),
        },
        "fields": fields,
        "query_hits": a.query_hits(query),
        "missing_sources": [],
        "conflicts": a.conflicts,
        "unknowns": a.unknowns,
    }
    out["missing_sources"] = a.missing_links(out, listing)
    return pk.bound(out, max_tokens or m.max_tokens)
