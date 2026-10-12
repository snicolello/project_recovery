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

| | Count | Cases |
|---|---|---|
| Edits the base validator passed with 0 failures | 30 of 46 | F1-a to c, e to i, k; F2-a to j (including f2); M-02 to 05, 08, 11, 12, 14 to 16 |
| Inputs that crashed the base validator | 3 | M-01 (byte-order mark), M-13 (deep nesting), M-18 (truncated output) |
| Base validator flagged, but kept a `verified` entry with no items | 1 | F3-a |
| Cases with an unexpected result after the fix | 0 | |
| Unedited assembled packets that fail after the fix | 0 of 5 | controls, both modes |

Stated limits of packet mode (no QMD), each accepted there and rejected under requery: F2-f (zeroed omitted-hit count), F2-j (a deleted hit) and M-14 (a hit title rewritten). The result's `guarantee.not_established` names them. The scenario gate also records the fourth limit, a `missing_sources` entry deleted when its only linking hit was trimmed (S1).
