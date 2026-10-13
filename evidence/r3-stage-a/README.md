# R3 Stage A evidence

Stage A has no valid query-headroom measurement yet. The first reserved run was
an infrastructure refusal, and its negative result is retained without tuning the
fixed measurement contract. A narrow setup amendment is predeclared for focused
review before any further full run.

## Attempt 1: setup refusal

- Command: `python -I scripts/measure_stage_a.py run --predeclaration evidence/r3-stage-a/predeclaration.json --predeclaration-sha256 f328275a4318588fcbfa6a9f6f2221a3664719ed7c52231fdd23275e61e34988`
- Method revision: `53b388d17d0838a80cb741fe5f4f4d2051962326`
- Predeclaration SHA-256: `f328275a4318588fcbfa6a9f6f2221a3664719ed7c52231fdd23275e61e34988`
- Harness SHA-256: `ce7e853169abfe6fd793f32a7c37eb45b50c039451fbaa708f256f41634d7726`
- Result: exit 1; 88 of 88 rows ineligible; 27 `RecipeError` and 61
  `FileExistsError` setup failures; every row had empty search work, zero trusted
  packet bytes and zero fetch-envelope bytes. Controls were invalid and aggregate
  savings are therefore null. This run made no consumer/query-saving observation.
- Boundary evidence: QMD state was outside the repository `.qmd` boundary. After
  the first refusal, the shared setup directory already existed and later setup
  attempts refused that collision.
- Safety: fixture hashes were 16/16 before and after and the tree digest was
  unchanged; runtime was under one second; 358,229 bytes were retained under the
  250 MiB cap; there was no timeout or launch error.

The exact original method is recoverable from the method revision above. Raw
attempt evidence is under `attempt-01/`, including the ledger, per-row JSONL,
aggregate result, full empty stdout/stderr logs and attempt summary.

## Accepted R2 regression

The separately reserved baseline command `python -I scripts/run_scenarios.py`
ran once with an external 600-second process-tree boundary. It exited 0 after
133.850 seconds with `ALL GATES PASS (184 checks)`. Fixture hashes were 16/16
before and after. Full stdout, empty stderr and the boundary summary are under
`regression-184/`. This establishes that the accepted R2 path remained intact;
it does not convert the refused Stage A attempt into a measurement.

## Predeclared infrastructure amendment

Every candidate/case now receives a distinct synthetic source copy and a distinct
QMD state directory below `.qmd/r3-stage-a`. QMD index, config and cache stay in
that external state lane. Continuous 250 MiB lane accounting sums
`.scratch/r3-stage-a` and `.qmd/r3-stage-a`; continuous 1 GiB shared accounting
sums repository `.scratch`, `.qmd` and `runtime-vaults`. Both caps terminate the
complete worker process tree.

The canonical sorted compact JSON projection of `runtime`, `measurement`,
`evidence` and `scenarios` hashes to
`e63b5514a235f956474cd540765f72d3ba8eeef5ed08c43beb860286b4312fc1`
in both the attempt-1 predeclaration and this amendment. Thus the candidate list,
scenario cases, evidence requirements, oracles, fetch policy, byte estimator,
aggregation, tie-breaking, failure treatment and interpretation are byte-equivalent.

No additional full run is authorized by this evidence package. The amended
commit and predeclaration hash require focused independent review and a new
orchestrator reservation.
