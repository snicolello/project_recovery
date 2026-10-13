# Reliance gate evidence (project_recovery #6), 2026-10-12

## Structural-diagnostic allocation remediation

Code revision `71e251d`, against the reviewed head `603b6c3`. The earlier matrix in
`results.json` remains a historical run at `fc2ffa9`; the separate
`allocation-results.json` records this remediation's before/after measurements,
source hashes and failing-before regression proof. `versions.json` records the
existing runtimes used; no dependency was installed.

The structural checker used to accumulate all problems before applying its
100-problem reporting cap. It now stops nested traversal upon discovering the
101st problem, retaining the first 100 in order and one truncation marker. That
marker does not claim a count for errors the checker no longer visits. Below or
exactly at the cap, diagnostics are unchanged.

| Safe reproduction (10,000 empty hits; 30,064 bytes) | `603b6c3` | `71e251d` |
|---|---:|---:|
| Structural check, peak traced Python allocation | 17,213,118 bytes | 36,124 bytes |
| Full validate, requery stand-in | 18,051,603 bytes | 1,883,139 bytes |
| Full validate, packet mode | 18,051,603 bytes | 1,882,970 bytes |
| Result in both modes | rejected | rejected |

`test_structural_limits.py` adds five tests: 99/100/101-problem boundaries;
nested object/map traversal stops; a 10,000-empty-hit memory and traversal
regression; an honest assembled packet; and rejection in both validation modes.
The memory regression fails on the exact old `shape.py` loaded as a separate
in-memory module (17,212,526 bytes against a 1,000,000-byte ceiling), and all five
tests pass with the fix. Parsing and other ordinary processing still scale with
input size; these measurements concern diagnostic amplification, not a constant
whole-process memory guarantee. No test approached the 4 MB input allowance.

Reproduce the measurements against the old export and the fixed checkout:

```powershell
python -I evidence/reliance-gate-2026-10-12/allocation_repro.py --code-root PATH_TO_603b6c3
python -I evidence/reliance-gate-2026-10-12/allocation_repro.py
python -I -m unittest discover -s tests -p test_structural_limits.py
```

Validation of the code at `71e251d`: 126 unit tests ran with no failures or errors
and one symlink-permission skip; the existing Windows junction check passed
outside the restrictive sandbox. All 184 actual-QMD scenario checks passed,
including 20 repeat runs and an index rebuild. The existing isolated QMD 2.8.3
runtime was reused, while all indexes and generated synthetic copies remained in
the remediation worktree. Fixture hashes matched 16/16 before and after, and the
entire 44-file fixture tree was unchanged. The product contract and `STATE.md`
are unchanged; no release gate moved.

A separate agent session, not the implementation author, independently reviewed
`603b6c3..71e251d`, reran the five focused tests and the fixed-code reproduction,
and found no defects within that focused scope. PR #8 and issue #6 remain pending
owner acceptance. The bounded-traversal fix does not alter the documented packet
mode or trust-root limitations below.

## Earlier reliance-gate matrix

`results.json` records each reproducing case in `tests/reliance_cases.py` run three ways:

- `before`: the R2 validator at the base revision `5ab0ea2`;
- `after_packet_mode`: this revision's `recover.py validate --hits packet`;
- `after_requery`: this revision's validator in requery mode, through the API, with a vault-backed stand-in that returns the hits the packet was assembled from. The scenario gates (`scripts/run_scenarios.py`, gate `reliance`) run requery through QMD itself.

All packets are synthetic. They are built by the deterministic assembler in a throwaway copy of `fixtures/synthetic-vault/`, with one borrow-path note (`Quote Decision`) added so that a verified decision and a conflict sit side by side. `fixtures/` is not written.

Reproduce, from this repository, with a clean checkout of the base revision at `PATH`:

```powershell
python -I evidence/reliance-gate-2026-10-12/before_after.py --before-repo PATH
```

## Result at the time of recording

Base `5ab0ea2`; this revision `fc2ffa9`, the code commit after the fourth review and its two focused re-checks. `results.json` records both. It was regenerated at `fc2ffa9`; earlier runs of this file (at `a76abda`, `bc791ee`, `5ae8a9b`, `91adf78` and `ef1c962`) are history in git and do not validate this head.

| | Count | Cases |
|---|---|---|
| Edited cases the base validator passed with 0 failures | 38 of 54 (10 flagged, 6 crashed) | F1-a to c, e to i, k; F2-a to j (including f2); M-02 to 05, 08, 11, 12, 14 to 16, 21 to 25, 27, 29, 30 |
| Inputs that crashed the base validator | 6 | M-01 (byte-order mark), M-13 (deep nesting), M-18 (truncated output), M-26 (5,000-digit integer), M-28 (lone surrogate), M-31 (500-level nesting) |
| Base validator flagged, but kept a `verified` entry with no items | 1 | F3-a |
| Cases with an unexpected result after the fix | 0 | |
| Unedited assembled packets that fail after the fix | 0 of 5 | controls, both modes |

Stated limits of packet mode (no QMD). Each is accepted in packet mode, rejected under requery, and named in the result's `guarantee.not_established`:

- F2-f, a zeroed omitted-hit count;
- F2-j, a deleted hit;
- M-14, a rewritten hit title;
- a deleted trace of an omitted hit: a `missing_sources` entry (scenario gate, S1) or a "hit could not be cited" unknown (`tests/test_reliance_gate.py`, R2).

A packet whose query dropped out-of-scope results is rejected in packet mode and validated with requery.

## Fourth review (of `efcc4e7`) and its focused re-checks (of `1fd34de` and `f159446`)

`round4_repro.py --code-root PATH` reproduces both fourth-review findings without large allocations. The oversized rank is 100,000, the value the review named.

| Finding | Before | `fc2ffa9` |
|---|---|---|
| F4-1, a 15,023-byte packet with hit rank 100,000 (search limit 10) | On `efcc4e7` (`git archive` export), the packet-mode replay built **100,000 entries**, about **19.2 MB** peak; requery mode does not replay. Both modes still ended `rejected`. | **0 replay entries**, 328 bytes peak; `rank_exceeds_search_limit`, rejected in both modes |
| F4-2, a 5,000-digit integer in `budget.tokens` | On `efcc4e7`, `ValueError` escaped validate in both modes | `not_rederivable` (`unparseable`), no packet returned, in both modes; the CLI exits 1 with JSON output and no traceback |
| Follow-up: a lone surrogate (`"\ud800"`) | On `1fd34de`, `UnicodeEncodeError` escaped validate in both modes; the CLI printed a traceback and no JSON | `not_rederivable` (`unparseable`) in both modes; the CLI exits 1 with JSON output and no traceback |
| Follow-up: a 4,300-digit omitted-hit count with `budget.limit` 1 | On `1fd34de`, `ValueError` escaped packet mode once trimming added 1 | rejected in both modes (counts bounded to 10^15) |
| Follow-up: `1e400` (an infinite number) | On `1fd34de`, parsed as infinity, then rejected as a wrong type | `not_rederivable` (`unparseable`) in both modes |
| Re-check of `f159446`: nesting 495 to 994 levels | On `f159446`, `RecursionError` escaped validate and the CLI in both modes | `not_rederivable` (`unparseable`, more than 64 levels) in both modes; the CLI exits 1 with JSON output |
| Re-check of `f159446`: `assemble --max-tokens` above 10^15 | On `f159446`, assemble produced a packet validate refuses | `assemble` exits 2 for a limit outside 1 to 10^15 |

Regressions and where they fail before their fix:

- `FourthReviewTests.test_f4_1_oversized_rank...` fails on the `efcc4e7` code. In packet mode it fails on peak memory (19.4 MB against a 4 MB ceiling); in requery mode, on the problem kind.
- `FourthReviewTests.test_f4_2...` and case M-26 fail on the `efcc4e7` code.
- `FourthReviewFollowUpTests` and cases M-28 to M-30 fail on the `91adf78` code.
- `NestingAndLimitTests` (nesting) and case M-31 fail on the `ef1c962` code.
- All of them pass at `fc2ffa9`. The `assemble` limit test covers new behaviour and was not run on the old code, which would start QMD.
- Case M-27 (rank 100,000) is a catalog case, not a before/after regression: the `efcc4e7` validator also ended `rejected`, after the allocation.
- The test that uses rank 10^15 runs only against the fixed code, because before the fix it would exhaust memory.
