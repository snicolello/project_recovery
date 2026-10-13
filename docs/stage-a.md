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
expected failure observations. They must fail closed and expose no trusted packet.
They are reported with zero consumer bytes and cannot manufacture a saving. The
stable S1-S8 cases must preserve the predeclared evidence coverage, answerable
field completeness, abstention, isolation and zero-unsupported-assertion rules.

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
