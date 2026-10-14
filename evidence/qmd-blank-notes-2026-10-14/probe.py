"""Probe QMD 2.8.3's handling of blank notes and empty collections (project_recovery #16).

    python -I evidence/qmd-blank-notes-2026-10-14/probe.py [--out results.json]

Synthetic only. Every vault is generated under .scratch/qmd-blank-probe/ (git-ignored) and
every index under .qmd/qmd-blank-probe-*/ (git-ignored); fixtures/ is never read or written.
QMD is driven only through the recovery client's allowlisted surface: ``collection add``,
``update`` and the four read tools (``status``, ``multi_get``, ``get``, ``query``).

Records, for each probe file, whether QMD indexes and serves it, alone and beside a real
note; whether a collection with no indexed document appears in ``status``; what the read
tools return for such a collection; and what happens when an indexed note is emptied,
refilled or deleted. The results are observations, not the rule: ``recipe.indexable`` is
checked against them (``predicate_agrees``).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import recipe  # noqa: E402
from qmd_client import McpSession, index_cli, installed_version  # noqa: E402

SCRATCH = REPO / ".scratch" / "qmd-blank-probe"
# The rule under test; None before it exists, so the first run records observations only.
INDEXABLE = getattr(recipe, "indexable", lambda data: None)
STATE = REPO / ".qmd"
REAL = b"# Real note\nObjective: probe the blank-note rule.\n"

# name -> bytes. JavaScript's String.prototype.trim() and Python's str.isspace() disagree
# on U+0085, U+001C to U+001F; U+200B and U+180E are whitespace in neither.
PROBES = {
    "empty": b"",
    "spaces": b"   ",
    "tabs-and-spaces": b" \t \t ",
    "newline-lf": b"\n",
    "newlines-crlf": b"\r\n\r\n",
    "mixed-whitespace": b" \t\r\n \n\t",
    "bom": b"\xef\xbb\xbf",
    "bom-newline": b"\xef\xbb\xbf\r\n",
    "frontmatter-only": b"---\ntitle: Probe\n---\n",
    "frontmatter-empty": b"---\n---\n",
    "vt-ff": b"\x0b\x0c",
    "nbsp": " ".encode("utf-8"),
    "ideographic-space-and-line-separator": "　  ".encode("utf-8"),
    "nel-U+0085": "\u0085".encode("utf-8"),
    "file-separator-U+001C": b"\x1c",
    "zero-width-space-U+200B": "​".encode("utf-8"),
    "mongolian-vowel-separator-U+180E": "᠎".encode("utf-8"),
}


def fresh(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def state(name: str) -> Path:
    path = STATE / f"qmd-blank-probe-{name}"
    if path.exists():
        shutil.rmtree(path)
    return path


def collection_names(status: dict) -> dict[str, int]:
    return {c["name"]: c.get("documents") for c in status.get("collections", [])}


def read_tools(s: McpSession, collection: str, files: list[str]) -> dict:
    served = s.multi_get(f"{collection}/**/*.md")
    raw = s.call_tool("multi_get", {"pattern": f"{collection}/**/*.md", "lineNumbers": False})
    gets = {f: s.get(f"{collection}/{f}") is not None for f in files}
    query = s.call_tool("query", {"searches": [{"type": "lex", "query": "probe"}],
                                  "collections": [collection], "limit": 10, "rerank": False})
    return {
        "multi_get_served": sorted(served),
        "multi_get_is_error": bool(raw.get("isError")),
        "get_served": gets,
        "query_is_error": bool(query.get("isError")),
        "query_results": len(query.get("structuredContent", {}).get("results", [])),
        "query_error_text": next((c.get("text", "")[:160] for c in query.get("content", [])
                                  if query.get("isError") and c.get("type") == "text"), None),
    }


def probe_alone_and_mixed() -> dict:
    """One collection per probe file (alone), one with no Markdown at all, and one with
    every probe file beside a real note (mixed), all in one index."""
    root = fresh(SCRATCH / "alone")
    st = state("alone")
    for name, data in PROBES.items():
        d = root / f"alone-{name}".replace("+", "")
        d.mkdir()
        (d / f"{name}.md").write_bytes(data)
    (root / "no-markdown").mkdir()
    (root / "no-markdown" / "readme.txt").write_bytes(b"not markdown\n")
    mixed = root / "mixed"
    mixed.mkdir()
    (mixed / "real.md").write_bytes(REAL)
    for name, data in PROBES.items():
        (mixed / f"{name}.md").write_bytes(data)
    for d in sorted(root.iterdir()):
        index_cli(st, ["collection", "add", str(d), "--name", d.name])
    index_cli(st, ["update"])
    out: dict = {"alone": {}, "mixed": {}}
    with McpSession(st) as s:
        listed = collection_names(s.status())
        for name, data in PROBES.items():
            coll = f"alone-{name}".replace("+", "")
            tools = read_tools(s, coll, [f"{name}.md"])
            observed = tools["get_served"][f"{name}.md"]
            out["alone"][name] = {
                "bytes_hex": data.hex(), "in_status": coll in listed, "status_documents": listed.get(coll),
                "indexed": observed, "predicate_indexable": INDEXABLE(data),
                "predicate_agrees": INDEXABLE(data) == observed, **tools}
        out["no_markdown"] = {"in_status": "no-markdown" in listed, **read_tools(s, "no-markdown", [])}
        tools = read_tools(s, "mixed", ["real.md"] + [f"{n}.md" for n in PROBES])
        out["mixed"] = {"in_status": "mixed" in listed, "status_documents": listed.get("mixed"), **tools,
                        "predicate_agrees": all(
                            tools["get_served"][f"{n}.md"] == INDEXABLE(d) for n, d in PROBES.items())}
    return out


def probe_transitions() -> dict:
    """A note indexed with content, then emptied, refilled and deleted; and a collection
    whose only note is emptied after indexing."""
    root = fresh(SCRATCH / "transitions")
    st = state("transitions")
    one, solo = root / "one", root / "solo"
    one.mkdir()
    solo.mkdir()
    (one / "real.md").write_bytes(REAL)
    (one / "note.md").write_bytes(b"# Note\nFirst content.\n")
    (solo / "only.md").write_bytes(b"# Only\nThe only note.\n")
    index_cli(st, ["collection", "add", str(one), "--name", "one"])
    index_cli(st, ["collection", "add", str(solo), "--name", "solo"])
    index_cli(st, ["update"])
    steps: dict = {}

    def observe(label: str) -> None:
        with McpSession(st) as s:
            listed = collection_names(s.status())
            served = s.multi_get("one/**/*.md")
            steps[label] = {
                "status": listed,
                "one_served": {k: v for k, v in sorted(served.items())},
                "solo_served": sorted(s.multi_get("solo/**/*.md")),
            }

    observe("1 indexed with content")
    (one / "note.md").write_bytes(b"")
    (solo / "only.md").write_bytes(b"\r\n")
    index_cli(st, ["update"])
    observe("2 after emptying note.md and only.md, update")
    (one / "note.md").write_bytes(b"# Note\nSecond content.\n")
    index_cli(st, ["update"])
    observe("3 after refilling note.md, update")
    (one / "note.md").unlink()
    (solo / "only.md").unlink()
    index_cli(st, ["update"])
    observe("4 after deleting note.md and only.md, update")
    st2 = state("transitions-rebuilt")
    (one / "note.md").write_bytes(b"")
    (solo / "only.md").write_bytes(b"")
    index_cli(st2, ["collection", "add", str(one), "--name", "one"])
    index_cli(st2, ["collection", "add", str(solo), "--name", "solo"])
    index_cli(st2, ["update"])
    with McpSession(st2) as s:
        steps["5 fresh index of the same blank files"] = {
            "status": collection_names(s.status()),
            "one_served": {k: v for k, v in sorted(s.multi_get("one/**/*.md").items())},
            "solo_served": sorted(s.multi_get("solo/**/*.md")),
        }
    return steps


TRIM_SCRIPT = ("const out = []; for (let c = 0; c <= 0x10FFFF; c++) { if (c >= 0xD800 && c <= 0xDFFF) continue; "
               "if (String.fromCodePoint(c).trim() === '') out.push(c); } console.log(JSON.stringify(out));")


def probe_trim() -> dict:
    """Every code point the Node that runs QMD removes with String.prototype.trim(),
    compared with the rule's set (recipe.JS_WHITESPACE)."""
    node = shutil.which("node")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    trimmed = json.loads(subprocess.run([node, "-e", TRIM_SCRIPT], capture_output=True, text=True,
                                        check=True).stdout)
    rule = sorted(ord(c) for c in getattr(recipe, "JS_WHITESPACE", ()))
    python_isspace = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF and chr(c).isspace()]
    return {"node": version, "trimmed_code_points": [f"U+{c:04X}" for c in trimmed],
            "rule_equals_node": rule == trimmed,
            "python_isspace_only": [f"U+{c:04X}" for c in python_isspace if c not in trimmed],
            "node_trim_only": [f"U+{c:04X}" for c in trimmed if c not in python_isspace]}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results.json")
    args = ap.parse_args()
    if installed_version() != "2.8.3":
        print("QMD 2.8.3 is not installed in qmd-runtime/", file=sys.stderr)
        return 2
    results = {"qmd": installed_version(), "trim": probe_trim(), **probe_alone_and_mixed(),
               "transitions": probe_transitions()}
    disagreements = [n for n, r in results["alone"].items() if not r["predicate_agrees"]]
    if not results["trim"]["rule_equals_node"]:
        disagreements.append("trim")
    if not results["mixed"]["predicate_agrees"]:
        disagreements.append("mixed")
    results["predicate_disagreements"] = disagreements
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"predicate_disagreements": disagreements, "out": str(args.out.name)}))
    return 1 if disagreements else 0


if __name__ == "__main__":
    sys.exit(main())
