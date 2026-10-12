# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Declared baseline for Project Recovery: verified current state and one safe next action.
- Status: Current. R1 accepted; R2 under the owner's bounded acceptance ruling of 2026-10-12 (PR #5 open, awaiting the owner's merge decision).
- As of: 2026-10-12, `main` at `6863db9` (PR #4, outcome ledger); R2 on branch `feat/119-r2-authority`, rebased onto it (pull request #5 to `main`), reviewed at `d2c94a1` plus this documentation revision. R2 ticket: https://github.com/snicolello/stephen-project-hub/issues/119 under Epic #113.
- Authority: Stephen (owner), through rulings recorded on hub Epic https://github.com/snicolello/stephen-project-hub/issues/113. Author of this baseline: a Claude Personal session on 2026-10-11; approver: the owner, at the R0 gate on the Epic.
- Sources: hub Epic #113 (rulings 1 to 9 and the release roadmap, 2026-10-10); `docs/discovery/*` (Astra Phase 0 brief, acceptance criteria and gap list, 2026-10-10); `evidence/scoped-evaluation-2026-10-10/` (executed tool runs, Basic Memory 0.23.2 and QMD 2.8.3).
- Objective: close R2 (authority and freshness) per hub #119, including owner ruling B: frontmatter-accepted notes are `decision_candidates`; `accepted_decisions` only on verified GitHub evidence.
- Next action: the owner merges PR #5 or requests changes; the R2 gate is recorded on Epic #113 only after merge. R3 does not start before that gate, and R3 may not rely on model-produced packets before project_recovery #6 closes.
- Read when:
  - `PROJECT.md`: checking identity, outcome, trust zone or boundaries.
  - `docs/recovery-contract.md`: implementing or reviewing any release; it is the product contract.
  - `fixtures/scenario-plan.json` and `fixtures/synthetic-vault/`: writing or running scenarios.
  - `skills/project-recovery/SKILL.md` and `docs/quickstart.md`: running or reviewing the recipe, the authority policy, the tokenizer check and the project_recovery #2 resolutions; `scripts/run_scenarios.py` scores every gate (S1 to S8, offline).
  - `docs/discovery/gap-list-2026-10-10.md`: understanding why the project builds a verification layer and not a retrieval engine.
  - `evidence/scoped-evaluation-2026-10-10/README.md`: reproducing the hand trial.

## Current baseline

Release R0 content and release R1 (`manifest/`, `skills/project-recovery/` with pinned QMD lockfile and stdlib Python scripts, `scripts/run_scenarios.py`, unit tests, `docs/quickstart.md`) are on `main`. R2, in review on `feat/119-r2-authority`: `authority.py` (serial verifier with offline, snapshot and gh transports), the manifest authority policy, `decision_candidates` versus verified `accepted_decisions`, a freshness re-check after assembly, seven Cobalt fixture notes, seven non-indexed borrow-path notes and about twenty synthetic GitHub snapshots, scenarios S6 to S8, 147 offline gate checks and 90 unit tests, remediated after independent review (records bound to the citing note), owner review (records bound to the approved note bytes by digest) and two re-reviews (whole-line markers in approver comments or approving reviews only; baseline lines never attached; record identity normalized across projects), and a validate pass that checks the bound content under `accepted_decisions` against what assembly produces. Five independent reviews and five remediations are recorded on hub #119; assembly (vault bytes to packet) held against every probe since `64fb1a9`. The contract is unchanged. No Librarian code exists.

**R2 supported boundary (owner ruling, [hub #113](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6127542754), 2026-10-12).** R2 is accepted for synthetic fixtures using packets directly produced by the deterministic assembler. A packet modified after assembly, or produced by a model, is outside the trusted boundary: `validate` does not establish its trustworthiness or completeness. The [fifth review's](https://github.com/snicolello/stephen-project-hub/issues/119#issuecomment-6127543421) findings F1 to F3 (validate accepts hand-edited values inside a verified entry; validate does not re-assemble, so deletions are silent; an emptied entry keeps `verified` after a local-status mismatch, exit 1) are a temporary accepted exception, not resolved defects; F4 (stale title-check line) is corrected. They are preserved with their dispositions on project_recovery #6, the R3 reliance gate. A newly discovered defect inside the assembly boundary still blocks R2.

## Completed

- 2026-10-10: Phase 0 discovery (Astra, Codex) and the one-day hand trial of Basic Memory and QMD; consolidated into hub Epic #113 with nine owner rulings. Hub #64 closed as absorbed; hub #17 item (4) repointed.
- 2026-10-11: R2 implemented and submitted for review (hub #119); project_recovery #2 items 1 to 4 resolved (see `skills/project-recovery/SKILL.md`).
- 2026-10-11: R1 merged `22bcaa7` (PR #1); gate recorded on hub Epic #113.
- 2026-10-11: repository scaffolded under the project-onboarding skill; Apache-2.0 licence; Astra outputs imported with workspace paths scrubbed.

## Pending

- R2: owner merge decision on PR #5, then the gate on Epic #113 (hub #119). Merge, deletion, R3 implementation and real-vault use are not authorized by the bounded acceptance ruling.
- https://github.com/snicolello/project_recovery/issues/2: resolutions in the R2 pull request; closing is the orchestrator's call after merge.

## Deferred

- R3 Librarian, R4 vault pilot, R5 public v1.0: each behind its predecessor's gate on Epic #113.
- R3 reliance gate (project_recovery #6): before R3 relies on any model-produced packet, `validate` must enforce an exact shape allowlist on accepted entries, items and receipts, replace or equal-check the verification block against fresh re-verification, and either re-derive conflicts, unknowns and candidates from the vault or state in the skill text that it cannot detect deletions. This gate is separate from R3 planning and is not closed by the R2 gate.
- Comparative 40-case benchmark: cancelled under ruling 3; re-entry only if a later release gate cannot be decided without it.

## Blocked

- None.

## Evidence

- Hub Epic #113 and its ruling comments; hub PR #114 (STATE.md routing).
- `evidence/scoped-evaluation-2026-10-10/evidence-verification.json`: twenty artifact consistency checks, all true, from the hand trial.
- `fixtures/synthetic-vault-hashes.json`: SHA-256 of the nine fixture notes.
- R1: https://github.com/snicolello/project_recovery/pull/1 (merged `22bcaa7`; `scripts/run_scenarios.py` gate output, review remediation, completion view on hub #118).
- R2: https://github.com/snicolello/project_recovery/pull/5; five review and remediation records on hub #119; the fifth review's full report and the owner's bounded acceptance ruling there and on #113; validation at the head recorded on PR #5.
