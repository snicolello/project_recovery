# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Declared baseline for Project Recovery: verified current state and one safe next action.
- Status: Current
- As of: 2026-10-11, release R0 (contract and fixtures) on the initial commit.
- Authority: Stephen (owner), through rulings recorded on hub Epic https://github.com/snicolello/stephen-project-hub/issues/113. Author of this baseline: a Claude Personal session on 2026-10-11; approver: the owner, at the R0 gate on the Epic.
- Sources: hub Epic #113 (rulings 1 to 9 and the release roadmap, 2026-10-10); `docs/discovery/*` (Astra Phase 0 brief, acceptance criteria and gap list, 2026-10-10); `evidence/scoped-evaluation-2026-10-10/` (executed tool runs, Basic Memory 0.23.2 and QMD 2.8.3).
- Objective: deliver release R0, then R1 (manifest and read, refresh, assemble recipe over QMD passing the five fixture scenarios).
- Next action: owner records the R0 gate on Epic #113 (repository name approved, secret scan clean, fixtures synthetic only). Then file the R1 child ticket on the hub and start from `docs/recovery-contract.md`. Do not start R1 implementation before the R0 gate is recorded.
- Read when:
  - `PROJECT.md`: checking identity, outcome, trust zone or boundaries.
  - `docs/recovery-contract.md`: implementing or reviewing any release; it is the product contract.
  - `fixtures/scenario-plan.json` and `fixtures/synthetic-vault/`: writing or running scenarios.
  - `docs/discovery/gap-list-2026-10-10.md`: understanding why the project builds a verification layer and not a retrieval engine.
  - `evidence/scoped-evaluation-2026-10-10/README.md`: reproducing the hand trial.

## Current baseline

The repository holds release R0 content only: the contract, nine synthetic fixture notes with hashes, five scenario expectations, the Phase 0 discovery documents, and the scrubbed evidence of the one-day hand trial. No recipe, manifest, verifier or Librarian code exists yet.

## Completed

- 2026-10-10: Phase 0 discovery (Astra, Codex) and the one-day hand trial of Basic Memory and QMD; consolidated into hub Epic #113 with nine owner rulings. Hub #64 closed as absorbed; hub #17 item (4) repointed.
- 2026-10-11: repository scaffolded under the project-onboarding skill; Apache-2.0 licence; Astra outputs imported with workspace paths scrubbed.

## Pending

- R0 gate ruling on Epic #113.
- R1 recipe child ticket (filed after the R0 gate).

## Deferred

- R2 authority and freshness, R3 Librarian, R4 vault pilot, R5 public v1.0: each behind its predecessor's gate on Epic #113.
- Comparative 40-case benchmark: cancelled under ruling 3; re-entry only if a later release gate cannot be decided without it.
- Board registration of a `Project Recovery` option on the portfolio board's project field: owner adds the option; the Agent Skills board config then records its identifier.

## Blocked

- None.

## Evidence

- Hub Epic #113 and its ruling comments; hub PR #114 (STATE.md routing).
- `evidence/scoped-evaluation-2026-10-10/evidence-verification.json`: twenty artifact consistency checks, all true, from the hand trial.
- `fixtures/synthetic-vault-hashes.json`: SHA-256 of the nine fixture notes.
