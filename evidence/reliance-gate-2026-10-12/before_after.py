"""Before/after evidence for project_recovery #6: every reproducing case in
tests/reliance_cases.py, run through the R2 validator (a checkout of the base revision)
and through this revision's validator.

    python -I evidence/reliance-gate-2026-10-12/before_after.py --before-repo PATH [--out FILE]

PATH is a separate checkout of the base revision (5ab0ea2) with no local changes. The
packets are built by this revision's assembler in a throwaway copy of the synthetic
vault; fixtures/ is never written. The base validator is run as a subprocess with its
own state directory under PATH/.qmd/, removed afterwards. This revision's validator runs
in packet mode through the command line, and in requery mode through the API with a
vault-backed stand-in for QMD (the scenario gates run requery through QMD itself).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tests"))

from reliance_cases import CASES, HITS, build, make_env  # noqa: E402  (sets sys.path)

import packet as pk  # noqa: E402
import recover  # noqa: E402
import rederive  # noqa: E402


def transport_for(name: str) -> str:
    return "offline" if name.endswith("offline") else "snapshot"


def run_before(before: Path, state: Path, env, path: Path, transport: str) -> dict:
    cmd = [sys.executable, "-I", str(before / "skills/project-recovery/scripts/recover.py"), "validate",
           "--manifest", str(before / "manifest/scenario-vault.json"), "--vault-root", str(env.root),
           "--state-dir", str(state), "--packet", str(path), "--verifier", transport]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        last = (r.stderr.strip().splitlines() or ["no output"])[-1]
        return {"exit": r.returncode, "verdict": "crashed", "detail": last[:160]}
    kinds = sorted({p.get("kind") for p in out.get("problems", [])})
    entry = {"exit": r.returncode, "verdict": "passed" if r.returncode == 0 else "flagged",
             "failures": out.get("failures"), "kinds": kinds}
    node = out.get("packet")
    for key in ("fields", "accepted_decisions", "decisions"):
        node = node.get(key) if isinstance(node, dict) else None
    kept = [d for d in node or [] if isinstance(d, dict) and d.get("authority_state") == "verified"
            and not d.get("items")]
    if kept:
        entry["output_keeps_verified_entry_without_items"] = True
    return entry


def run_after_cli(env, path: Path, transport: str) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = recover.main(["validate", "--manifest", str(env.m.path), "--vault-root", str(env.root),
                             "--state-dir", str(env.state), "--packet", str(path), "--verifier", transport,
                             "--hits", "packet"])
    out = json.loads(buf.getvalue())
    return {"exit": code, "result": out["result"], "failures": out["failures"],
            "first_problem": (out["problems"][0]["field"] + ": " + out["problems"][0]["kind"]) if out["problems"] else None}


def run_after_requery(env, data: bytes, project: str, transport: str) -> dict:
    out = rederive.validate(env.m, data, transport, None, "requery",
                            session_factory=lambda: rederive.VaultSession(env.m, project, HITS[project]))
    return {"result": out["result"], "failures": out["failures"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-repo", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=HERE.parent / "results.json")
    args = ap.parse_args()
    before = args.before_repo.resolve()
    rev = subprocess.run(["git", "-C", str(before), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    env = make_env()
    state = before / ".qmd" / f"r6-before-{uuid.uuid4().hex[:8]}"
    try:
        shutil.copytree(env.state, state)
        rows = []
        for name, packet in env.packets.items():  # controls: what the assembler produced
            path = env.root.parent / f"control-{name}.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            rows.append({"id": f"control-{name}", "finding": "control", "criterion": "AC5",
                         "what": f"assembled {name} packet, unedited",
                         "before": run_before(before, state, env, path, transport_for(name)),
                         "after_packet_mode": run_after_cli(env, path, transport_for(name)),
                         "after_requery": run_after_requery(env, path.read_bytes(), packet["project"],
                                                            transport_for(name))})
        for case in CASES:
            data = build(env, case)
            path = env.root.parent / f"{case.id}.json"
            path.write_bytes(data)
            t = transport_for(case.packet)
            project = env.packets[case.packet]["project"]
            rows.append({"id": case.id, "finding": case.finding, "criterion": case.criterion, "what": case.what,
                         "expect_after": case.expect, "modes": list(case.modes),
                         "before": run_before(before, state, env, path, t),
                         "after_packet_mode": run_after_cli(env, path, t),
                         "after_requery": run_after_requery(env, data, project, t)})
    finally:
        shutil.rmtree(state, ignore_errors=True)
        env.close()
    result = {"base_revision": rev, "revision": head, "cases": rows,
              "summary": {
                  "before_passed_with_zero_failures": [r["id"] for r in rows if r["before"]["verdict"] == "passed"
                                                       and not r["id"].startswith("control")],
                  "before_crashed": [r["id"] for r in rows if r["before"]["verdict"] == "crashed"],
                  "after_unexpected": [r["id"] for r in rows if not r["id"].startswith("control") and any(
                      r[f"after_{m}"]["result"] != r["expect_after"]
                      for m in ("packet_mode" if x == "packet" else "requery" for x in r["modes"]))],
                  "controls_after": {r["id"]: (r["after_packet_mode"]["result"], r["after_requery"]["result"])
                                     for r in rows if r["id"].startswith("control")},
              }}
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return 0 if not result["summary"]["after_unexpected"] else 1


if __name__ == "__main__":
    sys.exit(main())
