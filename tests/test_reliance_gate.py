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
import unittest

from reliance_cases import CASES, HITS, LIMIT_CASES, assemble, build, make_env, record_generation  # sets sys.path

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
                    elif not (mode == "packet" and case.replay_input):
                        # nothing from the submitted packet is kept: the output is the re-derivation
                        self.assertEqual(pk.canonical(r["packet"]), pk.canonical(original))

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


class DocumentationTests(unittest.TestCase):
    def test_f4_stale_title_line_stays_corrected(self):
        skill = (recipe.REPO / "skills" / "project-recovery" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("does not check a decision's title", skill)


if __name__ == "__main__":
    unittest.main()
