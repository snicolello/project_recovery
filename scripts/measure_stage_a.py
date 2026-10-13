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
import base64
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
DEFAULT_STATE_LANE = REPO / ".qmd" / "r3-stage-a"
SHARED_ACCOUNTING_ROOTS = (REPO / ".scratch", REPO / ".qmd", REPO / "runtime-vaults")
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


def retained_packet_problems(row: dict) -> list[str]:
    """Verify lossless retained bytes for exactly the rows with trusted packets."""
    encoding_key = "trusted_packet_encoding"
    packet_key = "trusted_packet_compact_base64"
    successful = row.get("validation") == "equal_to_rederived"
    present = encoding_key in row or packet_key in row
    if not successful:
        return ["non-successful row retained trusted packet content"] if present else []
    if row.get(encoding_key) != "base64-compact-utf8-json" or packet_key not in row:
        return ["successful row omitted lossless trusted packet content"]
    try:
        raw = base64.b64decode(row[packet_key], validate=True)
        packet = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"retained trusted packet is not valid compact UTF-8 JSON: {type(exc).__name__}"]
    problems: list[str] = []
    if pk.compact(packet) != raw:
        problems.append("retained trusted packet is not exact compact packet bytes")
    if len(raw) != row.get("trusted_packet_bytes"):
        problems.append("retained trusted packet byte length differs from charged bytes")
    if pk.digest(packet) != row.get("packet_digest"):
        problems.append("retained trusted packet digest differs from packet_digest")
    return problems


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


def roots_size(roots: tuple[Path, ...]) -> int:
    return sum(dir_size(root) for root in roots)


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
    implementation = data.get("implementation", {})
    if not implementation.get("files") or "scripts/measure_stage_a.py" not in implementation.get("files", {}):
        errors.append("measurement implementation is not hash-bound")
    for rel, digest in implementation.get("files", {}).items():
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"implementation hash is invalid: {rel}")
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
            if case.get("expected_validation") not in ("equal_to_rederived", "not_rederivable", "rejected"):
                errors.append(f"{cid} has unsupported expected validation")
            if case.get("expected_validation") != "equal_to_rederived" and not case.get("failure_oracle"):
                errors.append(f"{cid} has no failure oracle")
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


def all_packet_text(packet: dict) -> str:
    return "\n".join(i.get("text", "") for _, node in pk.iter_nodes(packet)
                      for key in ("items", "evidence") for i in node.get(key, []))


def failure_oracle_problems(submitted: dict, validation: dict, oracle: dict) -> list[str]:
    problems: list[str] = []
    if submitted.get("status") != oracle.get("submitted_status"):
        problems.append(f"submitted status {submitted.get('status')!r}")
    gaps = submitted.get("freshness", {}).get("generation_gap", [])
    actual_sources = sorted(str(g.get("source")) for g in gaps if g.get("source") is not None)
    if actual_sources != sorted(oracle.get("gap_sources", [])):
        problems.append(f"gap sources {actual_sources!r}")
    during_sources = sorted(str(g.get("source")) for g in gaps
                            if g.get("detected") == "during_assembly" and g.get("source") is not None)
    if during_sources != sorted(oracle.get("during_assembly_sources", [])):
        problems.append(f"during-assembly sources {during_sources!r}")
    if oracle.get("generation_changed_during_assembly") and not any(
            g.get("source") is None and g.get("detected") == "during_assembly"
            and "generation" in g.get("change", "") for g in gaps):
        problems.append("recorded generation change during assembly not named")
    conflicts = submitted.get("conflicts", [])
    for source in oracle.get("conflict_sources", []):
        if not any(c.get("source") == source for c in conflicts):
            problems.append(f"conflict source absent: {source}")
    text = all_packet_text(submitted)
    for stale in oracle.get("forbidden_stale_text", []):
        if stale in text:
            problems.append(f"stale assertion survived: {stale!r}")
    reasons = "\n".join(str(p.get("reason", "")) for p in validation.get("problems", []))
    for needle in oracle.get("validation_reason_contains", []):
        if needle not in reasons:
            problems.append(f"validation reason lacks {needle!r}")
    if not validation.get("problems"):
        problems.append("validation failure carried no diagnostic")
    return problems


def failure_observation(submitted: dict, validation: dict, oracle: dict) -> dict:
    """Retain the compact evidence that the failure oracle evaluated."""
    text = all_packet_text(submitted)
    return {"submitted_status": submitted.get("status"),
            "generation_gap": [{k: gap.get(k) for k in ("source", "detected", "change") if k in gap}
                               for gap in submitted.get("freshness", {}).get("generation_gap", [])],
            "conflicts": [{k: conflict.get(k) for k in ("field", "kind", "source") if k in conflict}
                          for conflict in submitted.get("conflicts", [])],
            "validation_problems": [{k: problem.get(k) for k in ("check", "field", "kind", "reason")
                                     if k in problem} for problem in validation.get("problems", [])],
            "forbidden_stale_text_present": {stale: stale in text
                                             for stale in oracle.get("forbidden_stale_text", [])}}


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


def s7_projection(packet: dict) -> dict:
    protected = ("objective", "authority", "accepted_decisions", "current_state", "blockers", "next_action")
    return {"protected": pk.strip_volatile({name: packet["fields"][name] for name in protected}),
            "conflicts": pk.strip_volatile(packet["conflicts"]),
            "unknowns": pk.strip_volatile(packet["unknowns"]), "status": packet["status"],
            "freshness": pk.strip_volatile(packet["freshness"]),
            "droppable_counts": {name: len(pk._droppable_list(packet, name)) for name in pk.DROPPABLE},
            "budget": copy.deepcopy(packet["budget"])}


def apply_s7_budget_checks(rows: list[dict]) -> None:
    query_ids = sorted({r["query_id"] for r in rows if r["scenario"] == "S7"})
    for query_id in query_ids:
        same = [r for r in rows if r["scenario"] == "S7" and r["query_id"] == query_id]
        reference = next((r for r in same if r["case"] == "S7-unbounded"), None)
        if not reference or not reference.get("eligible") or not reference.get("s7_projection"):
            for row in same:
                row["oracle_problems"].append("S7 unbounded reference unavailable")
                row["eligible"] = False
            continue
        ref = reference["s7_projection"]
        if ref["budget"]["truncated"] or ref["budget"]["tokens"] <= 4000:
            reference["oracle_problems"].append("S7 unbounded reference is not unbounded/over 4000")
            reference["eligible"] = False
        for row in same:
            if row["case"] in ("S7-unbounded", "S7-stale-4000") or not row.get("s7_projection"):
                continue
            got = row["s7_projection"]
            for key in ("protected", "conflicts", "unknowns", "status", "freshness"):
                if got[key] != ref[key]:
                    row["oracle_problems"].append(f"S7 {key} differs from unbounded reference")
            budget = got["budget"]
            for name in pk.DROPPABLE:
                expected = ref["droppable_counts"][name] - got["droppable_counts"][name]
                if budget["omitted"][name] != expected:
                    row["oracle_problems"].append(f"S7 omitted.{name} {budget['omitted'][name]} != {expected}")
            honest = budget["within_limit"] == (budget["tokens"] <= budget["limit"])
            honest = honest and budget["truncated"] == any(budget["omitted"].values())
            if not honest:
                row["oracle_problems"].append("S7 budget fit/truncation report is dishonest")
            row["eligible"] = not row["oracle_problems"]


def setup_requires_fresh_per_query(setup: str) -> bool:
    return setup in {"s4-immediate", "s4-after-3s", "s6-baseline-edited",
                     "s6-decision-edited", "s6-refresh-recorded"}


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


def prepare_case(case: dict, work: Path, state: Path) -> Prepared:
    setup = case["setup"]
    vault_copy = work / "vault"
    after_listing = None
    if setup in ("fixture", "scenario"):
        manifest_path = FIXTURE_MANIFEST if setup == "fixture" else SCENARIO_MANIFEST
        shutil.copytree(VAULT, vault_copy)
        m = recipe.load_manifest(manifest_path, vault_copy, state)
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
                  state: Path) -> dict:
    prepared = prepare_case(case, work, state)
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
        result["oracle_problems"].extend(failure_oracle_problems(
            submitted, validation, case["failure_oracle"]))
        result["failure_observation"] = failure_observation(
            submitted, validation, case["failure_oracle"])
        result["eligible"] = not result["oracle_problems"]
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
    retained_packet = pk.compact(trusted)
    packet_bytes = len(retained_packet)
    fetch_bytes = sum(len(compact(envelope)) for envelope in result["fetches"])
    result.update({"trusted_packet_bytes": packet_bytes, "fetch_envelope_bytes": fetch_bytes,
                   "total_consumer_bytes": packet_bytes + fetch_bytes,
                   "estimated_tokens": estimate_bytes(packet_bytes + fetch_bytes),
                   "packet_digest": pk.digest(trusted), "semantic_projection": semantic_projection(trusted),
                   "trusted_packet_encoding": "base64-compact-utf8-json",
                   "trusted_packet_compact_base64": base64.b64encode(retained_packet).decode("ascii"),
                   "s7_projection": s7_projection(trusted) if scenario["id"] == "S7" else None,
                   "eligible": False})
    result["oracle_problems"].extend(retained_packet_problems(result))
    result["eligible"] = not result["oracle_problems"]
    return result


def run_worker(predecl_path: Path, attempt_dir: Path, state_root: Path) -> int:
    predecl, predecl_hash = load_predeclaration(predecl_path)
    started = time.monotonic()
    rows: list[dict] = []
    for scenario in predecl["scenarios"]:
        for query_plan in scenario["queries"]:
            for case in scenario["cases"]:
                work = attempt_dir / "work" / scenario["id"] / query_plan["id"] / case["id"]
                state = state_root / scenario["id"] / query_plan["id"] / case["id"]
                work.mkdir(parents=True)
                try:
                    row = run_candidate(predecl, scenario, case, query_plan, work, state)
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
    apply_s7_budget_checks(rows)
    with (attempt_dir / "candidate-results-final.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
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
            consuming = [r for r in selected if r["expected_validation"] == "equal_to_rederived"
                         and not next(c for c in scenario["cases"] if c["id"] == r["case"]).get("reference_only")]
            tokens = sum(r["estimated_tokens"] for r in consuming)
            plans.append({"id": plan["id"], "query": plan["query"], "role": plan["role"],
                          "eligible": eligible, "semantic_equal_to_control": semantic_equal,
                          "estimated_tokens": tokens,
                          "fetches": sum(len(r["fetches"]) for r in consuming),
                          "zero_fetch_cases": [r["case"] for r in consuming if not r["fetches"]],
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


def terminate_process_tree(proc: subprocess.Popen) -> str | None:
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
    return detail


class BoundedRunError(RuntimeError):
    """Monitoring failed after launch, and the worker tree was stopped."""

    def __init__(self, cause: BaseException, termination_detail: str | None):
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.termination_detail = termination_detail


def run_bounded(cmd: list[str], timeout: int, lane_roots: tuple[Path, ...], lane_cap: int,
                shared_roots: tuple[Path, ...], shared_cap: int,
                stdout_path: Path, stderr_path: Path) -> tuple[int, bool, str | None, str | None]:
    """Run one attempt and terminate its process tree if the hard cap expires."""
    kwargs = {"cwd": REPO}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, **kwargs)
        try:
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    return 124, True, terminate_process_tree(proc), "time_cap"
                if roots_size(lane_roots) > lane_cap:
                    return 125, False, terminate_process_tree(proc), "stage_a_lane_cap"
                if roots_size(shared_roots) > shared_cap:
                    return 127, False, terminate_process_tree(proc), "shared_scratch_cap"
                time.sleep(0.25)
            return proc.returncode, False, None, None
        except BaseException as exc:
            termination_detail = terminate_process_tree(proc)
            raise BoundedRunError(exc, termination_detail) from exc


def git_result(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False)


def verify_launch_environment(predecl: dict, predecl_path: Path) -> tuple[list[str], dict]:
    problems: list[str] = []
    observed: dict = {"qmd": installed_version()}
    if observed["qmd"] != "2.8.3":
        problems.append(f"installed QMD is {observed['qmd']!r}, expected '2.8.3'")
    for rel, expected in predecl["implementation"]["files"].items():
        path = REPO / rel
        actual = file_sha256(path) if path.is_file() else None
        if actual != expected:
            problems.append(f"implementation hash mismatch: {rel}")
    head = git_result(["rev-parse", "HEAD"])
    observed["measurement_revision"] = head.stdout.strip() if head.returncode == 0 else None
    if head.returncode != 0:
        problems.append("cannot resolve measurement revision")
    ancestor = git_result(["merge-base", "--is-ancestor", predecl["source_revision"], "HEAD"])
    if ancestor.returncode != 0:
        problems.append("accepted source revision is not an ancestor of measurement HEAD")
    relevant = sorted(set(predecl["implementation"]["files"]) | {
        predecl_path.resolve().relative_to(REPO.resolve()).as_posix()})
    status = git_result(["status", "--porcelain", "--", *relevant])
    observed["relevant_status"] = status.stdout.splitlines()
    if status.returncode != 0 or status.stdout.strip():
        problems.append("method or accepted seam has uncommitted changes")
    return problems, observed


def projected_generated_source_bytes(predecl: dict) -> int:
    fixture_copies = 0
    stress_copies = 0
    for scenario in predecl["scenarios"]:
        query_count = len(scenario["queries"])
        for case in scenario["cases"]:
            if case["setup"].startswith("s7-"):
                stress_copies += query_count
            else:
                fixture_copies += query_count
    # Every candidate/case gets a non-overlapping source root. Each deterministic
    # S7 source is bounded conservatively at one MiB.
    return fixture_copies * dir_size(VAULT) + stress_copies * 1024 * 1024


def command_run(args, predecl: dict, predecl_hash: str) -> int:
    if args.predeclaration_sha256 != predecl_hash:
        raise SystemExit("predeclaration SHA-256 does not match; measurement refused")
    errors = validate_predeclaration(predecl)
    if errors:
        raise SystemExit("invalid predeclaration: " + "; ".join(errors))
    scratch = args.scratch.resolve()
    if any(scratch == p or p in scratch.parents or scratch in p.parents
           for p in (VAULT.resolve(), FIXTURES.resolve())):
        raise SystemExit("scratch must be outside every source root")
    scratch.mkdir(parents=True, exist_ok=True)
    cap = predecl["limits"]["stage_a_scratch_bytes"]
    shared_cap = predecl["limits"]["shared_scratch_bytes"]
    lane_roots = (scratch, DEFAULT_STATE_LANE)
    existing_size = roots_size(lane_roots)
    shared_existing_size = roots_size(SHARED_ACCOUNTING_ROOTS)
    if existing_size > cap:
        raise SystemExit("preexisting Stage A source/state lane exceeds its 250 MiB allocation")
    if shared_existing_size > shared_cap:
        raise SystemExit("preexisting shared scratch exceeds its 1 GiB allocation")
    minimum_free = predecl["limits"]["minimum_free_before_launch_bytes"]
    if cap - existing_size < minimum_free:
        raise SystemExit("insufficient free Stage A scratch allocation before launch")
    projected = projected_generated_source_bytes(predecl)
    if projected > predecl["limits"]["max_generated_source_bytes"]:
        raise SystemExit("bounded generated-source projection exceeds its predeclared maximum")
    environment_problems, observed_environment = verify_launch_environment(predecl, args.predeclaration)
    if environment_problems:
        raise SystemExit("launch environment refused: " + "; ".join(environment_problems))
    ledger = scratch / "attempts.jsonl"
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if ledger.exists() else []
    prior = sum(1 for record in records if record.get("event") == "started")
    if prior >= predecl["limits"]["attempts"]:
        raise SystemExit("20-attempt cap reached")
    attempt_no = prior + 1
    attempt_dir = scratch / "attempts" / f"attempt-{attempt_no:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    attempt_state_root = DEFAULT_STATE_LANE / f"attempt-{attempt_no:02d}"
    attempt_state_root.mkdir(parents=True, exist_ok=False)
    before = fixture_status()
    tree_before = tree_digest(FIXTURES)
    start_record = {"attempt": attempt_no, "event": "started", "at": utc_now(),
                    "predeclaration_sha256": predecl_hash, "fixture_before": before,
                    "launch_environment": observed_environment,
                    "accounting_roots": {"stage_a_lane": [str(p) for p in lane_roots],
                                         "shared": [str(p) for p in SHARED_ACCOUNTING_ROOTS]},
                    "preexisting_lane_bytes": existing_size,
                    "preexisting_shared_bytes": shared_existing_size,
                    "projected_generated_source_bytes": projected,
                    "shared_full_harness_budget_increment": 1}
    append_attempt(ledger, start_record)
    if not before["ok"]:
        append_attempt(ledger, {"attempt": attempt_no, "event": "stopped", "at": utc_now(),
                                "reason": "fixture hash verification failed before run"})
        return 2
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()), "_worker",
           "--predeclaration", str(args.predeclaration.resolve()), "--attempt-dir", str(attempt_dir),
           "--state-root", str(attempt_state_root)]
    launch_error = None
    try:
        code, timed_out, timeout_termination, stop_reason = run_bounded(
            cmd, predecl["limits"]["seconds_per_attempt"], lane_roots, cap,
            SHARED_ACCOUNTING_ROOTS, shared_cap,
            attempt_dir / "worker-stdout.log", attempt_dir / "worker-stderr.log")
    except BoundedRunError as exc:
        code, timed_out, timeout_termination, stop_reason = (
            126, False, exc.termination_detail, "launch_or_runner_error")
        launch_error = str(exc)
    except BaseException as exc:
        code, timed_out, timeout_termination, stop_reason = 126, False, None, "launch_error"
        launch_error = f"{type(exc).__name__}: {exc}"
    after = fixture_status()
    tree_unchanged = tree_digest(FIXTURES) == tree_before
    scratch_size = dir_size(scratch)
    state_size = dir_size(DEFAULT_STATE_LANE)
    lane_size = scratch_size + state_size
    shared_size = roots_size(SHARED_ACCOUNTING_ROOTS)
    final = {"attempt": attempt_no, "event": "finished", "at": utc_now(), "exit_code": code,
             "timed_out": timed_out, "timeout_process_tree_termination": timeout_termination,
             "bounded_stop_reason": stop_reason,
             "launch_error": launch_error,
             "fixture_after": after, "fixtures_tree_unchanged": tree_unchanged,
             "scratch_bytes": scratch_size, "external_state_bytes": state_size,
             "lane_accounted_bytes": lane_size, "lane_cap_bytes": cap,
             "shared_accounted_bytes": shared_size, "shared_cap_bytes": shared_cap}
    append_attempt(ledger, final)
    (attempt_dir / "attempt-summary.json").write_text(json.dumps({"start": start_record, "finish": final}, indent=2),
                                                       encoding="utf-8")
    if not after["ok"] or not tree_unchanged:
        return 3
    if lane_size > cap or shared_size > shared_cap:
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
    worker.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "_worker":
        return run_worker(args.predeclaration, args.attempt_dir, args.state_root)
    predecl, digest = load_predeclaration(args.predeclaration)
    if args.command == "preflight":
        errors = validate_predeclaration(predecl)
        print(json.dumps({"predeclaration": str(args.predeclaration), "sha256": digest,
                          "valid": not errors, "errors": errors}, indent=2))
        return 0 if not errors else 1
    return command_run(args, predecl, digest)


if __name__ == "__main__":
    raise SystemExit(main())
