# R3 deterministic preparation evidence

This evidence covers package B of hub issue #126 at source revision
`4351301dbb9a51bbaa3c3c96cf6498c40b403045` on
`codex/126-librarian-prep`. It evaluates only deterministic proposal parsing,
abstention posture, assembly, and fresh requery validation. No model was called or
downloaded, no runtime was installed, no network inference or live GitHub verification
was performed, and no real vault was used.

## Results

| Check | Exact command | Result |
|---|---|---|
| Fixture index refresh | `python -I skills/project-recovery/scripts/recover.py refresh --manifest manifest/fixture-vault.json` | QMD 2.8.3, 9 documents, generation `qmd-2.8.3:d3096a01a1830271` |
| Dedicated offline tests | `python -I -m unittest discover -s tests -p test_librarian.py -v` | 9 passed, 0 skipped |
| Full offline unit suite | `python -I -m unittest discover -s tests` | 137 run: 134 passed, 3 skipped |
| Actual-QMD integration | `$env:PROJECT_RECOVERY_QMD_INTEGRATION='1'; python -I -m unittest discover -s tests -p test_librarian_qmd.py` | 2 passed: one positive fresh requery validation and one deliberate requery mismatch rejection |
| Fixture integrity | `python -I scripts/verify_fixture_hashes.py` immediately before and after every command above | 16/16 matched before and after every run |
| Diff hygiene | `git diff --check` plus scoped secret-term scan over the four implementation files | clean; matches were only test/docs words such as `credentials`, `token estimator`, and `max_tokens` |

The full suite was run outside the restrictive sandbox so the existing temporary Windows
junction isolation test could execute. Inside the sandbox that existing test receives
`PermissionError: [WinError 5]`; outside it, the complete suite passed. The three full-suite
skips were the two opt-in actual-QMD tests (run separately and passed) and the existing
symlink test where host permission is unavailable.

The largest observed derived `.qmd/` scratch footprint after the actual-QMD checks was
159,057 bytes, below the 250 MB work-order limit. The index and cache stayed in the
worktree's ignored `.qmd/` directory, outside every source root. The shared `qmd-runtime`
junction was read/executed but not modified.

## Existing observation

The actual-QMD run emitted Python `ResourceWarning` messages for unclosed `stdin`/`stdout`
PIPE wrappers after the existing `McpSession.close` terminated the short-lived child.
The child exited and both integration outcomes passed. This is recorded as an existing
baseline observation without inferring a resource leak or changing the shared QMD client;
the independent reviewer/owner will decide its durable disposition.

Structured results and pinned versions are in `results.json` and `versions.json`.
