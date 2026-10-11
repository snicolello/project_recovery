"""Command-line entry for the read, refresh, assemble recipe.

    python -I recover.py refresh  --manifest M [--rebuild]
    python -I recover.py query    --manifest M --project P --text "restart"
    python -I recover.py fetch    --manifest M --project P --source "atlas/Project.md" --start 9 --end 10
    python -I recover.py assemble --manifest M --project P --query "Atlas project" [--max-tokens 4000] [--out F]
    python -I recover.py validate --manifest M --packet packet.json

Every command prints JSON on stdout. ``assemble`` prints compact JSON, the exact form
the 4,000-token bound is counted on; the other commands print indented JSON. Only
``refresh`` changes anything, and only the derived index under <repo>/.qmd/.
``validate`` exits 1 when any claim fails (see packet.audit).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import packet as pk  # noqa: E402
import recipe  # noqa: E402
from qmd_client import McpSession  # noqa: E402
from receipts import SourceError, make_receipt, normalize_text, safe_resolve, validate_receipt  # noqa: E402


def emit(value) -> None:
    sys.stdout.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def emit_compact(value) -> None:
    sys.stdout.write(pk.compact(value).decode("utf-8") + "\n")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("refresh", "query", "fetch", "assemble", "validate"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", required=True, type=Path)
        p.add_argument("--vault-root", type=Path, help="override the manifest's vault root")
        p.add_argument("--state-dir", type=Path, help="override the derived index location")
        if name == "refresh":
            p.add_argument("--rebuild", action="store_true", help="delete and rebuild the derived index")
        if name in ("query", "fetch", "assemble"):
            p.add_argument("--project", required=True)
        if name == "query":
            p.add_argument("--text", required=True)
        if name == "fetch":
            p.add_argument("--source", required=True, help="locator relative to the vault root")
            p.add_argument("--start", required=True, type=int)
            p.add_argument("--end", required=True, type=int)
        if name == "assemble":
            p.add_argument("--query", required=True)
            p.add_argument("--max-tokens", type=int)
            p.add_argument("--out", type=Path, help="also write the packet to this file (UTF-8)")
        if name == "validate":
            p.add_argument("--packet", required=True, type=Path)
    args = ap.parse_args(argv)
    m = recipe.load_manifest(args.manifest, args.vault_root, args.state_dir)

    if args.cmd == "refresh":
        record = recipe.refresh(m, rebuild=args.rebuild)
        emit({k: record[k] for k in ("generation", "refreshed_at", "engine")} | {"documents": len(record["files"])})
        return 0
    if args.cmd == "validate":
        original = json.loads(args.packet.read_text(encoding="utf-8"))
        project = m.projects.get(original.get("project")) if isinstance(original, dict) else None
        try:
            expected = recipe.load_generation(m)["generation"]
        except recipe.RecipeError:
            expected = None
        checked, problems = pk.audit(original, m.vault_root, expected, project.root if project else None)
        if project is None:
            problems.append({"field": "project", "kind": "scope_mismatch", "reason": "packet project not in manifest"})
        emit({"failures": len(problems), "problems": problems, "recorded_generation": expected, "packet": checked})
        return 1 if problems else 0

    proj = m.projects[args.project]
    with McpSession(m.state_dir) as session:
        if args.cmd == "query":
            hits = session.query(args.text, proj.collection, m.search_limit)
            emit([{"rank": i, "file": h.get("file"), "title": h.get("title"), "line": h.get("line")}
                  for i, h in enumerate(hits, 1)])
            return 0
        if args.cmd == "fetch":
            prefix = proj.source("")
            try:
                safe_resolve(m.vault_root, args.source)
            except SourceError as exc:
                emit({"error": str(exc)})
                return 2
            if not args.source.startswith(prefix):
                emit({"error": f"source outside project root {proj.root!r}"})
                return 2
            rel = args.source[len(prefix):]
            text = session.get(proj.qmd_path(rel), args.start, args.end - args.start + 1)
            if text is None:
                emit({"source": args.source, "status": "unknown", "reason": "not found in scope"})
                return 1
            cited = text.encode("utf-8")
            generation = recipe.load_generation(m)["generation"]
            receipt = make_receipt(args.source, args.start, args.end, cited, generation, recipe.now())
            ok, why = validate_receipt(receipt, m.vault_root, cited)
            emit({"text": normalize_text(cited), "receipt": receipt, "valid": ok, "reason": why})
            return 0 if ok else 1
        result = recipe.assemble(m, args.project, args.query, session, args.max_tokens)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(pk.compact(result).decode("utf-8") + "\n", encoding="utf-8")
        emit_compact(result)
        return 0


if __name__ == "__main__":
    sys.exit(main())
