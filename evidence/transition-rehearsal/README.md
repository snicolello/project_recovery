# Transition rehearsal evidence

Status: tested advance preparation for owner review under [hub issue 126](https://github.com/snicolello/stephen-project-hub/issues/126) and the [recorded owner ruling](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6136264847). This evidence does not accept R3, R4 or R5.

## Outcome

The synthetic maintained-install rehearsal passed on Windows at implementation revision `0fad9f3109189bc366eaf6054a43106da73f8752`. It copied the 16 hash-pinned notes, built a nine-document QMD 2.8.3 index outside the source root, performed a normal MCP query/read and snapshot-verified assembly, and returned `equal_to_rederived` with zero failures under `validate --hits requery`. Fixture and pilot source hashes matched before and after.

The executable negative checks rejected parent traversal, a Windows junction escape, a derived-state path inside the source root, an update-hook configuration, a poisoned MCP advertisement containing `write`, and direct calls to seven mutating tool names. The live QMD server advertised only `get`, `multi_get`, `query` and `status`. Index, cache, copied vault and output paths were disjoint as documented in `docs/transition-rehearsal.md`.

Generated package-C scratch measured 1.25 MB after all retained attempts, excluding the pre-existing QMD runtime junction, below the lane's 250 MB cap.

## Exact commands and results

Every test or rehearsal execution was bracketed by `python -I scripts/verify_fixture_hashes.py`; each bracket reported `ok 16 bad 0`.

Final Windows rehearsal:

```powershell
python -I scripts/verify_fixture_hashes.py
$env:PROJECT_RECOVERY_REVISION = (git rev-parse HEAD)
python -I scripts/rehearse_transition.py --run-id windows-0fad9f3
python -I scripts/verify_fixture_hashes.py
```

Result: pass in 1.621 seconds: refresh 0.895, assemble 0.325, requery validation 0.318. Generation `qmd-2.8.3:d3096a01a1830271`; packet SHA-256 `c0db86a58f0396c27801273f7413663fd19e7130ffeac6124e08d399a630fdf4`. The sanitized result is `windows-result.json`; ignored run artifacts remain under the three run-specific paths named there.

Final Windows unit suite:

```powershell
python -I scripts/verify_fixture_hashes.py
python -I -m unittest discover -s tests
python -I scripts/verify_fixture_hashes.py
```

Result: 133 tests run in 17.540 seconds: 132 passed and one existing symlink-permission test skipped. The retained unittest summary is `Ran 133 tests in 17.540s` and `OK (skipped=1)`; skips are included in the run count. The existing Windows junction test and the rehearsal's explicit junction probe passed outside the restrictive sandbox. The accepted 184-check scenario harness was not run by package C because package A/root owns that shared integration run.

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

```bash
cd /mnt/c/dev/project_recovery/.scratch/overnight-transition
python3 -I scripts/verify_fixture_hashes.py
python3 -I -m unittest discover -s tests -p test_transition_rehearsal.py
python3 -I scripts/verify_fixture_hashes.py
```

Result: seven dependency-free tests passed in 0.015 seconds on WSL2 Ubuntu with Python 3.12.3. A native QMD rehearsal was not run: the available Linux Node is 22.21.0 rather than the documented Node 24 prerequisite, and no approved Linux QMD 2.8.3 installation exists. Windows results do not establish Linux behavior.

## Reproduced QMD observation

QMD 2.8.3 still reproduces the original bounded snippet-line issue. In the `Atlas queue` lexical result, the separate match field correctly reports line 9, while the rendered snippet labels the actual line 8 heading as line 10 and the actual line 9 match as line 11. The product does not rely on those labels; it fetches and validates source spans. `upstream-qmd-snippet-line-labels.md` is a prepared, unsent report. No other current QMD defect was reproduced, and nothing was submitted upstream.

## Attempts and limitations

- The first focused unit invocation used package syntax (`python -I -m unittest tests.test_transition_rehearsal`) even though `tests/` is not a package. It failed during import before running tests; surrounding fixture checks passed. Discovery syntax was used thereafter.
- The first sandboxed link probe could not create a Windows junction. The harness was corrected to record `not_available` for a denied platform probe, and the authorized outside-sandbox runs then proved the junction escape was rejected.
- A sandboxed broad unit attempt encountered the accepted suite's Windows junction permission boundary. The final outside-sandbox suite passed. These environment failures are not product failures and are retained here rather than hidden.
- Another work package observed baseline `ResourceWarning` messages for unclosed subprocess pipes. Package C's standard outputs did not emit that warning, and no concrete impact appeared in this rehearsal, so accepted core code was not changed. The orchestrator should retain it as a baseline observation for any later focused diagnosis.
- This was a maintained-install engineering rehearsal by the implementation agent. It was not a fresh clone, fresh dependency install or outside-reader trial and therefore does not satisfy the R5 15-minute Windows-and-Linux usability criterion.

## Recovery

On a failed run, preserve its three run-specific paths, stop use of its packet and diagnose from `result.json`. Rerun with a fresh label after an in-scope correction. Deleting retained generated paths is an ordinary governed filesystem action outside the recovery surface; the rehearsal itself exposes no cleanup or source mutation capability.
