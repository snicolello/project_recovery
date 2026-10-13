"""Bounded structural diagnostics for project_recovery #6 allocation remediation.

Run: python -I -m unittest discover -s tests -p test_structural_limits.py
"""
from __future__ import annotations

import json
import sys
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import rederive  # noqa: E402
import shape  # noqa: E402
from reliance_cases import HITS, assemble, make_env  # noqa: E402


class StructuralDiagnosticLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = make_env(packets=False)
        cls.honest = assemble(cls.env, "cobalt")
        cls.malformed = (b'{"project":"cobalt","query":"approve deployment","query_hits":['
                         + b",".join([b"{}"] * 10_000) + b"]}")

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_problem_cap_boundaries_preserve_order_and_mark_only_overflow(self):
        spec = shape.ListOf(shape.STR)
        for count, expected_length, truncated in ((99, 99, False), (100, 100, False), (101, 101, True)):
            with self.subTest(count=count), mock.patch.object(shape, "PACKET", spec):
                problems = shape.check([0] * count)
                self.assertEqual(len(problems), expected_length)
                self.assertEqual([p["field"] for p in problems[:shape.MAX_PROBLEMS]],
                                 [f"[{i}]" for i in range(min(count, shape.MAX_PROBLEMS))])
                self.assertEqual(problems[-1]["kind"] == "truncated", truncated)
                if truncated:
                    self.assertNotRegex(problems[-1]["reason"], r"\b\d+\b")

    def test_nested_object_map_stops_at_first_unreported_problem(self):
        spec = shape.Obj({"mapping": shape.MapOf(shape.STR), "tail": shape.STR})
        packet = {"mapping": {f"key-{i:03}": 0 for i in range(10_000)}, "tail": 0}
        calls = 0
        original = shape.problem

        def counted(*args):
            nonlocal calls
            calls += 1
            return original(*args)

        with mock.patch.object(shape, "PACKET", spec), mock.patch.object(shape, "problem", counted):
            problems = shape.check(packet)
        self.assertEqual(calls, shape.MAX_PROBLEMS + 1)
        self.assertEqual(problems[-1]["kind"], "truncated")
        self.assertEqual(problems[0]["field"], "mapping.key-000")
        self.assertEqual(problems[-2]["field"], "mapping.key-099")
        self.assertNotIn("tail", [p["field"] for p in problems])

    def test_ten_thousand_empty_hits_stop_traversal_with_bounded_allocation(self):
        packet = shape.parse(self.malformed)
        calls = 0
        original = shape.problem

        def counted(*args):
            nonlocal calls
            calls += 1
            return original(*args)

        tracemalloc.start()
        try:
            with mock.patch.object(shape, "problem", counted):
                problems = shape.check(packet)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 1_000_000)
        self.assertEqual(calls, shape.MAX_PROBLEMS + 1)
        self.assertEqual(len(problems), shape.MAX_PROBLEMS + 1)
        self.assertEqual(problems[-1]["kind"], "truncated")

    def test_honest_assembled_packet_still_passes_structure(self):
        self.assertEqual(shape.check(self.honest), [])

    def test_full_validate_rejects_malformed_hits_in_both_modes(self):
        env = self.env
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                result = rederive.validate(
                    env.m,
                    self.malformed,
                    "snapshot",
                    None,
                    mode,
                    session_factory=lambda: rederive.VaultSession(env.m, "cobalt", HITS["cobalt"]),
                )
                self.assertEqual(result["result"], "rejected")
                self.assertEqual(result["checks"]["structure"]["failures"], shape.MAX_PROBLEMS + 1)
                self.assertEqual(result["problems"][shape.MAX_PROBLEMS]["kind"], "truncated")


if __name__ == "__main__":
    unittest.main()
