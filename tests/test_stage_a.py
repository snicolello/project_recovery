from __future__ import annotations

import base64
import importlib.util
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertTrue({"S7-stale-4000", "S7-unbounded", "S7-limit-4000", "S7-limit-2000",
                         "S7-limit-1000", "S7-limit-400"} <= cases)
        self.assertTrue({"S8-cobalt", "S8-atlas"} <= cases)

    def test_estimator_combines_bytes_before_rounding(self):
        for byte_count in (0, 1, 2, 3, 29, 30, 10_001):
            self.assertEqual(math.ceil(byte_count / 2.9), stage_a.estimate_bytes(byte_count))
        self.assertEqual(1, stage_a.estimate_bytes(1 + 1))
        self.assertEqual(2, stage_a.estimate_bytes(1) + stage_a.estimate_bytes(1))

    def test_successful_packet_retention_round_trips_and_matches_accounting(self):
        packet = {"schema": "project-recovery-packet-v1", "status": "complete",
                  "fields": {"objective": "synthetic"}, "unknowns": [], "conflicts": []}
        raw = stage_a.pk.compact(packet)
        row = {"validation": "equal_to_rederived",
               "trusted_packet_encoding": "base64-compact-utf8-json",
               "trusted_packet_compact_base64": base64.b64encode(raw).decode("ascii"),
               "trusted_packet_bytes": len(raw), "packet_digest": stage_a.pk.digest(packet)}
        self.assertEqual([], stage_a.retained_packet_problems(row))
        self.assertEqual(raw, base64.b64decode(row["trusted_packet_compact_base64"], validate=True))

        wrong_length = dict(row, trusted_packet_bytes=len(raw) + 1)
        self.assertIn("retained trusted packet byte length differs from charged bytes",
                      stage_a.retained_packet_problems(wrong_length))
        wrong_digest = dict(row, packet_digest="0" * 64)
        self.assertIn("retained trusted packet digest differs from packet_digest",
                      stage_a.retained_packet_problems(wrong_digest))

    def test_packet_content_is_present_if_and_only_if_validation_succeeds(self):
        self.assertEqual(["successful row omitted lossless trusted packet content"],
                         stage_a.retained_packet_problems(
                             {"validation": "equal_to_rederived"}))
        self.assertEqual([], stage_a.retained_packet_problems(
            {"validation": "not_rederivable", "trusted_packet_bytes": 0}))
        self.assertEqual(["non-successful row retained trusted packet content"],
                         stage_a.retained_packet_problems(
                             {"validation": "rejected",
                              "trusted_packet_encoding": "base64-compact-utf8-json",
                              "trusted_packet_compact_base64": "e30="}))

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

    def test_amended_measurement_projection_matches_attempt_one(self):
        fields = {key: self.data[key] for key in ("runtime", "measurement", "evidence", "scenarios")}
        canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode("utf-8")
        expected = self.data["amendment"]["fixed_measurement_projection_sha256_before_and_after"]
        self.assertEqual(expected, hashlib.sha256(canonical).hexdigest())

    def test_attempt_ledger_counts_starts_not_lines(self):
        records = [
            {"attempt": 1, "event": "started"},
            {"attempt": 1, "event": "finished"},
            {"attempt": 2, "event": "started"},
            {"attempt": 2, "event": "stopped"},
        ]
        self.assertEqual(2, sum(1 for record in records if record["event"] == "started"))

    def test_timing_and_concurrency_setups_are_fresh_per_query(self):
        for setup in ("s4-immediate", "s4-after-3s", "s6-baseline-edited",
                      "s6-decision-edited", "s6-refresh-recorded"):
            self.assertTrue(stage_a.setup_requires_fresh_per_query(setup))
        self.assertFalse(stage_a.setup_requires_fresh_per_query("s4-after-refresh"))

    def test_every_expected_failure_has_a_specific_oracle(self):
        failures = [case for scenario in self.data["scenarios"] for case in scenario["cases"]
                    if case["expected_validation"] != "equal_to_rederived"]
        self.assertTrue(failures)
        for case in failures:
            with self.subTest(case=case["id"]):
                self.assertIn("submitted_status", case["failure_oracle"])
                self.assertIn("gap_sources", case["failure_oracle"])

    def test_s7_unbounded_is_reference_only(self):
        s7 = next(s for s in self.data["scenarios"] if s["id"] == "S7")
        reference = next(c for c in s7["cases"] if c["id"] == "S7-unbounded")
        self.assertTrue(reference["reference_only"])
        self.assertEqual(1_000_000_000, reference["max_tokens"])

    def test_generated_source_projection_is_predeclared_bounded(self):
        projected = stage_a.projected_generated_source_bytes(self.data)
        self.assertLessEqual(projected, self.data["limits"]["max_generated_source_bytes"])
        self.assertEqual(20, self.data["limits"]["shared_full_harness_budget"])

    def test_setup_refuses_state_outside_repo_qmd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(stage_a.recipe, "refresh"):
                with self.assertRaises(stage_a.recipe.RecipeError):
                    stage_a.prepare_case({"setup": "fixture"}, root / "work", root / "state")

    def test_setup_uses_distinct_sources_and_valid_external_qmd_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_a = stage_a.DEFAULT_STATE_LANE / "pure-path-test-a"
            state_b = stage_a.DEFAULT_STATE_LANE / "pure-path-test-b"
            with mock.patch.object(stage_a.recipe, "refresh") as refresh:
                prepared_a = stage_a.prepare_case({"setup": "fixture"}, root / "a", state_a)
                prepared_b = stage_a.prepare_case({"setup": "fixture"}, root / "b", state_b)
        self.assertEqual(state_a.resolve(), prepared_a.manifest.state_dir)
        self.assertEqual(state_b.resolve(), prepared_b.manifest.state_dir)
        self.assertNotEqual(prepared_a.manifest.vault_root, prepared_b.manifest.vault_root)
        self.assertEqual(2, refresh.call_count)

    def test_shared_accounting_cap_stops_worker_tree(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (mock.patch.object(stage_a.subprocess, "Popen", return_value=proc),
                  mock.patch.object(stage_a, "roots_size", side_effect=[0, 2049]),
                  mock.patch.object(stage_a, "terminate_process_tree",
                                    return_value="terminated shared cap") as terminate):
                result = stage_a.run_bounded(["worker"], 600, (root,), 1024,
                                             (root / "shared",), 2048,
                                             root / "stdout.log", root / "stderr.log")
        self.assertEqual((127, False, "terminated shared cap", "shared_scratch_cap"), result)
        terminate.assert_called_once_with(proc)

    def test_s7_cross_budget_check_enforces_protected_and_omission_invariants(self):
        base_projection = {"protected": {"objective": "same"}, "conflicts": ["same"],
                           "unknowns": ["same"], "status": "complete", "freshness": {"generation": "g"},
                           "droppable_counts": {"query_hits": 10, "other_decisions": 2,
                                                "decision_candidates": 3},
                           "budget": {"limit": 1_000_000_000, "tokens": 5000,
                                      "truncated": False, "within_limit": True,
                                      "omitted": {"query_hits": 0, "other_decisions": 0,
                                                  "decision_candidates": 0}}}
        bounded_projection = json.loads(json.dumps(base_projection))
        bounded_projection["droppable_counts"].update({"query_hits": 8, "other_decisions": 1})
        bounded_projection["budget"] = {"limit": 4000, "tokens": 3900, "truncated": True,
                                        "within_limit": True,
                                        "omitted": {"query_hits": 2, "other_decisions": 1,
                                                    "decision_candidates": 0}}
        rows = [
            {"scenario": "S7", "query_id": "q", "case": "S7-unbounded", "eligible": True,
             "s7_projection": base_projection, "oracle_problems": []},
            {"scenario": "S7", "query_id": "q", "case": "S7-limit-4000", "eligible": True,
             "s7_projection": bounded_projection, "oracle_problems": []},
        ]
        stage_a.apply_s7_budget_checks(rows)
        self.assertTrue(rows[1]["eligible"])
        rows[1]["s7_projection"]["protected"] = {"objective": "changed"}
        stage_a.apply_s7_budget_checks(rows)
        self.assertFalse(rows[1]["eligible"])

    def test_expected_failure_retains_the_evidence_its_oracle_checks(self):
        submitted = {"status": "incomplete", "freshness": {"generation_gap": [
            {"source": "atlas/Project.md", "change": "changed", "detected": "during_assembly"}]},
            "conflicts": [{"field": "current_state", "kind": "source_changed",
                           "source": "atlas/Project.md"}]}
        validation = {"problems": [{"check": "rederivation", "field": "packet",
                                    "kind": "not_rederivable", "reason": "atlas/Project.md changed"}]}
        oracle = {"forbidden_stale_text": ["Parser complete"]}
        observed = stage_a.failure_observation(submitted, validation, oracle)
        self.assertEqual("incomplete", observed["submitted_status"])
        self.assertEqual("during_assembly", observed["generation_gap"][0]["detected"])
        self.assertEqual("source_changed", observed["conflicts"][0]["kind"])
        self.assertIn("atlas/Project.md", observed["validation_problems"][0]["reason"])
        self.assertFalse(observed["forbidden_stale_text_present"]["Parser complete"])

    def test_monitor_failure_terminates_worker_tree_and_retains_detail(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (mock.patch.object(stage_a.subprocess, "Popen", return_value=proc),
                  mock.patch.object(stage_a, "roots_size", side_effect=OSError("scratch vanished")),
                  mock.patch.object(stage_a, "terminate_process_tree",
                                    return_value="terminated pid tree") as terminate):
                with self.assertRaises(stage_a.BoundedRunError) as caught:
                    stage_a.run_bounded(["worker"], 600, (root,), 1024,
                                        (root / "shared",), 2048,
                                        root / "stdout.log", root / "stderr.log")
        terminate.assert_called_once_with(proc)
        self.assertEqual("terminated pid tree", caught.exception.termination_detail)
        self.assertIn("scratch vanished", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
