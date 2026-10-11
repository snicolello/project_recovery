"""Run scenarios S1 to S5 against the fixture vault and score the R1 gates.

    python -I scripts/run_scenarios.py [--runs 20]

Gates: recovery completeness, unsupported assertions, abstention, isolation,
freshness (S4), budget, read-only tool surface, repeatability (20 runs including
one index rebuild), negative tests, and fixture-hash integrity before and after.
Exits non-zero if any gate fails. Packets and a results file are written to
.scratch/run_scenarios/ (git-ignored). fixtures/ is never written; S4 edits a
throwaway copy under runtime-vaults/ (git-ignored).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import packet as pk  # noqa: E402
import recipe  # noqa: E402
from qmd_client import ALLOWED_TOOLS, McpSession  # noqa: E402
from receipts import SourceError, safe_resolve, validate_receipt  # noqa: E402

MANIFEST = REPO / "manifest" / "fixture-vault.json"
FIXTURES = REPO / "fixtures"
VAULT = FIXTURES / "synthetic-vault"
OUT = REPO / ".scratch" / "run_scenarios"
STATE_MAIN = REPO / ".qmd" / "run-fixture"
STATE_S4 = REPO / ".qmd" / "run-s4"
S4_COPY = REPO / "runtime-vaults" / "s4"

ATLAS_UNKNOWN = ["authority.approver", "authority.approvals.rollout_approval", "authority.approvals.rollout_owner"]
ATLAS_FIELDS = {
    "objective": ["offline field-report queue for one laptop"],
    "current_state": ["Parser complete"],
    "accepted_decisions": ["SQLite"],
    "blockers": ["Missing sample for an empty report"],
    "next_action": ["Add the empty-report fixture and run the parser tests", "Deployment is not authorized"],
}
SCENARIOS = {
    "S1": {"project": "atlas", "query": "Atlas project", "fields": ATLAS_FIELDS, "unknown": ATLAS_UNKNOWN,
           "forbid": ["BEACON", "99 seconds"]},
    "S2": {"project": "atlas", "query": "queue", "fields": ATLAS_FIELDS, "unknown": ATLAS_UNKNOWN,
           "forbid": ["BEACON"]},
    "S3-atlas": {"project": "atlas", "query": "restart", "fields": ATLAS_FIELDS, "unknown": ATLAS_UNKNOWN,
                 "hits": ["retry-window 15 seconds"], "forbid": ["BEACON", "retry-window 99"]},
    "S3-beacon": {"project": "beacon", "query": "restart", "unknown": ["authority.approver"],
                  "fields": {"objective": ["hosted alert relay"], "current_state": ["Load test complete"],
                             "accepted_decisions": ["PostgreSQL"], "blockers": ["None recorded"],
                             "next_action": ["Prepare the demo recording"]},
                  "hits": ["retry-window 99 seconds"], "forbid": ["ATLAS", "retry-window 15", "SQLite"]},
    "S5": {"project": "atlas", "query": "rollout", "fields": ATLAS_FIELDS, "unknown": ATLAS_UNKNOWN,
           "forbid": ["BEACON"]},
}
FIXED = list(SCENARIOS)  # the repeatability set (S4 mutates its copy and is scored separately)


class Gates:
    def __init__(self) -> None:
        self.results: list[dict] = []

    def check(self, gate: str, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append({"gate": gate, "check": name, "pass": bool(ok), "detail": detail})
        return ok

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.results if not r["pass"]]


def tree_digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def verify_fixture_script() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-I", "scripts/verify_fixture_hashes.py"], cwd=REPO,
                       capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]


def field_texts(packet: dict, name: str) -> list[str]:
    node = packet["fields"][name]
    if "decisions" in node:
        return [i["text"] for d in node["decisions"] for i in d.get("items", [])]
    return [i["text"] for i in node.get("items", [])]


def all_texts(packet: dict) -> list[str]:
    return [i["text"] for _, n in pk.iter_nodes(packet) for k in ("items", "evidence") for i in n.get(k, [])]


def score(g: Gates, sid: str, spec: dict, packet: dict, root: Path) -> None:
    proj_root = spec["project"] + "/"
    # Completeness: every answerable field established and carrying the expected text.
    total = hit = 0
    for name, needles in spec["fields"].items():
        texts = " ".join(field_texts(packet, name))
        established = packet["fields"][name].get("status") == "established"
        for needle in needles:
            total += 1
            hit += int(established and needle in texts)
    g.check("completeness", sid, hit == total, f"{hit}/{total} answerable values recovered")
    problems = pk.unsupported_assertions(packet, root)
    g.check("unsupported", sid, not problems, f"{len(problems)} unsupported material assertions")
    unknown = {u["field"] for u in packet["unknowns"]}
    wrong_abstain = [f for f in spec["fields"] if f in unknown]
    missing_abstain = [f for f in spec["unknown"] if f not in unknown]
    g.check("abstention", sid, not wrong_abstain and not missing_abstain,
            f"unknown as expected: {sorted(spec['unknown'])}; wrongly abstained: {wrong_abstain}; "
            f"missing: {missing_abstain}")
    foreign = [r["source"] for r in pk.ordered_receipts(packet) if not r["source"].startswith(proj_root)]
    leaked = [n for n in spec.get("forbid", []) if any(n in t for t in all_texts(packet))]
    g.check("isolation", sid, not foreign and not leaked, f"foreign sources {foreign}; leaked text {leaked}")
    if "hits" in spec:
        hit_text = " ".join(i["text"] for h in packet["query_hits"] for i in h.get("items", []))
        g.check("completeness", f"{sid} query evidence", all(n in hit_text for n in spec["hits"]),
                f"expected {spec['hits']} in cited query hits")
    b = packet["budget"]
    g.check("budget", sid, b["within_limit"] and b["tokens"] <= 4000,
            f"{b['tokens']} tokens ({b['tokenizer']}), truncated={b['truncated']}")
    g.check("freshness", sid, packet["status"] == "complete" and not packet["freshness"]["generation_gap"],
            f"status {packet['status']}, generation {packet['freshness']['generation']}")


def score_s2(g: Gates, packet: dict) -> None:
    f = packet["fields"]
    acc = [(d["title"], d["local_status"], d["authority_state"]) for d in f["accepted_decisions"]["decisions"]]
    other = {d["title"]: (d["local_status"], " ".join(i["text"] for i in d["items"]))
             for d in f["other_decisions"]["decisions"]}
    ok = (("Queue Decision", "accepted", "local_only") in acc
          and other.get("Queue Proposal", ("", ""))[0] == "draft" and "PostgreSQL" in other["Queue Proposal"][1]
          and other.get("Queue Archive", ("", ""))[0] == "superseded" and "Redis" in other["Queue Archive"][1])
    states = {d["authority_state"] for d in f["accepted_decisions"]["decisions"] + f["other_decisions"]["decisions"]}
    g.check("completeness", "S2 decisions with status", ok, f"accepted {acc}; other { {k: v[0] for k, v in other.items()} }")
    g.check("authority", "S2 labels", states == {"local_only"} and f["authority"]["authority_state"] == "local_only"
            and f["authority"]["verification"].startswith("not_performed"),
            f"authority states {sorted(states)}; verification: {f['authority']['verification'][:40]}")


def score_s5(g: Gates, packet: dict) -> None:
    ap = packet["fields"]["authority"]["approvals"]
    ok = all(ap[k]["status"] == "unknown" and ap[k]["evidence"] for k in ("rollout_approval", "rollout_owner"))
    missing = [m["link"] for m in packet["missing_sources"]]
    g.check("abstention", "S5 approval and owner unknown", ok, "rollout_approval and rollout_owner = unknown, with cited evidence")
    g.check("abstention", "S5 missing note not fabricated", "Rollout Approval" in missing
            and not any("Rollout Approval.md" in r["source"] for r in pk.ordered_receipts(packet)),
            f"missing_sources {missing}; no locator for the missing note")


def assemble_all(m, names) -> tuple[dict[str, dict], set, list]:
    out = {}
    with McpSession(m.state_dir) as s:
        for sid in names:
            out[sid] = recipe.assemble(m, SCENARIOS[sid]["project"], SCENARIOS[sid]["query"], s)
        calls, advertised = set(s.calls), s.advertised
    return out, calls, advertised


def negative_tests(g: Gates, m, s1: dict) -> None:
    root = m.vault_root
    bad = copy.deepcopy(s1)
    bad["fields"]["objective"]["items"][0]["receipt"]["content_sha"] = "0" * 64
    checked = pk.revalidate(bad, root)
    ok = (checked["fields"]["objective"]["status"] == "unknown"
          and any(u["field"] == "fields.objective" for u in checked["unknowns"])
          and any(c["field"] == "fields.objective" and c["kind"] == "receipt_validation_failed" for c in checked["conflicts"]))
    g.check("negative", "corrupted content_sha -> unknown + conflict", ok, "objective receipt sha zeroed")
    bad = copy.deepcopy(s1)
    bad["fields"]["current_state"]["items"][0]["text"] = "Current state: Deployed to production."
    checked = pk.revalidate(bad, root)
    g.check("negative", "altered cited text -> unknown + conflict",
            checked["fields"]["current_state"]["status"] == "unknown"
            and any(c["field"] == "fields.current_state" for c in checked["conflicts"]), "text no longer matches bytes")
    bad = copy.deepcopy(s1)
    bad["fields"]["blockers"]["items"][0]["receipt"]["source"] = "atlas/../beacon/Project.md"
    checked = pk.revalidate(bad, root)
    g.check("negative", "traversal locator -> unknown + conflict",
            checked["fields"]["blockers"]["status"] == "unknown", "atlas/../beacon/Project.md rejected")
    for loc in ("../fixtures/synthetic-vault/atlas/Project.md", "/etc/passwd", "C:/x.md", "atlas\\Project.md"):
        try:
            safe_resolve(root, loc)
            g.check("negative", f"reject locator {loc}", False, "accepted")
        except SourceError:
            g.check("negative", f"reject locator {loc}", True, "rejected")
    ok, why = validate_receipt({"source": "atlas/Rollout Approval.md", "span": [1, 1], "content_sha": "0" * 64,
                                "generation": "x", "revision": "unknown", "observed_at": "x"}, root)
    g.check("negative", "missing source never validates", not ok, why)
    with McpSession(m.state_dir) as s:
        raw = s.query("Beacon", "atlas")
        raw99 = s.query("BEACON-99", "atlas")
        packet = recipe.assemble(m, "atlas", "Beacon", s)
    beacon = [r["source"] for r in pk.ordered_receipts(packet) if r["source"].startswith("beacon/")]
    g.check("negative", "Beacon query under Atlas scope returns nothing from Beacon",
            not raw and not raw99 and not packet["query_hits"] and not beacon,
            f"raw hits {len(raw)}+{len(raw99)}, packet hits {len(packet['query_hits'])}, beacon receipts {len(beacon)}")
    tiny = pk.bound(copy.deepcopy(s1), 1200)
    g.check("negative", "budget trims hits but keeps conflicts and unknowns",
            tiny["budget"]["truncated"] and tiny["unknowns"] == s1["unknowns"] and tiny["conflicts"] == s1["conflicts"]
            and tiny["budget"]["omitted"]["query_hits"] > 0,
            f"limit 1200 -> omitted {tiny['budget']['omitted']}, within_limit={tiny['budget']['within_limit']}")


def run_s4(g: Gates, out_dir: Path) -> dict:
    if S4_COPY.exists():
        shutil.rmtree(S4_COPY)
    shutil.copytree(VAULT, S4_COPY)
    expected = json.loads((FIXTURES / "synthetic-vault-hashes.json").read_text(encoding="utf-8"))
    g.check("freshness", "S4 runtime copy matches fixture hashes", tree_digest(S4_COPY) == expected, str(S4_COPY.relative_to(REPO)))
    m = recipe.load_manifest(MANIFEST, S4_COPY, STATE_S4)
    recipe.refresh(m, rebuild=True)
    runbook = S4_COPY / "atlas" / "Restart Runbook.md"
    phases = {}

    def packet_now(label):
        with McpSession(m.state_dir) as s:
            p = recipe.assemble(m, "atlas", "restart", s)
        phases[label] = p
        (out_dir / f"S4-{label}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
        hit = next((h for h in p["query_hits"] if h["source"] == "atlas/Restart Runbook.md"), None)
        return p, " ".join(i["text"] for i in (hit or {}).get("items", []))

    p, text = packet_now("before-edit")
    g.check("freshness", "S4 before edit: 15 seconds", "retry-window 15 seconds" in text and p["status"] == "complete", "")
    data = runbook.read_bytes()
    runbook.write_bytes(data.replace(b"local-r1", b"local-r2").replace(b"15 seconds", b"45 seconds")
                        .replace(b"REVISION-OLD-15", b"REVISION-NEW-45"))
    for label, wait in (("immediate", 0), ("after-3s", 3)):
        time.sleep(wait)
        p, text = packet_now(label)
        gap = [x["source"] for x in p["freshness"]["generation_gap"]]
        stale = any("15 seconds" in t for t in all_texts(p))
        conflict = any(c["source"] == "atlas/Restart Runbook.md" for c in p["conflicts"])
        g.check("freshness", f"S4 {label}: incomplete packet names the generation gap",
                p["status"] == "incomplete" and gap == ["atlas/Restart Runbook.md"] and not stale and conflict,
                f"status {p['status']}, gap {gap}, stale text asserted={stale}, conflict recorded={conflict}")
        g.check("unsupported", f"S4 {label}", not pk.unsupported_assertions(p, m.vault_root), "")
    recipe.refresh(m)
    p, text = packet_now("after-refresh")
    g.check("freshness", "S4 after explicit refresh: new bytes",
            p["status"] == "complete" and "retry-window 45 seconds" in text and "REVISION-NEW-45" in text,
            f"status {p['status']}, generation {p['freshness']['generation']}")
    g.check("unsupported", "S4 after-refresh", not pk.unsupported_assertions(p, m.vault_root), "")
    return phases


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    args = ap.parse_args()
    g = Gates()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "packets").mkdir(exist_ok=True)

    ok, line = verify_fixture_script()
    g.check("integrity", "fixture hashes before", ok, line)
    tree_before = tree_digest(FIXTURES)

    m = recipe.load_manifest(MANIFEST, None, STATE_MAIN)
    first_gen = recipe.refresh(m, rebuild=True)["generation"]
    packets, calls, advertised = assemble_all(m, FIXED)
    for sid, p in packets.items():
        (OUT / "packets" / f"{sid}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
        score(g, sid, SCENARIOS[sid], p, m.vault_root)
    score_s2(g, packets["S2"])
    score_s5(g, packets["S5"])
    g.check("read-only", "QMD advertises only the four read tools", set(advertised) == ALLOWED_TOOLS, str(advertised))
    g.check("read-only", "recipe called only allowlisted tools", calls <= ALLOWED_TOOLS, str(sorted(calls)))

    negative_tests(g, m, packets["S1"])
    run_s4(g, OUT / "packets")

    # Repeatability: identical canonical packets and ordered receipts, one rebuild midway.
    reference = {sid: (pk.digest(p), pk.ordered_receipts(p)) for sid, p in packets.items()}
    mismatches, rebuild_gen = [], None
    for run in range(1, args.runs + 1):
        if run == args.runs // 2 + 1:
            rebuild_gen = recipe.refresh(m, rebuild=True)["generation"]
        again, _, _ = assemble_all(m, FIXED)
        for sid, p in again.items():
            if (pk.digest(p), pk.ordered_receipts(p)) != reference[sid]:
                mismatches.append(f"run {run} {sid}")
    g.check("repeatability", f"{args.runs} runs x {len(FIXED)} packets identical, rebuild before run {args.runs // 2 + 1}",
            not mismatches and rebuild_gen == first_gen,
            f"mismatches {mismatches[:5]}; generation before {first_gen}, after rebuild {rebuild_gen}; "
            f"digests " + ", ".join(f"{k}={v[0][:12]}" for k, v in reference.items()))

    ok, line = verify_fixture_script()
    g.check("integrity", "fixture hashes after", ok, line)
    g.check("integrity", "fixtures/ tree unchanged (all files, not only notes)", tree_digest(FIXTURES) == tree_before,
            f"{len(tree_before)} files")

    (OUT / "results.json").write_text(json.dumps(g.results, indent=2), encoding="utf-8")
    width = max(len(r["check"]) for r in g.results)
    for r in g.results:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['gate']:<13} {r['check']:<{width}}  {r['detail']}")
    gates = sorted({r["gate"] for r in g.results})
    print()
    for gate in gates:
        rs = [r for r in g.results if r["gate"] == gate]
        print(f"gate {gate:<13} {sum(r['pass'] for r in rs)}/{len(rs)}")
    print(f"\n{'ALL GATES PASS' if not g.failed else f'{len(g.failed)} CHECK(S) FAILED'} "
          f"({len(g.results)} checks; packets in .scratch/run_scenarios/packets/)")
    return 1 if g.failed else 0


if __name__ == "__main__":
    sys.exit(main())
