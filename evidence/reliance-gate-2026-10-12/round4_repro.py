"""Safe reproduction of the fourth-review findings on PR #8 (project_recovery #6).

    python -I evidence/reliance-gate-2026-10-12/round4_repro.py [--code-root PATH]

PATH is a checkout or export whose skills/project-recovery/scripts/ is tested (default:
this repository). Nothing large is allocated: the oversized rank is 100,000, the value
named in the review, and the replay is measured, never pushed toward memory exhaustion.

F4-1  a hit rank far above the manifest's search limit: how many replay entries the
      fallback replay builds, and what validate returns in both modes.
F4-2  a 5,000-digit integer in budget.tokens: whether validate returns a structured
      rejection or raises, in both modes.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code-root", type=Path, default=REPO)
    args = ap.parse_args()
    code = args.code_root.resolve()
    sys.path.insert(0, str(code / "skills" / "project-recovery" / "scripts"))
    sys.path.insert(0, str(REPO / "tests"))
    import rederive  # the code under test
    from reliance_cases import HITS, make_env  # packet builder from this repository

    env = make_env(packets=False)
    out = {"code_root": str(code.name)}
    try:
        from reliance_cases import assemble
        p = assemble(env, "cobalt")
        proj = env.m.projects["cobalt"]
        indexed = set(__import__("recipe").load_generation(env.m)["files"])

        # F4-1: oversized rank
        forged = copy.deepcopy(p)
        forged["query_hits"][0]["rank"] = 100_000
        data = json.dumps(forged).encode("utf-8")
        args_ = (forged, proj, indexed) + ((env.m.search_limit,) if rederive.replay_hits.__code__.co_argcount > 3 else ())
        tracemalloc.start()
        hits, _ = rederive.replay_hits(*args_)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        f41 = {"packet_bytes": len(data), "rank": 100_000, "search_limit": env.m.search_limit,
               "replay_entries": len(hits), "replay_peak_bytes": peak}
        for mode in rederive.MODES:
            t = time.perf_counter()
            r = rederive.validate(env.m, data, "snapshot", None, mode,
                                  session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"]))
            f41[mode] = {"result": r["result"], "failures": r["failures"], "seconds": round(time.perf_counter() - t, 2),
                         "first_problem": r["problems"][0]["kind"] if r["problems"] else None}
        out["F4-1 oversized rank"] = f41

        # F4-2: 5,000-digit integer
        text = json.dumps(p).replace(f'"tokens": {p["budget"]["tokens"]}', '"tokens": ' + "9" * 5000, 1)
        f42 = {"packet_bytes": len(text)}
        for mode in rederive.MODES:
            try:
                r = rederive.validate(env.m, text.encode("utf-8"), "snapshot", None, mode,
                                      session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"]))
                f42[mode] = {"result": r["result"], "packet_returned": r["packet"] is not None,
                             "problem": r["problems"][0]["reason"][:90] if r["problems"] else None}
            except Exception as exc:  # the defect: an exception escapes validate
                f42[mode] = {"raised": f"{type(exc).__name__}: {str(exc)[:90]}"}
        out["F4-2 oversized integer"] = f42
    finally:
        env.close()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
