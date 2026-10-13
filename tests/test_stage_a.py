from __future__ import annotations

import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "measure_stage_a.py"
SPEC = importlib.util.spec_from_file_location("measure_stage_a", SCRIPT)
assert SPEC and SPEC.loader
stage_a = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage_a
SPEC.loader.exec_module(stage_a)


class StageAPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = REPO / "evidence" / "r3-stage-a" / "predeclaration.json"
        cls.data, cls.digest = stage_a.load_predeclaration(cls.path)

    def test_predeclaration_is_complete_and_valid(self):
        self.assertEqual([], stage_a.validate_predeclaration(self.data))
        self.assertEqual([f"S{i}" for i in range(1, 9)],
                         [scenario["id"] for scenario in self.data["scenarios"]])
        self.assertEqual(64, len(self.digest))

    def test_required_mutation_and_budget_cases_are_frozen(self):
        cases = {case["id"] for scenario in self.data["scenarios"] for case in scenario["cases"]}
        self.assertTrue({"S4-before", "S4-immediate", "S4-after-3s", "S4-after-refresh"} <= cases)
        self.assertTrue({"S6-control", "S6-baseline-edited", "S6-decision-edited",
                         "S6-refresh-recorded"} <= cases)
        self.assertTrue({"S7-stale-4000", "S7-limit-4000", "S7-limit-2000",
                         "S7-limit-1000", "S7-limit-400"} <= cases)
        self.assertTrue({"S8-cobalt", "S8-atlas"} <= cases)

    def test_estimator_combines_bytes_before_rounding(self):
        for byte_count in (0, 1, 2, 3, 29, 30, 10_001):
            self.assertEqual(math.ceil(byte_count / 2.9), stage_a.estimate_bytes(byte_count))
        self.assertEqual(1, stage_a.estimate_bytes(1 + 1))
        self.assertEqual(2, stage_a.estimate_bytes(1) + stage_a.estimate_bytes(1))

    def test_best_selection_excludes_failures_and_uses_declared_order_for_ties(self):
        plans = [
            {"id": "failed", "eligible": False, "estimated_tokens": 1},
            {"id": "first", "eligible": True, "estimated_tokens": 10},
            {"id": "second", "eligible": True, "estimated_tokens": 10},
        ]
        self.assertEqual("first", stage_a.select_best(plans)["id"])
        self.assertIsNone(stage_a.select_best([plans[0]]))

    def test_larger_validated_receipt_can_cover_required_subspan(self):
        packet = {"node": {"items": [{"text": "x", "receipt": {
            "source": "atlas/Project.md", "span": [8, 16], "content_sha": "0" * 64,
            "generation": "g", "revision": "unknown", "observed_at": "t"}}]}}
        requirement = {"source": "atlas/Project.md", "span": [9, 9], "content_sha": "1" * 64}
        self.assertTrue(stage_a.covered_by_packet(packet, requirement))

    def test_static_predeclared_receipts_match_fixture_bytes(self):
        dynamic = {"atlas-restart-new", "stress-objective", "stress-decision-a",
                   "stress-decision-b", "stress-next"}
        for evidence_id, item in self.data["evidence"].items():
            if evidence_id not in dynamic:
                with self.subTest(evidence=evidence_id):
                    self.assertTrue(stage_a.source_requirement_valid(stage_a.VAULT, item))

    def test_accounting_and_interpretation_are_explicit(self):
        method = self.data["measurement"]
        self.assertFalse(method["search_work_charged"])
        self.assertIn("failed fetches", " ".join(method["charged"]))
        self.assertIn("zero", method["failure_method"])
        self.assertIn("never a universal upper bound", method["scope_limit"])
        self.assertIn("control retained", method["scenario_selection"])

    def test_attempt_ledger_counts_starts_not_lines(self):
        records = [
            {"attempt": 1, "event": "started"},
            {"attempt": 1, "event": "finished"},
            {"attempt": 2, "event": "started"},
            {"attempt": 2, "event": "stopped"},
        ]
        self.assertEqual(2, sum(1 for record in records if record["event"] == "started"))


if __name__ == "__main__":
    unittest.main()
