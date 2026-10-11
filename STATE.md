# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Declared baseline for Project Recovery: verified current state and one safe next action.
- Status: R1 in review. Recipe implemented on branch `feat/118-r1-recipe`; all scenario gates pass; merge held for the owner.
- As of: 2026-10-11, release R1 (manifest and read, refresh, assemble recipe over QMD), hub ticket https://github.com/snicolello/stephen-project-hub/issues/118 under work order #117.
- Authority: Stephen (owner), through rulings recorded on hub Epic https://github.com/snicolello/stephen-project-hub/issues/113. Author of this baseline: a Claude Personal session on 2026-10-11; approver: the owner, at the R0 gate on the Epic.
- Sources: hub Epic #113 (rulings 1 to 9 and the release roadmap, 2026-10-10); `docs/discovery/*` (Astra Phase 0 brief, acceptance criteria and gap list, 2026-10-10); `evidence/scoped-evaluation-2026-10-10/` (executed tool runs, Basic Memory 0.23.2 and QMD 2.8.3).
- Objective: land release R1: a manifest and a read-only read, refresh, assemble recipe over pinned QMD 2.8.3 (lexical only) that passes scenarios S1 to S5 with zero unsupported assertions, shipped as the `skills/project-recovery/` agent skill.
- Next action: owner reviews the R1 pull request (independent review, personal-mvp scrutiny) and records the R1 gate on Epic #113. Do not start R2 (authority and freshness) before that gate is recorded.
- Read when:
  - `PROJECT.md`: checking identity, outcome, trust zone or boundaries.
  - `docs/recovery-contract.md`: implementing or reviewing any release; it is the product contract.
  - `fixtures/scenario-plan.json` and `fixtures/synthetic-vault/`: writing or running scenarios.
  - `skills/project-recovery/SKILL.md` and `docs/quickstart.md`: running or reviewing the R1 recipe; `scripts/run_scenarios.py` scores every gate.
  - `docs/discovery/gap-list-2026-10-10.md`: understanding why the project builds a verification layer and not a retrieval engine.
  - `evidence/scoped-evaluation-2026-10-10/README.md`: reproducing the hand trial.

## Current baseline

Release R0 content (contract, nine synthetic fixture notes with hashes, five scenario expectations, discovery documents, hand-trial evidence) is on `main`. Release R1 is proposed on `feat/118-r1-recipe`: `manifest/` (schema, fixture-vault manifest, pinned versions), `skills/project-recovery/` (SKILL.md, pinned QMD lockfile, stdlib Python scripts for install, refresh, query, fetch, assemble and validate), `scripts/run_scenarios.py`, unit tests and `docs/quickstart.md`. Every decision is labelled `local_only`; GitHub verification is R2. No Librarian code exists.

## Completed

- 2026-10-10: Phase 0 discovery (Astra, Codex) and the one-day hand trial of Basic Memory and QMD; consolidated into hub Epic #113 with nine owner rulings. Hub #64 closed as absorbed; hub #17 item (4) repointed.
- 2026-10-11: repository scaffolded under the project-onboarding skill; Apache-2.0 licence; Astra outputs imported with workspace paths scrubbed.

## Pending

- R1 pull request review and the R1 gate ruling on Epic #113 (R0 gate approved by the owner on 2026-10-11).

## Deferred

- R2 authority and freshness, R3 Librarian, R4 vault pilot, R5 public v1.0: each behind its predecessor's gate on Epic #113.
- Comparative 40-case benchmark: cancelled under ruling 3; re-entry only if a later release gate cannot be decided without it.

## Blocked

- None.

## Evidence

- Hub Epic #113 and its ruling comments; hub PR #114 (STATE.md routing).
- `evidence/scoped-evaluation-2026-10-10/evidence-verification.json`: twenty artifact consistency checks, all true, from the hand trial.
- `fixtures/synthetic-vault-hashes.json`: SHA-256 of the nine fixture notes.
