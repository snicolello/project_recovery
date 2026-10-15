"""Separate governed capture utility; not a recovery tool and never run by the gates.

Reads live GitHub acceptance records and exclusively creates a capture under .qmd.
Requires authorization for the chosen source and live reads. The owner currently
holds all live runs; synthetic tests replace GhTransport.get instead of using network.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "project-recovery" / "scripts"))

import last_checked  # noqa: E402
import recipe  # noqa: E402
from receipts import SourceError  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--project", required=True)
    ap.add_argument("--vault-root", type=Path)
    ap.add_argument("--out", required=True, type=Path, help="new .json file under repository .qmd, outside source roots")
    args = ap.parse_args(argv)
    try:
        m = recipe.load_manifest(args.manifest, args.vault_root)
        last_checked.output_path(m, args.out)
        bundle = last_checked.capture(m, args.project)
        pin = last_checked.write_capture(m, bundle, args.out)
    except (OSError, ValueError, recipe.RecipeError, SourceError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    print(json.dumps({"bundle_sha256": pin, "project": args.project,
                      "captured_at": bundle["captured_at"], "decisions": len(bundle["decisions"]),
                      "trust_root": last_checked.TRUST, "statement": last_checked.STATEMENT}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
