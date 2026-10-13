"""Measure bounded R3 Stage A query headroom against the accepted R2 seam.

The measurement is intentionally gated.  ``preflight`` validates the committed
predeclaration without starting QMD.  ``run`` requires the caller to provide the
exact SHA-256 of that file, records an attempt before doing work, verifies the
synthetic fixtures before and after, and runs the worker with a hard wall-clock
timeout.  The worker uses the existing assembler and ``validate --hits requery``;
only the validator-returned packet is trusted or charged.

No network, model, download, install, or live authority transport is used.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO / "skills" / "project-recovery" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

import packet as pk  # noqa: E402
import recipe  # noqa: E402
import rederive  # noqa: E402
from qmd_client import McpSession, installed_version  # noqa: E402
from receipts import make_receipt, normalize_text, safe_resolve, validate_receipt  # noqa: E402

DEFAULT_PREDECLARATION = REPO / "evidence" / "r3-stage-a" / "predeclaration.json"
DEFAULT_SCRATCH = REPO / ".scratch" / "r3-stage-a"
FIXTURES = REPO / "fixtures"
VAULT = FIXTURES / "synthetic-vault"
EXPECTED_HASHES = FIXTURES / "synthetic-vault-hashes.json"
FIXTURE_MANIFEST = REPO / "manifest" / "fixture-vault.json"
SCENARIO_MANIFEST = REPO / "manifest" / "scenario-vault.json"
CORE_UNKNOWN_UNIVERSE = {
    "objective", "accepted_decisions", "current_state", "blockers", "next_action",
    "authority.approver", "authority.approvals.rollout_approval", "authority.approvals.rollout_owner",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compact(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def estimate_bytes(byte_count: int, divisor: float = 2.9) -> int:
    """The frozen estimator: ceil(total consumer-visible UTF-8 bytes / 2.9)."""
    if byte_count < 0 or divisor <= 0:
        raise ValueError("byte_count must be non-negative and divisor positive")
    return math.ceil(byte_count / divisor)


def select_best(plans: list[dict]) -> dict | None:
    """Select the lowest-cost eligible plan; list order is the frozen tie-break."""
    eligible = [(index, plan) for index, plan in enumerate(plans) if plan.get("eligible")]
    return min(eligible, key=lambda item: (item[1]["estimated_tokens"], item[0]))[1] if eligible else None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def fixture_status() -> dict:
    expected = json.loads(EXPECTED_HASHES.read_text(encoding="utf-8"))
    actual = tree_digest(VAULT)
    return {"ok": actual == expected, "expected_count": len(expected), "actual_count": len(actual),
            "missing": sorted(set(expected) - set(actual)), "extra": sorted(set(actual) - set(expected)),
            "mismatched": sorted(k for k in set(expected) & set(actual) if expected[k] != actual[k])}


def dir_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def load_predeclaration(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def validate_predeclaration(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "project-recovery-r3-stage-a-predeclaration-v1":
        errors.append("unexpected schema")
    if data.get("source_revision") != "7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28":
        errors.append("source_revision is not the accepted baseline")
    measure = data.get("measurement", {})
    if measure.get("estimator") != "ceil(total_compact_utf8_bytes/2.9)":
        errors.append("estimator is not frozen to bytes/2.9")
    if measure.get("trusted_packet_source") != "validate_requery.packet":
        errors.append("trusted packet source must be validate_requery.packet")
    if measure.get("search_work_charged") is not False:
        errors.append("search work must be reported separately, not charged")
    limits = data.get("limits", {})
    if limits.get("attempts") != 20 or limits.get("seconds_per_attempt") != 600:
        errors.append("attempt/runtime bounds differ from the ruling")
    evidence = data.get("evidence", {})
    for eid, item in evidence.items():
        if not isinstance(item.get("source"), str) or not isinstance(item.get("span"), list):
            errors.append(f"evidence {eid} has no source/span")
        if len(item.get("content_sha", "")) != 64:
            errors.append(f"evidence {eid} has no SHA-256")
    scenarios = data.get("scenarios", [])
    ids = [s.get("id") for s in scenarios]
    if ids != [f"S{i}" for i in range(1, 9)]:
        errors.append("scenarios must be exactly S1 through S8 in order")
    case_ids: set[str] = set()
    for scenario in scenarios:
        plans = scenario.get("queries", [])
        if not plans or plans[0].get("role") != "control":
            errors.append(f"{scenario.get('id')} does not start with one control query")
        if len({p.get("id") for p in plans}) != len(plans):
            errors.append(f"{scenario.get('id')} has duplicate query ids")
        for case in scenario.get("cases", []):
            cid = case.get("id")
            if cid in case_ids:
                errors.append(f"duplicate case id {cid}")
            case_ids.add(cid)
            for eid in case.get("required_evidence", []):
                if eid not in evidence:
                    errors.append(f"{cid} references unknown evidence {eid}")
            if case.get("expected_validation") not in ("equal_to_rederived", "not_rederivable"):
                errors.append(f"{cid} has unsupported expected validation")
    return errors


def field_texts(packet: dict, name: str) -> list[str]:
    node = packet["fields"][name]
    if "decisions" in node:
        return [i["text"] for d in node["decisions"] for i in d.get("items", [])]
    return [i["text"] for i in node.get("items", [])]


def packet_text(packet: dict) -> str:
    return "\n".join(i.get("text", "") for _, node in pk.iter_nodes(packet)
                      for key in ("items", "evidence") for i in node.get(key, []))


def core_unknowns(packet: dict) -> list[str]:
    return sorted(u.get("field") for u in packet.get("unknowns", []) if u.get("field") in CORE_UNKNOWN_UNIVERSE)


def semantic_projection(packet: dict) -> dict:
    return pk.strip_volatile({"status": packet.get("status"), "fields": packet.get("fields"),
                              "unknowns": core_unknowns(packet),
                              "conflicts": [c for c in packet.get("conflicts", [])
                                            if c.get("field") != "query_hits"]})


def oracle_problems(packet: dict, oracle: dict, m: recipe.Manifest, project: str,
                    transport: str | None) -> list[str]:
    problems: list[str] = []
    if packet.get("status") != oracle.get("packet_status", "complete"):
        problems.append(f"packet status {packet.get('status')!r}")
    for field, needles in oracle.get("field_contains", {}).items():
        text = " ".join(field_texts(packet, field))
        for needle in needles:
            if needle not in text:
                problems.append(f"{field} lacks {needle!r}")
    if core_unknowns(packet) != sorted(oracle.get("expected_core_unknowns", [])):
        problems.append(f"core unknowns {core_unknowns(packet)!r}")
    text = packet_text(packet)
    for needle in oracle.get("forbidden_text", []):
        if needle in text:
            problems.append(f"forbidden text present: {needle!r}")
    receipts = pk.ordered_receipts(packet)
    for prefix in oracle.get("forbidden_source_prefixes", []):
        if any(r.get("source", "").startswith(prefix) for r in receipts):
            problems.append(f"forbidden source prefix present: {prefix!r}")
    kinds = {c.get("kind") for c in packet.get("conflicts", [])}
    for kind in oracle.get("required_conflict_kinds", []):
        if kind not in kinds:
            problems.append(f"required conflict kind absent: {kind!r}")
    recheck = recipe.make_rechecker(m, project, recipe.make_verifier(m, transport))
    unsupported = pk.unsupported_assertions(packet, Path(oracle["vault_root"]), recheck=recheck)
    if unsupported:
        problems.append(f"{len(unsupported)} unsupported assertion(s)")
    return problems


class TraceSession:
    """Session proxy that records search work without adding it to frontier cost."""

    def __init__(self, session):
        self.session = session
        self.queries: list[dict] = []

    def __enter__(self):
        self.session.__enter__()
        return self

    def __exit__(self, *exc):
        return self.session.__exit__(*exc)

    def query(self, text: str, collection: str, limit: int = 10):
        hits = self.session.query(text, collection, limit)
        self.queries.append({"text": text, "collection": collection, "limit": limit,
                             "returned": len(hits),
                             "files": [h.get("file") for h in hits]})
        return hits

    def __getattr__(self, name):
        return getattr(self.session, name)


class ActAfterListing:
    def __init__(self, session, action):
        self.session, self.action, self.done = session, action, False

    def multi_get(self, *args, **kwargs):
        result = self.session.multi_get(*args, **kwargs)
        if not self.done:
            self.done = True
            self.action()
        return result

    def __getattr__(self, name):
        return getattr(self.session, name)


def edit_bytes(path: Path, old: bytes, new: bytes) -> None:
    data = path.read_bytes()
    if old not in data:
        raise RuntimeError(f"edit marker absent in {path}: {old!r}")
    path.write_bytes(data.replace(old, new))


def build_stress(root: Path) -> Path:
    vault = root / "vault" / "stress"
    vault.mkdir(parents=True)

    def note(name: str, front: list[str], body: list[str]) -> None:
        lines = ["---", f"title: {name}", "type: note", "project: stress", *front,
                 "---", f"# {name}", *body]
        (vault / f"{name}.md").write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

    note("Stress Project", ["status: active"], [
        "Objective: Exercise the packet budget under load.",
        "Accepted decision: Stress baseline claim A.",
        "Accepted decision: Stress baseline claim B.",
        "Next authorized action: Review the truncation report."])
    for i in range(1, 31):
        note(f"Stress Draft {i:02d}", ["status: draft"], [
            f"Stress draft {i:02d} proposes load option {i:02d}; it is not approved and its filler text occupies budget."])
    for i in range(1, 13):
        note(f"Stress Claim {i:02d}", ["status: accepted",
             f"acceptance_record: https://github.example.test/portfolio/stress/pull/{i}"], [
            f"Stress claim {i:02d} says load option {i:02d} was accepted; offline, the record cannot be read."])
    raw = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    raw["name"] = "r3-stage-a-stress"
    raw["vault"]["root"] = "vault"
    raw["index"]["search"]["limit"] = 25
    raw["authority_policy"]["repositories"] = [{"host": "github.example.test", "repo": "portfolio/stress",
                                                   "projects": ["stress"], "approvers": ["fixture-owner"]}]
    stress = copy.deepcopy(raw["projects"]["beacon"])
    stress.update({"collection": "stress", "root": "stress", "baseline_note": "Stress Project.md"})
    raw["projects"] = {"stress": stress}
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return manifest


@dataclass
class Prepared:
    manifest: recipe.Manifest
    after_listing: object | None


def prepare_case(case: dict, work: Path) -> Prepared:
    setup = case["setup"]
    state = work / "state"
    vault_copy = work / "vault"
    after_listing = None
    if setup in ("fixture", "scenario"):
        manifest_path = FIXTURE_MANIFEST if setup == "fixture" else SCENARIO_MANIFEST
        m = recipe.load_manifest(manifest_path, None, state)
        recipe.refresh(m, rebuild=True)
    elif setup.startswith("s4-") or setup.startswith("s6-"):
        shutil.copytree(VAULT, vault_copy)
        m = recipe.load_manifest(FIXTURE_MANIFEST, vault_copy, state)
        recipe.refresh(m, rebuild=True)
        if setup.startswith("s4-") and setup != "s4-before":
            edit_bytes(vault_copy / "atlas" / "Restart Runbook.md", b"local-r1", b"local-r2")
            edit_bytes(vault_copy / "atlas" / "Restart Runbook.md", b"15 seconds", b"45 seconds")
            edit_bytes(vault_copy / "atlas" / "Restart Runbook.md", b"REVISION-OLD-15", b"REVISION-NEW-45")
            if setup == "s4-after-refresh":
                recipe.refresh(m)
            elif setup == "s4-after-3s":
                time.sleep(3)
        elif setup == "s6-baseline-edited":
            after_listing = lambda: edit_bytes(vault_copy / "atlas" / "Project.md", b"Parser complete", b"Parser rewritten")
        elif setup == "s6-decision-edited":
            after_listing = lambda: edit_bytes(vault_copy / "atlas" / "Queue Decision.md", b"Atlas queue uses SQLite.", b"Atlas queue uses DuckDB.")
        elif setup == "s6-refresh-recorded":
            def refresh_after_edit():
                edit_bytes(vault_copy / "atlas" / "Restart Runbook.md", b"15 seconds", b"45 seconds")
                recipe.refresh(m)
            after_listing = refresh_after_edit
    elif setup.startswith("s7-"):
        manifest_path = build_stress(work / "generated")
        m = recipe.load_manifest(manifest_path, None, state)
        recipe.refresh(m, rebuild=True)
        stress = work / "generated" / "vault" / "stress"
        edit_bytes(stress / "Stress Draft 01.md", b"filler text", b"edited filler text")
        edit_bytes(stress / "Stress Claim 01.md", b"was accepted", b"was accepted (edited)")
        if setup == "s7-after-refresh":
            recipe.refresh(m)
    else:
        raise ValueError(f"unknown setup {setup!r}")
    return Prepared(m, after_listing)


def requirement_identity(req: dict) -> tuple[str, int, int, str]:
    return req["source"], req["span"][0], req["span"][1], req["content_sha"]


def source_requirement_valid(root: Path, req: dict) -> bool:
    path = safe_resolve(root, req["source"])
    lines = path.read_bytes().split(b"\n")
    start, end = req["span"]
    cited = b"\n".join(lines[start - 1:end])
    return hashlib.sha256(cited).hexdigest() == req["content_sha"]


def covered_by_packet(packet: dict, req: dict) -> bool:
    start, end = req["span"]
    return any(r.get("source") == req["source"] and r.get("span", [0, 0])[0] <= start
               and r.get("span", [0, 0])[1] >= end for r in pk.ordered_receipts(packet))


def fetch_requirement(m: recipe.Manifest, project: str, req: dict, session: McpSession) -> dict:
    request = {"source": req["source"], "span": req["span"]}
    prefix = m.projects[project].source("")
    if not req["source"].startswith(prefix):
        return {"request": request, "result": {"status": "unknown", "valid": False,
                "reason": f"source outside project root {m.projects[project].root!r}"}}
    start, end = req["span"]
    text = session.get(m.projects[project].qmd_path(req["source"][len(prefix):]), start, end - start + 1)
    if text is None:
        return {"request": request, "result": {"status": "unknown", "valid": False,
                "reason": "not found in scope"}}
    cited = text.encode("utf-8")
    receipt = make_receipt(req["source"], start, end, cited, recipe.load_generation(m)["generation"], utc_now())
    valid, reason = validate_receipt(receipt, m.vault_root, cited)
    valid = valid and receipt["content_sha"] == req["content_sha"]
    if not valid and reason == "ok":
        reason = "content differs from the predeclared receipt"
    return {"request": request, "result": {"status": "established" if valid else "unknown",
            "text": normalize_text(cited), "receipt": receipt, "valid": valid, "reason": reason}}


def run_candidate(predecl: dict, scenario: dict, case: dict, query_plan: dict, work: Path,
                  prepared: Prepared | None = None) -> dict:
    prepared = prepared or prepare_case(case, work)
    m = prepared.manifest
    project = case["project"]
    transport = case.get("transport")
    trace = TraceSession(McpSession(m.state_dir, timeout=60))
    with trace as entered:
        session = ActAfterListing(entered, prepared.after_listing) if prepared.after_listing else entered
        submitted = recipe.assemble(m, project, query_plan["query"], session,
                                    case.get("max_tokens"), recipe.make_verifier(m, transport))
    # TraceSession delegates context management, but rederive retains no handle.  The
    # assembly trace is sufficient to report candidate exploration; validation is
    # reported as one additional fixed requery operation when it runs.
    validation = rederive.validate(m, compact(submitted), transport, None, "requery")
    expected = case["expected_validation"]
    result = {"case": case["id"], "query_id": query_plan["id"], "query": query_plan["query"],
              "expected_validation": expected, "validation": validation["result"],
              "validation_failures": validation["failures"],
              "search_work": {"assembly": trace.queries,
                              "validation_requery_performed": validation["checks"]["rederivation"]["performed"]},
              "trusted_packet_bytes": 0, "fetch_envelope_bytes": 0, "total_consumer_bytes": 0,
              "estimated_tokens": 0, "fetches": [], "coverage": {"covered": 0, "required": 0},
              "oracle_problems": [], "eligible": False}
    if validation["result"] != expected:
        result["oracle_problems"].append(f"validation {validation['result']!r}, expected {expected!r}")
        return result
    if expected != "equal_to_rederived":
        # Expected stale/concurrent failure: no packet is trusted or shown to the
        # consumer, so its charged bytes are explicitly zero.
        result["eligible"] = True
        result["expected_failure_observation"] = True
        return result
    trusted = validation["packet"]
    if trusted is None:
        result["oracle_problems"].append("validator returned no trusted packet")
        return result
    oracle = copy.deepcopy(case["oracle"])
    oracle["vault_root"] = str(m.vault_root)
    result["oracle_problems"].extend(oracle_problems(trusted, oracle, m, project, transport))
    requirements = [predecl["evidence"][eid] for eid in case.get("required_evidence", [])]
    bad_declared = [r for r in requirements if not source_requirement_valid(m.vault_root, r)]
    if bad_declared:
        result["oracle_problems"].append("predeclared evidence does not match current source bytes")
    covered = [r for r in requirements if covered_by_packet(trusted, r)]
    missing = [r for r in requirements if r not in covered]
    max_fetches = predecl["measurement"]["fetch_policy"]["max_fetches_per_case"]
    if missing:
        with McpSession(m.state_dir, timeout=60) as fetch_session:
            for req in missing[:max_fetches]:
                envelope = fetch_requirement(m, project, req, fetch_session)
                result["fetches"].append(envelope)
                if envelope["result"].get("valid"):
                    covered.append(req)
    result["coverage"] = {"covered": len(covered), "required": len(requirements)}
    if len(covered) != len(requirements):
        result["oracle_problems"].append(f"evidence coverage {len(covered)}/{len(requirements)}")
    packet_bytes = len(pk.compact(trusted))
    fetch_bytes = sum(len(compact(envelope)) for envelope in result["fetches"])
    result.update({"trusted_packet_bytes": packet_bytes, "fetch_envelope_bytes": fetch_bytes,
                   "total_consumer_bytes": packet_bytes + fetch_bytes,
                   "estimated_tokens": estimate_bytes(packet_bytes + fetch_bytes),
                   "packet_digest": pk.digest(trusted), "semantic_projection": semantic_projection(trusted),
                   "eligible": not result["oracle_problems"]})
    return result


def run_worker(predecl_path: Path, attempt_dir: Path) -> int:
    predecl, predecl_hash = load_predeclaration(predecl_path)
    started = time.monotonic()
    rows: list[dict] = []
    prepared_cache: dict[str, Prepared] = {}
    for scenario in predecl["scenarios"]:
        for query_plan in scenario["queries"]:
            for case in scenario["cases"]:
                work = attempt_dir / "work" / scenario["id"] / query_plan["id"] / case["id"]
                work.mkdir(parents=True)
                try:
                    setup = case["setup"]
                    mutable_during_assembly = setup in {
                        "s6-baseline-edited", "s6-decision-edited", "s6-refresh-recorded"}
                    cache_key = setup if not mutable_during_assembly else ""
                    if cache_key and cache_key not in prepared_cache:
                        shared = attempt_dir / "work" / "shared" / setup
                        shared.mkdir(parents=True)
                        prepared_cache[cache_key] = prepare_case(case, shared)
                    row = run_candidate(predecl, scenario, case, query_plan, work,
                                        prepared_cache.get(cache_key) if cache_key else None)
                except Exception as exc:  # preserve the failed candidate and continue bounded work
                    row = {"case": case["id"], "query_id": query_plan["id"], "query": query_plan["query"],
                           "expected_validation": case["expected_validation"], "validation": "harness_error",
                           "validation_failures": 1, "search_work": {}, "trusted_packet_bytes": 0,
                           "fetch_envelope_bytes": 0, "total_consumer_bytes": 0, "estimated_tokens": 0,
                           "fetches": [], "coverage": {"covered": 0, "required": len(case.get("required_evidence", []))},
                           "oracle_problems": [f"{type(exc).__name__}: {exc}"], "eligible": False}
                row["scenario"] = scenario["id"]
                rows.append(row)
                with (attempt_dir / "candidate-results.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    scenario_results = []
    for scenario in predecl["scenarios"]:
        plans = []
        control_projection: dict[str, dict] = {}
        for plan in scenario["queries"]:
            selected = [r for r in rows if r["scenario"] == scenario["id"] and r["query_id"] == plan["id"]]
            if plan["role"] == "control":
                control_projection = {r["case"]: r.get("semantic_projection") for r in selected
                                      if r["expected_validation"] == "equal_to_rederived"}
            semantic_equal = all(r["expected_validation"] != "equal_to_rederived"
                                 or r.get("semantic_projection") == control_projection.get(r["case"])
                                 for r in selected) if plan["role"] != "control" else True
            eligible = all(r["eligible"] for r in selected) and semantic_equal
            tokens = sum(r["estimated_tokens"] for r in selected
                         if r["expected_validation"] == "equal_to_rederived")
            plans.append({"id": plan["id"], "query": plan["query"], "role": plan["role"],
                          "eligible": eligible, "semantic_equal_to_control": semantic_equal,
                          "estimated_tokens": tokens,
                          "fetches": sum(len(r["fetches"]) for r in selected),
                          "zero_fetch_cases": [r["case"] for r in selected if not r["fetches"]],
                          "failed_cases": [r["case"] for r in selected if not r["eligible"]]})
        control = plans[0]
        best = select_best(plans[1:])
        achievable = select_best(([control] if control["eligible"] else []) + plans[1:])
        reduction = None if not best or not control["estimated_tokens"] else \
            (control["estimated_tokens"] - best["estimated_tokens"]) / control["estimated_tokens"]
        scenario_results.append({"id": scenario["id"], "control": control, "candidates": plans[1:],
                                 "best_non_control_candidate": best,
                                 "achievable_best_with_control": achievable,
                                 "non_control_relative_reduction": reduction,
                                 "achievable_relative_reduction": None if not achievable or not control["estimated_tokens"]
                                 else (control["estimated_tokens"] - achievable["estimated_tokens"])
                                 / control["estimated_tokens"]})
    baseline = sum(s["control"]["estimated_tokens"] for s in scenario_results)
    complete = all(s["control"]["eligible"] and s["best_non_control_candidate"] for s in scenario_results)
    best_total = sum(s["best_non_control_candidate"]["estimated_tokens"] for s in scenario_results) if complete else None
    achievable_total = sum(s["achievable_best_with_control"]["estimated_tokens"] for s in scenario_results) \
        if all(s["achievable_best_with_control"] for s in scenario_results) else None
    reduction = (baseline - best_total) / baseline if best_total is not None and baseline else None
    achievable_reduction = (baseline - achievable_total) / baseline \
        if achievable_total is not None and baseline else None
    output = {"schema": "project-recovery-r3-stage-a-results-v1", "predeclaration_sha256": predecl_hash,
              "source_revision": predecl["source_revision"], "runtime": {"python": sys.version.split()[0],
              "qmd": installed_version(), "platform": sys.platform}, "elapsed_seconds": time.monotonic() - started,
              "scenarios": scenario_results, "cases": rows,
              "aggregate": {"control_estimated_tokens": baseline,
                            "best_non_control_candidates_estimated_tokens": best_total,
                            "non_control_relative_reduction": reduction,
                            "achievable_best_with_control_estimated_tokens": achievable_total,
                            "achievable_relative_reduction": achievable_reduction,
                            "reference_15_percent_met_by_non_control":
                            None if reduction is None else reduction >= 0.15,
                            "interpretation": "Best within the fixed candidate list; not a universal upper bound."},
              "all_controls_valid": all(s["control"]["eligible"] for s in scenario_results),
              "all_scenarios_have_valid_candidate": all(s["best_non_control_candidate"] for s in scenario_results)}
    (attempt_dir / "results.json").write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if output["all_controls_valid"] and output["all_scenarios_have_valid_candidate"] else 1


def append_attempt(ledger: Path, value: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(value, ensure_ascii=False) + "\n")


def run_bounded(cmd: list[str], timeout: int) -> tuple[int, bool, str | None]:
    """Run one attempt and terminate its process tree if the hard cap expires."""
    kwargs = {"cwd": REPO}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    try:
        return proc.wait(timeout=timeout), False, None
    except subprocess.TimeoutExpired:
        detail = None
        if os.name == "nt":
            killed = subprocess.run(["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                                    capture_output=True, text=True, check=False)
            detail = (killed.stdout or killed.stderr).strip()[-500:]
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return 124, True, detail


def command_run(args, predecl: dict, predecl_hash: str) -> int:
    if args.predeclaration_sha256 != predecl_hash:
        raise SystemExit("predeclaration SHA-256 does not match; measurement refused")
    errors = validate_predeclaration(predecl)
    if errors:
        raise SystemExit("invalid predeclaration: " + "; ".join(errors))
    scratch = args.scratch.resolve()
    if any(scratch == p or p in scratch.parents for p in (VAULT.resolve(), FIXTURES.resolve())):
        raise SystemExit("scratch must be outside every source root")
    scratch.mkdir(parents=True, exist_ok=True)
    ledger = scratch / "attempts.jsonl"
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if ledger.exists() else []
    prior = sum(1 for record in records if record.get("event") == "started")
    if prior >= predecl["limits"]["attempts"]:
        raise SystemExit("20-attempt cap reached")
    attempt_no = prior + 1
    attempt_dir = scratch / "attempts" / f"attempt-{attempt_no:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    before = fixture_status()
    tree_before = tree_digest(FIXTURES)
    start_record = {"attempt": attempt_no, "event": "started", "at": utc_now(),
                    "predeclaration_sha256": predecl_hash, "fixture_before": before}
    append_attempt(ledger, start_record)
    if not before["ok"]:
        append_attempt(ledger, {"attempt": attempt_no, "event": "stopped", "at": utc_now(),
                                "reason": "fixture hash verification failed before run"})
        return 2
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()), "_worker",
           "--predeclaration", str(args.predeclaration.resolve()), "--attempt-dir", str(attempt_dir)]
    code, timed_out, timeout_termination = run_bounded(cmd, predecl["limits"]["seconds_per_attempt"])
    after = fixture_status()
    tree_unchanged = tree_digest(FIXTURES) == tree_before
    size = dir_size(scratch)
    cap = predecl["limits"]["stage_a_scratch_bytes"]
    final = {"attempt": attempt_no, "event": "finished", "at": utc_now(), "exit_code": code,
             "timed_out": timed_out, "timeout_process_tree_termination": timeout_termination,
             "fixture_after": after, "fixtures_tree_unchanged": tree_unchanged,
             "scratch_bytes": size, "scratch_cap_bytes": cap}
    append_attempt(ledger, final)
    (attempt_dir / "attempt-summary.json").write_text(json.dumps({"start": start_record, "finish": final}, indent=2),
                                                       encoding="utf-8")
    if not after["ok"] or not tree_unchanged:
        return 3
    if size > cap:
        return 4
    if code == 0 and args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(attempt_dir / "results.json", args.out)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--predeclaration", type=Path, default=DEFAULT_PREDECLARATION)
    run = sub.add_parser("run")
    run.add_argument("--predeclaration", type=Path, default=DEFAULT_PREDECLARATION)
    run.add_argument("--predeclaration-sha256", required=True)
    run.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
    run.add_argument("--out", type=Path, default=REPO / "evidence" / "r3-stage-a" / "results.json")
    worker = sub.add_parser("_worker")
    worker.add_argument("--predeclaration", type=Path, required=True)
    worker.add_argument("--attempt-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "_worker":
        return run_worker(args.predeclaration, args.attempt_dir)
    predecl, digest = load_predeclaration(args.predeclaration)
    if args.command == "preflight":
        errors = validate_predeclaration(predecl)
        print(json.dumps({"predeclaration": str(args.predeclaration), "sha256": digest,
                          "valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    return command_run(args, predecl, digest)


if __name__ == "__main__":
    raise SystemExit(main())
