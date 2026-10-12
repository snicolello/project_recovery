# Reliance gate evidence (project_recovery #6), 2026-10-12

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

Base `5ab0ea2`; this revision `91adf78`, the code commit after the fourth review's remediation. `results.json` records both. It was regenerated at `91adf78`; earlier runs of this file (at `a76abda`, `bc791ee` and `5ae8a9b`) are history in git and do not validate this head.

| | Count | Cases |
|---|---|---|
| Edited cases the base validator passed with 0 failures | 36 of 50 (10 flagged, 4 crashed) | F1-a to c, e to i, k; F2-a to j (including f2); M-02 to 05, 08, 11, 12, 14 to 16, 21 to 25, 27 |
| Inputs that crashed the base validator | 4 | M-01 (byte-order mark), M-13 (deep nesting), M-18 (truncated output), M-26 (5,000-digit integer) |
| Base validator flagged, but kept a `verified` entry with no items | 1 | F3-a |
| Cases with an unexpected result after the fix | 0 | |
| Unedited assembled packets that fail after the fix | 0 of 5 | controls, both modes |

Stated limits of packet mode (no QMD). Each is accepted in packet mode, rejected under requery, and named in the result's `guarantee.not_established`:

- F2-f, a zeroed omitted-hit count;
- F2-j, a deleted hit;
- M-14, a rewritten hit title;
- a deleted trace of an omitted hit: a `missing_sources` entry (scenario gate, S1) or a "hit could not be cited" unknown (`tests/test_reliance_gate.py`, R2).

A packet whose query dropped out-of-scope results is rejected in packet mode and validated with requery.

## Fourth review (of `efcc4e7`): `round4_repro.py`

`round4_repro.py --code-root PATH` reproduces both findings without large allocations. The oversized rank is 100,000, the value the review named.

| Finding | `efcc4e7` (`git archive` export) | `91adf78` |
|---|---|---|
| F4-1, a 15,023-byte packet with hit rank 100,000 (search limit 10) | the packet-mode replay built **100,000 entries**, about **19.2 MB** peak; validate rejected the packet in both modes only after that allocation | **0 replay entries**, 328 bytes peak; `rank_exceeds_search_limit`, rejected in both modes |
| F4-2, a 5,000-digit integer in `budget.tokens` | `ValueError` escaped validate in both modes | `not_rederivable` (`unparseable`), no packet returned, in both modes; the CLI exits 1 with JSON output and no traceback |

The regressions (`FourthReviewTests`, cases M-26 and M-27) fail on the `efcc4e7` code and pass at `91adf78`. The test that uses rank 10^15 runs only against the fixed code, because before the fix it would exhaust memory.
