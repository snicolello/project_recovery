# Synthetic transition rehearsal

Status: advance preparation under hub issue 126. Passing this rehearsal does not accept R3, R4 or R5 and does not satisfy the R5 outside-reader, fresh-install, 15-minute criterion.

This rehearsal exercises the existing recovery product on a copied synthetic vault. It uses the existing pinned QMD 2.8.3 runtime, fixed snapshot authority records and Python standard library only. It makes no model call and no network request. It never targets a real vault.

## Consumer run

Start from the repository root with an existing QMD 2.8.3 installation produced by the reviewed installer in the quickstart. Verify the fixtures, choose a new run label and run:

```powershell
python -I scripts/verify_fixture_hashes.py
$env:PROJECT_RECOVERY_REVISION = (git rev-parse HEAD)
python -I scripts/rehearse_transition.py --run-id consumer-check-01
python -I scripts/verify_fixture_hashes.py
```

On a bash host with Python 3, use the equivalent commands:

```bash
python3 -I scripts/verify_fixture_hashes.py
export PROJECT_RECOVERY_REVISION="$(git rev-parse HEAD)"
python3 -I scripts/rehearse_transition.py --run-id consumer-check-01
python3 -I scripts/verify_fixture_hashes.py
```

Success is exit code 0 and a report whose `status` is `pass`. The retained report is `.scratch/transition-rehearsal/consumer-check-01/result.json`. It records timings, the packet digest, the exact read-only MCP tool surface, rejected mutating tool names, path-containment and hostile-configuration probes, `validate --hits requery`, and fixture/pilot hashes before and after.

Use a fresh run label for every attempt. Existing paths are never overwritten or deleted. This makes a failed run inspectable and prevents an earlier index from being mistaken for a new rehearsal.

## Isolation and read-only boundary

The run uses three disjoint roots:

- `runtime-vaults/transition-rehearsal/<run-id>/` is the copied synthetic source. Its complete file and hash set must match `fixtures/synthetic-vault-hashes.json` before and after recovery.
- `.qmd/transition-rehearsal-<run-id>/` holds QMD configuration, index and the materialized isolated cache root. QMD receives the offline and CPU-only environment already enforced by `qmd_client.py`.
- `.scratch/transition-rehearsal/<run-id>/` holds the packet, trust-root probes and result report.

The MCP session must advertise exactly `get`, `multi_get`, `query` and `status`. The rehearsal performs a normal read through real QMD and separately proves that a server advertisement containing `write` is rejected at session startup. That negative probe stubs the launch command, so it runs on a host without QMD and becomes `accepted` under deliberate allowlist widening; the rehearsal fails closed in that case. A real, un-entered `McpSession` also proves that `write`, `edit`, `move`, `delete`, `shell`, `update` and `embed` are refused before transport. Index maintenance remains a separate exact-argument allowlist limited to `collection add <absolute source> --name <safe name>` and `update`; update hooks are refused with their precise error. A dedicated state probe places both roots below `.qmd/`, then attempts to put state inside the probe vault. This isolates the vault-overlap rule from the broader state-boundary rule and requires its precise error. Parent traversal and an available symlink or Windows junction escape are rejected by the source locator boundary.

The retained result observes `index.sqlite`, `xdg-cache/` and `config/` under the run state instead of recording a literal pass. It snapshots metadata for the default `~/.cache/qmd` and `~/.config/qmd` paths before and after and fails if either changes. The report stores repository-relative run paths and metadata fingerprints; it does not publish user-profile paths or home-directory filenames.

The report also probes the bounded QMD 2.8.3 snippet-label observation from the original evaluation. A reproduced mismatch is recorded but does not fail the rehearsal: the recovery recipe never cites rendered search-snippet labels. It fetches the selected source and verifies the receipt against source bytes. An unsent upstream report is retained under `evidence/transition-rehearsal/` for owner review.

## Failure and recovery

Stop the affected transition work if the report says `failed`, if either fixture check fails, if the pilot source changes, if a path overlaps, if QMD advertises another tool, if either default home path changes, or if requery validation does not return `equal_to_rederived`. Preserve the three run paths and the console output for diagnosis. Do not reuse a partially built state directory. An operator interrupt is not converted into an ordinary failed result; `KeyboardInterrupt` propagates after the fixture-finalization block runs.

After correcting an in-scope defect, rerun with a new label and compare the two reports. If recovery would require a new dependency, access change, real-vault use, weakened check or destructive repair, leave the run stopped for owner review.

Rollback is external to the read-only recovery surface. The source fixtures are untouched, so rollback means stopping use of the candidate packet and retaining or removing only the three run-specific generated paths through an ordinary governed filesystem action. The marker `.project-recovery-state` identifies QMD-owned state, but it is not authority to delete an unknown or shared path.

## Platform bounds

The maintained-install rehearsal is an engineering preflight. It may show that the current checked-out revision works with a previously installed, pinned runtime on an available host. It does not measure clone/setup time, dependency download behavior or an outside reader's interpretation of the quickstart. Those are separate R5 release criteria and remain pending owner authorization and a fresh Windows plus Linux trial.
