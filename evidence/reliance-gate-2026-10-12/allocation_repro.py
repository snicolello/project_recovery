"""Bounded structural-diagnostic allocation reproduction for PR #8 / issue #6.

Run this script with --code-root pointing to either 603b6c3 or the fixed checkout.
It measures at most 10,000 empty hits (30,064 bytes), never a near-limit payload.
Requery uses the same vault-backed stand-in as the unit tests; scenario gates
separately exercise real QMD. Only synthetic throwaway copies are used.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import sys
import tracemalloc
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def measure(call):
    gc.collect()
    tracemalloc.start()
    try:
        result = call()
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, peak


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=REPO)
    args = parser.parse_args()
    scripts = args.code_root.resolve() / "skills/project-recovery/scripts"
    sys.path.insert(0, str(scripts))
    sys.path.insert(0, str(REPO / "tests"))
    import rederive
    import shape
    from reliance_cases import HITS, make_env

    out = {"python": platform.python_version(), "platform": sys.platform,
           "shape_sha256": hashlib.sha256((scripts / "shape.py").read_bytes()).hexdigest(),
           "measurement": "peak traced Python allocation; input and fixture setup excluded",
           "cases": []}
    env = make_env(packets=False)
    try:
        for count in (1_000, 10_000):
            data = (b'{"project":"cobalt","query":"approve deployment","query_hits":['
                    + b",".join([b"{}"] * count) + b"]}")
            parsed = shape.parse(data)
            problems, peak = measure(lambda: shape.check(parsed))
            row = {"empty_hits": count, "input_bytes": len(data),
                   "structure": {"problems": len(problems), "peak_bytes": peak}, "validate": {}}
            for mode in rederive.MODES:
                result, peak = measure(lambda: rederive.validate(
                    env.m, data, "snapshot", None, mode,
                    session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"])))
                row["validate"][mode] = {"result": result["result"],
                                          "structure_problems": result["checks"]["structure"]["failures"],
                                          "peak_bytes": peak}
            out["cases"].append(row)
    finally:
        env.close()
    print(json.dumps(out, indent=2))
    return 0 if all(r["result"] == "rejected" for c in out["cases"] for r in c["validate"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
