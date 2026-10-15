"""Synthetic #17 capture/replay gates; no GitHub, QMD or source-fixture writes.

GhTransport's GET is replaced with committed synthetic REST responses. Historical
context is deliberately tested separately from currently accepted decisions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock

from reliance_cases import HITS, QUERY, REPO, VAULT, make_env

import authority as au
import last_checked as lc
import packet as pk
import recipe
import rederive

SNAPSHOTS = REPO / "fixtures" / "github-snapshots"
SOURCE = "cobalt/Theme Decision.md"
OLD_CHECK = "2026-10-12T00:00:00.000Z"
FUTURE = "2999-01-01T00:00:00.000Z"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture_hashes() -> dict:
    return {p.relative_to(VAULT).as_posix(): sha(p.read_bytes())
            for p in sorted(VAULT.rglob("*")) if p.is_file()}


class LastCheckedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_fixtures = fixture_hashes()
        expected = json.loads((REPO / "fixtures" / "synthetic-vault-hashes.json").read_text("utf-8"))
        if cls.original_fixtures != expected:
            raise AssertionError("synthetic fixture hashes differ before last-checked tests")

    @classmethod
    def tearDownClass(cls):
        if fixture_hashes() != cls.original_fixtures:
            raise AssertionError("last-checked tests changed source fixtures")

    def setUp(self):
        self.env = make_env(packets=False)
        self.m = self.env.m
        self.path = self.m.state_dir / "last-checked.json"
        self.requests = []

    def tearDown(self):
        self.env.close()

    def capture(self, project="cobalt", get=None):
        snapshots = au.SnapshotTransport(SNAPSHOTS)

        def fixture_get(transport, host, api_path):
            self.requests.append((host, api_path))
            return snapshots.get(host, api_path)

        with mock.patch.object(au.GhTransport, "get", get or fixture_get):
            return lc.capture(self.m, project)

    def stored(self, project="cobalt", bundle=None):
        bundle = self.capture(project) if bundle is None else bundle
        pin = lc.write_capture(self.m, bundle, self.path)
        return bundle, lc.Replay(self.path, pin)

    def repin(self, bundle):
        self.path.write_text(json.dumps(bundle), encoding="utf-8")
        return lc.Replay(self.path, sha(self.path.read_bytes()))

    def assemble(self, history=None, project="cobalt", limit=10 ** 6):
        with rederive.VaultSession(self.m, project, HITS[project]) as session:
            kwargs = {} if history is None else {"history": history}
            return recipe.assemble(self.m, project, QUERY, session, limit,
                                   recipe.make_verifier(self.m, "offline"), **kwargs)

    def validate(self, packet, mode, history=None):
        kwargs = {} if history is None else {"history": history}
        return rederive.validate(self.m, json.dumps(packet).encode("utf-8"), "offline", None, mode,
                                 session_factory=lambda: rederive.VaultSession(self.m, "cobalt", HITS["cobalt"]),
                                 **kwargs)

    def assert_invalid(self, replay, project="cobalt"):
        result = replay.read(self.m, project)
        self.assertEqual(result["status"], "invalid", result)
        self.assertEqual(result["entries"], [], result)
        self.assertTrue(result["reason"])

    def test_capture_retains_only_successfully_verified_claims_and_raw_responses(self):
        bundle = self.capture()
        self.assertEqual(bundle["format"], "recovery-last-checked-v1")
        self.assertEqual((bundle["project"], bundle["captured_via"]), ("cobalt", "gh"))
        self.assertEqual([d["source"] for d in bundle["decisions"]], [SOURCE])
        decision = bundle["decisions"][0]
        self.assertEqual(decision["note_digest"], sha((self.env.root / SOURCE).read_bytes()))
        self.assertEqual(set(decision["note_names"]), {"theme-decision", "Theme Decision"})
        self.assertEqual(decision["actor"], "fixture-owner")
        self.assertTrue(decision["last_checked_at"])
        self.assertTrue(bundle["responses"])
        self.assertTrue(self.requests)
        self.assertEqual(bundle["policy"]["verifier"], {"transport": "gh", "serial": True})
        original = self.m.raw["authority_policy"]
        self.assertEqual({k: v for k, v in bundle["policy"].items() if k != "verifier"},
                         {k: v for k, v in original.items() if k != "verifier"})

    def test_merge_capture_keeps_each_response_needed_to_recheck_content_binding(self):
        bundle, replay = self.stored("atlas")
        paths = {r["api_path"] for r in bundle["responses"]}
        self.assertIn("repos/portfolio/atlas/pulls/7", paths)
        self.assertIn("repos/portfolio/atlas/pulls/7/reviews", paths)
        result = replay.read(self.m, "atlas")
        self.assertEqual(result["status"], "historical", result)
        self.assertEqual([e["source"] for e in result["entries"]], ["atlas/Queue Decision.md"])

    def test_valid_history_never_establishes_current_acceptance(self):
        bundle, replay = self.stored()
        with mock.patch.object(au.GhTransport, "get", side_effect=AssertionError("replay made a network request")):
            result = replay.read(self.m, "cobalt")
            packet = self.assemble(replay)
        self.assertEqual(result["status"], "historical", result)
        entry = result["entries"][0]
        self.assertEqual((entry["applicability"], entry["acceptance_effect"]), ("matches", "none"))
        self.assertEqual(entry["last_checked_at"], bundle["decisions"][0]["last_checked_at"])
        self.assertEqual(entry["approved_digest"], sha((self.env.root / SOURCE).read_bytes()))
        self.assertEqual(packet["fields"]["accepted_decisions"]["decisions"], [])
        self.assertEqual(packet["fields"]["accepted_decisions"]["status"], "unknown")
        theme = next(d for d in packet["fields"]["decision_candidates"]["decisions"]
                     if d["source"] == SOURCE)
        self.assertEqual(theme["authority_state"], "unverified")
        self.assertEqual(packet["last_checked"]["entries"], result["entries"])

    def test_old_evidence_retains_original_time_without_local_refresh(self):
        with mock.patch.object(au, "now", return_value=OLD_CHECK):
            bundle = self.capture()
        _, replay = self.stored(bundle=bundle)
        result = replay.read(self.m, "cobalt")
        self.assertEqual(result["status"], "historical", result)
        self.assertEqual(result["entries"][0]["last_checked_at"], OLD_CHECK)
        self.assertNotEqual(result["replayed_at"], OLD_CHECK)

    def test_both_validation_modes_derive_history_from_validator_owned_replay(self):
        _, replay = self.stored()
        packet = self.assemble(replay)
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                result = self.validate(packet, mode, replay)
                self.assertEqual((result["result"], result["failures"]), ("equal_to_rederived", 0), result["problems"])
                self.assertEqual(result["packet"]["last_checked"]["entries"], packet["last_checked"]["entries"])

    def test_forged_deleted_and_timestamp_modified_packet_history_is_rejected(self):
        _, replay = self.stored()
        original = self.assemble(replay)
        changes = {
            "deleted block": lambda p: p.pop("last_checked"),
            "deleted entry": lambda p: p["last_checked"]["entries"].clear(),
            "forged actor": lambda p: p["last_checked"]["entries"][0].update(actor="visitor"),
            "fresh check claim": lambda p: p["last_checked"]["entries"][0].update(last_checked_at=FUTURE),
            "current acceptance claim": lambda p: p["last_checked"]["entries"][0].update(acceptance_effect="verified"),
        }
        for label, mutate in changes.items():
            for mode in rederive.MODES:
                with self.subTest(change=label, mode=mode):
                    packet = copy.deepcopy(original)
                    mutate(packet)
                    result = self.validate(packet, mode, replay)
                    self.assertEqual(result["result"], "rejected", result["problems"])
                    self.assertGreater(result["failures"], 0)

    def test_packet_cannot_select_its_own_history_when_validator_has_none(self):
        _, replay = self.stored()
        packet = self.assemble(replay)
        for mode in rederive.MODES:
            result = self.validate(packet, mode)
            self.assertEqual(result["result"], "rejected", result["problems"])

    def test_missing_capture_is_unavailable_and_empty(self):
        result = lc.Replay(self.path, "0" * 64).read(self.m, "cobalt")
        self.assertEqual((result["status"], result["entries"]), ("unavailable", []))

    def test_missing_wrong_or_noncanonical_pin_fails_closed(self):
        self.stored()
        for pin in (None, "", "xyz", "0" * 64, "A" * 64):
            with self.subTest(pin=pin):
                self.assert_invalid(lc.Replay(self.path, pin))

    def test_altered_capture_fails_supplied_pin(self):
        _, replay = self.stored()
        self.path.write_bytes(self.path.read_bytes() + b" ")
        self.assert_invalid(replay)

    def test_malformed_capture_is_invalid_even_with_matching_pin(self):
        self.path.write_bytes(b"{not json")
        self.assert_invalid(lc.Replay(self.path, sha(self.path.read_bytes())))

    def test_hostile_json_and_excessive_structure_problems_fail_closed(self):
        bundle, _ = self.stored()
        malformed = (b"[]", b"null", b'{"x":1,"x":2}', b'{"x":NaN}',
                     b'{"x":' + b"[" * 80 + b"0" + b"]" * 80 + b"}")
        for data in malformed:
            with self.subTest(data=data[:50]):
                self.path.write_bytes(data)
                self.assert_invalid(lc.Replay(self.path, sha(data)))
        bundle.update({f"unexpected_{i}": "synthetic" for i in range(110)})
        self.assert_invalid(self.repin(bundle))

    def test_wrong_project_is_invalid(self):
        _, replay = self.stored()
        self.assert_invalid(replay, "atlas")

    def test_snapshot_or_offline_transport_cannot_create_live_capture(self):
        for transport in (au.SnapshotTransport(SNAPSHOTS), au.OfflineTransport()):
            with self.subTest(transport=transport.name):
                with self.assertRaises((ValueError, recipe.RecipeError)):
                    lc.capture(self.m, "cobalt", au.Verifier(self.m.raw["authority_policy"], transport))

    def test_fake_gh_transport_cannot_masquerade_as_live_capture(self):
        class FakeGh:
            name = "gh"
            def get(self, host, path):
                raise AssertionError("untrusted transport should not be called")
        with self.assertRaises((ValueError, recipe.RecipeError)):
            lc.capture(self.m, "cobalt", au.Verifier(self.m.raw["authority_policy"], FakeGh()))

    def test_capture_with_different_acceptance_policy_is_refused(self):
        policy = copy.deepcopy(self.m.raw["authority_policy"])
        policy["repositories"][1]["approvers"] = ["visitor"]
        with self.assertRaises((ValueError, recipe.RecipeError)):
            lc.capture(self.m, "cobalt", au.Verifier(policy, au.GhTransport()))

    def test_previously_used_verifier_cannot_claim_a_fresh_check(self):
        verifier = au.Verifier(copy.deepcopy(self.m.raw["authority_policy"]), au.GhTransport())
        snapshots = au.SnapshotTransport(SNAPSHOTS)
        with mock.patch.object(au.GhTransport, "get",
                               lambda transport, host, path: snapshots.get(host, path)):
            verifier.fetch_path("github.example.test", "repos/portfolio/cobalt/issues/comments/501")
        with mock.patch.object(au.GhTransport, "get", side_effect=AssertionError("cached capture requested network")):
            with self.assertRaises((ValueError, recipe.RecipeError)):
                lc.capture(self.m, "cobalt", verifier)

    def test_source_or_policy_changes_during_capture_are_refused(self):
        snapshots = au.SnapshotTransport(SNAPSHOTS)
        source = self.env.root / SOURCE
        original_source = source.read_bytes()
        original_policy = copy.deepcopy(self.m.raw["authority_policy"])
        for change in ("source", "policy"):
            source.write_bytes(original_source)
            self.m.raw["authority_policy"] = copy.deepcopy(original_policy)

            def racing_get(transport, host, api_path):
                response = snapshots.get(host, api_path)
                if change == "source":
                    source.write_bytes(original_source + b"\nSynthetic capture-time change.\n")
                else:
                    self.m.raw["authority_policy"]["repositories"][1]["approvers"] = ["visitor"]
                return response

            with self.subTest(change=change):
                with self.assertRaises((ValueError, recipe.RecipeError)):
                    self.capture(get=racing_get)

    def test_unavailable_requests_do_not_become_historical_approvals(self):
        def unavailable(transport, host, path):
            raise au.Unavailable("synthetic offline refusal")
        bundle = self.capture(get=unavailable)
        self.assertEqual(bundle["decisions"], [])
        _, replay = self.stored(bundle=bundle)
        self.assertEqual(replay.read(self.m, "cobalt")["entries"], [])

    def test_inconsistent_or_untrusted_captures_are_invalid_even_if_repinned(self):
        original, _ = self.stored()
        changes = {
            "snapshot provenance": lambda b: b.update(captured_via="snapshot"),
            "future capture": lambda b: b.update(captured_at=FUTURE),
            "future verification": lambda b: b["decisions"][0].update(last_checked_at=FUTURE),
            "forged actor": lambda b: b["decisions"][0].update(actor="visitor"),
            "forged revision": lambda b: b["decisions"][0].update(revision="forged"),
            "forged digest": lambda b: b["decisions"][0].update(note_digest="0" * 64),
            "missing evidence": lambda b: b.update(responses=[]),
            "unrelated source": lambda b: b["decisions"][0].update(source="atlas/Queue Decision.md"),
            "policy digest": lambda b: b.update(policy_sha256="0" * 64),
        }
        for label, mutate in changes.items():
            with self.subTest(change=label):
                bundle = copy.deepcopy(original)
                mutate(bundle)
                self.assert_invalid(self.repin(bundle))

    def test_changed_note_remains_historical_without_claiming_current_coverage(self):
        _, replay = self.stored()
        path = self.env.root / SOURCE
        path.write_bytes(path.read_bytes() + b"\nSynthetic later change.\n")
        result = replay.read(self.m, "cobalt")
        self.assertEqual((result["status"], result["entries"][0]["applicability"]), ("historical", "note_changed"))
        self.assertEqual(result["entries"][0]["acceptance_effect"], "none")

    def test_changed_policy_is_explicit_and_verifier_selection_does_not_change_policy(self):
        _, replay = self.stored()
        self.m.raw["authority_policy"]["verifier"] = {"transport": "offline", "serial": True}
        self.assertEqual(replay.read(self.m, "cobalt")["entries"][0]["applicability"], "matches")
        self.m.raw["authority_policy"]["repositories"][1]["approvers"] = ["visitor"]
        result = replay.read(self.m, "cobalt")
        self.assertEqual((result["status"], result["entries"][0]["applicability"]), ("historical", "policy_changed"))

    def test_changed_reference_is_explicit(self):
        _, replay = self.stored()
        path = self.env.root / SOURCE
        path.write_bytes(path.read_bytes().replace(b"issuecomment-501", b"issuecomment-502"))
        result = replay.read(self.m, "cobalt")
        self.assertEqual((result["status"], result["entries"][0]["applicability"]), ("historical", "reference_changed"))

    def test_missing_source_is_explicit(self):
        _, replay = self.stored()
        (self.env.root / SOURCE).unlink()
        result = replay.read(self.m, "cobalt")
        self.assertEqual((result["status"], result["entries"][0]["applicability"]), ("historical", "missing_source"))

    def test_capture_and_replay_leave_source_bytes_unchanged(self):
        before = {p.relative_to(self.env.root).as_posix(): p.read_bytes()
                  for p in self.env.root.rglob("*") if p.is_file()}
        _, replay = self.stored()
        packet = self.assemble(replay)
        for mode in rederive.MODES:
            self.validate(packet, mode, replay)
        after = {p.relative_to(self.env.root).as_posix(): p.read_bytes()
                 for p in self.env.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_capture_write_is_new_json_only_and_outside_vault(self):
        bundle = self.capture()
        pin = lc.write_capture(self.m, bundle, self.path)
        self.assertEqual(pin, sha(self.path.read_bytes()))
        original = self.path.read_bytes()
        with self.assertRaises((ValueError, recipe.RecipeError, FileExistsError)):
            lc.write_capture(self.m, bundle, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        for path in (self.m.state_dir / "capture.txt", self.env.root / "capture.json",
                     self.env.root.parent / "outside.json", self.m.state_dir / ".." / ".." / "escape.json"):
            with self.subTest(path=path):
                with self.assertRaises((ValueError, recipe.RecipeError)):
                    lc.write_capture(self.m, bundle, path)
                self.assertFalse(path.exists())

    def test_history_is_budgeted_and_omissions_are_explicit(self):
        _, replay = self.stored()
        packet = self.assemble(replay, limit=1)
        self.assertEqual(packet["last_checked"]["entries"], [])
        self.assertEqual(packet["budget"]["omitted"]["last_checked"], 1)
        self.assertTrue(packet["budget"]["truncated"])
        for mode in rederive.MODES:
            result = self.validate(packet, mode, replay)
            self.assertEqual(result["result"], "equal_to_rederived", result["problems"])

    def test_no_history_keeps_original_packet_shape_and_content(self):
        with mock.patch.object(recipe, "now", return_value=OLD_CHECK):
            original = self.assemble()
            with rederive.VaultSession(self.m, "cobalt", HITS["cobalt"]) as session:
                explicit = recipe.assemble(self.m, "cobalt", QUERY, session, 10 ** 6,
                                           recipe.make_verifier(self.m, "offline"), history=None)
        self.assertNotIn("last_checked", original)
        self.assertNotIn("last_checked", original["budget"]["omitted"])
        self.assertEqual(pk.compact(original), pk.compact(explicit))


if __name__ == "__main__":
    unittest.main()
