# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Level-0 routing baseline for the accepted release state, current gates and one safe continuation.
- Status: Current project facts. R2 and reliance gate #6 are accepted; R3 is deferred; R4 is open and blocked at owner confirmation of both paths. No R3 or R4 release is accepted.
- As of: 2026-10-13, verified against [`project_recovery` `main` at `54ad8b021721040130c69a953f61a07177569f11`](https://github.com/snicolello/project_recovery/commit/54ad8b021721040130c69a953f61a07177569f11).
- Authority: Stephen (owner), through rulings on [hub Epic #113](https://github.com/snicolello/stephen-project-hub/issues/113). The current R3/R4 ruling and its precision correction are [recorded here](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6145720151); only the owner can accept a release or change its gate.
- Sources: the [current owner instruction and verified merge state](https://github.com/snicolello/stephen-project-hub/issues/126#issuecomment-6151931166), [LF-retention and merge disposition](https://github.com/snicolello/stephen-project-hub/issues/126#issuecomment-6151101009), private [R4 ticket #127](https://github.com/snicolello/stephen-project-hub/issues/127), and the commit-pinned evidence linked below.
- Objective: preserve the accepted R2 plus #6 baseline while preparing the owner-gated R4 read-only live-folder pilot without exposing private source metadata or accepting R3.
- Next action: on private [R4 ticket #127](https://github.com/snicolello/stephen-project-hub/issues/127), obtain the owner's explicit confirmation of both the source and index/cache paths. Metadata-only preparation is authorized; do not execute the pilot before both confirmations.
- Read when:
  - [`PROJECT.md`](https://github.com/snicolello/project_recovery/blob/54ad8b021721040130c69a953f61a07177569f11/PROJECT.md): checking project identity, outcome, trust zone or scope.
  - [`docs/recovery-contract.md`](https://github.com/snicolello/project_recovery/blob/54ad8b021721040130c69a953f61a07177569f11/docs/recovery-contract.md): implementing or reviewing any release; this remains the product contract.
  - [R4 ticket #127](https://github.com/snicolello/stephen-project-hub/issues/127): preparing or reviewing the live-folder pilot, its private path gate or publication controls.
  - [`evidence/r3-stage-a/README.md`](https://github.com/snicolello/project_recovery/blob/7c77b70fdfc779570a19bb60b14f9153e41db5d2/evidence/r3-stage-a/README.md): interpreting Stage A, its measurement population and retained evidence.
  - [`evidence/transition-rehearsal/README.md`](https://github.com/snicolello/project_recovery/blob/644613e4a27c4697f069f0c87c07c5951c07f9dc/evidence/transition-rehearsal/README.md): reviewing synthetic transition checks and their limits.
  - [`skills/project-recovery/SKILL.md`](https://github.com/snicolello/project_recovery/blob/54ad8b021721040130c69a953f61a07177569f11/skills/project-recovery/SKILL.md) and [`docs/quickstart.md`](https://github.com/snicolello/project_recovery/blob/54ad8b021721040130c69a953f61a07177569f11/docs/quickstart.md): running the accepted recipe or checking its validation guarantees.

## Current baseline

The accepted release baseline remains R2 plus reliance gate #6, recorded on `main` at [`7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28`](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28). It includes the recovery contract, synthetic fixtures, manifest, pinned QMD recipe, deterministic assembler, serial GitHub authority verification, freshness checks and received-packet validation. The recovery path exposes no write, edit, move or delete tools. Fixtures remain synthetic and the product contract is unchanged.

Current merged `main` adds tested synthetic transition preparation and Stage A evidence through PRs [#11](https://github.com/snicolello/project_recovery/pull/11) and [#12](https://github.com/snicolello/project_recovery/pull/12). Those merges accept no release and do not turn the preparation into a live R4 pilot.

## Completed

- R0, R1 and R2 were accepted through owner rulings on Epic #113. Reliance gate [#6](https://github.com/snicolello/project_recovery/issues/6) was later accepted and closed; the accepted-state revision is [`7e73ca4`](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28).
- PR [#11](https://github.com/snicolello/project_recovery/pull/11) merged reviewed head `644613e` as [`15add318`](https://github.com/snicolello/project_recovery/commit/15add318df1a262b8f8935bf2eb0e6c27a1e2603). Its synthetic transition rehearsal passed the recorded read-only, containment, isolation and requery checks; it is advance preparation only.
- PR [#12](https://github.com/snicolello/project_recovery/pull/12) merged reviewed head `7c77b70` as [`54ad8b02`](https://github.com/snicolello/project_recovery/commit/54ad8b021721040130c69a953f61a07177569f11). Stage A's predeclared figure of record is an 8.629% best-in-hindsight estimated reduction. Across all 37 eligible comparisons, timestamp-normalized recovered `fields` were identical; eligible savings came from echoed `query_hits` and `missing_sources`. This is not a claim of universal raw-byte identity. The earlier 15% figure was a reference only, not an acceptance threshold.
- The owner retained the LF audit export; its recorded and locally verified SHA-256 is `9c1bfb832ff2948100f5de1bcfab3e097fca2301328b813ba145cd9c6401e597`.
- PR [#13](https://github.com/snicolello/project_recovery/pull/13) was closed unmerged. Its historical approval memo remains at [`fb84324`](https://github.com/snicolello/project_recovery/commit/fb84324e142c97ef33bde03170fbc262e868f09a) and is superseded by this fresh baseline.

## Pending

- R4 ticket [#127](https://github.com/snicolello/stephen-project-hub/issues/127) is open in the private Personal hub. R3 was waived only as its predecessor; no R3 or R4 acceptance followed. The ticket awaits explicit owner confirmation of both paths, and no pilot has executed. Public records intentionally contain no real source or index/cache path metadata.
- After both paths are confirmed, R4 still requires its ticketed read-only, source-integrity, privacy, validation and separate-review gates. There is no operating-system sandbox around the recipe; client enforcement and before/after source hashes are the applicable controls.

## Deferred

- R3 query selection and the Stage B model trial are deferred without acceptance. Re-enter only if R4 pilot evidence shows query-dependent recovered content or frontier-token cost becomes material.
- PR [#10](https://github.com/snicolello/project_recovery/pull/10) is parked and closed unmerged. Its runtime/model proposal is prepared, not approved, and deferred with R3.
- The QMD snippet-label report is prepared but unsent; upstream submission still requires separate owner approval.
- R5 public v1.0 remains gated on its owner ruling and the recovery contract's outside-reader usability evidence.
- Open backlog issue [#14](https://github.com/snicolello/project_recovery/issues/14) owns the missing-QMD stderr-handle leak; it is not a release acceptance or R4 pilot change.

## Blocked

- R4 pilot execution is blocked only at the explicit confirmation of both paths and the remaining pre-run conditions on private ticket #127. Metadata-only preparation may continue within that ticket's bounds.

## Evidence

- [R2 plus #6 accepted-state revision](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28) and [#6 acceptance record](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136067672).
- [Stage A evidence and post-hoc interpretation](https://github.com/snicolello/project_recovery/blob/7c77b70fdfc779570a19bb60b14f9153e41db5d2/evidence/r3-stage-a/README.md), including the 8.629% figure, 37-comparison scope, fixture integrity and accepted-core regression evidence.
- [Synthetic transition evidence](https://github.com/snicolello/project_recovery/blob/644613e4a27c4697f069f0c87c07c5951c07f9dc/evidence/transition-rehearsal/README.md), including the retained Windows rehearsal, negative guards, cross-host tests and stated limits.
- [R4 work contract and current gate](https://github.com/snicolello/stephen-project-hub/issues/127). This source is private; detailed path metadata stays there.
