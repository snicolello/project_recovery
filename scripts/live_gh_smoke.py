"""Optional live smoke test of the gh-backed verifier. Never part of the gates.

    python -I scripts/live_gh_smoke.py --reference https://github.com/OWNER/REPO/pull/N --approver LOGIN
                                       [--binding HEAD_SHA]

Reads one acceptance record from GitHub through the user's existing ``gh`` session, with
one read-only ``gh api --method GET`` request, using the same Verifier and normalization
the snapshot transport uses offline. The policy is built in memory: the cited repository
is allowlisted for a throwaway project named ``smoke`` with the given approver. Nothing is
written. Exit 0 when the record verifies, 1 when it is invalid or unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "project-recovery" / "scripts"))

import authority as au  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True, help="pull, review or issue-comment URL")
    ap.add_argument("--approver", required=True, action="append", help="login allowed to accept (repeatable)")
    ap.add_argument("--binding", help="expected subject revision (PR head or review commit)")
    args = ap.parse_args()
    ref = au.parse_reference(args.reference)
    if ref is None:
        print(json.dumps({"result": "invalid", "reason": "not a pull, review or issue-comment URL"}))
        return 1
    policy = {
        "local_claims": "decision_candidates",
        "verifier": {"transport": "gh", "serial": True},
        "acceptance_records": [{"kind": "pull_merge"}, {"kind": "pull_review"},
                               {"kind": "issue_comment", "body_marker": "ACCEPTED:"}],
        "repositories": [{"host": ref.host, "repo": ref.repo, "projects": ["smoke"], "approvers": args.approver}],
        "reference": {"body_labels": [""]},
    }
    verifier = au.Verifier(policy, au.GhTransport())
    result = verifier.verify(args.reference, "smoke", args.binding)
    print(json.dumps({"verification": result, "summary": verifier.summary()}, indent=2))
    return 0 if result["result"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
