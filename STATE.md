# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Level-0 routing baseline for the accepted release state, current gates and one safe continuation.
- Status: R2 and reliance gate #6 remain accepted; R3 is deferred. R4 is accepted as a bounded read-only mechanics pilot. On `main`, [PR #19](https://github.com/snicolello/project_recovery/pull/19) fixed the blank-note refresh blocker [#16](https://github.com/snicolello/project_recovery/issues/16) and the stderr-handle leak [#14](https://github.com/snicolello/project_recovery/issues/14) on synthetic evidence. Neither the fix nor its merge is release acceptance. Actual use / transition readiness remains blocked by authority/decision format [#17](https://github.com/snicolello/project_recovery/issues/17). Authority and accepted decisions remain unknown in run-004, and recovery completeness is false.
- As of: 2026-10-14, at the merge of PR #19.
- Authority: Stephen (owner), through rulings on the hub coordination Epic #113. Only the owner can change acceptance or scope. The hub is private: its links below work only for the owner and owner-side agents.
- Sources:
  - the owner rulings authorizing the [#16 fix](https://github.com/snicolello/project_recovery/issues/16#issuecomment-6177400662) and the [#14 fix](https://github.com/snicolello/project_recovery/issues/14#issuecomment-6177400983);
  - the R4 acceptance ruling ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6172657227)) and the R3 deferral and predecessor waiver ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6145720151)), both still in force;
  - the public evidence below.

  Live pilot conditions and run detail are kept in the owner's private coordination record, not here.
- Objective: preserve accepted R2/#6 and bounded R4 mechanics evidence, and resolve the remaining transition blocker (#17) without claiming readiness for actual use.
- Next action: #17's labelled-line authority mapping. It needs its own dispatch and work contract, and #17's backlog record authorizes no implementation by itself. Closing #16 and #14 is the owner's. No live run, source write or move, or new install is authorized. Any later live run needs its source path reconfirmed by the owner first.
- Read when:
  - [`PROJECT.md`](PROJECT.md): checking project identity, outcome, trust zone or scope.
  - [`docs/recovery-contract.md`](docs/recovery-contract.md): implementing or reviewing any release; this remains the product contract. Section 4 was amended on 2026-10-14 for blank notes and empty collections under the #16 ruling.
  - [`skills/project-recovery/SKILL.md`](skills/project-recovery/SKILL.md) and [`docs/quickstart.md`](docs/quickstart.md): running the accepted recipe or checking its validation guarantees.
  - [`evidence/qmd-blank-notes-2026-10-14/README.md`](evidence/qmd-blank-notes-2026-10-14/README.md): QMD 2.8.3's observed blank-note and empty-collection behaviour behind the #16 rule.
  - [`evidence/r4-pilot/run-004/README.md`](evidence/r4-pilot/run-004/README.md): the public aggregate of the accepted R4 pilot and its limits.
  - [`evidence/r3-stage-a/README.md`](evidence/r3-stage-a/README.md) and [`evidence/transition-rehearsal/README.md`](evidence/transition-rehearsal/README.md): Stage A and the synthetic transition checks, and their limits.

## Current baseline

The accepted implementation baseline is R2 plus reliance gate #6, recorded at [`7e73ca4`](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28), plus merged preparation through [`54ad8b02`](https://github.com/snicolello/project_recovery/commit/54ad8b021721040130c69a953f61a07177569f11) (the run-004 implementation baseline). The accepted release position also includes R4's bounded read-only mechanics pilot. R4 acceptance changed no core code or product contract. The recovery path exposes no write, edit, move or delete tools. Fixtures remain synthetic.

PR #19 changed the accepted core under the owner's rulings on #16 and #14:

- **Indexability rule.** Refresh mirrors QMD 2.8.3: text that is empty after JavaScript's `trim()` is not indexed.
- **Blank notes.** They are recorded as present, not indexable, with their hashes kept in the generation record.
- **Verified empty.** A collection QMD does not list is verified empty only when its root exists as a directory and the disk scan finds no indexable note in it. Every field of a verified-empty project is `unknown`. A missing or renamed root fails refresh.
- **Integrity gates unchanged.** Every Markdown file is hashed, and a changed, added or deleted non-blank note still fails refresh.
- **Emptied notes.** QMD keeps an emptied note's last indexed content, so refresh then fails closed and names `--rebuild`.
- **MCP client (#14).** It resolves the QMD command before opening its stderr log, and closes the log on every failed start.

Recovery contract section 4 records the new states.

## Completed

- R0, R1 and R2 were accepted through owner rulings on Epic #113. Reliance gate [#6](https://github.com/snicolello/project_recovery/issues/6) was accepted and closed.
- PR [#11](https://github.com/snicolello/project_recovery/pull/11) added a synthetic transition rehearsal; it is advance preparation only.
- PR [#12](https://github.com/snicolello/project_recovery/pull/12) added Stage A.
  - Its predeclared figure of record is an 8.629% best-in-hindsight estimated reduction.
  - Across all 37 eligible comparisons, timestamp-normalized recovered `fields` were identical. This is not a claim of universal raw-byte identity.
- PR [#13](https://github.com/snicolello/project_recovery/pull/13) was closed unmerged; its approval memo is historical.
- R4 run-004 established live retrieval, assembly and `validate --hits requery` returning `equal_to_rederived`, with source and fixture integrity preserved.
  - The owner accepted R4 against its written gate, "read-only enforcement demonstrated; owner approval", as a bounded mechanics pilot.
  - The public aggregate was published through PR [#15](https://github.com/snicolello/project_recovery/pull/15), and the R4 ticket was closed.
  - Acceptance is not readiness for actual use.
- The first live R4 attempt stopped safely at refresh, before assembly, on a blank note. PR #19 fixed that defect (#16) on synthetic evidence (probes, scenario S9, unit tests) without weakening either integrity gate. The fix has not been run against a live folder.
- PR #19 also fixed the missing-QMD stderr-handle leak (#14).

## Pending

- Run-004's limits remain as stated in its public aggregate:
  - One agent-authored starter note, not the owner's own notes.
  - Main authority unknown, because the expected frontmatter field is absent.
  - No accepted decision offline.
  - Packet `status: complete` means generation health only.
  - No operating-system sandbox or network isolation: client enforcement and before/after source hashes are the controls.
- R3 was waived only as R4's predecessor, without acceptance. Public records omit real source, index and cache paths, note names and content.

## Deferred

- R3 query selection and the Stage B model trial are deferred without acceptance. Re-enter only if pilot evidence shows query-dependent recovered content, or frontier-token cost becomes material.
- PR [#10](https://github.com/snicolello/project_recovery/pull/10) is parked and closed unmerged. Its runtime/model proposal is prepared, not approved, and deferred with R3.
- The QMD snippet-label report is prepared but unsent; upstream submission requires separate owner approval.
- R5 public v1.0 remains gated on its owner ruling and the contract's outside-reader usability evidence.
- Follow-ups noted on PR #19, not authorized:
  - QMD skips dot-folders and some build folders that refresh still scans; such a note fails refresh closed.
  - The MCP client does not close its subprocess pipes.

## Blocked

- Actual use / transition readiness is blocked by [#17](https://github.com/snicolello/project_recovery/issues/17), authority/decision format and offline provenance. Owner notes need an approved format and acceptance workflow, or a configurable alternative to the current frontmatter mapping. Local labels never prove decision acceptance. No complete-recovery or broader transition readiness is established.

## Evidence

- [R2 plus #6 accepted-state revision](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28) and [#6 acceptance record](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136067672).
- [Stage A evidence](evidence/r3-stage-a/README.md), with the 8.629% figure, the 37-comparison scope and fixture integrity.
- [Synthetic transition evidence](evidence/transition-rehearsal/README.md) and its stated limits.
- [Run-004 aggregate evidence and limits](evidence/r4-pilot/run-004/README.md) and [aggregate results](evidence/r4-pilot/run-004/summary.json): retained measurements only.
- [QMD 2.8.3 blank-note probe](evidence/qmd-blank-notes-2026-10-14/README.md). On PR #19, fixture hashes matched 16/16 before and after, every scenario check passed (220: the 184 from before plus 36 in S9) and the unit suite passed.
