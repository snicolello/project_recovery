"""Install the pinned QMD package into the repository's git-ignored qmd-runtime/.

Package scripts are disabled (--ignore-scripts), npm uses a throwaway cache in
a short temporary directory that is deleted afterwards (deep cache paths inside
the clone can exceed the Windows path limit), nothing is installed globally, and
the only network access is npm fetching the exact tarballs named in the
committed lockfile.

Usage: python -I skills/project-recovery/scripts/install_qmd.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
REPO = SKILL.parent.parent
PIN = SKILL / "qmd"
RUNTIME = REPO / "qmd-runtime"
EXPECTED_VERSION = "2.8.3"


def remove_cache(cache: Path) -> bool:
    """Delete the temporary npm cache; say so, with its path, if anything is left behind."""
    shutil.rmtree(cache, ignore_errors=True)
    if cache.exists():
        print(f"warning: temporary npm cache not fully removed; delete it by hand: {cache}", file=sys.stderr)
        return False
    return True


def main() -> int:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print("npm not found on PATH; install Node 24 first", file=sys.stderr)
        return 2
    RUNTIME.mkdir(exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(PIN / name, RUNTIME / name)
    cache = Path(tempfile.mkdtemp(prefix="prq-npm-"))
    cmd = [
        npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--update-notifier=false",
        "--cache", str(cache),
    ]
    print("running: npm ci --ignore-scripts --no-audit --no-fund (temporary cache)", flush=True)
    try:
        result = subprocess.run(cmd, cwd=RUNTIME)
    finally:
        remove_cache(cache)
    if result.returncode != 0:
        return result.returncode
    pkg = json.loads((RUNTIME / "node_modules" / "@tobilu" / "qmd" / "package.json").read_text(encoding="utf-8"))
    if pkg.get("version") != EXPECTED_VERSION:
        print(f"unexpected QMD version {pkg.get('version')}", file=sys.stderr)
        return 3
    print(f"QMD {pkg['version']} installed in qmd-runtime/ with package scripts disabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
