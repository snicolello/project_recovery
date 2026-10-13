"""Dedicated offline tests for the model-independent Librarian preparation seam."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from reliance_cases import HITS, make_env  # also adds the product scripts to sys.path

import librarian  # noqa: E402
import rederive  # noqa: E402


def raw(queries=None, claims=None, **extra) -> bytes:
    base = {
        "queries": ["approve deployment"] if queries is None else queries,
        "claims": ({name: f"raw {name}" for name in librarian.CLAIM_FIELDS}
                   if claims is None else claims),
    }
    base.update(extra)
    return json.dumps(base).encode("utf-8")


class LibrarianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = make_env(packets=False)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def prepare(self, proposal: bytes, *, validation_hits=None, transport="offline") -> dict:
        env = self.env
        return librarian.prepare(
            env.m, "atlas", proposal, transport=transport, max_tokens=10 ** 6,
            assembly_session_factory=lambda _q: rederive.VaultSession(env.m, "atlas", HITS["atlas"]),
            validation_session_factory=lambda _q: rederive.VaultSession(
                env.m, "atlas", HITS["atlas"] if validation_hits is None else validation_hits),
        )

    def test_validated_output_is_fresh_rederived_packet_and_excludes_raw_claim_text(self):
        marker = "RAW MODEL WORDING MUST NOT SURVIVE"
        claims = {name: f"{marker} {name}" for name in librarian.CLAIM_FIELDS}
        result = self.prepare(raw(claims=claims))
        self.assertEqual(result["status"], "prepared")
        self.assertEqual([r["status"] for r in result["results"]], ["validated"])
        packet = result["packets"][0]
        self.assertIs(packet, result["results"][0]["packet"])
        self.assertEqual((packet["status"], packet["query"]), ("complete", "approve deployment"))
        self.assertNotIn(marker, json.dumps(result))
        self.assertFalse(result["proposal"]["raw_claim_text_returned"])

    def test_validator_rejection_returns_no_packet(self):
        result = self.prepare(raw(), validation_hits=[])
        self.assertEqual((result["status"], result["packets"]), ("rejected", []))
        attempt = result["results"][0]
        self.assertEqual((attempt["status"], attempt["packet"]), ("rejected", None))
        self.assertIn("hits=requery validation returned 'rejected'", attempt["reason"])
        self.assertTrue(attempt["problems"])

    def test_abstention_score_names_unsafe_claim_and_false_abstention(self):
        claims = {name: f"raw {name}" for name in librarian.CLAIM_FIELDS}
        claims["objective"] = None  # Atlas objective is deterministically established.
        # Offline verification leaves accepted_decisions unknown, but the raw proposal claims it.
        result = self.prepare(raw(claims=claims))
        score = result["results"][0]["abstention"]
        by_field = {row["field"]: row for row in score["fields"]}
        self.assertEqual(by_field["objective"]["outcome"], "false_abstention")
        self.assertEqual(by_field["accepted_decisions"]["outcome"], "claim_on_unknown_or_conflict")
        self.assertEqual(by_field["authority"]["outcome"], "claim_on_unknown_or_conflict")
        self.assertEqual(score["counts"]["false_abstention"], 1)
        self.assertGreaterEqual(score["counts"]["claim_on_unknown_or_conflict"], 2)
        self.assertFalse(score["claim_text_correctness_established"])

    def test_explicit_abstention_on_unknown_is_scored_correctly(self):
        claims = {name: f"raw {name}" for name in librarian.CLAIM_FIELDS}
        claims["accepted_decisions"] = None
        score = self.prepare(raw(claims=claims))["results"][0]["abstention"]
        row = next(x for x in score["fields"] if x["field"] == "accepted_decisions")
        self.assertEqual(row["outcome"], "correct_abstention")

    def test_malformed_rejected_without_starting_sessions(self):
        calls = []
        result = librarian.prepare(
            self.env.m, "atlas", b'{"queries":',
            assembly_session_factory=lambda _q: calls.append("assembly"),
            validation_session_factory=lambda _q: calls.append("validation"),
        )
        self.assertEqual((result["status"], result["results"], result["packets"]), ("rejected", [], []))
        self.assertEqual(calls, [])

    def test_forged_packet_and_out_of_scope_claim_are_rejected(self):
        forged = raw(packet={"fields": {"next_action": "deploy"}})
        out_of_scope = json.loads(raw())
        out_of_scope["claims"]["work_credentials"] = "read them"
        for proposal in (forged, json.dumps(out_of_scope).encode("utf-8")):
            with self.subTest(proposal=proposal[:80]):
                result = self.prepare(proposal)
                self.assertEqual((result["status"], result["packets"]), ("rejected", []))

    def test_duplicate_keys_non_finite_values_and_controls_are_rejected(self):
        claims = json.dumps({name: "x" for name in librarian.CLAIM_FIELDS})
        cases = [
            (f'{{"queries":["q"],"queries":["other"],"claims":{claims}}}').encode(),
            raw(queries=["line\nbreak"]),
            raw(claims={**{name: "x" for name in librarian.CLAIM_FIELDS}, "objective": float("nan")}),
            (b'{"queries":' + b'[' * 1000 + b']' * 1000 + b',"claims":{}}'),
        ]
        for proposal in cases:
            with self.subTest(proposal=proposal[:80]):
                self.assertEqual(self.prepare(proposal)["status"], "rejected")

    def test_query_claim_count_length_and_total_byte_bounds(self):
        claims = {name: "x" for name in librarian.CLAIM_FIELDS}
        cases = [
            raw(queries=[]),
            raw(queries=[str(i) for i in range(librarian.MAX_QUERIES + 1)]),
            raw(queries=["q" * (librarian.MAX_QUERY_CHARS + 1)]),
            raw(claims={**claims, "objective": "x" * (librarian.MAX_CLAIM_CHARS + 1)}),
            b" " * (librarian.MAX_PROPOSAL_BYTES + 1),
        ]
        for proposal in cases:
            with self.subTest(size=len(proposal)):
                result = self.prepare(proposal)
                self.assertEqual((result["status"], result["packets"]), ("rejected", []))

    def test_multiple_queries_are_bounded_independent_validations(self):
        result = self.prepare(raw(queries=["approve deployment", "Atlas project state"]))
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(len(result["packets"]), 2)
        self.assertEqual([p["query"] for p in result["packets"]],
                         ["approve deployment", "Atlas project state"])
        self.assertTrue(all(r["status"] == "validated" for r in result["results"]))


if __name__ == "__main__":
    unittest.main()
