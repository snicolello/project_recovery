import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_stage_a_retained", ROOT / "scripts" / "analyze_stage_a_retained.py"
)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(analysis)


class StageAPosthocAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = analysis.analyze()

    def test_source_and_duplicate_preservation(self):
        source = self.report["source"]
        self.assertEqual(analysis.EXPECTED_HASHES["raw_attempt_3"], source["raw_result_sha256"])
        self.assertEqual(analysis.METHOD_REVISION, source["method_revision"])
        duplicates = self.report["duplicates_and_preservation"]
        self.assertEqual("removed exact duplicate", duplicates["candidate_results_final_jsonl"]["status"])
        self.assertTrue(duplicates["result_containers"]["parsed_json_identical"])
        self.assertFalse(duplicates["result_containers"]["byte_identical"])

    def test_recovered_fields_and_s2_zero_hits(self):
        mechanism = self.report["mechanism"]
        self.assertTrue(mechanism["raw_fields_equal_size_across_all_comparisons"])
        self.assertFalse(mechanism["raw_fields_byte_identical_across_all_comparisons"])
        self.assertTrue(mechanism["stripped_fields_byte_identical_across_all_comparisons"])
        self.assertEqual(
            ["budget", "missing_sources", "query", "query_hits"],
            mechanism["stripped_packet_difference_keys"],
        )
        self.assertEqual(0, mechanism["s2_zero_hit_observation"]["query_hit_count"])
        self.assertEqual(0, mechanism["s2_zero_hit_observation"]["fetch_envelope_bytes"])
        population = mechanism["all_validated_packet_population"]
        self.assertEqual(64, population["validated_packet_rows"])
        self.assertEqual(48, population["same_case_candidate_control_comparisons"])
        self.assertEqual(46, population["normalized_fields_matches"])
        self.assertEqual(
            [
                {"scenario": "S7", "case": "S7-limit-2000", "query_id": "project"},
                {"scenario": "S7", "case": "S7-limit-2000", "query_id": "report"},
            ],
            population["normalized_fields_mismatches"],
        )

    def test_section_byte_examples(self):
        table = {
            row["scenario"]: row
            for row in self.report["mechanism"]["control_vs_best_in_hindsight_section_bytes"]
        }
        self.assertEqual(6897, table["S1"]["control"]["fields"])
        self.assertEqual(2970, table["S1"]["control"]["query_hits"])
        self.assertEqual(820, table["S1"]["best_in_hindsight_non_control"]["query_hits"])
        self.assertEqual(4, table["S2"]["best_in_hindsight_non_control"]["query_hits"])

    def test_hindsight_and_ablation_numbers(self):
        h = self.report["hindsight"]
        self.assertEqual(42427, h["best_in_hindsight_non_control_estimated_tokens"])
        self.assertAlmostEqual(0.08629452556316493, h["best_in_hindsight_non_control_relative_reduction"])
        self.assertEqual(43477.666666666664, h["mean_eligible_candidate_estimated_tokens"])
        self.assertEqual("130433/3", h["mean_eligible_candidate_estimated_tokens_exact"])
        self.assertEqual(44428, h["worst_eligible_candidate_estimated_tokens"])
        ablation = self.report["empty_echoed_hit_list_ablation"]
        self.assertEqual(40563, ablation["ablated_control_estimated_tokens"])
        self.assertAlmostEqual(0.12643752422793642, ablation["relative_reduction"])

    def test_s6_canonical_duplicate_and_without_s6(self):
        duplicate = self.report["s6_duplicate"]
        for row in duplicate["shared_query_comparisons"]:
            self.assertFalse(row["raw_packet_byte_identical"])
            self.assertTrue(row["canonical_packet_byte_identical"])
            self.assertTrue(row["packet_digest_identical"])
        without = duplicate["without_s6"]
        self.assertEqual(42511, without["control_estimated_tokens"])
        self.assertEqual(39289, without["best_in_hindsight_non_control_estimated_tokens"])
        self.assertAlmostEqual(0.07579214791465738, without["best_in_hindsight_non_control_relative_reduction"])
        self.assertAlmostEqual(0.08263743501681918, without["best_in_hindsight_including_control_relative_reduction"])

    def test_predeclaration_history(self):
        history = self.report["predeclaration_history"]
        changes = history["changes_before_first_measurement"]
        self.assertTrue(changes["s7_unbounded_reference_added"])
        self.assertEqual(
            {"before": "not_rederivable", "after": "rejected"},
            changes["s6_refresh_recorded_expected_validation"],
        )
        self.assertIn("recorded for comparison", history["binding_precision"])

    def test_checked_output_matches_fresh_analysis(self):
        checked = json.loads((analysis.EVIDENCE / "posthoc-analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(self.report, checked)


if __name__ == "__main__":
    unittest.main()
