# Quickstart (draft, release R2, Windows)

Reproduce the R2 result: recover the synthetic Atlas, Beacon and Cobalt projects through QMD, see a decision move from candidate to accepted only when its acceptance record is verified, and pass scenarios S1 to S8. About ten minutes on Windows. Linux instructions arrive with release R5.

Everything stays inside the clone. QMD is installed into the git-ignored `qmd-runtime/`; its index lives in the git-ignored `.qmd/`; scenarios S4, S6, S7 and S8 edit throwaway copies in the git-ignored `runtime-vaults/`. Nothing is installed globally, no hooks are added, no model is downloaded, and `fixtures/` is never written. Acceptance records are read from fixed synthetic snapshots or not at all; only the optional step 7 reads GitHub.

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

Expected last line: `ok 16 bad 0` (the nine R0 notes plus seven Cobalt notes added in R2).

## 4. Install QMD 2.8.3, pinned, scripts disabled

Read `skills/project-recovery/scripts/install_qmd.py` first; it is short. It copies `skills/project-recovery/qmd/package.json` and its lockfile into `qmd-runtime/` and runs `npm ci --ignore-scripts` there, with a throwaway npm cache in a temporary directory that is deleted afterwards.

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

The packet is printed as compact JSON (the form its token budget is counted on) and also written, as UTF-8, to `.scratch/atlas-packet.json` (git-ignored). Open it. You should see:

- `freshness.statement` naming the generation the packet was assembled from;
- the objective, current state, blocker and next action from `atlas/Project.md`;
- `accepted_decisions` `unknown`, and the SQLite decision under `decision_candidates` with `local_status` `accepted`, `authority_state` `unverified` and `verification.result` `unavailable`: the manifest's default transport is `offline`, so the acceptance record the note cites was not read, and `authority_verification.statement` says so;
- the draft PostgreSQL and superseded Redis decisions under `other_decisions`, and `unknowns` for the accepted decisions, the approver, the rollout approval and the rollout owner.

Every item has a receipt. Now read the cited record from the fixed synthetic snapshot instead:

```powershell
python -I skills/project-recovery/scripts/recover.py assemble --manifest manifest/fixture-vault.json --project atlas --query "Atlas project" --verifier snapshot --out .scratch/atlas-verified.json
```

The SQLite decision is now under `accepted_decisions`, `verified`, with `revision` `fixture-merge-a7`, a `verified_at` time and `approved_digest`: the synthetic merge commit message says `ACCEPTED: queue-decision sha256:90c16e8b...`, the SHA-256 of the note's bytes. Change one character of `atlas/Queue Decision.md` in a copy and the same record no longer accepts it (`approved_text_mismatch`). Check both packets by hand:

```powershell
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/atlas-packet.json
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/atlas-verified.json --verifier snapshot
```

Expected: `"failures": 0` for both. Run the second command without `--verifier snapshot`: offline, the accepted decision cannot be re-verified, so it is demoted to a candidate and the exit code is 1. Edit one `content_sha`, change a candidate's `authority_state` to `verified`, or change the verified `revision`, and the claim is rejected the same way.

## 6. Run all scenarios and gates

```powershell
python -I scripts/run_scenarios.py
python -I -m unittest discover -s tests
python -I scripts/verify_fixture_hashes.py
```

`run_scenarios.py` takes about 35 seconds and needs no network. Its last line must be `ALL GATES PASS (135 checks; ...)` and it exits 0. It scores, for each scenario, recovery completeness, unsupported assertions, abstention, isolation, freshness (generation stated) and the token budget; the S2 decisions offline (candidate, unverified) and through the snapshot verifier (accepted, verified); the S4 changed-source sequence on a copy; S6 edits and a refresh made while a packet is being assembled; S7 budget stress on a generated vault; S8 adversarial instructions in a Cobalt note, compared with the same vault without that note, plus replayed, unmerged, non-approver and unreadable acceptance records, an approver's acceptance comment cited by a copied template or pasted text, and an unchanged approval record against a changed decision text, a replacement note or a changed theme (each `approved_text_mismatch`), and approval text that is quoted, negated, fenced, or written by a non-approver into a pull request title or squash message; the negative tests (corrupted receipt, altered text, traversal locators, missing note, out-of-scope query, budget trimming, forged revision, hand-promoted candidate, rate-limited transport); the read-only tool surface; 20 repeat runs of eight packets with an index rebuild before run 11; and fixture integrity before and after. The packets it produced are in `.scratch/run_scenarios/packets/`.

The unit tests print `OK` (one symlink test is skipped when Windows does not allow unprivileged symlinks; the junction test still runs).

## 7. Optional: verify one record live

Not needed for any gate. If the GitHub CLI `gh` is installed and signed in, read one real acceptance record with one read-only request:

```powershell
python -I scripts/live_gh_smoke.py --reference https://github.com/snicolello/project_recovery/pull/1 --approver snicolello
```

It reads the pull request and its merge commit, one request at a time. Expected: `"result": "invalid"`, reason `approved_text_mismatch`, because that merge message names no note digest; `revision` is the merge commit and `summary.requests` is 2. Offline, or without `gh`, the result is `unavailable`. The exit code is 1 in both cases; nothing fails silently.

## 8. Clean up

Everything the run created is git-ignored and can be deleted:

```powershell
python -I -c "import os, shutil; [shutil.rmtree('\\\\?\\' + os.path.abspath(d), ignore_errors=True) for d in ('qmd-runtime', '.qmd', '.scratch', 'runtime-vaults')]"
```

The `\\?\` prefix lets Python delete `node_modules` paths longer than the classic Windows 260-character limit, which `Remove-Item` in Windows PowerShell 5.1 cannot. Then delete the clone itself the same way if you no longer need it.

## Troubleshooting

- `QMD not installed`: run step 4.
- `no recorded generation`: run the `refresh` command in step 5.
- Redirecting output with `>` in Windows PowerShell 5.1 writes UTF-16, which `validate` cannot read. Use `--out` as shown.
- A packet with `"status": "incomplete"`: a note changed after the last refresh, or during assembly. Run `refresh` again, then `assemble`.
- No accepted decisions: expected offline. Use `--verifier snapshot` for the fixtures, or `--verifier gh` for a real allowlisted repository.
