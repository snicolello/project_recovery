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
preexisting over-cap scratch, checks a conservative generated-source bound, polls
scratch use throughout execution and terminates the complete process tree on the
250 MiB lane cap or 600-second time cap. It reserves the attempt before launch,
captures complete worker stdout and stderr, verifies fixture hashes after failures,
and records one increment against the shared 20-full-harness-run budget. The
separate existing 184-check regression is another orchestrator-counted full run.

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
