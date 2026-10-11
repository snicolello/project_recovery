"""Install the pinned QMD package into the repository's git-ignored qmd-runtime/.

Package scripts are disabled (--ignore-scripts), the npm cache is kept inside
qmd-runtime/, nothing is installed globally, and the only network access is
npm fetching the exact tarballs named in the committed lockfile.

Usage: python -I skills/project-recovery/scripts/install_qmd.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
REPO = SKILL.parent.parent
PIN = SKILL / "qmd"
RUNTIME = REPO / "qmd-runtime"
EXPECTED_VERSION = "2.8.3"


def main() -> int:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print("npm not found on PATH; install Node 24 first", file=sys.stderr)
        return 2
    RUNTIME.mkdir(exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        shutil.copyfile(PIN / name, RUNTIME / name)
    cmd = [
        npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", "--update-notifier=false",
        "--cache", str(RUNTIME / ".npm-cache"),
    ]
    print("running:", " ".join(Path(c).name if i == 0 else c for i, c in enumerate(cmd)), flush=True)
    result = subprocess.run(cmd, cwd=RUNTIME)
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
