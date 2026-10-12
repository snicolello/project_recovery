"""Optional live smoke test of the gh-backed verifier. Never part of the gates.

    python -I scripts/live_gh_smoke.py --reference https://github.com/OWNER/REPO/pull/N --approver LOGIN
                                       [--binding HEAD_SHA] [--note FILE --name NOTE_NAME]

Reads one acceptance record from GitHub through the user's existing ``gh`` session, with
one read-only ``gh api --method GET`` request, using the same Verifier and normalization
the snapshot transport uses offline. The policy is built in memory: the cited repository
is allowlisted for a throwaway project named ``smoke`` with the given approver. Nothing is
written. Content binding applies: approver-authored approval text (comment body, review
body, or for a merge an approving review on it, read with a second serial GET) must contain
``ACCEPTED: <NOTE_NAME> sha256:<SHA-256 of FILE>``. Without --note the result is ``invalid``
(approved_text_mismatch) after the record was read, which still exercises the live reads.
Exit 0 when the record verifies, 1 when it is invalid or unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
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
    ap.add_argument("--note", type=Path, help="local note file whose SHA-256 the approval text must name")
    ap.add_argument("--name", help="note name (permalink or title) the approval text must name")
    args = ap.parse_args()
    ref = au.parse_reference(args.reference)
    if ref is None:
        print(json.dumps({"result": "invalid", "reason": "not a pull, review or issue-comment URL"}))
        return 1
    policy = {
        "local_claims": "decision_candidates",
        "verifier": {"transport": "gh", "serial": True},
        "acceptance_records": [{"kind": k, "body_marker": "ACCEPTED:"}
                               for k in ("pull_merge", "pull_review", "issue_comment")],
        "repositories": [{"host": ref.host, "repo": ref.repo, "projects": ["smoke"], "approvers": args.approver}],
        "reference": {"body_labels": [""]},
    }
    verifier = au.Verifier(policy, au.GhTransport())
    digest = hashlib.sha256(args.note.read_bytes()).hexdigest() if args.note else None
    result = verifier.verify(args.reference, "smoke", args.binding, (args.name,) if args.name else (), digest)
    print(json.dumps({"verification": result, "summary": verifier.summary()}, indent=2))
    return 0 if result["result"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
