# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Declared baseline for Project Recovery: verified current state and one safe next action.
- Status: Current. R2 accepted; reliance gate #6 accepted and closed; R3 not started.
- As of: 2026-10-12 (owner's time zone), `main` at `fe6b4fb` (PR #8 merged by the owner), plus this documentation update.
- Authority: Stephen (owner), through rulings recorded on hub Epic https://github.com/snicolello/stephen-project-hub/issues/113. The owner's “Approved and Merged, great work” acceptance of PR #8 is [recorded here](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6136063604).
- Sources: Epic #113 and its rulings; the [#6 acceptance record](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136067672); merged PRs #1, #5 and #8; `evidence/reliance-gate-2026-10-12/`.
- Objective: hold the accepted R2 baseline and the completed reliance gate until the owner opens R3 on Epic #113.
- Next action: await a separate owner ruling on the [R3 decision packet](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6130175603). Neither proposed stage nor the proposed 15% threshold is approved. Closing #6 does not start R3.
- Read when:
  - `PROJECT.md`: checking identity, outcome, trust zone or boundaries.
  - `docs/recovery-contract.md`: implementing or reviewing any release; it is the product contract.
  - `fixtures/scenario-plan.json` and `fixtures/synthetic-vault/`: writing or running scenarios.
  - `skills/project-recovery/SKILL.md` and `docs/quickstart.md`: running the recipe or checking validation guarantees and limits; `scripts/run_scenarios.py` scores S1 to S8.
  - `docs/discovery/gap-list-2026-10-10.md` and `evidence/scoped-evaluation-2026-10-10/README.md`: understanding the verification layer and the original hand trial.

## Current baseline

R0, R1 and R2 are on `main`: the recovery contract, synthetic fixtures, manifest, pinned QMD recipe, deterministic assembler, serial GitHub authority verification and freshness checks. The recovery path is read-only. Fixtures remain synthetic; no real vault or Work-zone material is authorized. The product contract is unchanged. No Librarian code exists.

PR #8 adds the accepted #6 reliance gate. Received packets must pass an explicit structural allowlist and equal-checks against fresh deterministic re-derivation, apart from the documented wall-clock fields. The default `validate --hits requery` obtains hits through QMD; `--hits packet` reconstructs from the packet's hit claims and has narrower guarantees. A consumer uses the returned re-derived packet only after successful validation.

The final allocation fix stops structural traversal on discovery of the 101st problem, retaining the first 100 diagnostics in order plus a truncation marker. This bounds diagnostic amplification; parsing and other processing still scale with input size. Counts, ranks, limits and token figures above 10^15, nesting deeper than 64 levels, and input beyond the documented 4 MB allowance are rejected.

**Acceptance and remaining limits.** The [bounded R2 ruling](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6127542754) accepted assembler-produced packets and preserved F1 to F3 as temporary exceptions. Those findings are now addressed by the accepted #6 implementation and its explicit guarantees; they are no longer an open reliance gate. This does not make packet mode equivalent to requery: hit selection, order, titles and omitted-hit count remain packet claims, and deleted traces of omitted hits are not detected. Packet mode rejects packets whose query dropped out-of-scope results and requires requery. Wall-clock fields are checked for presence and format. Vault bytes, snapshot files and approvers' GitHub accounts remain trust roots; validation does not establish submitter provenance. These limits are documented in the skill and quickstart and still apply to any future R3 design.

## Completed

- 2026-10-12: reliance gate [#6](https://github.com/snicolello/project_recovery/issues/6) accepted and closed after owner merge of [PR #8](https://github.com/snicolello/project_recovery/pull/8) at `fe6b4fb`; acceptance recorded on Epic #113. The merged tree is identical to reviewed head `eb7380b` (allocation code `71e251d`).
- 2026-10-12: R2 merged `0b11a91` (PR #5) under the owner's bounded acceptance ruling; gate recorded on Epic #113; hub #119 closed. PR #7 recorded the post-R2 baseline.
- 2026-10-11: R1 merged `22bcaa7` (PR #1); gate recorded on Epic #113. project_recovery #2 items 1 to 4 were resolved and the issue closed after R2.
- 2026-10-11: repository scaffolded with Apache-2.0 licence; discovery outputs imported with workspace paths scrubbed.
- 2026-10-10: Phase 0 discovery and the hand trial of Basic Memory and QMD consolidated into Epic #113 with nine owner rulings. Hub #64 closed as absorbed; hub #17 item (4) repointed.

## Pending

- Owner ruling on the R3 decision packet. Approval of PR #8 completes a prerequisite only; no R3 implementation, model call or new dependency is authorized.

## Deferred

- R3 Librarian, R4 vault pilot, R5 public v1.0: each needs its applicable owner ruling on Epic #113.
- Comparative 40-case benchmark: cancelled under ruling 3; re-entry only if a later release gate cannot be decided without it.

## Blocked

- No unresolved implementation defect in the completed allocation remediation. R3 awaits authorization as above.

## Evidence

- [Final #6 completion evidence](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136010028): 126 unit tests run, 125 passed and one symlink-permission skip; 184/184 actual-QMD scenario checks, including 20 repeat runs and index rebuild. The Windows junction check passed outside the restrictive sandbox. These checks apply to the merged code because its tree equals reviewed head `eb7380b`.
- `evidence/reliance-gate-2026-10-12/allocation-results.json`, `allocation_repro.py` and `versions.json`: reproducible before/after evidence and existing pinned runtimes. The 10,000-empty-hit input reduced structural peak traced Python allocation from 17,213,118 to 36,124 bytes; full validation remained rejecting in both modes. Measurements use `tracemalloc`, not process RSS, and did not approach the 4 MB allowance.
- Independent focused review of `603b6c3..71e251d` by a separate agent session: no remaining allocation finding; five focused tests and reproduction rerun. Earlier reliance-gate review history and its limits remain on PR #8 and issue #6.
- `fixtures/synthetic-vault-hashes.json`: 16/16 SHA-256 hashes matched before and after remediation; the entire 44-file fixture tree and product contract were unchanged.
- Historical evidence: `evidence/reliance-gate-2026-10-12/results.json` records the earlier matrix at `fc2ffa9`, not the final allocation run. R2 acceptance evidence at `bc6b8d5` (90 tests, 147 scenario checks) is on PR #5 and hub #119. The hand-trial consistency checks remain in `evidence/scoped-evaluation-2026-10-10/evidence-verification.json`.
