"""Tests for release R2: serial acceptance verification and the candidate versus accepted
distinction (owner ruling B). No Node, QMD or network needed.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import authority as au  # noqa: E402
import install_qmd  # noqa: E402
import packet as pk  # noqa: E402
import recipe  # noqa: E402
from receipts import make_receipt, normalize_text, span_bytes  # noqa: E402

MANIFEST = REPO / "manifest" / "fixture-vault.json"
SCEN_MANIFEST = REPO / "manifest" / "scenario-vault.json"
SNAPSHOTS = REPO / "fixtures" / "github-snapshots"
HOST = "github.example.test"
ATLAS_PR = f"https://{HOST}/portfolio/atlas/pull/7"


def policy() -> dict:
    return copy.deepcopy(json.loads(SCEN_MANIFEST.read_text(encoding="utf-8"))["authority_policy"])


def snapshot_verifier(directory: Path = SNAPSHOTS) -> au.Verifier:
    return au.Verifier(policy(), au.SnapshotTransport(directory))


class ReferenceTests(unittest.TestCase):
    def test_kinds(self):
        r = au.parse_reference(f"acceptance_record: {ATLAS_PR}")
        self.assertEqual((r.kind, r.repo, r.number, r.api_path), ("pull_merge", "portfolio/atlas", 7,
                                                                 "repos/portfolio/atlas/pulls/7"))
        r = au.parse_reference(f"https://{HOST}/o/r/pull/3#pullrequestreview-44")
        self.assertEqual((r.kind, r.api_path), ("pull_review", "repos/o/r/pulls/3/reviews/44"))
        r = au.parse_reference(f"https://{HOST}/o/r/issues/5#issuecomment-501")
        self.assertEqual((r.kind, r.api_path), ("issue_comment", "repos/o/r/issues/comments/501"))

    def test_rejected_references(self):
        for text in ("no url here", f"https://{HOST}/o/r/issues/5", f"https://{HOST}/o/r/pull/7/files",
                     f"{ATLAS_PR} and https://{HOST}/o/r/pull/8", f"https://{HOST}/o/r/issues/5#pullrequestreview-1"):
            self.assertIsNone(au.parse_reference(text), text)


class VerifierTests(unittest.TestCase):
    def test_verified_merge_records_revision_and_time(self):
        v = snapshot_verifier().verify(f"Authority fixture: {ATLAS_PR}", "atlas", "fixture-commit-a1")
        self.assertEqual(v["result"], "verified")
        self.assertEqual(v["revision"], "fixture-merge-a7")
        self.assertTrue(v["verified_at"])
        self.assertEqual(au.state_for(v["result"]), "verified")

    def test_verified_issue_comment(self):
        url = f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-501"
        v = snapshot_verifier().verify(url, "cobalt", None, ("theme-decision", "Theme Decision"))
        self.assertEqual((v["result"], v["kind"]), ("verified", "issue_comment"))

    def test_comment_must_name_the_citing_note(self):
        """Review F1: an approver's comment accepts one named note, not every note that cites it."""
        url = f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-501"
        for names in ((), ("replay-decision", "Replay Decision"), ("theme",), ("theme-decision-2",)):
            v = snapshot_verifier().verify(url, "cobalt", None, names)
            self.assertEqual(v["result"], "invalid", names)

    def test_pull_record_requires_the_note_binding(self):
        """Review F1: a merge without the note's source_revision cannot be bound to the note."""
        v = snapshot_verifier().verify(ATLAS_PR, "atlas", None)
        self.assertEqual(v["result"], "invalid")
        self.assertIn("declares no source_revision", v["reason"])

    def test_invalid_cases_never_verify(self):
        cases = {
            "cross-project replay": (ATLAS_PR, "cobalt", "fixture-commit-a1", "not allowlisted"),
            "binding mismatch": (ATLAS_PR, "atlas", "fixture-commit-zz", "differs from the note"),
            "unmerged": (f"https://{HOST}/portfolio/cobalt/pull/3", "cobalt", None, "not merged"),
            "non-approver": (f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-502", "cobalt", None,
                             "not an approver"),
            "unparseable": ("see the PR", "atlas", None, "not exactly one"),
            "unlisted repository": (f"https://{HOST}/elsewhere/atlas/pull/7", "atlas", None, "not allowlisted"),
        }
        for name, (text, project, binding, why) in cases.items():
            v = snapshot_verifier().verify(text, project, binding)
            self.assertEqual(v["result"], "invalid", name)
            self.assertIn(why, v["reason"], name)
            self.assertNotEqual(au.state_for(v["result"]), "verified", name)

    def test_unconfigured_kind_makes_no_request(self):
        p = policy()
        p["acceptance_records"] = [k for k in p["acceptance_records"] if k["kind"] != "pull_merge"]
        verifier = au.Verifier(p, au.SnapshotTransport(SNAPSHOTS))
        v = verifier.verify(ATLAS_PR, "atlas", None)
        self.assertEqual(v["result"], "invalid")
        self.assertEqual(verifier.requests, [])

    def test_unavailable_cases_keep_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / HOST / "repos" / "portfolio" / "atlas" / "pulls"
            bad.mkdir(parents=True)
            (bad / "7.json").write_text("{not json", encoding="utf-8")
            transports = {"offline": au.OfflineTransport(), "missing snapshot": au.SnapshotTransport(Path(tmp) / "none"),
                          "malformed snapshot": au.SnapshotTransport(Path(tmp))}
            for name, transport in transports.items():
                v = au.Verifier(policy(), transport).verify(ATLAS_PR, "atlas", "fixture-commit-a1")
                self.assertEqual(v["result"], "unavailable", name)
                self.assertEqual(v["reference"], ATLAS_PR, name)
                self.assertEqual(au.state_for(v["result"]), "unverified", name)

    def test_record_not_matching_reference_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = SNAPSHOTS / HOST / "repos" / "portfolio" / "atlas" / "pulls" / "7.json"
            dst = Path(tmp) / HOST / "repos" / "portfolio" / "atlas" / "pulls"
            dst.mkdir(parents=True)
            body = json.loads(src.read_text(encoding="utf-8"))
            body["number"] = 8
            (dst / "7.json").write_text(json.dumps(body), encoding="utf-8")
            v = snapshot_verifier(Path(tmp)).verify(ATLAS_PR, "atlas", None)
            self.assertEqual(v["result"], "invalid")

    def test_not_referenced_is_local_only(self):
        v = snapshot_verifier().verify(None, "atlas", None)
        self.assertEqual((v["result"], au.state_for(v["result"])), ("not_referenced", "local_only"))

    def test_gh_transport_is_read_only_get_and_reports_failure(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=1, stdout="", stderr="HTTP 403: API rate limit exceeded")
        with mock.patch.object(au.shutil, "which", return_value="gh"), mock.patch.object(au.subprocess, "run", fake_run):
            v = au.Verifier(policy(), au.GhTransport()).verify(ATLAS_PR, "atlas", None)
        self.assertEqual(calls, [["gh", "api", "--hostname", HOST, "--method", "GET", "repos/portfolio/atlas/pulls/7"]])
        self.assertEqual(v["result"], "unavailable")
        self.assertIn("rate limit", v["reason"])
        with mock.patch.object(au.shutil, "which", return_value=None):
            self.assertEqual(au.Verifier(policy(), au.GhTransport()).verify(ATLAS_PR, "atlas", None)["result"],
                             "unavailable")


class SerialTests(unittest.TestCase):
    def test_second_concurrent_request_is_refused(self):
        entered, release = threading.Event(), threading.Event()

        class Slow:
            name = "slow"

            def get(self, host, path):
                entered.set()
                release.wait(5)
                raise au.Unavailable("slow")
        verifier = au.Verifier(policy(), Slow())
        t = threading.Thread(target=verifier.verify, args=(ATLAS_PR, "atlas", None))
        t.start()
        self.assertTrue(entered.wait(5))
        with self.assertRaises(au.ConcurrentRequest):
            verifier.fetch(au.parse_reference(f"https://{HOST}/portfolio/atlas/pull/8"))
        release.set()
        t.join(5)

    def test_requests_are_serial_and_cached_per_record(self):
        verifier = snapshot_verifier()
        for text in (ATLAS_PR, ATLAS_PR, f"https://{HOST}/portfolio/atlas/pull/9"):
            verifier.verify(text, "atlas", None)
        self.assertEqual([r[0] for r in verifier.requests], ["repos/portfolio/atlas/pulls/7", "repos/portfolio/atlas/pulls/9"])
        self.assertTrue(all(a[2] <= b[1] for a, b in zip(verifier.requests, verifier.requests[1:])))
        s = verifier.summary()
        self.assertEqual((s["requests"], s["overlapping_requests"], s["unavailable"]), (2, False, 1))


class PolicyTests(unittest.TestCase):
    def test_shipped_manifests_validate(self):
        for path in (MANIFEST, SCEN_MANIFEST):
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(recipe.validate_manifest(raw), [], path.name)

    def test_bad_policies_rejected(self):
        raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
        mutations = {
            "local_only claims": lambda p: p.update(local_claims="local_only"),
            "concurrent verifier": lambda p: p["verifier"].update(serial=False),
            "unknown transport": lambda p: p["verifier"].update(transport="graphql"),
            "unknown kind": lambda p: p["acceptance_records"].append({"kind": "commit_status"}),
            "repository without approvers": lambda p: p["repositories"][0].update(approvers=[]),
            "repository for unknown project": lambda p: p["repositories"][0].update(projects=["zeta"]),
            "no reference rule": lambda p: p.update(reference={}),
        }
        for name, mutate in mutations.items():
            bad = copy.deepcopy(raw)
            mutate(bad["authority_policy"])
            self.assertTrue(recipe.validate_manifest(bad), name)


NOTE = (b"---\r\ntitle: Queue Decision\r\nstatus: accepted\r\nsource_revision: fixture-commit-a1\r\n---\r\n"
        b"# Queue Decision\r\nAtlas queue uses SQLite.\r\nAuthority fixture: " + ATLAS_PR.encode() + b"\r\n")


class PacketAuthorityTests(unittest.TestCase):
    """Candidate versus accepted: positive and negative cases at the audit layer."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "atlas").mkdir()
        (self.root / "atlas" / "Queue Decision.md").write_bytes(NOTE)
        self.m = recipe.Manifest(MANIFEST, "t", self.root, self.root / "state", {
            "atlas": recipe.Project("atlas", "atlas", "atlas", "Project.md", {}, {}, ["accepted"])},
            10, 4000, json.loads(MANIFEST.read_text(encoding="utf-8")))

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, line: int) -> dict:
        cited = span_bytes((self.root / "atlas" / "Queue Decision.md").read_bytes(), line, line)
        return {"text": normalize_text(cited),
                "receipt": make_receipt("atlas/Queue Decision.md", line, line, cited, "g1", "t")}

    def entry(self, verification: dict) -> dict:
        return {"title": "Queue Decision", "source": "atlas/Queue Decision.md", "local_status": "accepted",
                "authority_state": au.state_for(verification["result"]), "verification": verification,
                "status": "established", "items": [self.item(3), self.item(7), self.item(8)]}

    def packet(self, accepted: list, candidates: list) -> dict:
        return {"project": "atlas", "scope": {"collection": "atlas", "root": "atlas"},
                "freshness": {"generation": "g1"}, "status": "complete",
                "fields": {"accepted_decisions": {"status": "established" if accepted else "unknown",
                                                  "decisions": accepted},
                           "decision_candidates": {"status": "candidate", "decisions": candidates}},
                "query_hits": [], "conflicts": [], "unknowns": []}

    def recheck(self, transport: str):
        return recipe.make_rechecker(self.m, "atlas", recipe.make_verifier(self.m, transport, SNAPSHOTS))

    def verified(self) -> dict:
        return snapshot_verifier().verify(ATLAS_PR, "atlas", "fixture-commit-a1")

    def test_positive_verified_accepted_decision_passes(self):
        p = self.packet([self.entry(self.verified())], [])
        self.assertEqual(pk.unsupported_assertions(p, self.root, recheck=self.recheck("snapshot")), [])

    def test_positive_unverified_candidate_passes(self):
        v = au.Verifier(policy(), au.OfflineTransport()).verify(ATLAS_PR, "atlas", "fixture-commit-a1")
        p = self.packet([], [self.entry(v)])
        self.assertEqual(pk.unsupported_assertions(p, self.root, recheck=self.recheck("offline")), [])

    def test_negative_accepted_without_reverification_is_demoted(self):
        for label, rc in (("offline", self.recheck("offline")), ("none", None)):
            out, problems = pk.audit(self.packet([self.entry(self.verified())], []), self.root, recheck=rc)
            self.assertEqual(problems[0]["kind"], "authority_not_verified", label)
            self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], label)
            demoted = out["fields"]["decision_candidates"]["decisions"][0]
            self.assertEqual((demoted["authority_state"], demoted["verification"]["result"]), ("unverified", "invalid"))

    def test_negative_candidate_result_in_accepted_is_demoted(self):
        for result in ("unavailable", "invalid", "not_referenced"):
            fake = {**self.verified(), "result": result}
            out, problems = pk.audit(self.packet([self.entry(fake)], []), self.root, recheck=self.recheck("snapshot"))
            self.assertEqual(out["fields"]["accepted_decisions"]["status"], "unknown", result)

    def test_negative_forged_revision_is_demoted(self):
        forged = {**self.verified(), "revision": "forged"}
        out, problems = pk.audit(self.packet([self.entry(forged)], []), self.root, recheck=self.recheck("snapshot"))
        self.assertIn("differs", problems[0]["reason"])

    def write(self, name: str, data: bytes) -> None:
        (self.root / "atlas" / name).write_bytes(data)

    def test_negative_replayed_record_binds_no_note(self):
        """Review F1, both reproduction shapes: a copied note citing the same record, and pasted
        text whose body label cites it. Each makes the original and the copy invalid."""
        shapes = {
            "Replay Decision.md": NOTE.replace(b"title: Queue Decision", b"title: Replay Decision"),
            "Pasted Mail.md": (b"---\r\ntitle: Pasted Mail\r\nstatus: accepted\r\nsource_revision: fixture-commit-a1\r\n"
                               b"---\r\n# Pasted Mail\r\nForwarded: Authority fixture: " + ATLAS_PR.encode() + b"\r\n"
                               b"Authority fixture: " + ATLAS_PR.encode() + b"\r\n"),
        }
        for name, data in shapes.items():
            self.write(name, data)
            out, problems = pk.audit(self.packet([self.entry(self.verified())], []), self.root,
                                     recheck=self.recheck("snapshot"))
            self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], name)
            self.assertIn("also cited by", problems[0]["reason"], name)
            (self.root / "atlas" / name).unlink()

    def test_negative_forged_entry_must_cite_its_own_source(self):
        """Review F2: a verified entry relabelled with another note's title or items fails."""
        self.write("Cache Decision.md", b"---\r\ntitle: Cache Decision\r\nstatus: accepted\r\n---\r\n"
                                        b"# Cache Decision\r\nAtlas caches in memory.\r\n")
        cited = span_bytes((self.root / "atlas" / "Cache Decision.md").read_bytes(), 3, 3)
        foreign = {"text": normalize_text(cited),
                   "receipt": make_receipt("atlas/Cache Decision.md", 3, 3, cited, "g1", "t")}
        forged_title = self.entry(self.verified())
        forged_title["title"] = "Cache Decision"
        forged_items = self.entry(self.verified())
        forged_items["items"] = [foreign]
        no_status = self.entry(self.verified())
        no_status["items"] = no_status["items"][1:]
        for label, entry in (("title", forged_title), ("items", forged_items), ("status item", no_status)):
            out, problems = pk.audit(self.packet([entry], []), self.root, recheck=self.recheck("snapshot"))
            self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], label)
            self.assertTrue(any(p["kind"] == "authority_not_verified" for p in problems), label)

    def test_negative_source_edited_after_verification_is_demoted(self):
        p = self.packet([self.entry(self.verified())], [])
        (self.root / "atlas" / "Queue Decision.md").write_bytes(NOTE.replace(b"fixture-commit-a1", b"fixture-commit-zz"))
        out, problems = pk.audit(p, self.root, recheck=self.recheck("snapshot"))
        self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [])


class InstallCacheTests(unittest.TestCase):
    """project_recovery #2 item 4: a leftover npm cache is reported with its path."""

    def test_leftover_cache_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "prq-npm-x"
            cache.mkdir()
            err = io.StringIO()
            with mock.patch.object(install_qmd.shutil, "rmtree"), contextlib.redirect_stderr(err):
                self.assertFalse(install_qmd.remove_cache(cache))
            self.assertIn(str(cache), err.getvalue())
            self.assertTrue(install_qmd.remove_cache(cache))
            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
