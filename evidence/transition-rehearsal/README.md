# Transition rehearsal evidence

Status: tested advance preparation for owner review under [hub issue 126](https://github.com/snicolello/stephen-project-hub/issues/126) and the [current owner ruling](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6145720151). This evidence does not accept R3, R4 or R5.

## Outcome

The single authorized synthetic maintained-install rehearsal passed on Windows at implementation revision `fe9031f109bfe9f6aecfc2b4b1e1d75d57fc0840`. It copied the 16 hash-pinned notes, built a nine-document QMD 2.8.3 index outside the source root, performed a normal MCP query/read and snapshot-verified assembly, and returned `equal_to_rederived` with zero failures under `validate --hits requery`. Fixture and pilot source hashes matched before and after.

The executable negative checks rejected parent traversal, a Windows junction escape, a derived-state path inside the source root with the exact vault-overlap error, an update-hook configuration with its exact error, a poisoned MCP advertisement containing `write`, and direct calls to seven mutating tool names through a real un-entered `McpSession`. The live QMD server advertised only `get`, `multi_get`, `query` and `status`. The raw result observes the index, cache and configuration below isolated state and shows that default `~/.cache/qmd` and `~/.config/qmd` were absent and unchanged. All retained paths are repository-relative.

Generated package-C scratch measured 3.16 MB decimal after all retained attempts, excluding the pre-existing QMD runtime junction, below the lane's 250 MB cap.

## Exact commands and results

Every test or rehearsal execution was bracketed by `python -I scripts/verify_fixture_hashes.py`; each bracket reported `ok 16 bad 0`.

Final Windows rehearsal:

```powershell
python -I scripts/verify_fixture_hashes.py
$env:PROJECT_RECOVERY_REVISION = 'fe9031f109bfe9f6aecfc2b4b1e1d75d57fc0840'
python -I scripts/rehearse_transition.py --run-id windows-fe9031f
python -I scripts/verify_fixture_hashes.py
```

Result: pass in 1.797 seconds: refresh 0.903, assemble 0.462, requery validation 0.349. Generation `qmd-2.8.3:d3096a01a1830271`; packet SHA-256 `9a047f642aa00d7e6310ea83c6c33f260b14bd8f5b72572af856ba059aae143e`. `windows-fe9031f-result.json` retains the raw result fields and relative provenance, with line endings normalized for Git (SHA-256 `8aad1a9ab9ac1c22b1c9723eff5876af684c973a9667e246a5aa4fc86391da77`); ignored run artifacts remain under the relative run-specific paths named there. The earlier handwritten `windows-result.json` was retired.

Final Windows unit suite:

```powershell
python -I scripts/verify_fixture_hashes.py
python -I -m unittest discover -s tests
python -I scripts/verify_fixture_hashes.py
```

Result: 140 tests run in 20.678 seconds: 139 passed and one existing symlink-permission test skipped. The retained unittest summary is `Ran 140 tests in 20.678s` and `OK (skipped=1)`; skips are included in the run count. The existing Windows junction test and the rehearsal's explicit junction probe passed outside the restrictive sandbox. The accepted 184-check scenario harness was not run by package C because package A/root owns that shared integration run.

Maintained-install quickstart exercise, using the prose commands in `docs/quickstart.md` and its existing QMD installation:

```powershell
python -I scripts/verify_fixture_hashes.py
python -I skills/project-recovery/scripts/recover.py refresh --manifest manifest/fixture-vault.json
python -I skills/project-recovery/scripts/recover.py assemble --manifest manifest/fixture-vault.json --project atlas --query "Atlas project" --out .scratch/quickstart-maintained/atlas-packet.json
python -I skills/project-recovery/scripts/recover.py assemble --manifest manifest/fixture-vault.json --project atlas --query "Atlas project" --verifier snapshot --out .scratch/quickstart-maintained/atlas-verified.json
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/quickstart-maintained/atlas-packet.json
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/quickstart-maintained/atlas-verified.json --verifier snapshot
python -I scripts/verify_fixture_hashes.py
```

Result: both validations returned `equal_to_rederived` with zero failures. The five product operations took 4.403 seconds total. The installer step was intentionally not executed: issue 126 forbids new setup, and the worktree reused the existing pinned, immutable QMD 2.8.3 runtime. No concrete quickstart defect was observed, so `docs/quickstart.md` was not changed.

Available Ubuntu checks:

From the repository root on the available WSL host:

```bash
python3 -I scripts/verify_fixture_hashes.py
python3 -I -m unittest discover -s tests
python3 -I scripts/verify_fixture_hashes.py
```

Result: the complete 140-test suite passed in 17.652 seconds on WSL2 Ubuntu with Python 3.12.3: 139 passed and one existing symlink-permission test skipped. The suite ran from a `git archive` of exact revision `fe9031f109bfe9f6aecfc2b4b1e1d75d57fc0840`; the archive had no `qmd-runtime`, and `qmd` was absent from the host path. Fixture hashes were 16/16 before and after. A native QMD rehearsal was not run: the available Linux host has no approved native QMD 2.8.3 installation. Windows results do not establish Linux QMD behavior.

## Reproduced QMD observation

QMD 2.8.3 still reproduces the original bounded snippet-line issue. In the `Atlas queue` lexical result, the separate match field correctly reports line 9, while the rendered snippet labels the actual line 8 heading as line 10 and the actual line 9 match as line 11. The product does not rely on those labels; it fetches and validates source spans. `upstream-qmd-snippet-line-labels.md` is a prepared, unsent report. No other current QMD defect was reproduced, and nothing was submitted upstream.

## Attempts and limitations

- The first focused unit invocation used package syntax (`python -I -m unittest tests.test_transition_rehearsal`) even though `tests/` is not a package. It failed during import before running tests; surrounding fixture checks passed. Discovery syntax was used thereafter.
- The first sandboxed link probe could not create a Windows junction. The harness was corrected to record `not_available` for a denied platform probe, and the authorized outside-sandbox runs then proved the junction escape was rejected.
- A sandboxed full Windows suite reached all 140 tests in 295.953 seconds but ended with `PermissionError: [WinError 5] Access is denied` when the existing junction-escape test attempted to create its temporary junction; one existing test was skipped. Fixture checks were 16/16 before and after. The justified outside-sandbox rerun passed all runnable tests in 20.678 seconds.
- Initial WSL inspection was denied by the Windows sandbox. Authorized read-only WSL access then confirmed Ubuntu, Python 3.12.3 and no `qmd` command. The committed source was extracted to a new bounded scratch path and the full no-QMD suite passed; no Linux setup or installation occurred.
- The baseline `ResourceWarning` has a source-confirmed unclosed-log-handle cause when `McpSession.__enter__` fails before entering its cleanup block. It is recorded as [Project Recovery issue 14](https://github.com/snicolello/project_recovery/issues/14) for WP7; accepted core code is outside this package and was not changed.
- This was a maintained-install engineering rehearsal by a separate Codex agent session. It was not a fresh clone, fresh dependency install or outside-reader trial and therefore does not satisfy the R5 15-minute Windows-and-Linux usability criterion.

## Recovery

On a failed run, preserve its three run-specific paths, stop use of its packet and diagnose from `result.json`. Rerun with a fresh label after an in-scope correction. Deleting retained generated paths is an ordinary governed filesystem action outside the recovery surface; the rehearsal itself exposes no cleanup or source mutation capability.
