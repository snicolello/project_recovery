# R3 Stage A evidence

Stage A completed a packet-retaining query-headroom measurement under the frozen,
independently reviewed method. The exact validator-returned packets and fetch
envelopes now make every charged byte, coverage claim and aggregate independently
recomputable. Attempt 1 was refused, attempt 2 remains provisional because it
omitted packet inputs, and attempt 3 is the final auditable measurement.

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

## Attempt 2: execution valid, cost evidence provisional

- Command: `python -I scripts/measure_stage_a.py run --predeclaration evidence/r3-stage-a/predeclaration.json --predeclaration-sha256 15e585a258ef723be740e26fdc2f68fb39a783bf9c22157fce8077279ac15433`
- Method revision: `9fa99e743ae7d40d79164876946e408e7a57f673`
- Predeclaration SHA-256: `15e585a258ef723be740e26fdc2f68fb39a783bf9c22157fce8077279ac15433`
- Harness SHA-256: `aaa614c9e29fd891a9cd144d14b990fe0c1385d6fd42b5f500ac95c10eadf743`
- Result: exit 0 in 346.843 seconds. All 88 rows were eligible. Validation
  produced 64 equal packets, 20 expected `not_rederivable` results and four
  expected rejections. All 24 predeclared mutation failures matched their exact
  oracles and charged zero consumer bytes. Successful coverage was 460/460,
  with no oracle problems or unsupported assertions.
- Fetches: 42 of 42 explicit fetches across the full 88-row grid established the
  requested span; none failed. Of 62 zero-fetch rows, 24 were expected refusals
  with no trusted packet. The 64 validated-packet rows had 38 zero-fetch rows.
  Excluding four S7 diagnostic references leaves 60 consuming rows, 40 fetches
  and 36 zero-fetch rows. The eight selected non-control plans span 15 consuming
  cases with 10 fetches and nine zero-fetch cases.
- Provisional aggregate: the R2 controls total 46,434 estimated tokens. The best eligible
  non-control query in each fixed list totals 42,427, an 8.629% reduction. Keeping
  the R2 control when it is cheaper totals 42,136, a 9.256% achievable reduction.
  The 15% owner reference was not met and is not an acceptance threshold.

| Scenario | Control | Best non-control | Non-control change | Best with control |
|---|---:|---:|---:|---:|
| S1 | 3,923 | 3,138 (`ATLAS-42`) | 20.010% lower | 3,138 |
| S2 | 7,600 | 5,713 (`SQLite PostgreSQL Redis`) | 24.829% lower | 5,713 |
| S3 | 4,853 | 4,574 (`retry-window`) | 5.749% lower | 4,574 |
| S4 | 6,640 | 6,078 (`retry-window`) | 8.464% lower | 6,078 |
| S5 | 3,142 | 3,145 (`UNKNOWN approval`) | 0.095% higher | 3,142 control |
| S6 | 3,923 | 3,138 (`ATLAS-42`) | 20.010% lower | 3,138 |
| S7 | 9,170 | 9,178 (`load option`) | 0.087% higher | 9,170 control |
| S8 | 7,183 | 7,463 (`Recovery marker`) | 3.898% higher | 7,183 control |

The S7 `Stress Project` and `truncation report` plans passed every row oracle but
were not eligible plans because their consuming semantic projections differed
from the control. `load option` was the only eligible S7 non-control plan. These
results identify the best choices only within the frozen query lists; they do not
bound other Librarian strategies.

Raw evidence is under `attempt-02/`; the full attempt result is also `results.json`
and the compact audit view is `summary.json`. The full result SHA-256 is
`fef7e6b7eb53e2545777f21e2c32fc96f6b15c1a28220f486dc2d36767934513`.
These files are preserved byte-for-byte. They omit the exact trusted packet
content for all 64 successful rows, so their charged packet bytes, coverage and
aggregate costs cannot be independently reconstructed and are not final findings.

## Evidence-retention amendment

The frozen amended predeclaration SHA-256 is
`11c071e9260c34dca3e3d601a94177a380e2a8db971ec21ae5ca01265d2b55ba` and the
amended harness SHA-256 is
`d9fde7bf98813249f571299ff3117d5308b1a7e8a21a03d081fb687ccf9bf89a`.
The amended harness stores the exact compact UTF-8 validator-returned packet as
base64 for every `equal_to_rederived` row. It decodes and parses that content,
requires byte-for-byte equality with the packet compactor, checks its length
against `trusted_packet_bytes`, and checks its digest against `packet_digest`.
Expected refusals and failures retain no packet content. This bookkeeping is not
consumer-visible and does not change any charged bytes or frozen measurement field.
Preflight accepted this predeclaration and 21 focused pure tests passed with the
synthetic fixture manifest at 16/16 immediately before and after each check.

## Attempt 3: final auditable Stage A measurement

- Command: `python -I scripts/measure_stage_a.py run --predeclaration evidence/r3-stage-a/predeclaration.json --predeclaration-sha256 11c071e9260c34dca3e3d601a94177a380e2a8db971ec21ae5ca01265d2b55ba`
- Method revision: `541ea4397574d2a3ed8874085be4aaf5e37ef704`
- Harness SHA-256: `d9fde7bf98813249f571299ff3117d5308b1a7e8a21a03d081fb687ccf9bf89a`
- Raw result SHA-256: `522cb351f402e316055f74c3546735de53a9218d440d2e78db1e0aced47eef6d`
- LF-normalized audit export SHA-256: `9c1bfb832ff2948100f5de1bcfab3e097fca2301328b813ba145cd9c6401e597`
- Result: exit 0; 348.297-second worker and 351.508-second bounded start to
  finish. There was no timeout, cap stop, launch error, fixture change, or oracle
  problem. All 88 rows were eligible: 64 `equal_to_rederived`, 20 expected
  `not_rederivable`, and four expected rejections. The 24 refused rows retained
  no packet and charged zero bytes.
- Auditable packets: all 64 successful rows retain the exact compact packet as
  base64. Their 692,470 decoded bytes exactly equal their charged packet bytes;
  every compact round-trip, length, and digest check passed.
- Coverage and fetches: 460/460 requirements were covered. All 42 fetch envelopes
  were established and retained, totaling 19,870 bytes. Of 62 zero-fetch rows,
  24 were expected refusals. The 64 packet rows had 38 zero-fetch rows. Excluding
  four S7 diagnostic references leaves 60 consuming rows, 40 fetches, and 36
  zero-fetch rows. The selected non-control plans cover 15 consuming cases with
  10 fetches and nine zero-fetch cases.
- Aggregate: controls total 46,434 estimated tokens. The best eligible non-control
  in each fixed list totals 42,427, an 8.629% reduction. Retaining the cheaper
  control in S5, S7, and S8 totals 42,136, a 9.256% achievable reduction. The
  15% reference was not met and is not an acceptance threshold.

The per-scenario choices and values are the table above. S7 `project` and `report`
again passed row oracles but were excluded for semantic mismatch. The raw result,
lossless packets, fetch envelopes, row stream, complete ledger, boundary summary,
and empty worker logs are under `attempt-03/`; `results.json` is the same result
content with LF-normalized line endings and `summary.json` is the concise owner
view.

The Windows runner wrote attempt-3 JSON and JSONL evidence with CRLF endings. The
raw files under `attempt-03/` are preserved with explicit
`-text whitespace=cr-at-eol` attributes, and `files.sha256` hashes those bytes.
Top-level `results.json` is an LF-normalized audit export with identical parsed
JSON and base64 packet values. Attempts 1 and 2 remain byte-identical.

## Independent final audit

The independent evidence audit passed with no blocking or actionable findings at
reviewed evidence revision `f63a2781bd5effe5b805aef09138a84bf705187f`.
It independently decoded all 64 packets; verified all 1,328 packet receipts, 460
required evidence entries, 42 fetch envelopes, 24 refusal oracles, every row cost,
the S7 cross-budget checks and semantic exclusions, and both aggregates. It also
confirmed fixture integrity, runtime and scratch bounds, the global 4/20 run count,
and tracked-file hashes. The reviewed raw result SHA-256 is
`522cb351f402e316055f74c3546735de53a9218d440d2e78db1e0aced47eef6d`;
the reviewed LF audit export SHA-256 is
`9c1bfb832ff2948100f5de1bcfab3e097fca2301328b813ba145cd9c6401e597`.

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

Those shared roots resolve inside this A worktree. They do not include sibling
worktrees; the orchestrator enforces the overnight 1 GiB total across worktrees
using the 250 MiB lane allocations and reported sibling totals. After attempt 3
and its final ledger writes, this A lane used 40,569,165 bytes and all three
A-worktree shared roots used 42,750,778 bytes.

The canonical sorted compact JSON projection of `runtime`, `measurement`,
`evidence` and `scenarios` hashes to
`e63b5514a235f956474cd540765f72d3ba8eeef5ed08c43beb860286b4312fc1`
in both the attempt-1 predeclaration and this amendment. Thus the candidate list,
scenario cases, evidence requirements, oracles, fetch policy, byte estimator,
aggregation, tie-breaking, failure treatment and interpretation are byte-equivalent.

No additional full run is authorized or needed. Attempt 3 passed final independent
evidence audit and is decision-ready for the owner. Attempt 2 remains provisional;
15% remains context, not a release gate.
