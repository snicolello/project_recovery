# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Declared baseline for Project Recovery: verified current state and one safe next action.
- Status: Current. R1 accepted; R2 in review (PR open, merge held for the owner).
- As of: 2026-10-11, `main` at `50f52d0`; R2 on branch `feat/119-r2-authority` (pull request to `main`). R2 ticket: https://github.com/snicolello/stephen-project-hub/issues/119 under Epic #113.
- Authority: Stephen (owner), through rulings recorded on hub Epic https://github.com/snicolello/stephen-project-hub/issues/113. Author of this baseline: a Claude Personal session on 2026-10-11; approver: the owner, at the R0 gate on the Epic.
- Sources: hub Epic #113 (rulings 1 to 9 and the release roadmap, 2026-10-10); `docs/discovery/*` (Astra Phase 0 brief, acceptance criteria and gap list, 2026-10-10); `evidence/scoped-evaluation-2026-10-10/` (executed tool runs, Basic Memory 0.23.2 and QMD 2.8.3).
- Objective: close R2 (authority and freshness) per hub #119, including owner ruling B: frontmatter-accepted notes are `decision_candidates`; `accepted_decisions` only on verified GitHub evidence.
- Next action: independent review of the R2 pull request (orchestrator), then owner merge and the R2 gate on Epic #113. R3 does not start before that gate.
- Read when:
  - `PROJECT.md`: checking identity, outcome, trust zone or boundaries.
  - `docs/recovery-contract.md`: implementing or reviewing any release; it is the product contract.
  - `fixtures/scenario-plan.json` and `fixtures/synthetic-vault/`: writing or running scenarios.
  - `skills/project-recovery/SKILL.md` and `docs/quickstart.md`: running or reviewing the recipe, the authority policy, the tokenizer check and the project_recovery #2 resolutions; `scripts/run_scenarios.py` scores every gate (S1 to S8, offline).
  - `docs/discovery/gap-list-2026-10-10.md`: understanding why the project builds a verification layer and not a retrieval engine.
  - `evidence/scoped-evaluation-2026-10-10/README.md`: reproducing the hand trial.

## Current baseline

Release R0 content and release R1 (`manifest/`, `skills/project-recovery/` with pinned QMD lockfile and stdlib Python scripts, `scripts/run_scenarios.py`, unit tests, `docs/quickstart.md`) are on `main`. R2, in review on `feat/119-r2-authority`: `authority.py` (serial verifier with offline, snapshot and gh transports), the manifest authority policy, `decision_candidates` versus verified `accepted_decisions`, a freshness re-check after assembly, seven Cobalt fixture notes and four synthetic GitHub snapshots, scenarios S6 to S8, 119 offline gate checks and 71 unit tests, remediated after independent review (records bound to the citing note). The contract is unchanged. No Librarian code exists.

## Completed

- 2026-10-10: Phase 0 discovery (Astra, Codex) and the one-day hand trial of Basic Memory and QMD; consolidated into hub Epic #113 with nine owner rulings. Hub #64 closed as absorbed; hub #17 item (4) repointed.
- 2026-10-11: R2 implemented and submitted for review (hub #119); project_recovery #2 items 1 to 4 resolved (see `skills/project-recovery/SKILL.md`).
- 2026-10-11: R1 merged `22bcaa7` (PR #1); gate recorded on hub Epic #113.
- 2026-10-11: repository scaffolded under the project-onboarding skill; Apache-2.0 licence; Astra outputs imported with workspace paths scrubbed.

## Pending

- R2: independent review, owner merge, gate on Epic #113 (hub #119).
- https://github.com/snicolello/project_recovery/issues/2: resolutions in the R2 pull request; closing is the orchestrator's call after merge.

## Deferred

- R3 Librarian, R4 vault pilot, R5 public v1.0: each behind its predecessor's gate on Epic #113.
- Comparative 40-case benchmark: cancelled under ruling 3; re-entry only if a later release gate cannot be decided without it.

## Blocked

- None.

## Evidence

- Hub Epic #113 and its ruling comments; hub PR #114 (STATE.md routing).
- `evidence/scoped-evaluation-2026-10-10/evidence-verification.json`: twenty artifact consistency checks, all true, from the hand trial.
- `fixtures/synthetic-vault-hashes.json`: SHA-256 of the nine fixture notes.
- R1: https://github.com/snicolello/project_recovery/pull/1 (merged `22bcaa7`; `scripts/run_scenarios.py` gate output, review remediation, completion view on hub #118).
