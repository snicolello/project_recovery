# Quickstart (draft, release R1, Windows)

Reproduce the R1 result: recover the synthetic Atlas and Beacon projects through QMD and pass scenarios S1 to S5. About ten minutes on Windows. Linux instructions arrive with release R5.

Everything stays inside the clone. QMD is installed into the git-ignored `qmd-runtime/`; its index lives in the git-ignored `.qmd/`; the S4 scenario edits a throwaway copy in the git-ignored `runtime-vaults/`. Nothing is installed globally, no hooks are added, no model is downloaded, and `fixtures/` is never written.

## 1. Prerequisites

- Windows 10 or 11.
- Git.
- Node 24 with npm (tested: Node 24.13.0, npm 11.6.2). Check with `node --version` and `npm --version`.
- Python 3.11 or later (tested: 3.11.9). Standard library only; nothing is installed with pip. Check with `python --version`.
- Network access for one step only: npm downloading the exact packages pinned in the committed lockfile.

## 2. Clone

```powershell
git clone https://github.com/snicolello/project_recovery.git
cd project_recovery
```

## 3. Confirm the fixtures are intact

```powershell
python -I scripts/verify_fixture_hashes.py
```

Expected last line: `ok 9 bad 0`.

## 4. Install QMD 2.8.3, pinned, scripts disabled

Read `skills/project-recovery/scripts/install_qmd.py` first; it is short. It copies `skills/project-recovery/qmd/package.json` and its lockfile into `qmd-runtime/` and runs `npm ci --ignore-scripts` there, with the npm cache inside that directory.

```powershell
python -I skills/project-recovery/scripts/install_qmd.py
```

Expected last line: `QMD 2.8.3 installed in qmd-runtime/ with package scripts disabled`.

## 5. Recover a project by hand

Build the index and record its generation:

```powershell
python -I skills/project-recovery/scripts/recover.py refresh --manifest manifest/fixture-vault.json
```

Expected: JSON with `"generation": "qmd-2.8.3:d3096a01a1830271"` and `"documents": 9`. The generation is derived from content, so it is the same on every machine with the same fixture bytes.

Assemble the Atlas packet:

```powershell
python -I skills/project-recovery/scripts/recover.py assemble --manifest manifest/fixture-vault.json --project atlas --query "Atlas project" --out .scratch/atlas-packet.json
```

The packet is printed and also written, as UTF-8, to `.scratch/atlas-packet.json` (git-ignored). Open it. You should see the objective, current state, blocker and next action from `atlas/Project.md`, the accepted SQLite decision labelled `local_only`, the draft PostgreSQL and superseded Redis decisions under `other_decisions`, and `unknowns` for the approver, the rollout approval and the rollout owner. Every item has a receipt. Check one by hand:

```powershell
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/atlas-packet.json
```

Expected: `"receipts_failed": 0`. Edit one `content_sha` in the file and run it again: that field becomes `unknown`, a conflict appears, and the exit code is 1.

## 6. Run all scenarios and gates

```powershell
python -I scripts/run_scenarios.py
python -I -m unittest discover -s tests
python -I scripts/verify_fixture_hashes.py
```

`run_scenarios.py` takes about 20 seconds. Its last line must be `ALL GATES PASS (60 checks; ...)` and it exits 0. It scores, for each scenario, recovery completeness, unsupported assertions, abstention, isolation, freshness and the token budget; then the S4 changed-source sequence on a copy (before edit, immediately after, after 3 seconds, after an explicit refresh); the negative tests (corrupted receipt, altered text, traversal locators, missing note, a Beacon query under Atlas scope, budget trimming); the read-only tool surface; 20 repeat runs with an index rebuild before run 11; and fixture integrity before and after. The packets it produced are in `.scratch/run_scenarios/packets/`.

The unit tests print `OK` (one symlink test is skipped when Windows does not allow unprivileged symlinks; the junction test still runs).

## 7. Clean up

Everything the run created is git-ignored and can be deleted:

```powershell
Remove-Item -Recurse -Force qmd-runtime, .qmd, .scratch, runtime-vaults
```

## Troubleshooting

- `QMD not installed`: run step 4.
- `no recorded generation`: run the `refresh` command in step 5.
- Redirecting output with `>` in Windows PowerShell 5.1 writes UTF-16, which `validate` cannot read. Use `--out` as shown.
- A packet with `"status": "incomplete"`: a note changed after the last refresh. Run `refresh` again, then `assemble`.
