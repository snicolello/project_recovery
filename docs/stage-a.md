# R3 Stage A measurement

Stage A is a bounded, offline measurement of query-selection headroom against the
accepted R2 recovery path. It does not call a model and does not alter product code.
The committed predeclaration in `evidence/r3-stage-a/predeclaration.json` fixes the
R2 control and candidate queries, scenario variants, evidence spans, fetch policy,
token estimator, aggregation, tie-breaking, failure treatment, limits and
interpretation before any result is observed.

The harness trusts only a packet returned by the existing validator after
`validate --hits requery` reports `equal_to_rederived`. Consumer cost is the UTF-8
byte length of that compact packet plus the compact envelopes of all explicit
span fetches the consumer reads, divided by 2.9 and rounded up. Candidate search
work and validator traffic are reported separately because the consumer does not
receive them. Failed fetch envelopes are charged; zero-fetch cases remain explicit.

S4 stale phases, S6 concurrent-change phases and the pre-refresh S7 phase are
expected failure observations. Each has a specific predeclared gap, conflict and
stale-text oracle; an unrelated `not_rederivable` result is a failure. They must
fail closed and expose no trusted packet. They are reported with zero consumer
bytes and cannot manufacture a saving. S7 also builds one unbounded diagnostic
reference per query plan and checks every bounded packet's protected fields,
conflicts, unknowns, freshness, omission counts and fit report against it. The
reference is not charged as another consumer case.

The predeclaration binds the harness, accepted R2 assembly/validation seams and
manifests by SHA-256. Launch refuses a changed or dirty method, a product baseline
that is no longer an ancestor, or installed QMD other than 2.8.3. The attempt
record captures the actual measurement revision. The runner also refuses
preexisting over-cap scratch, checks a conservative generated-source bound, gives
every candidate a distinct synthetic source copy and QMD state below
`.qmd/r3-stage-a`, and polls both the source scratch and external state. It
terminates the complete process tree on the 250 MiB Stage A lane cap, the 1 GiB
shared cap or the 600-second time cap. It reserves the attempt before launch,
captures complete worker stdout and stderr, verifies fixture hashes after failures,
and records one increment against the shared 20-full-harness-run budget. The
separate existing 184-check regression is another orchestrator-counted full run.

Attempt 1 produced no query or consumer-cost observation: setup refused all 88
rows because QMD state was outside the repository `.qmd` boundary, and later rows
also encountered the already-created shared setup directory. Its zero-byte rows
remain failure evidence. Before another measurement, the implementation-only
amendment above was committed and re-predeclared. The candidate list, semantic
oracles, required coverage, fetch rules, byte estimator, aggregation, failure
treatment and interpretation are unchanged.

The corrected attempt at reviewed method revision `9fa99e7` completed all 88
rows with no oracle failures, but its cost findings are provisional because the
successful rows omitted the lossless validator-returned packet content required
to independently recompute charged packet bytes, receipts and coverage. Its raw
evidence remains byte-identical. The provisional fixed-list best non-controls reduced the
46,434-token control total to 42,427 (8.629%); retaining a cheaper control in S5,
S7 and S8 reduced the achievable total to 42,136 (9.256%). The 15% reference was
not met. All 24 expected mutation refusals matched their frozen causes and charged
zero consumer bytes; successful evidence coverage was 460/460. The full grid had
42 established fetches, including two for four uncharged S7 references. The 60
consuming rows had 40 fetches and 36 zero-fetch rows; selected non-control plans
had 10 fetches across 15 consuming cases, nine of them zero-fetch. S7's `project`
and `report` plans passed row oracles but were excluded because their semantic
projections differed from the control. These are best results within the fixed
lists only.

The retention-only amendment records the exact compact packet bytes as base64 on
every successful row, verifies their compact round-trip, charged length and digest,
and rejects packet content on every unsuccessful row. It changes no consumer cost
or other frozen measurement field. A focused independent review and fresh owner
reservation are required before an auditable remeasurement.

That review passed, and the reserved packet-retaining attempt completed all 88
rows without an oracle or boundary failure. All 64 successful rows retain 692,470
exact compact packet bytes, with matching charged lengths and digests; all 24
expected refusals remain packet-free and charge zero. The independently
recomputable result repeats the 42,427-token best-non-control total (8.629% below
the 46,434 control) and the 42,136 achievable total when cheaper controls are kept
(9.256% below). The result is pending final independent evidence audit and owner
decision.

Before methodology approval, run only the preflight and focused pure tests, with
fixture hash checks immediately before and after:

```powershell
python -I scripts/verify_fixture_hashes.py
python -I scripts/measure_stage_a.py preflight
python -I -m unittest discover -s tests -p test_stage_a.py
python -I scripts/verify_fixture_hashes.py
```

After independent methodology review, pass the exact predeclaration SHA-256 shown
by `preflight` to the gated command:

```powershell
python -I scripts/measure_stage_a.py run --predeclaration-sha256 <sha256>
```

The command reserves and records the attempt before launch, enforces the 20-attempt
ledger, kills the spawned process tree at 600 seconds, preserves partial candidate
results, verifies the full fixture tree before and after, and refuses Stage A scratch
above its initial 250 MiB allocation. Every result reports the best non-control
query honestly, including negative savings, and the achievable best when retaining
the R2 control. Both are best only within the fixed list; neither is an upper bound
for other Librarian strategies. The 15% figure is owner context, not a pass/fail gate.
