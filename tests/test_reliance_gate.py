"""project_recovery #6, the R3 reliance gate: validate re-derives a received packet.

Each case in ``reliance_cases.CASES`` names its finding (fifth review F1 to F3, or a
model-shaped, malformed or adversarial variant) and its acceptance criterion. No Node,
QMD or network needed: ``requery`` mode is exercised with a vault-backed stand-in that
returns the hits the packet was assembled from; the scenario gates run it through QMD.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tracemalloc
import unittest
import unittest.mock

from reliance_cases import (CASES, EMPTY_HIT, HITS, LIMIT_CASES, LINK_NOTE, assemble, build, make_env,  # sets sys.path
                            record_generation, resettle)

import packet as pk  # noqa: E402
import recipe  # noqa: E402
import recover  # noqa: E402
import rederive  # noqa: E402

LIMIT_TEXT = rederive.GUARANTEE["not_rederived_in_packet_mode"][0]


def transport_for(name: str) -> str:
    return "offline" if name.endswith("offline") else "snapshot"


def tree(root) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class RelianceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = make_env()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def validate(self, data: bytes, mode: str, project: str, transport: str = "snapshot") -> dict:
        env = self.env
        return rederive.validate(env.m, data, transport, None, mode,
                                 session_factory=lambda: rederive.VaultSession(env.m, project, HITS[project]))

    def packet_bytes(self, name: str) -> bytes:
        return json.dumps(self.env.packets[name]).encode("utf-8")

    # AC5: what the assembler produces still validates, and validate returns the re-derived packet
    def test_assembler_packets_validate_in_both_modes(self):
        for name, p in self.env.packets.items():
            for mode in rederive.MODES:
                with self.subTest(packet=name, mode=mode):
                    r = self.validate(self.packet_bytes(name), mode, p["project"], transport_for(name))
                    self.assertEqual((r["result"], r["failures"]), ("equal_to_rederived", 0), r["problems"][:3])
                    self.assertEqual(pk.canonical(r["packet"]), pk.canonical(p))
                    self.assertEqual(r["checks"]["rederivation"]["rederived_digest"], pk.digest(p))

    def test_fixture_packets_exercise_what_the_cases_need(self):
        p = self.env.packets
        self.assertEqual([d["title"] for d in p["cobalt"]["fields"]["accepted_decisions"]["decisions"]], ["Theme Decision"])
        self.assertTrue(p["cobalt"]["conflicts"] and p["cobalt"]["unknowns"] and p["cobalt"]["query_hits"])
        self.assertTrue(p["atlas"]["missing_sources"] and p["atlas"]["fields"]["other_decisions"]["decisions"])
        self.assertEqual(p["atlas_offline"]["fields"]["accepted_decisions"]["status"], "unknown")
        omitted = p["atlas_tight"]["budget"]["omitted"]
        self.assertTrue(omitted["query_hits"] and (omitted["other_decisions"] or omitted["decision_candidates"]), omitted)
        self.assertEqual((p["cobalt_tight"]["budget"]["omitted"], p["cobalt_tight"]["query_hits"]),
                         ({"query_hits": 1, "other_decisions": 0, "decision_candidates": 0}, []))

    # AC1 to AC4, AC6: every reproducing case is rejected (or refused) under every mode it lists
    def test_reproducing_cases(self):
        for case in CASES:
            for mode in case.modes:
                with self.subTest(case=case.id, finding=case.finding, mode=mode, what=case.what):
                    original = self.env.packets[case.packet]
                    r = self.validate(build(self.env, case), mode, original["project"], transport_for(case.packet))
                    self.assertEqual(r["result"], case.expect, r["problems"][:3])
                    if case.expect == "equal_to_rederived":
                        continue
                    self.assertGreater(r["failures"], 0)
                    self.assertTrue(any(x["field"] != "budget.tokens" for x in r["problems"]), r["problems"])
                    if case.expect == "not_rederivable":
                        self.assertIsNone(r["packet"])
                    elif not ((mode == "packet" and case.replay_input) or case.replay_input == "both"):
                        # nothing from the submitted packet is kept: the output is the re-derivation
                        self.assertEqual(pk.canonical(r["packet"]), pk.canonical(original))

    def test_injected_text_never_reaches_the_output(self):
        """Review R1 and re-review R11: a packet cannot write its own conflicts, hits or unknowns."""
        for case in (c for c in CASES if c.id in ("M-23", "M-24", "M-25")):
            for mode in rederive.MODES:
                with self.subTest(case=case.id, mode=mode):
                    r = self.validate(build(self.env, case), mode, "cobalt")
                    self.assertEqual(r["result"], "rejected")
                    self.assertNotIn("OWNER", json.dumps(r["packet"]))

    def test_case_ids_are_unique_and_traced(self):
        ids = [c.id for c in CASES]
        self.assertEqual(len(ids), len(set(ids)))
        for c in CASES:
            self.assertIn(c.finding, ("F1", "F2", "F3", "model"))
            self.assertRegex(c.criterion, r"^AC[1-7]$")
        for finding in ("F1", "F2", "F3"):
            self.assertTrue(any(c.finding == finding for c in CASES), finding)

    def test_structure_and_rederivation_are_reported_separately(self):
        case = next(c for c in CASES if c.id == "F1-a")
        r = self.validate(build(self.env, case), "packet", "cobalt")
        self.assertEqual(r["checks"]["structure"]["failures"], 1)
        self.assertEqual({x["check"] for x in r["problems"]}, {"structure", "rederivation"})
        p = copy.deepcopy(self.env.packets["cobalt"])
        v = p["fields"]["accepted_decisions"]["decisions"][0]["verification"]
        v["reason"] = "x" * len(v["reason"].encode("utf-8"))  # same length: no token-count difference
        r = self.validate(json.dumps(p).encode("utf-8"), "packet", "cobalt")
        self.assertEqual(r["checks"]["structure"]["failures"], 0)
        self.assertEqual([x["field"] for x in r["problems"]],
                         ["fields.accepted_decisions.decisions[0].verification.reason"])

    # AC7: the limits of packet mode are stated, and tested as limits
    def test_packet_mode_limits_are_stated_not_hidden(self):
        for case in (c for c in CASES if c.id in LIMIT_CASES):
            with self.subTest(case=case.id):
                original = self.env.packets[case.packet]
                r = self.validate(build(self.env, case), "packet", original["project"], transport_for(case.packet))
                self.assertEqual(r["result"], "equal_to_rederived")
                self.assertIn(LIMIT_TEXT, r["guarantee"]["not_established"])
        r = self.validate(self.packet_bytes("cobalt"), "requery", "cobalt")
        self.assertNotIn(LIMIT_TEXT, r["guarantee"]["not_established"])

    def test_guarantee_is_stated_only_on_a_pass(self):
        ok = self.validate(self.packet_bytes("cobalt"), "requery", "cobalt")
        self.assertIn("deterministic assembler", ok["guarantee"]["established"])
        self.assertTrue(any("trust root" in x for x in ok["guarantee"]["not_established"]))
        bad = self.validate(build(self.env, CASES[0]), "requery", "cobalt")
        self.assertIsNone(bad["guarantee"]["established"])

    # AC4 (F3): the claim-level audit also demotes; no verified entry survives a mismatch
    def test_audit_demotes_after_local_status_mismatch(self):
        forged = copy.deepcopy(self.env.packets["cobalt"])
        forged["fields"]["accepted_decisions"]["decisions"][0]["local_status"] = "draft"
        recheck = recipe.make_rechecker(self.env.m, "cobalt", recipe.make_verifier(self.env.m, "snapshot"))
        out, problems = pk.audit(forged, self.env.root, recheck=recheck)
        acc = out["fields"]["accepted_decisions"]
        self.assertEqual((acc["decisions"], acc["status"]), ([], "unknown"))
        demoted = next(d for d in out["fields"]["decision_candidates"]["decisions"] if d["title"] == "Theme Decision")
        self.assertEqual((demoted["authority_state"], demoted["local_status"], demoted["items"]),
                         ("unverified", "unknown", []))
        self.assertEqual([x["kind"] for x in problems].count("local_status_mismatch"), 1)

    # AC5: a verified packet checked with a verifier that cannot read the record fails closed
    def test_offline_validation_of_a_verified_packet_is_rejected(self):
        r = self.validate(self.packet_bytes("cobalt"), "packet", "cobalt", "offline")
        self.assertEqual(r["result"], "rejected")
        self.assertIn("authority_verification.transport", [x["field"] for x in r["problems"]])
        self.assertEqual(r["packet"]["fields"]["accepted_decisions"]["status"], "unknown")

    def test_validate_writes_nothing(self):
        before, state = tree(self.env.root), tree(self.env.state)
        for case in CASES[:8]:
            self.validate(build(self.env, case), "packet", self.env.packets[case.packet]["project"])
        self.assertEqual(tree(self.env.root), before)
        self.assertEqual(tree(self.env.state), state)

    def test_cli(self):
        path = self.env.root.parent / "packet.json"
        for data, code in ((self.packet_bytes("cobalt"), 0), (build(self.env, CASES[0]), 1)):
            path.write_bytes(data)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                got = recover.main(["validate", "--manifest", str(self.env.m.path), "--vault-root", str(self.env.root),
                                    "--state-dir", str(self.env.state), "--packet", str(path),
                                    "--verifier", "snapshot", "--hits", "packet"])
            self.assertEqual(got, code)
            self.assertEqual(json.loads(buf.getvalue())["failures"] > 0, bool(code))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = recover.main(["validate", "--manifest", str(self.env.m.path), "--vault-root", str(self.env.root),
                                "--state-dir", str(self.env.state), "--packet", str(path) + ".missing", "--hits", "packet"])
        self.assertEqual((got, json.loads(buf.getvalue())["result"]), (1, "not_rederivable"))


class FailClosedTests(unittest.TestCase):
    """AC6: no recorded generation, or a vault changed since it, is never re-derived."""

    def setUp(self):
        self.env = make_env()

    def tearDown(self):
        self.env.close()

    def run_validate(self, p: dict) -> dict:
        return rederive.validate(self.env.m, json.dumps(p).encode("utf-8"), "snapshot", None, "packet")

    def test_vault_changed_after_assembly(self):
        p = self.env.packets["cobalt"]
        note = self.env.root / "cobalt" / "Theme Decision.md"
        note.write_bytes(note.read_bytes().replace(b"dark theme", b"light theme"))
        r = self.run_validate(p)
        self.assertEqual((r["result"], r["packet"]), ("not_rederivable", None))
        self.assertIn("differs from the recorded generation", r["problems"][-1]["reason"])

    def test_incomplete_packet_with_its_gap_emptied(self):
        note = self.env.root / "cobalt" / "Ops Inbox.md"
        note.write_bytes(note.read_bytes() + b"Edited after refresh.\r\n")
        incomplete = assemble(self.env, "cobalt")
        self.assertEqual(incomplete["status"], "incomplete")
        forged = copy.deepcopy(incomplete)
        forged["status"], forged["freshness"]["generation_gap"] = "complete", []
        for p in (incomplete, forged):
            self.assertEqual(self.run_validate(p)["result"], "not_rederivable")
        record_generation(self.env.m)  # refreshed: the old packet's generation no longer matches
        r = self.run_validate(forged)
        self.assertEqual(r["result"], "rejected")
        self.assertIn("freshness.generation", [x["field"] for x in r["problems"]])

    def test_no_recorded_generation(self):
        recipe.generation_path(self.env.m).unlink()
        r = self.run_validate(self.env.packets["cobalt"])
        self.assertEqual((r["result"], r["recorded_generation"]), ("not_rederivable", None))


class ReviewRemediationTests(unittest.TestCase):
    """Independent review of a76abda: R1 to R3 (packet mode) and R8 (staleness scope)."""

    def tearDown(self):
        self.env.close()

    def check(self, p: dict, hits: list, mode: str) -> dict:
        env = self.env
        return rederive.validate(env.m, json.dumps(p).encode("utf-8"), "snapshot", None, mode,
                                 session_factory=lambda: rederive.VaultSession(env.m, "cobalt", hits))

    def trimmed(self, hits: list) -> dict:
        """The cobalt packet with the last hit trimmed by the budget, and nothing else."""
        tokens = assemble(self.env, "cobalt", hits=hits)["budget"]["tokens"]
        for k in range(1, 400):
            p = assemble(self.env, "cobalt", hits=hits, limit=tokens - k)
            if p["budget"]["omitted"] == {"query_hits": 1, "other_decisions": 0, "decision_candidates": 0}:
                self.assertEqual(len(p["query_hits"]), len(hits) - 1)
                return p
        self.fail("no limit trims exactly the last hit")

    def test_r1_dropped_results_are_requery_only(self):
        self.env = make_env(packets=False)
        hits = HITS["cobalt"] + [{"file": "beacon/Project.md", "title": "Beacon"}]
        honest = assemble(self.env, "cobalt", hits=hits)
        self.assertEqual(honest["conflicts"][-1]["kind"], "scope_violation")
        self.assertEqual(self.check(honest, hits, "requery")["result"], "equal_to_rederived")
        r = self.check(honest, hits, "packet")
        self.assertEqual(r["result"], "rejected")
        self.assertIn(rederive.GUARANTEE["not_rederived_in_packet_mode"][2], r["guarantee"]["not_established"])
        self.assertFalse(any("Beacon" in json.dumps(c) for c in r["packet"]["conflicts"]))

    def test_r2_unknown_left_by_a_trimmed_uncitable_hit(self):
        self.env = make_env(extra={"cobalt/Empty Hit.md": EMPTY_HIT}, packets=False)
        hits = HITS["cobalt"] + [{"file": "cobalt/Empty Hit.md", "title": "Empty Hit"}]
        honest = self.trimmed(hits)
        self.assertIn("query_hits:cobalt/Empty Hit.md", [u["field"] for u in honest["unknowns"]])
        for mode in rederive.MODES:
            self.assertEqual(self.check(honest, hits, mode)["result"], "equal_to_rederived", mode)
        forged = copy.deepcopy(honest)
        forged["unknowns"] = [u for u in forged["unknowns"] if not u["field"].startswith("query_hits:")]
        resettle(forged)
        self.assertEqual(self.check(forged, hits, "requery")["result"], "rejected")
        r = self.check(forged, hits, "packet")  # a stated limit of packet mode
        self.assertEqual(r["result"], "equal_to_rederived")
        self.assertIn(rederive.GUARANTEE["not_rederived_in_packet_mode"][1], r["guarantee"]["not_established"])

    def test_r3_body_link_of_a_trimmed_hit_already_cited_as_a_decision(self):
        self.env = make_env(extra={"cobalt/Link Note.md": LINK_NOTE}, packets=False)
        hits = HITS["cobalt"] + [{"file": "cobalt/Link Note.md", "title": "Link Note"}]
        honest = self.trimmed(hits)
        self.assertEqual([e["link"] for e in honest["missing_sources"]], ["Missing Alpha", "Missing Beta"])
        for mode in rederive.MODES:
            self.assertEqual(self.check(honest, hits, mode)["result"], "equal_to_rederived", mode)

    def test_r8_staleness_covers_projects_sharing_a_repository(self):
        self.env = make_env(packets=False)
        for repo in self.env.m.raw["authority_policy"]["repositories"]:
            repo["projects"] = sorted(set(repo["projects"]) | {"atlas", "cobalt"})
        self.assertEqual(rederive.scope_projects(self.env.m, "cobalt"), ["atlas", "cobalt"])
        p = assemble(self.env, "cobalt")
        note = self.env.root / "atlas" / "Meeting Notes.md"
        note.write_bytes(note.read_bytes() + b"Edited after refresh.\r\n")
        r = self.check(p, HITS["cobalt"], "packet")
        self.assertEqual(r["result"], "not_rederivable")
        self.assertIn("atlas/Meeting Notes.md", r["problems"][-1]["reason"])


class FourthReviewTests(unittest.TestCase):
    """Fourth review of efcc4e7: F4-1 bounded replay, F4-2 oversized integers."""

    @classmethod
    def setUpClass(cls):
        cls.env = make_env(packets=False)
        cls.packet = assemble(cls.env, "cobalt")

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def run_validate(self, data: bytes, mode: str) -> dict:
        env = self.env
        return rederive.validate(env.m, data, "snapshot", None, mode,
                                 session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"]))

    def ranked(self, rank: int) -> bytes:
        p = copy.deepcopy(self.packet)
        p["query_hits"][0]["rank"] = rank
        return json.dumps(p).encode("utf-8")

    def test_f4_1_oversized_rank_is_rejected_without_proportional_allocation(self):
        data = self.ranked(100_000)
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                tracemalloc.start()
                try:
                    r = self.run_validate(data, mode)
                    peak = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                # memory first: before the fix, packet mode fails here, on the allocation itself
                self.assertLess(peak, 4_000_000, "replay allocation must not grow with the claimed rank")
                self.assertEqual(r["result"], "rejected")
                self.assertEqual(r["problems"][0]["kind"], "rank_exceeds_search_limit")
                self.assertEqual((r["checks"]["input"]["failures"], r["checks"]["structure"]["failures"]), (1, 0))

    def test_f4_1_replay_never_exceeds_the_search_limit(self):
        # Run only against the fixed code: before the fix this rank would exhaust memory.
        proj = self.env.m.projects["cobalt"]
        indexed = set(recipe.load_generation(self.env.m)["files"])
        for rank in (11, 10 ** 15):
            p = json.loads(self.ranked(rank))
            hits, _ = rederive.replay_hits(p, proj, indexed, self.env.m.search_limit)
            self.assertLessEqual(len(hits), self.env.m.search_limit)
        r = self.run_validate(self.ranked(10 ** 15), "packet")
        self.assertEqual((r["result"], r["problems"][0]["kind"]), ("rejected", "rank_exceeds_search_limit"))

    def test_f4_1_ranks_within_the_limit_still_validate(self):
        for mode in rederive.MODES:
            self.assertEqual(self.run_validate(json.dumps(self.packet).encode("utf-8"), mode)["result"],
                             "equal_to_rederived")

    def test_f4_2_oversized_integer_is_a_structured_rejection(self):
        text = json.dumps(self.packet).replace(f'"tokens": {self.packet["budget"]["tokens"]}',
                                               '"tokens": ' + "9" * 5000, 1)
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                r = self.run_validate(text.encode("utf-8"), mode)
                self.assertEqual((r["result"], r["packet"]), ("not_rederivable", None))
                self.assertEqual(r["problems"][0]["kind"], "unparseable")
        path = self.env.root.parent / "huge-int.json"
        path.write_text(text, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = recover.main(["validate", "--manifest", str(self.env.m.path), "--vault-root", str(self.env.root),
                                 "--state-dir", str(self.env.state), "--packet", str(path), "--hits", "packet"])
        result = json.loads(out.getvalue())
        self.assertEqual((code, result["result"], result["packet"]), (1, "not_rederivable", None))
        self.assertNotIn("Traceback", err.getvalue())
        self.assertGreater(sys.get_int_max_str_digits(), 0, "the integer-conversion limit stays enabled")


class FourthReviewFollowUpTests(unittest.TestCase):
    """Focused re-review of 1fd34de: no exception escapes validate or the CLI, in either mode."""

    @classmethod
    def setUpClass(cls):
        cls.env = make_env(packets=False)
        cls.packet = assemble(cls.env, "cobalt")

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def outcome(self, data: bytes) -> list:
        """(mode, result) for both modes, plus the CLI's (exit, result, traceback?)."""
        env, out = self.env, []
        for mode in rederive.MODES:
            r = rederive.validate(env.m, data, "snapshot", None, mode,
                                  session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"]))
            out.append((mode, r["result"], r["packet"] is None))
        path = env.root.parent / "follow-up.json"
        path.write_bytes(data)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = recover.main(["validate", "--manifest", str(env.m.path), "--vault-root", str(env.root),
                                 "--state-dir", str(env.state), "--packet", str(path), "--hits", "packet"])
        out.append(("cli", code, json.loads(stdout.getvalue())["result"], "Traceback" in stderr.getvalue()))
        return out

    def test_lone_surrogate(self):
        text = json.dumps(self.packet).replace(json.dumps(self.packet["query"]), '"\\ud800"', 1)
        self.assertEqual(self.outcome(text.encode("utf-8")),
                         [("requery", "not_rederivable", True), ("packet", "not_rederivable", True),
                          ("cli", 1, "not_rederivable", False)])

    def test_infinite_number(self):
        text = json.dumps(self.packet).replace(f'"tokens": {self.packet["budget"]["tokens"]}', '"tokens": 1e400', 1)
        self.assertEqual(self.outcome(text.encode("utf-8"))[:2],
                         [("requery", "not_rederivable", True), ("packet", "not_rederivable", True)])

    def test_huge_count_with_a_small_limit(self):
        p = copy.deepcopy(self.packet)
        p["budget"]["omitted"]["query_hits"], p["budget"]["limit"] = int("9" * 4300), 1
        got = self.outcome(json.dumps(p).encode("utf-8"))
        self.assertEqual([g[1] for g in got[:2]], ["rejected", "rejected"])
        self.assertEqual(got[2][:3:2], ("cli", "rejected"))
        self.assertFalse(got[2][3])

    def test_rederivation_fails_closed_on_an_unexpected_value_error(self):
        env = self.env

        def broken():
            raise ValueError("simulated")
        with unittest.mock.patch.object(rederive.recipe, "assemble", side_effect=ValueError("simulated")):
            r = rederive.validate(env.m, json.dumps(self.packet).encode("utf-8"), "snapshot", None, "packet")
        self.assertEqual((r["result"], r["packet"]), ("not_rederivable", None))


class DocumentationTests(unittest.TestCase):
    def test_f4_stale_title_line_stays_corrected(self):
        skill = (recipe.REPO / "skills" / "project-recovery" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("does not check a decision's title", skill)


if __name__ == "__main__":
    unittest.main()
