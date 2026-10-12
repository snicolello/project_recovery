"""Tests for release R2: serial acceptance verification and the candidate versus accepted
distinction (owner ruling B). No Node, QMD or network needed.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
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


VAULT = REPO / "fixtures" / "synthetic-vault"
QUEUE = (VAULT / "atlas" / "Queue Decision.md").read_bytes()
THEME = (VAULT / "cobalt" / "Theme Decision.md").read_bytes()
THEME_URL = f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-501"
QUEUE_NAMES = ("queue-decision", "Queue Decision")
THEME_NAMES = ("theme-decision", "Theme Decision")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
        v = snapshot_verifier().verify(f"Authority fixture: {ATLAS_PR}", "atlas", "fixture-commit-a1",
                                       QUEUE_NAMES, sha(QUEUE))
        self.assertEqual(v["result"], "verified")
        self.assertEqual(v["revision"], "fixture-merge-a7")
        self.assertTrue(v["verified_at"])
        self.assertEqual(au.state_for(v["result"]), "verified")

    def test_verified_issue_comment(self):
        url = f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-501"
        v = snapshot_verifier().verify(url, "cobalt", None, THEME_NAMES, sha(THEME))
        self.assertEqual((v["result"], v["kind"]), ("verified", "issue_comment"))
        changed = snapshot_verifier().verify(url, "cobalt", None, THEME_NAMES,
                                             sha(THEME.replace(b"dark theme", b"light theme")))
        self.assertEqual((changed["result"], changed.get("mismatch")), ("invalid", True))

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


BORROW = REPO / "fixtures" / "borrow-notes" / "cobalt"


def borrow(title: str) -> tuple[str, tuple, str]:
    """(digest, names, permalink) of a committed borrow-path note."""
    data = (BORROW / f"{title}.md").read_bytes()
    perm = title.lower().replace(" ", "-")
    return hashlib.sha256(data).hexdigest(), (perm, title), perm


class BorrowPathTests(unittest.TestCase):
    """Re-review 2026-10-12: approval text that is quoted, negated, fenced, or written by a
    non-approver never binds, even when it names the note and its exact digest."""

    COBALT = f"https://{HOST}/portfolio/cobalt"

    def verify(self, url: str, title: str, binding: str | None = None, directory: Path = SNAPSHOTS) -> dict:
        digest, names, _ = borrow(title)
        return snapshot_verifier(directory).verify(url, "cobalt", binding, names, digest)

    def test_quoted_negated_and_fenced_markers_do_not_bind(self):
        for n, title in ((503, "Quote Decision"), (504, "Refused Decision"), (505, "Fenced Decision")):
            v = self.verify(f"{self.COBALT}/issues/5#issuecomment-{n}", title)
            self.assertEqual((v["result"], v.get("conflict")), ("invalid", "approved_text_mismatch"), title)

    def test_marker_parser_takes_only_whole_lines(self):
        d = "a" * 64
        self.assertEqual(au.approval_markers(f"x\r\nACCEPTED: n sha256:{d}\r\n", "ACCEPTED:"), [("n", d)])
        for text in (f"> ACCEPTED: n sha256:{d}", f"NOT ACCEPTED: n sha256:{d}", f"  ACCEPTED: n sha256:{d}",
                     f"```\nACCEPTED: n sha256:{d}\n```", f"~~~\nACCEPTED: n sha256:{d}\n~~~",
                     f"```\nunterminated\nACCEPTED: n sha256:{d}", f"ACCEPTED: n sha256:{d} but no",
                     f"ACCEPTED: n sha256:{d}0"):
            self.assertEqual(au.approval_markers(text, "ACCEPTED:"), [], text)

    def test_merge_messages_titles_and_commit_messages_never_bind(self):
        """Re-review 3, F2: markers in a merge message, a PR title or a squashed commit message
        never bind, whoever wrote the pull request; only an approver's approving review does."""
        for n, title, rev in ((11, "Banner Decision", "fixture-commit-c11"), (12, "Squash Decision", "fixture-commit-c12"),
                              (13, "Commit Decision", "fixture-commit-c13")):
            v = self.verify(f"{self.COBALT}/pull/{n}", title, rev)
            self.assertEqual((v["result"], v.get("conflict")), ("invalid", "approved_text_mismatch"), title)
            self.assertIn("no approver-authored approval text", v["reason"], title)
        with tempfile.TemporaryDirectory() as tmp:  # an approver author changes nothing
            root = self.edited(tmp, "pulls/11.json", user={"login": "fixture-owner"})
            v = self.verify(f"{self.COBALT}/pull/11", "Banner Decision", "fixture-commit-c11", root)
            self.assertEqual(v.get("conflict"), "approved_text_mismatch")

    def test_marker_only_in_a_non_approver_review_is_refused(self):
        v = self.verify(f"{self.COBALT}/pull/14", "Visitor Decision", "fixture-commit-c14")
        self.assertEqual((v["result"], v.get("conflict")), ("invalid", "approval_text_not_approver_authored"))

    def edited(self, tmp: str, rel: str, review: dict | None = None, **changes) -> Path:
        root = Path(tmp) / "snaps"
        shutil.copytree(SNAPSHOTS, root)
        path = root / HOST / "repos" / "portfolio" / "cobalt" / rel
        body = json.loads(path.read_text(encoding="utf-8"))
        if review is not None:
            body[0].update(review)
        else:
            body.update(changes)
        path.write_text(json.dumps(body), encoding="utf-8")
        return root

    def test_review_must_be_an_approving_review_by_an_approver_on_the_note_revision(self):
        url = f"{self.COBALT}/pull/14"
        cases = {"approver, approved, same revision": ({"user": {"login": "fixture-owner"}}, "verified"),
                 "approver, changes requested": ({"user": {"login": "fixture-owner"}, "state": "CHANGES_REQUESTED"},
                                                 "approval_text_not_approver_authored"),
                 "approver, other revision": ({"user": {"login": "fixture-owner"}, "commit_id": "fixture-commit-zz"},
                                              "approval_text_not_approver_authored")}
        for label, (change, expected) in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                v = self.verify(url, "Visitor Decision", "fixture-commit-c14", self.edited(tmp, "pulls/14/reviews.json", change))
                self.assertEqual(v["result"] if expected == "verified" else v.get("conflict"), expected, label)


class ReferenceIdentityTests(unittest.TestCase):
    """Re-review 3, B1 and B2: record identity is ASCII and case-insensitive, and the record
    must belong to the cited repository."""

    def test_non_ascii_digits_are_not_a_reference(self):
        self.assertIsNone(au.parse_reference(f"https://{HOST}/portfolio/atlas/pull/\u0667"))
        self.assertIsNone(au.parse_reference(f"https://{HOST}/portfolio/cobalt/issues/5#issuecomment-50\u0661"))

    def test_case_variants_share_one_identity(self):
        a = au.parse_reference(f"https://{HOST}/portfolio/Cobalt/issues/5#issuecomment-501")
        b = au.parse_reference(f"https://{HOST.upper()}/Portfolio/cobalt/issues/5#issuecomment-501")
        self.assertEqual(au.ref_key(a), au.ref_key(b))

    def test_record_from_another_repository_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "snaps"
            shutil.copytree(SNAPSHOTS, root)
            path = root / HOST / "repos" / "portfolio" / "atlas" / "pulls" / "7.json"
            body = json.loads(path.read_text(encoding="utf-8"))
            body["html_url"] = f"https://{HOST}/elsewhere/atlas/pull/7"
            path.write_text(json.dumps(body), encoding="utf-8")
            v = snapshot_verifier(root).verify(ATLAS_PR, "atlas", "fixture-commit-a1", QUEUE_NAMES, sha(QUEUE))
            self.assertEqual(v["result"], "invalid")
            self.assertIn("record belongs to elsewhere/atlas", v["reason"])


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


class PacketAuthorityTests(unittest.TestCase):
    """Candidate versus accepted at the audit layer, on the real fixture note bytes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for project in ("atlas", "cobalt"):
            (self.root / project).mkdir()
        self.write("atlas/Queue Decision.md", QUEUE)
        self.write("cobalt/Theme Decision.md", THEME)
        raw = json.loads(SCEN_MANIFEST.read_text(encoding="utf-8"))
        self.m = recipe.Manifest(SCEN_MANIFEST, "t", self.root, self.root / "state", {
            p: recipe.Project(p, p, p, "Project.md", {}, {}, ["accepted"]) for p in ("atlas", "cobalt")},
            10, 4000, raw)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel: str, data: bytes) -> None:
        (self.root / rel).write_bytes(data)

    def item(self, rel: str, line: int) -> dict:
        cited = span_bytes((self.root / rel).read_bytes(), line, line)
        return {"text": normalize_text(cited), "receipt": make_receipt(rel, line, line, cited, "g1", "t")}

    def entry(self, rel: str, verification: dict, title: str | None = None) -> dict:
        """A decision entry with fresh receipts on the current bytes of ``rel``: its status,
        statement and reference lines."""
        note = recipe.parse_note((self.root / rel).read_bytes().decode("utf-8"))
        ref = au.reference_line(self.m.raw["authority_policy"], note)
        lines = [note["front"]["status"].number, note["statement"].number, ref.number]
        return {"title": title or recipe.front_value(note["front"]["title"]), "source": rel,
                "local_status": "accepted", "authority_state": au.state_for(verification["result"]),
                "verification": verification, "status": "established", "items": [self.item(rel, n) for n in lines]}

    def packet(self, project: str, accepted: list, candidates: list) -> dict:
        return {"project": project, "scope": {"collection": project, "root": project},
                "freshness": {"generation": "g1"}, "status": "complete",
                "fields": {"accepted_decisions": {"status": "established" if accepted else "unknown",
                                                  "decisions": accepted},
                           "decision_candidates": {"status": "candidate", "decisions": candidates}},
                "query_hits": [], "conflicts": [], "unknowns": []}

    def recheck(self, project: str, transport: str = "snapshot"):
        return recipe.make_rechecker(self.m, project, recipe.make_verifier(self.m, transport, SNAPSHOTS))

    def verified(self) -> dict:
        return snapshot_verifier().verify(ATLAS_PR, "atlas", "fixture-commit-a1", QUEUE_NAMES, sha(QUEUE))

    def verified_theme(self) -> dict:
        return snapshot_verifier().verify(THEME_URL, "cobalt", None, THEME_NAMES, sha(THEME))

    def audit(self, project: str, entry: dict, transport: str = "snapshot"):
        return pk.audit(self.packet(project, [entry], []), self.root, recheck=self.recheck(project, transport))

    def assert_demoted(self, out: dict, problems: list, kind: str, label: str = ""):
        self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], label)
        self.assertIn(kind, [p["kind"] for p in problems], label)

    # Positive controls ---------------------------------------------------------

    def test_positive_unchanged_controls_pass(self):
        self.assertEqual(self.verified()["result"], "verified")
        self.assertEqual(self.verified_theme()["result"], "verified")
        for project, rel, v in (("atlas", "atlas/Queue Decision.md", self.verified()),
                                ("cobalt", "cobalt/Theme Decision.md", self.verified_theme())):
            self.assertEqual(self.audit(project, self.entry(rel, v))[1], [], rel)

    def test_positive_unverified_candidate_passes(self):
        v = au.Verifier(policy(), au.OfflineTransport()).verify(ATLAS_PR, "atlas", "fixture-commit-a1",
                                                                 QUEUE_NAMES, sha(QUEUE))
        p = self.packet("atlas", [], [self.entry("atlas/Queue Decision.md", v)])
        self.assertEqual(pk.unsupported_assertions(p, self.root, recheck=self.recheck("atlas", "offline")), [])

    # Owner review 2026-10-12: content binding -----------------------------------

    def test_owner_case_a_changed_decision_text_is_demoted(self):
        claimed = self.verified()
        self.write("atlas/Queue Decision.md", QUEUE.replace(b"Atlas queue uses SQLite", b"Atlas queue uses Redis"))
        out, problems = self.audit("atlas", self.entry("atlas/Queue Decision.md", claimed))
        self.assert_demoted(out, problems, "approved_text_mismatch")
        v = snapshot_verifier().verify(ATLAS_PR, "atlas", "fixture-commit-a1", QUEUE_NAMES,
                                       sha((self.root / "atlas/Queue Decision.md").read_bytes()))
        self.assertEqual((v["result"], v.get("mismatch")), ("invalid", True))

    def test_owner_case_b_replacement_note_is_demoted(self):
        claimed = self.verified()
        (self.root / "atlas" / "Queue Decision.md").unlink()
        self.write("atlas/Deploy Decision.md",
                   b"---\r\ntitle: Deploy Decision\r\ntype: note\r\npermalink: deploy-decision\r\nproject: atlas\r\n"
                   b"status: accepted\r\nsource_revision: fixture-commit-a1\r\n---\r\n# Deploy Decision\r\n"
                   b"Atlas deploys to production without approval.\r\nAuthority fixture: " + ATLAS_PR.encode() + b"\r\n")
        out, problems = self.audit("atlas", self.entry("atlas/Deploy Decision.md", claimed))
        self.assert_demoted(out, problems, "approved_text_mismatch")

    def test_owner_case_c_changed_theme_is_demoted(self):
        claimed = self.verified_theme()
        self.write("cobalt/Theme Decision.md", THEME.replace(b"dark theme", b"light theme"))
        out, problems = self.audit("cobalt", self.entry("cobalt/Theme Decision.md", claimed))
        self.assert_demoted(out, problems, "approved_text_mismatch")

    def test_record_without_a_digest_never_promotes(self):
        v = snapshot_verifier().verify(ATLAS_PR, "atlas", "fixture-commit-a1", QUEUE_NAMES, None)
        self.assertEqual((v["result"], v.get("mismatch")), ("invalid", True))

    # Earlier review rounds -------------------------------------------------------

    def test_negative_accepted_without_reverification_is_demoted(self):
        for label, transport in (("offline", "offline"), ("none", None)):
            entry = self.entry("atlas/Queue Decision.md", self.verified())
            rc = self.recheck("atlas", transport) if transport else None
            out, problems = pk.audit(self.packet("atlas", [entry], []), self.root, recheck=rc)
            self.assertEqual(problems[0]["kind"], "authority_not_verified", label)
            self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], label)
            demoted = out["fields"]["decision_candidates"]["decisions"][0]
            self.assertEqual((demoted["authority_state"], demoted["verification"]["result"]), ("unverified", "invalid"))

    def test_negative_candidate_result_in_accepted_is_demoted(self):
        for result in ("unavailable", "invalid", "not_referenced"):
            fake = {**self.verified(), "result": result}
            out, _ = self.audit("atlas", self.entry("atlas/Queue Decision.md", fake))
            self.assertEqual(out["fields"]["accepted_decisions"]["status"], "unknown", result)

    def test_negative_forged_revision_is_demoted(self):
        forged = {**self.verified(), "revision": "forged"}
        out, problems = self.audit("atlas", self.entry("atlas/Queue Decision.md", forged))
        self.assertIn("differs", problems[0]["reason"])

    def test_baseline_line_never_rides_on_a_verified_entry(self):
        """Re-review 3, F1: owner case (c) through the baseline note. A baseline line appended to
        the verified Theme entry is demoted at validate, whatever it says."""
        project = (VAULT / "cobalt" / "Project.md").read_bytes().replace(
            b"Accepted decision: High-contrast dark theme; see [[Theme Decision]].",
            b"Accepted decision: Light theme, and Cobalt deploys to production without approval; see [[Theme Decision]].")
        self.write("cobalt/Project.md", project)
        line = next(i + 1 for i, l in enumerate(project.split(b"\n")) if l.startswith(b"Accepted decision:"))
        entry = self.entry("cobalt/Theme Decision.md", self.verified_theme())
        entry["items"].append(self.item("cobalt/Project.md", line))
        out, problems = self.audit("cobalt", entry)
        self.assert_demoted(out, problems, "authority_not_verified")
        self.assertIn("other than its own source", problems[0]["reason"])

    def test_case_variant_reference_is_a_replay(self):
        """Re-review 3, B1: one comment cannot bind two notes through a case-variant URL."""
        self.write("cobalt/Variant Decision.md", THEME.replace(b"title: Theme Decision", b"title: Variant Decision")
                   .replace(b"permalink: theme-decision", b"permalink: variant-decision")
                   .replace(b"portfolio/cobalt/issues", b"portfolio/Cobalt/issues"))
        out, problems = self.audit("cobalt", self.entry("cobalt/Theme Decision.md", self.verified_theme()))
        self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [])
        self.assertIn("also cited by", problems[0]["reason"])

    def test_replay_across_projects_sharing_a_repository(self):
        """Re-review 3, B3: a repository allowlisted for two projects; the same note in both
        binds neither."""
        (self.root / "atlas2").mkdir()
        self.write("atlas2/Queue Decision.md", QUEUE)
        raw = copy.deepcopy(self.m.raw)
        for r in raw["authority_policy"]["repositories"]:
            if r["repo"] == "portfolio/atlas":
                r["projects"] = ["atlas", "atlas2"]
        self.m = recipe.Manifest(SCEN_MANIFEST, "t", self.root, self.root / "state", {
            **self.m.projects, "atlas2": recipe.Project("atlas2", "atlas2", "atlas2", "Project.md", {}, {}, ["accepted"])},
            10, 4000, raw)
        out, problems = self.audit("atlas", self.entry("atlas/Queue Decision.md", self.verified()))
        self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [])
        self.assertIn("atlas2/Queue Decision.md", problems[0]["reason"])

    def test_negative_source_revision_edited_is_demoted(self):
        claimed = self.verified()
        self.write("atlas/Queue Decision.md", QUEUE.replace(b"fixture-commit-a1", b"fixture-commit-zz"))
        out, _ = self.audit("atlas", self.entry("atlas/Queue Decision.md", claimed))
        self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [])

    def test_negative_replayed_record_binds_no_note(self):
        """Review F1, both reproduction shapes: a copied note citing the same record, and pasted
        text whose body label cites it. Each makes the original and the copy invalid."""
        shapes = {
            "atlas/Replay Decision.md": QUEUE.replace(b"title: Queue Decision", b"title: Replay Decision"),
            "atlas/Pasted Mail.md": (b"---\r\ntitle: Pasted Mail\r\nstatus: accepted\r\nsource_revision: fixture-commit-a1\r\n"
                                     b"---\r\n# Pasted Mail\r\nForwarded: Authority fixture: " + ATLAS_PR.encode() + b"\r\n"
                                     b"Authority fixture: " + ATLAS_PR.encode() + b"\r\n"),
        }
        for rel, data in shapes.items():
            self.write(rel, data)
            out, problems = self.audit("atlas", self.entry("atlas/Queue Decision.md", self.verified()))
            self.assertEqual(out["fields"]["accepted_decisions"]["decisions"], [], rel)
            self.assertIn("also cited by", problems[0]["reason"], rel)
            (self.root / rel).unlink()

    def test_negative_forged_entry_must_cite_its_own_source(self):
        """Review F2: a verified entry relabelled with another note's title or items fails."""
        self.write("atlas/Cache Decision.md", b"---\r\ntitle: Cache Decision\r\nstatus: accepted\r\n---\r\n"
                                              b"# Cache Decision\r\nAtlas caches in memory.\r\n")
        foreign = self.item("atlas/Cache Decision.md", 3)
        forged_title = self.entry("atlas/Queue Decision.md", self.verified(), title="Cache Decision")
        forged_items = self.entry("atlas/Queue Decision.md", self.verified())
        forged_items["items"] = [foreign]
        no_status = self.entry("atlas/Queue Decision.md", self.verified())
        no_status["items"] = no_status["items"][1:]
        for label, entry in (("title", forged_title), ("items", forged_items), ("status item", no_status)):
            out, problems = self.audit("atlas", entry)
            self.assert_demoted(out, problems, "authority_not_verified", label)


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
