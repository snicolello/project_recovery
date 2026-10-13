"""Recompute the R3 Stage A post-hoc observations from retained evidence.

This is an audit tool, not part of the predeclared measurement.  It reads the
final attempt, checks the preserved raw/export relationship, and emits a
deterministic JSON report.  It never invokes QMD or the Stage A harness.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "r3-stage-a"
RAW_RESULT = EVIDENCE / "attempt-03" / "results.json"
LF_EXPORT = EVIDENCE / "results.json"
PREDECLARATION = EVIDENCE / "predeclaration.json"
CURRENT_CANDIDATES = EVIDENCE / "attempt-03" / "candidate-results.jsonl"
REMOVED_DUPLICATE = EVIDENCE / "attempt-03" / "candidate-results-final.jsonl"
PRESERVATION_COMMIT = "10849760e6eb380eb8b55308cfffa594276a1a3f"
METHOD_REVISION = "541ea4397574d2a3ed8874085be4aaf5e37ef704"
HISTORY_START = "5330507"
HISTORY_END = "aab2944"

EXPECTED_HASHES = {
    "raw_attempt_3": "522cb351f402e316055f74c3546735de53a9218d440d2e78db1e0aced47eef6d",
    "lf_audit_export": "9c1bfb832ff2948100f5de1bcfab3e097fca2301328b813ba145cd9c6401e597",
    "predeclaration": "11c071e9260c34dca3e3d601a94177a380e2a8db971ec21ae5ca01265d2b55ba",
    "candidate_jsonl": "277639b97a0e91ff94f514f79a2f744372d374b5c367a01713dc39ab31ba0175",
}
VOLATILE_KEYS = frozenset({"observed_at", "refreshed_at", "assembled_at", "verified_at"})
SECTION_NAMES = ("fields", "query_hits", "missing_sources", "query")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(value: object, *, sort_keys: bool = False) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":")
    ).encode("utf-8")


def strip_volatile(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: strip_volatile(child)
            for key, child in value.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [strip_volatile(child) for child in value]
    return value


def load_packet(row: dict) -> dict:
    assert row["validation"] == "equal_to_rederived"
    assert row["trusted_packet_encoding"] == "base64-compact-utf8-json"
    raw = base64.b64decode(row["trusted_packet_compact_base64"], validate=True)
    assert len(raw) == row["trusted_packet_bytes"]
    packet = json.loads(raw)
    assert compact(packet) == raw
    return packet


def git_blob(revision: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative_path}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def query_plans(result: dict) -> dict[str, dict[str, dict]]:
    return {
        scenario["id"]: {
            plan["id"]: plan
            for plan in [scenario["control"], *scenario["candidates"]]
        }
        for scenario in result["scenarios"]
    }


def successful_rows(result: dict, scenario: str, query_id: str) -> list[dict]:
    return [
        row
        for row in result["cases"]
        if row["scenario"] == scenario
        and row["query_id"] == query_id
        and row["validation"] == "equal_to_rederived"
        and row["case"] != "S7-unbounded"
    ]


def plan_sections(result: dict, scenario: str, query_id: str) -> dict:
    rows = successful_rows(result, scenario, query_id)
    packets = [load_packet(row) for row in rows]
    values = {
        section: sum(len(compact(packet[section])) for packet in packets)
        for section in SECTION_NAMES
    }
    values.update(
        {
            "packet": sum(row["trusted_packet_bytes"] for row in rows),
            "fetch_envelopes": sum(row["fetch_envelope_bytes"] for row in rows),
            "query_hit_count": sum(len(packet["query_hits"]) for packet in packets),
            "consuming_cases": len(rows),
        }
    )
    return values


def relative_reduction(control: float, candidate: float) -> float:
    return (control - candidate) / control


def packet_difference_keys(left: dict, right: dict) -> list[str]:
    left = strip_volatile(left)
    right = strip_volatile(right)
    return sorted(
        key for key in set(left) | set(right) if left.get(key) != right.get(key)
    )


def analyze_mechanism(result: dict) -> dict:
    plans = query_plans(result)
    eligible_comparisons = 0
    differing_keys: set[str] = set()
    raw_fields_same_size = True
    raw_fields_identical = True
    stripped_fields_identical = True

    for scenario in result["scenarios"]:
        sid = scenario["id"]
        eligible_ids = {
            plan_id for plan_id, plan in plans[sid].items() if plan["eligible"]
        }
        control_by_case = {
            row["case"]: row
            for row in successful_rows(result, sid, "control")
        }
        for query_id in sorted(eligible_ids - {"control"}):
            for row in successful_rows(result, sid, query_id):
                control = control_by_case[row["case"]]
                control_packet = load_packet(control)
                candidate_packet = load_packet(row)
                control_fields = compact(control_packet["fields"])
                candidate_fields = compact(candidate_packet["fields"])
                control_stripped = compact(strip_volatile(control_packet["fields"]), sort_keys=True)
                candidate_stripped = compact(strip_volatile(candidate_packet["fields"]), sort_keys=True)
                raw_fields_same_size &= len(control_fields) == len(candidate_fields)
                raw_fields_identical &= control_fields == candidate_fields
                stripped_fields_identical &= control_stripped == candidate_stripped
                keys = packet_difference_keys(control_packet, candidate_packet)
                differing_keys.update(keys)
                eligible_comparisons += 1

    allowed_differences = {"budget", "missing_sources", "query", "query_hits"}
    assert eligible_comparisons
    assert raw_fields_same_size
    assert not raw_fields_identical
    assert stripped_fields_identical
    assert differing_keys <= allowed_differences

    validated_rows = [
        row for row in result["cases"] if row["validation"] == "equal_to_rederived"
    ]
    validated_by_case: dict[tuple[str, str], dict[str, dict]] = {}
    for row in validated_rows:
        validated_by_case.setdefault((row["scenario"], row["case"]), {})[
            row["query_id"]
        ] = row
    all_comparisons = 0
    normalized_mismatches = []
    for (sid, case_id), rows in sorted(validated_by_case.items()):
        control = rows.get("control")
        if not control:
            continue
        control_fields = compact(
            strip_volatile(load_packet(control)["fields"]), sort_keys=True
        )
        for query_id, row in sorted(rows.items()):
            if query_id == "control":
                continue
            all_comparisons += 1
            candidate_fields = compact(
                strip_volatile(load_packet(row)["fields"]), sort_keys=True
            )
            if candidate_fields != control_fields:
                normalized_mismatches.append(
                    {"scenario": sid, "case": case_id, "query_id": query_id}
                )
    assert len(validated_rows) == 64
    assert all_comparisons == 48
    assert normalized_mismatches == [
        {"scenario": "S7", "case": "S7-limit-2000", "query_id": "project"},
        {"scenario": "S7", "case": "S7-limit-2000", "query_id": "report"},
    ]

    best_sections = []
    for scenario in result["scenarios"]:
        sid = scenario["id"]
        best = scenario["best_non_control_candidate"]
        best_sections.append(
            {
                "scenario": sid,
                "control_query_id": "control",
                "best_in_hindsight_query_id": best["id"],
                "control": plan_sections(result, sid, "control"),
                "best_in_hindsight_non_control": plan_sections(result, sid, best["id"]),
            }
        )

    s2 = next(item for item in best_sections if item["scenario"] == "S2")
    assert s2["best_in_hindsight_query_id"] == "decisions"
    assert s2["best_in_hindsight_non_control"]["query_hit_count"] == 0
    assert s2["best_in_hindsight_non_control"]["fetch_envelopes"] == 0

    return {
        "eligible_control_candidate_comparisons": eligible_comparisons,
        "qualifier": (
            "Raw fields are equal-size but differ in observed_at timestamps. After the "
            "predeclared volatile-field stripping, recovered fields are byte-identical "
            "across eligible control/candidate comparisons."
        ),
        "raw_fields_equal_size_across_all_comparisons": raw_fields_same_size,
        "raw_fields_byte_identical_across_all_comparisons": raw_fields_identical,
        "stripped_fields_byte_identical_across_all_comparisons": stripped_fields_identical,
        "stripped_packet_difference_keys": sorted(differing_keys),
        "all_validated_packet_population": {
            "validated_packet_rows": len(validated_rows),
            "same_case_candidate_control_comparisons": all_comparisons,
            "normalized_fields_matches": all_comparisons - len(normalized_mismatches),
            "normalized_fields_mismatches": normalized_mismatches,
            "scope_note": "The two mismatches are the S7 plans excluded for semantic mismatch. The 24 refused rows retain no packet and are outside this comparison.",
        },
        "control_vs_best_in_hindsight_section_bytes": best_sections,
        "s2_zero_hit_observation": {
            "query_id": "decisions",
            "consuming_cases": s2["best_in_hindsight_non_control"]["consuming_cases"],
            "query_hit_count": 0,
            "fetch_envelope_bytes": 0,
        },
    }


def ablate_echoed_hits(result: dict) -> dict:
    total = 0
    for scenario in result["scenarios"]:
        for row in successful_rows(result, scenario["id"], "control"):
            packet = load_packet(row)
            packet["query_hits"] = []
            packet["missing_sources"] = []
            packet_bytes = len(compact(packet))
            total += -(-(packet_bytes + row["fetch_envelope_bytes"]) * 10 // 29)
    original = result["aggregate"]["control_estimated_tokens"]
    assert original == 46434
    assert total == 40563
    return {
        "label": "post-hoc observation only; no follow-up measurement is authorized",
        "mechanism": "Empty both echoed query_hits and missing_sources in control packets, retain fetch envelopes, and reapply ceil(bytes/2.9) per row.",
        "original_control_estimated_tokens": original,
        "ablated_control_estimated_tokens": total,
        "relative_reduction": relative_reduction(original, total),
    }


def hindsight_summary(result: dict) -> dict:
    scenarios = result["scenarios"]
    control = sum(item["control"]["estimated_tokens"] for item in scenarios)
    best = sum(item["best_non_control_candidate"]["estimated_tokens"] for item in scenarios)
    with_control = sum(item["achievable_best_with_control"]["estimated_tokens"] for item in scenarios)
    means = []
    worst = []
    for item in scenarios:
        eligible = [plan for plan in item["candidates"] if plan["eligible"]]
        means.append(sum(plan["estimated_tokens"] for plan in eligible) / len(eligible))
        worst.append(max(plan["estimated_tokens"] for plan in eligible))
    mean_total = sum(means)
    worst_total = sum(worst)
    assert (control, best, with_control) == (46434, 42427, 42136)
    assert mean_total == 43477.66666666667
    assert worst_total == 44428
    return {
        "terminology": "All selections in this section are best-in-hindsight within the frozen eligible candidate lists.",
        "control_estimated_tokens": control,
        "best_in_hindsight_non_control_estimated_tokens": best,
        "best_in_hindsight_non_control_relative_reduction": relative_reduction(control, best),
        "best_in_hindsight_including_control_estimated_tokens": with_control,
        "best_in_hindsight_including_control_relative_reduction": relative_reduction(control, with_control),
        "mean_eligible_candidate_estimated_tokens": mean_total,
        "mean_eligible_candidate_relative_reduction": relative_reduction(control, mean_total),
        "worst_eligible_candidate_estimated_tokens": worst_total,
        "worst_eligible_candidate_relative_reduction": relative_reduction(control, worst_total),
        "definition": "Mean: arithmetic mean of eligible non-control plan totals within each scenario, summed across scenarios. Worst: most expensive eligible non-control plan in each scenario, summed across scenarios.",
    }


def s6_duplicate(result: dict) -> dict:
    comparisons = []
    for query_id in ("control", "marker"):
        s1_row = successful_rows(result, "S1", query_id)[0]
        s6_row = successful_rows(result, "S6", query_id)[0]
        p1 = load_packet(s1_row)
        p6 = load_packet(s6_row)
        comparisons.append(
            {
                "query_id": query_id,
                "raw_packet_byte_identical": compact(p1) == compact(p6),
                "canonical_packet_byte_identical": compact(strip_volatile(p1), sort_keys=True)
                == compact(strip_volatile(p6), sort_keys=True),
                "packet_digest_identical": s1_row["packet_digest"] == s6_row["packet_digest"],
                "estimated_tokens_identical": s1_row["estimated_tokens"] == s6_row["estimated_tokens"],
            }
        )
    assert all(not row["raw_packet_byte_identical"] for row in comparisons)
    assert all(row["canonical_packet_byte_identical"] for row in comparisons)
    assert all(row["packet_digest_identical"] for row in comparisons)
    assert all(row["estimated_tokens_identical"] for row in comparisons)

    without = [item for item in result["scenarios"] if item["id"] != "S6"]
    control = sum(item["control"]["estimated_tokens"] for item in without)
    best = sum(item["best_non_control_candidate"]["estimated_tokens"] for item in without)
    with_control = sum(item["achievable_best_with_control"]["estimated_tokens"] for item in without)
    assert (control, best, with_control) == (42511, 39289, 38998)
    return {
        "qualifier": "S1 and S6 control/marker packets are canonical/digest equivalents, not literal raw-packet identities; volatile timestamps differ.",
        "shared_query_comparisons": comparisons,
        "without_s6": {
            "control_estimated_tokens": control,
            "best_in_hindsight_non_control_estimated_tokens": best,
            "best_in_hindsight_non_control_relative_reduction": relative_reduction(control, best),
            "best_in_hindsight_including_control_estimated_tokens": with_control,
            "best_in_hindsight_including_control_relative_reduction": relative_reduction(control, with_control),
        },
    }


def history_analysis() -> dict:
    old = json.loads(git_blob(HISTORY_START, "evidence/r3-stage-a/predeclaration.json"))
    amended = json.loads(git_blob(HISTORY_END, "evidence/r3-stage-a/predeclaration.json"))
    old_cases = {case["id"]: case for s in old["scenarios"] for case in s["cases"]}
    new_cases = {case["id"]: case for s in amended["scenarios"] for case in s["cases"]}
    added_failure_oracles = sorted(
        case_id for case_id in new_cases if "failure_oracle" in new_cases[case_id]
    )
    assert added_failure_oracles == [
        "S4-after-3s",
        "S4-immediate",
        "S6-baseline-edited",
        "S6-decision-edited",
        "S6-refresh-recorded",
        "S7-stale-4000",
    ]
    assert "S7-unbounded" not in old_cases and new_cases["S7-unbounded"]["reference_only"]
    assert old_cases["S6-refresh-recorded"]["expected_validation"] == "not_rederivable"
    assert new_cases["S6-refresh-recorded"]["expected_validation"] == "rejected"
    harness = (ROOT / "scripts" / "measure_stage_a.py").read_text(encoding="utf-8")
    assert 'predecl["implementation"]["files"]' in harness
    assert "fixed_measurement_projection" not in harness
    return {
        "start_revision": HISTORY_START,
        "end_revision": HISTORY_END,
        "changes_before_first_measurement": {
            "failure_oracles_added": added_failure_oracles,
            "s7_unbounded_reference_added": True,
            "s6_refresh_recorded_expected_validation": {
                "before": "not_rederivable",
                "after": "rejected",
            },
        },
        "binding_precision": "Each attempt launch-gated the implementation.files hashes in its predeclaration. The fixed_measurement_projection hash was recorded for comparison but is not checked by the harness at runtime.",
    }


def duplicate_analysis() -> dict:
    current = CURRENT_CANDIDATES.read_bytes()
    preserved = git_blob(PRESERVATION_COMMIT, REMOVED_DUPLICATE.relative_to(ROOT).as_posix())
    assert sha256(current) == EXPECTED_HASHES["candidate_jsonl"]
    assert preserved == current
    raw = RAW_RESULT.read_bytes()
    export = LF_EXPORT.read_bytes()
    assert sha256(raw) == EXPECTED_HASHES["raw_attempt_3"]
    assert sha256(export) == EXPECTED_HASHES["lf_audit_export"]
    assert raw != export
    assert json.loads(raw) == json.loads(export)
    return {
        "candidate_results_final_jsonl": {
            "status": "removed exact duplicate",
            "preserved_at_revision": PRESERVATION_COMMIT,
            "sha256": sha256(preserved),
            "bytes": len(preserved),
            "identical_to": "attempt-03/candidate-results.jsonl",
        },
        "result_containers": {
            "status": "both retained because they are parsed-identical but not byte-identical",
            "raw_attempt_3": {"sha256": sha256(raw), "bytes": len(raw)},
            "lf_audit_export": {"sha256": sha256(export), "bytes": len(export)},
            "parsed_json_identical": True,
            "byte_identical": False,
        },
    }


def analyze() -> dict:
    raw = RAW_RESULT.read_bytes()
    predecl = PREDECLARATION.read_bytes()
    assert sha256(raw) == EXPECTED_HASHES["raw_attempt_3"]
    assert sha256(predecl) == EXPECTED_HASHES["predeclaration"]
    result = json.loads(raw)
    assert len(result["cases"]) == 88
    assert all(row["eligible"] for row in result["cases"])
    return {
        "schema": "project-recovery-r3-stage-a-posthoc-v1",
        "status": "post-hoc analysis; not predeclared; R3 remains deferred",
        "source": {
            "attempt": 3,
            "raw_result_sha256": sha256(raw),
            "predeclaration_sha256": sha256(predecl),
            "method_revision": METHOD_REVISION,
            "accepted_source_revision": result["source_revision"],
        },
        "duplicates_and_preservation": duplicate_analysis(),
        "mechanism": analyze_mechanism(result),
        "empty_echoed_hit_list_ablation": ablate_echoed_hits(result),
        "s6_duplicate": s6_duplicate(result),
        "hindsight": hindsight_summary(result),
        "predeclaration_history": history_analysis(),
        "limits": {
            "full_harness_runs_used": 4,
            "full_harness_run_limit": 20,
            "stage_a_lane_limit_bytes": 250 * 1024 * 1024,
            "note": "The live 20-run ledger is retained in gitignored .scratch/r3-stage-a; checked-in attempt snapshots preserve each Stage A reservation. This post-hoc script performs no harness run.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.dumps(analyze(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8", newline="\n")
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
