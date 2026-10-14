"""Validate a packet by re-deriving it (project_recovery #6, the R3 reliance gate).

A packet received from elsewhere (another agent, a model, a file edited by hand) is
trusted only as far as the deterministic assembler reproduces it. ``validate``:

1. parses the packet strictly and checks its structure against an exact allowlist
   (``shape.py``: required outcome 1);
2. re-runs ``recipe.assemble`` for the packet's project, query and token limit, from the
   vault bytes at the recorded generation, with the validator's own verifier, so every
   acceptance record is read again (required outcome 2);
3. compares the two packets value by value, so an added, rewritten, relabelled or deleted
   value anywhere (conflicts, unknowns, candidates, missing sources, the generation gap,
   the budget) is a failure (required outcome 3).

The packet validate returns is the re-derived one. In requery mode nothing from the
submitted packet is kept; in packet mode only its hit selection is (the replay inputs
below), and every hit is re-cited from the vault bytes. Wall-clock values (``observed_at``, ``assembled_at``, ``verified_at``, ``refreshed_at``) are compared
for presence and format, not value.

Query hits, two modes. ``requery`` (the default) runs the packet's query through QMD again,
so hit selection, order, titles and the omitted-hit count are re-derived too. ``packet``
replays the packet's own hit selection (sources, ranks, titles, the omitted-hit count)
through a vault-backed reader with no QMD; every replayed hit is re-cited from the vault
bytes, but which hits were chosen, their order and titles are the packet's claim and are
reported as not re-derived.

What a pass means, and what it does not, is stated in every result (``GUARANTEE``).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import packet as pk
import recipe
import shape
from qmd_client import McpSession, QmdError
from receipts import SourceError, read_source

WALL_CLOCK = frozenset({"observed_at", "assembled_at", "verified_at", "refreshed_at"})
MAX_DIFFERENCES = 100
MODES = ("requery", "packet")

GUARANTEE = {
    "established": (
        "The packet is well-formed under the exact packet allowlist and equals, value for value "
        "(wall-clock times excepted), the packet the deterministic assembler produces from the vault "
        "bytes at the recorded generation, for the same project, query and token limit, with this "
        "validator's acceptance-record verifier."),
    "not_established": [
        "that the notes in the vault are true, current or written by whom they say: the vault bytes "
        "are the trust root, and byte equality is integrity, not approval",
        "anything beyond the verifier's trust root: snapshot files are operator-supplied and trusted "
        "as given; live records trust the approvers' GitHub accounts",
        "who produced the submitted packet, or how: validate carries no signature or provenance "
        "for the submitter",
        "that the query was a good question to ask, or that the packet is the right one for a task",
        "that the vault or the acceptance records stay as they were after validation",
    ],
    "not_rederived_in_packet_mode": [
        "which query hits were selected, their order and titles, and budget.omitted.query_hits: "
        "taken from the packet, not from QMD (each replayed hit is still re-cited from vault bytes)",
        "traces of query hits the packet leaves out (missing_sources entries and 'hit could not be "
        "cited' unknowns): each one the packet names is re-derived from that note's bytes, but one "
        "the packet deletes is not detected",
        "a packet whose query dropped results outside its scope (query_hits scope_violation "
        "conflicts) is not validated in this mode: it is rejected; use requery",
    ],
}


class VaultSession:
    """Stand-in for QMD's read tools, used only by validate's ``packet`` mode.

    ``get`` and ``multi_get`` serve the bytes on disk for the documents indexed at the
    recorded generation (validate first checks the vault still matches it, so these are
    the bytes QMD would serve). A file QMD does not index (``recipe.indexable``) is not
    served, as QMD would not serve it. ``query`` returns the replayed hit list for the
    packet's collection and nothing for any other."""

    def __init__(self, m: recipe.Manifest, collection: str, hits: list[dict]):
        self.m = m
        self.hits, self.collection = hits, collection
        self.by_collection = {p.collection: p for p in m.projects.values()}

    def _documents(self, proj: recipe.Project) -> dict[str, str]:
        prefix = proj.source("")
        return {src[len(prefix):]: src for src, (_, ok) in recipe.disk_scan(self.m, proj).items() if ok}

    def _read(self, qmd_path: str) -> bytes | None:
        collection, _, rel = qmd_path.partition("/")
        proj = self.by_collection.get(collection)
        if proj is None:
            return None
        source = self._documents(proj).get(rel)
        if source is None:
            return None
        try:
            return read_source(self.m.vault_root, source)
        except SourceError:
            return None

    def get(self, path: str, from_line: int | None = None, max_lines: int | None = None) -> str | None:
        data = self._read(path)
        if data is None:
            return None
        if from_line is None:
            return data.decode("utf-8", errors="replace")
        lines = data.split(b"\n")
        end = len(lines) if max_lines is None else min(len(lines), from_line + max_lines - 1)
        if not 1 <= from_line <= end:
            return None
        return b"\n".join(lines[from_line - 1:end]).decode("utf-8", errors="replace")

    def multi_get(self, pattern: str, max_bytes: int = 1_000_000) -> dict[str, str]:
        collection = pattern.partition("/")[0]
        proj = self.by_collection.get(collection)
        if proj is None:
            return {}
        out = {}
        for rel in sorted(self._documents(proj)):
            text = self.get(proj.qmd_path(rel))
            if text is not None:
                out[proj.qmd_path(rel)] = text
        return out

    def query(self, text: str, collection: str, limit: int = 10) -> list[dict]:
        return [dict(h) for h in self.hits[:limit]] if collection == self.collection else []

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def replay_hits(packet: dict, proj: recipe.Project, indexed: set, limit: int) -> tuple[list[dict], int]:
    """The QMD result list a packet's hits imply, and its claimed omitted-hit count.

    Each kept hit sits at its rank. A rank with no kept hit (QMD returned something there
    that assembly dropped) is replayed as an unresolvable result, so the re-derived packet
    gains a conflict and the difference is reported. Dropped results are never replayed
    from the packet's own ``scope_violation`` conflicts: their ``source`` is text the
    packet supplies, and replaying it would let the packet write its own conflicts (review
    of a76abda, R1). Such a packet is validated only in requery mode.

    QMD returns only documents indexed at the recorded generation, so a hit whose source is
    not one of ``indexed`` is replayed as an unresolvable result too; otherwise a packet
    could name a note that does not exist and carry its own text into the re-derived
    ``query_hits`` and ``unknowns`` (re-review of bc791ee, R11).

    QMD returns at most ``limit`` (the manifest's search limit) results, so a rank above it
    is never replayed and the replay never holds more than ``limit`` entries, whatever rank
    a packet claims (fourth review of efcc4e7, F4-1); ``validate`` also reports each such
    rank (``rank_exceeds_search_limit``, an input problem), so the packet is rejected."""
    prefix = proj.source("")
    kept: dict[int, dict] = {}
    for h in packet.get("query_hits") if isinstance(packet.get("query_hits"), list) else []:
        if not isinstance(h, dict) or not isinstance(h.get("source"), str):
            continue
        rank = h.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or not 1 <= rank <= limit or rank in kept:
            continue
        source = h["source"]
        file = proj.qmd_path(source[len(prefix):]) if source.startswith(prefix) and source in indexed else ""
        kept[rank] = {"file": file, "title": h.get("title") if isinstance(h.get("title"), str) else None}
    out = [kept.get(pos, {"file": "", "title": None}) for pos in range(1, max(kept, default=0) + 1)]
    budget = packet.get("budget") if isinstance(packet.get("budget"), dict) else {}
    omitted = budget["omitted"].get("query_hits") if isinstance(budget.get("omitted"), dict) else 0
    ok = isinstance(omitted, int) and not isinstance(omitted, bool) and 0 <= omitted <= shape.MAX_INT
    return out, omitted if ok else 0


def link_pairs(packet: dict) -> set[tuple[str, str]]:
    """Every (link, source) pair a packet names in ``missing_sources``."""
    out = set()
    for e in packet.get("missing_sources") if isinstance(packet.get("missing_sources"), list) else []:
        if isinstance(e, dict) and isinstance(e.get("link"), str) and isinstance(e.get("linked_from"), list):
            out.update((e["link"], s) for s in e["linked_from"] if isinstance(s, str))
    return out


def uncited_hits(packet: dict) -> list[str]:
    """Sources of the ``query_hits:<source>`` unknowns a packet names, in order."""
    unknowns = packet.get("unknowns") if isinstance(packet.get("unknowns"), list) else []
    return [u["field"][len("query_hits:"):] for u in unknowns
            if isinstance(u, dict) and isinstance(u.get("field"), str) and u["field"].startswith("query_hits:")]


def hidden_sources(packet: dict, first: dict, indexed: set) -> list[str]:
    """Notes the packet's traces say were query hits that the replay did not reproduce: an
    unknown for a hit that could not be cited, or a missing link, taken per (link, source)
    pair, since a note already cited as a decision may also have been a trimmed hit whose
    body carries further links (review of a76abda, R2 and R3). Uncitable hits keep the
    packet's unknowns order; the rest follow, sorted. Only documents indexed at the recorded
    generation can have been hits (R11); a trace naming anything else stays unreproduced."""
    visible = {h.get("source") for h in first.get("query_hits", [])}
    out = [s for s in uncited_hits(packet) if s not in uncited_hits(first) and s not in visible and s in indexed]
    links = sorted(({s for _, s in link_pairs(packet) - link_pairs(first)} & indexed) - visible - set(out))
    return list(dict.fromkeys(out + links))


def comparable(value):
    """The packet with wall-clock values replaced by a marker: presence counts, value does not."""
    if isinstance(value, dict):
        return {k: ("<wall-clock>" if k in WALL_CLOCK else comparable(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def differences(submitted, rederived, path: str = "", out: list | None = None) -> list[dict]:
    """Every value where the submitted packet differs from the re-derived one."""
    out = [] if out is None else out
    if len(out) >= MAX_DIFFERENCES:
        return out
    if isinstance(submitted, dict) and isinstance(rederived, dict):
        for key in list(rederived) + [k for k in submitted if k not in rederived]:
            sub = shape.join(path, key)
            if key not in submitted:
                add(out, sub, "missing_from_packet", f"re-derived packet has {brief(rederived[key])}; packet has none")
            elif key not in rederived:
                add(out, sub, "not_rederived", f"packet has {brief(submitted[key])}; re-derived packet has none")
            else:
                differences(submitted[key], rederived[key], sub, out)
    elif isinstance(submitted, list) and isinstance(rederived, list):
        for i in range(max(len(submitted), len(rederived))):
            sub = f"{path}[{i}]"
            if i >= len(submitted):
                add(out, sub, "missing_from_packet", f"re-derived packet has {brief(rederived[i])}; packet has none")
            elif i >= len(rederived):
                add(out, sub, "not_rederived", f"packet has {brief(submitted[i])}; re-derived packet has none")
            else:
                differences(submitted[i], rederived[i], sub, out)
    elif type(submitted) is not type(rederived) or submitted != rederived:
        add(out, path, "differs_from_rederived", f"packet has {brief(submitted)}; re-derived {brief(rederived)}")
    return out


def add(out: list, path: str, kind: str, reason: str) -> None:
    if len(out) < MAX_DIFFERENCES:
        out.append({"check": "rederivation", "field": path or "packet", "kind": kind, "reason": reason})
    elif len(out) == MAX_DIFFERENCES:
        out.append({"check": "rederivation", "field": "packet", "kind": "truncated",
                    "reason": f"more than {MAX_DIFFERENCES} differences; the rest are not listed"})


def brief(value) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "..."


def not_rederivable(reason: str) -> dict:
    return {"check": "rederivation", "field": "packet", "kind": "not_rederivable", "reason": reason}


def scope_projects(m: recipe.Manifest, project: str) -> list[str]:
    """``project`` and every project sharing one of its allowlisted repositories: assembly
    reads all of their notes (``recipe.shared_notes``), so all must match the generation
    (review of a76abda, R8)."""
    repos = [r for r in m.raw["authority_policy"].get("repositories", []) if project in r.get("projects", [])]
    return sorted({project} | {q for r in repos for q in r.get("projects", []) if q in m.projects})


def oversized_ranks(m: recipe.Manifest, packet: dict) -> list[dict]:
    """A problem for each query hit ranked above the manifest's search limit: QMD never
    returns more results than that, so no assembled packet has one (F4-1)."""
    hits = packet.get("query_hits") if isinstance(packet.get("query_hits"), list) else []
    out = []
    for i, h in enumerate(hits):
        rank = h.get("rank") if isinstance(h, dict) else None
        if isinstance(rank, int) and not isinstance(rank, bool) and rank > m.search_limit:
            out.append({"check": "input", "field": f"query_hits[{i}].rank", "kind": "rank_exceeds_search_limit",
                        "reason": f"rank {brief(rank)} exceeds the manifest's search limit {m.search_limit}"})
        if len(out) >= MAX_DIFFERENCES:
            break
    return out


def rederive(m: recipe.Manifest, packet: dict, transport: str | None = None, snapshot_dir: Path | None = None,
             mode: str = "requery", session_factory=None) -> tuple[dict | None, list[dict]]:
    """(re-derived packet or None, problems that prevent re-derivation). The verifier is
    built fresh from the manifest (``transport`` and ``snapshot_dir`` override it), so
    every acceptance record is read again and request counts start at zero."""
    if mode not in MODES:
        return None, [not_rederivable(f"unknown hits mode {mode!r}")]
    project = packet.get("project")
    if not isinstance(project, str) or project not in m.projects:
        return None, [not_rederivable(f"packet project {project!r} is not in the manifest")]
    query = packet.get("query")
    if not isinstance(query, str):
        return None, [not_rederivable("packet query is not a string")]
    proj = m.projects[project]
    try:
        record = recipe.load_generation(m)
    except recipe.RecipeError as exc:
        return None, [not_rederivable(f"{exc}: nothing to re-derive against")]
    gap = [g for name in scope_projects(m, project) for g in recipe.generation_gap(m, m.projects[name], record)]
    if gap:
        return None, [not_rederivable(
            f"the vault differs from the recorded generation {record['generation']} "
            f"({len(gap)} source(s): {', '.join(str(g['source']) for g in gap[:3])}); run refresh, then assemble")]
    budget = packet.get("budget") if isinstance(packet.get("budget"), dict) else {}
    limit = budget.get("limit")
    limit = limit if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= shape.MAX_INT \
        else m.max_tokens
    def verifier():
        return recipe.make_verifier(m, transport, snapshot_dir)
    try:
        if mode == "requery":
            factory = session_factory or (lambda: McpSession(m.state_dir))
            with factory() as session:
                return recipe.assemble(m, project, query, session, limit, verifier()), []
        indexed = recipe.indexed_sources(record)
        hits, omitted = replay_hits(packet, proj, indexed, m.search_limit)
        with VaultSession(m, proj.collection, hits) as session:
            first = recipe.assemble(m, project, query, session, limit, verifier(), omitted_hits=omitted)
        # missing_sources and the unknowns for uncitable hits are computed before the budget
        # trims hits, so they may come from a hit the packet no longer shows. Each note those
        # traces name that the replay did not reproduce is re-cited as a hidden, already-trimmed
        # hit, from the vault bytes; a trace those bytes do not support still differs.
        hidden = hidden_sources(packet, first, indexed)
        if not hidden:
            return first, []
        prefix = proj.source("")
        tail = [{"file": proj.qmd_path(s[len(prefix):]) if s.startswith(prefix) else s, "title": None}
                for s in hidden]
        with VaultSession(m, proj.collection, hits + tail) as session:
            return recipe.assemble(m, project, query, session, limit, verifier(),
                                   omitted_hits=max(omitted - len(tail), 0), hidden_from_rank=len(hits) + 1), []
    except (QmdError, OSError, recipe.RecipeError) as exc:
        hint = "; use --hits packet to replay the packet's hits without QMD" if mode == "requery" else ""
        return None, [not_rederivable(f"re-assembly failed: {exc}{hint}")]
    except (ValueError, ArithmeticError, UnicodeError, RecursionError) as exc:
        # Fail closed: a value the packet supplied that re-assembly cannot handle is never
        # a pass and never an escaping exception (fourth-review follow-up).
        return None, [not_rederivable(f"re-assembly refused a packet value: {type(exc).__name__}: {str(exc)[:120]}")]


def validate(m: recipe.Manifest, data: bytes, transport: str | None = None, snapshot_dir: Path | None = None,
             mode: str = "requery", session_factory=None) -> dict:
    """Validation result for packet bytes. ``result`` is ``equal_to_rederived`` only when the
    packet is well-formed and equals its re-derivation; ``packet`` is the re-derived packet
    (None when it could not be re-derived)."""
    try:
        submitted = shape.parse(data)
    except shape.ParseError as exc:
        problems = [{"check": "input", "field": "packet", "kind": "unparseable", "reason": str(exc)}]
        return report("not_rederivable", problems, [], m, mode, None, None)
    structure = shape.check(submitted)
    ranks = oversized_ranks(m, submitted)
    rederived, blocked = rederive(m, submitted, transport, snapshot_dir, mode, session_factory)
    if rederived is None:
        return report("not_rederivable", structure + ranks + blocked, structure, m, mode, submitted, None)
    try:
        diffs = differences(comparable(submitted), comparable(rederived))
    except (ValueError, ArithmeticError, UnicodeError, RecursionError) as exc:  # fail closed
        return report("not_rederivable", structure + ranks + [not_rederivable(
            f"comparison refused a packet value: {type(exc).__name__}")], structure, m, mode, submitted, None)
    problems = structure + ranks + diffs
    return report("rejected" if problems else "equal_to_rederived", problems, structure, m, mode, submitted, rederived)


def report(result: str, problems: list, structure: list, m: recipe.Manifest, mode: str,
           submitted: dict | None, rederived: dict | None) -> dict:
    try:
        recorded = recipe.load_generation(m)["generation"]
    except recipe.RecipeError:
        recorded = None
    guarantee = {"established": GUARANTEE["established"] if result == "equal_to_rederived" else None,
                 "not_established": list(GUARANTEE["not_established"])
                 + (GUARANTEE["not_rederived_in_packet_mode"] if mode == "packet" else [])}
    return {
        "result": result,
        "failures": len(problems),
        "checks": {
            "input": {"failures": sum(1 for p in problems if p["check"] == "input")},
            "structure": {"failures": len(structure)},
            "rederivation": {"performed": rederived is not None, "hits": mode,
                             "differences": sum(1 for p in problems if p["check"] == "rederivation"
                                                and p["kind"] != "not_rederivable"),
                             "submitted_digest": pk.digest(submitted) if isinstance(submitted, dict) else None,
                             "rederived_digest": pk.digest(rederived) if rederived is not None else None},
        },
        "guarantee": guarantee,
        "problems": problems,
        "recorded_generation": recorded,
        "packet": copy.deepcopy(rederived) if rederived is not None else None,
    }
