# Project State

- Project: Project Recovery (`RECOVERY`)
- Purpose: Level-0 routing baseline for the accepted release state, current gates and one safe continuation.
- Status: R2 and reliance gate #6 remain accepted; R3 is deferred. R4 is accepted as a bounded read-only mechanics pilot. [PR #19](https://github.com/snicolello/project_recovery/pull/19) fixed blank-note refresh ([#16](https://github.com/snicolello/project_recovery/issues/16)) and the stderr-handle leak ([#14](https://github.com/snicolello/project_recovery/issues/14)) on synthetic evidence; the owner accepted both at synthetic scope and they were closed as completed on 2026-10-18. Neither the fix, its merge nor those closures is release acceptance or actual-use readiness. The owner accepted [#17](https://github.com/snicolello/project_recovery/issues/17)'s implementation at synthetic scope ([PR #20](https://github.com/snicolello/project_recovery/pull/20)'s authority mapping and [PR #21](https://github.com/snicolello/project_recovery/pull/21)'s option 2 last-checked evidence workflow) and #17 was closed as completed under the owner's ruling. The remaining pilot and actual-use/transition readiness decisions belong to [#23](https://github.com/snicolello/project_recovery/issues/23). GitHub remains the acceptance authority; history is context with `acceptance_effect: none`, offline current acceptance stays unverified and accepted decisions stay unknown. All live capture and recovery runs remain on hold. Actual-use and transition readiness are not established. Run-004's authority and accepted decisions remain unknown, and recovery completeness remains false.
- As of: 2026-10-20, recording the #25 pipe-cleanup fix in [PR #29](https://github.com/snicolello/project_recovery/pull/29), after the 2026-10-18 closure of #14 and #16 at synthetic scope, #17's closure and the transfer of readiness to #23. PR #29 changes only the MCP client's cleanup, its tests and a rehearsal test double; no fixture or contract has changed since [PR #22](https://github.com/snicolello/project_recovery/pull/22) merged at `c4b3a6b`.
- Authority: Stephen (owner), through rulings on the hub coordination Epic #113. Only the owner can change acceptance or scope. The hub is private: its links below work only for the owner and owner-side agents.
- Sources:
  - the owner rulings authorizing the [#16 fix](https://github.com/snicolello/project_recovery/issues/16#issuecomment-6177400662), the [#14 fix](https://github.com/snicolello/project_recovery/issues/14#issuecomment-6177400983) and the [#17 labelled-line mapping](https://github.com/snicolello/project_recovery/issues/17#issuecomment-6177401293);
  - the governing-record contract amendment and stricter frontmatter behavior accepted by the owner ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6198390697));
  - the option 2 last-checked evidence ruling, synthetic implementation authorization and live-run hold ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6201195668));
  - the #17 synthetic-scope acceptance ruling ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6202294163)) and prepared pilot approval packet with unconfirmed private inputs and execution on hold ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6202308663));
  - the ruling closing #17 at synthetic scope and moving the remaining pilot and readiness questions to #23, which supersedes the packet's references to #17 as readiness owner ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6203956770));
  - the R4 acceptance ruling ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6172657227)) and the R3 deferral and predecessor waiver ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6145720151)), both still in force;
  - the ruling accepting #14 and #16 at synthetic scope and closing both, with #25 and #26 kept as follow-ups and live runs on hold ([owner-only link](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6257547880));
  - the public evidence below.

  Live pilot conditions and run detail are kept in the owner's private coordination record, not here.
- Objective: preserve accepted R2/#6 and bounded R4 mechanics evidence, the blank-note and authority-format fixes, and a truthful distinction between historical approval evidence and current acceptance, while #23 holds the remaining pilot and readiness decisions.
- Next action: the owner's decisions under [#23](https://github.com/snicolello/project_recovery/issues/23), which carries the next safe action: complete the private pilot input sheet, then a separate exact execution ruling if desired. All live capture and recovery runs remain on hold. No source write or move, new install or readiness ruling is implied; the current source path must be reconfirmed before any later live run.
- Read when:
  - [`PROJECT.md`](PROJECT.md): checking project identity, outcome, trust zone or scope.
  - [#23](https://github.com/snicolello/project_recovery/issues/23): the current pilot and actual-use/transition readiness questions, their completion conditions and the next safe action. [#17](https://github.com/snicolello/project_recovery/issues/17) keeps the accepted implementation criteria and evidence.
  - [`docs/recovery-contract.md`](docs/recovery-contract.md): implementing or reviewing any release; this remains the product contract. Section 4 was amended on 2026-10-14 for blank notes and empty collections under the #16 ruling, and on 2026-10-15 for the governing-record mapping and stricter frontmatter behavior under the Epic #113 ruling.
  - [`skills/project-recovery/SKILL.md`](skills/project-recovery/SKILL.md) and [`docs/quickstart.md`](docs/quickstart.md): running the accepted recipe, configuring the governing-record mapping or checking its validation guarantees.
  - [`docs/last-checked-evidence.md`](docs/last-checked-evidence.md): optional historical context, separate governed capture, independently retained bundle pins, original check times and unchanged offline acceptance limits.
  - [`evidence/qmd-blank-notes-2026-10-14/README.md`](evidence/qmd-blank-notes-2026-10-14/README.md): QMD 2.8.3's observed blank-note and empty-collection behaviour behind the #16 rule.
  - [`evidence/r4-pilot/run-004/README.md`](evidence/r4-pilot/run-004/README.md): the public aggregate of the accepted R4 pilot and its limits.
  - [`evidence/r3-stage-a/README.md`](evidence/r3-stage-a/README.md) and [`evidence/transition-rehearsal/README.md`](evidence/transition-rehearsal/README.md): Stage A and the synthetic transition checks, and their limits.

## Current baseline

The accepted implementation baseline is R2 plus reliance gate #6, recorded at [`7e73ca4`](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28), plus merged preparation through [`54ad8b02`](https://github.com/snicolello/project_recovery/commit/54ad8b021721040130c69a953f61a07177569f11) (the run-004 implementation baseline). The accepted release position also includes R4's bounded read-only mechanics pilot. R4 acceptance changed no core code or product contract. The recovery path exposes no write, edit, move or delete tools. Fixtures remain synthetic.

The owner also accepted #17's authority mapping and last-checked workflow at synthetic scope, integrated through [`ad4726a`](https://github.com/snicolello/project_recovery/commit/ad4726a591da936a554fb4fd32761270631d0d0f). This changes the accepted synthetic implementation baseline, not the release or live-readiness gates. No real-source capture or post-fix recovery evidence is added by that acceptance.

PR #19 changed the accepted core under the owner's rulings on #16 and #14:

- **Indexability rule.** Refresh mirrors QMD 2.8.3: text that is empty after JavaScript's `trim()` is not indexed.
- **Blank notes.** They are recorded as present, not indexable, with their hashes kept in the generation record.
- **Verified empty.** A collection QMD does not list is verified empty only when its root exists as a directory and the disk scan finds no indexable note in it. Every field of a verified-empty project is `unknown`. A missing or renamed root fails refresh.
- **Integrity gates unchanged.** Every Markdown file is hashed, and a changed, added or deleted non-blank note still fails refresh.
- **Emptied notes.** QMD keeps an emptied note's last indexed content, so refresh then fails closed and names `--rebuild`.
- **MCP client (#14).** It resolves the QMD command before opening its stderr log, and closes the log on every failed start.

PR #20 changed the governing-record mapping under the owner's ruling on #17:

- **Labelled line.** A manifest may set `authority.record_label` (for example `- **Status:**`) instead of the frontmatter `authority.record_key`. The one body line starting with that label is cited with a receipt, read by the same reader as labelled fields and approvals.
- **One mapping.** Configuring both, or an unknown `authority` key, is refused when the manifest loads, and a label never falls back to frontmatter.
- **Examples ignored.** The shared labelled-line reader skips lines inside fenced code blocks and HTML comments (the patterns approval markers already ignore), for the status line, labelled fields, the approver and approvals. Governing status is classified from the visible value after comments are hidden; comment-only values and `UNKNOWN` after a comment stay unknown, while receipts retain the raw line. An inline-code `UNKNOWN` counts as `UNKNOWN`, for the status line and approvals.
- **Fails closed, both mappings.** No matching line, more than one (an `authority_ambiguous` conflict), or a value that is empty or starts with `UNKNOWN` leaves authority `unknown`, with the matching lines kept as evidence. For the frontmatter mapping, a repeated key and an empty or `UNKNOWN` value are newly unknown; a single key behaves as before: the eight repeatability packets (S1 to S8) keep the canonical digests retained in `evidence/r3-stage-a/regression-184/stdout.log`.
- **Decision acceptance unchanged.** Decisions are accepted only through configured acceptance records. Offline, unavailable and local claims stay candidate, unknown or unverified.

Recovery contract section 4 records these changes and the owner's option 2 ruling. The last-checked workflow adds an optional historical block, read-only replay under an independently supplied pin, exact historical-time comparison in validation, and a separate capture utility outside the recovery tool surface. It uses the existing acceptance verifier and changes no current decision result. Missing or invalid evidence yields no history; changed note bytes, references and policy are labelled. No new dependency or acceptance authority is introduced.

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
- The first live R4 attempt stopped safely at refresh, before assembly, on a blank note. PR #19 fixed that defect (#16) on synthetic evidence (probes, scenario S9, unit tests) without weakening either integrity gate. It also fixed the missing-QMD stderr-handle leak (#14).
- Run-004 left main authority unknown because the expected frontmatter field was absent. PR #20 fixed that format gap (#17) on synthetic evidence: plain `STATE.md`-style fixtures in `fixtures/authority-notes/`, scenario S10 and unit tests.
- PR #21 implemented separate last-checked capture and historical replay under the owner's option 2 ruling. The owner accepted #17's implementation at synthetic scope using the retained evidence below.
- On 2026-10-15 #17 was closed as completed at synthetic scope under the owner's ruling, which moved its remaining pilot and readiness questions to #23. [PR #22](https://github.com/snicolello/project_recovery/pull/22) merged the accepted state record at `c4b3a6b`. The closure changed no repository baseline.
- The blank-note fix, authority mapping and last-checked workflow have not been run against a live folder.

## Pending

- Run-004's limits remain as stated in its public aggregate:
  - One agent-authored starter note, not the owner's own notes.
  - Main authority unknown, because the expected frontmatter field is absent. The labelled mapping would need an owner-configured manifest and a new authorized run to change that result.
  - No accepted decision offline.
  - Packet `status: complete` means generation health only.
  - No operating-system sandbox or network isolation: client enforcement and before/after source hashes are the controls.
- [#23](https://github.com/snicolello/project_recovery/issues/23) owns the remaining representative-input selection, genuine acceptance capture/replay, operator trust/freshness checks, exact execution inputs, pilot approval and actual-use/transition readiness decisions. The private pilot packet proposes bounded checks but requires exact input confirmation and explicit execution approval. Option 2 is historical context, not an offline approval workflow. Offline decisions stay unverified candidates, and accepted decisions stay unknown.
- #23 records that the acceptance-record preparation dependency is resolved: a GitHub acceptance record is posted on the private Epic and its approved note remains outside the vault. That is prepared evidence only. No Recovery verification of it, real-source capture or historical replay has been run, and the note's digest is not a capture-bundle pin.
- [#16](https://github.com/snicolello/project_recovery/issues/16) and [#14](https://github.com/snicolello/project_recovery/issues/14) are fixed on synthetic evidence and were closed as completed at synthetic scope on 2026-10-18 under the owner's ruling; each issue's closure receipt holds the evidence. Those closures do not fix the two follow-ups:
  - Subprocess-pipe cleanup ([#25](https://github.com/snicolello/project_recovery/issues/25)): [PR #29](https://github.com/snicolello/project_recovery/pull/29) makes the MCP client release the server's stdin and stdout pipes on shutdown and on every failed start, on synthetic evidence; if the server cannot be stopped, stdout is released only when the reader reaches end of file (EOF). #25 stays open: accepting and closing it are the owner's, and the fix is not release acceptance or actual-use readiness.
  - Ignored-directory compatibility ([#26](https://github.com/snicolello/project_recovery/issues/26)) remains open: QMD skips dot-folders and some build folders that refresh still scans, so such a note fails refresh closed.
- R3 was waived only as R4's predecessor, without acceptance. Public records omit real source, index and cache paths, note names and content.
- Limits of the labelled mapping: the label must match the start of the line exactly (an indented, nested or differently written label is absent); a line inside a fenced code block or HTML comment never matches, and an unclosed fence or comment hides the rest of the note; a status line that runs onto a second line is cited as its first line only.

## Deferred

- MCP shutdown residuals ([PR #29, Remaining risks](https://github.com/snicolello/project_recovery/pull/29#remaining-risks)): if terminate and kill both fail, the reader join is limited to 5 s and stdout remains open until the reader reaches EOF; a descendant that inherits the pipe can delay EOF after the server exits. The pre-existing terminate-timeout path calls `kill()` without `wait()`, which can produce a subprocess "still running" ResourceWarning. These remain deferred beyond #25; revisit if shutdown warnings occur or before repeated-session operation makes delayed cleanup material.
- R3 query selection and the Stage B model trial are deferred without acceptance. Re-enter only if pilot evidence shows query-dependent recovered content, or frontier-token cost becomes material.
- PR [#10](https://github.com/snicolello/project_recovery/pull/10) is parked and closed unmerged. Its runtime/model proposal is prepared, not approved, and deferred with R3.
- The QMD snippet-label report is prepared but unsent; upstream submission requires separate owner approval.
- R5 public v1.0 remains gated on its owner ruling and the contract's outside-reader usability evidence.

## Blocked

- The blank-note gap has a synthetic fix, and #17's authority mapping and last-checked implementation are accepted at synthetic scope. Actual-use and transition readiness remain owner gates under #23, separate from the R3 and R5 gates. Representative live recovery, genuine acceptance capture/replay and operator pin custody remain unverified. Any live evidence needs a separately authorized run; all live runs remain on hold. No complete-recovery or transition readiness is established.

## Evidence

- [R2 plus #6 accepted-state revision](https://github.com/snicolello/project_recovery/commit/7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28) and [#6 acceptance record](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136067672).
- [Stage A evidence](evidence/r3-stage-a/README.md), with the 8.629% figure, the 37-comparison scope and fixture integrity.
- [Synthetic transition evidence](evidence/transition-rehearsal/README.md) and its stated limits.
- [Run-004 aggregate evidence and limits](evidence/r4-pilot/run-004/README.md) and [aggregate results](evidence/r4-pilot/run-004/summary.json): retained measurements only.
- [QMD 2.8.3 blank-note probe](evidence/qmd-blank-notes-2026-10-14/README.md). On PR #19, tested head `5ed6f8a91360d667126e77dd0620c518719edc5d`, fixture hashes matched 16/16 before and after, every scenario check passed (220: the 184 from before plus 36 in S9) and 192 unit tests passed (Ubuntu skips the Windows-only junction test; Windows skipped none), in [Ubuntu/Windows CI](https://github.com/snicolello/project_recovery/actions/runs/38636982928) and again on the [merge commit `cf5aaa9`](https://github.com/snicolello/project_recovery/actions/runs/38661530452). These are retained results, not a new run.
- [PR #20](https://github.com/snicolello/project_recovery/pull/20) retains the synthetic validation evidence: before/after fixture hashes, scenarios S1 to S10, unit tests and CI, including the comment-value regressions and unchanged raw receipts.
- [PR #21](https://github.com/snicolello/project_recovery/pull/21), tested head `519505bee770057956885748092cd00de1785329`, retains the accepted synthetic evidence: 261 unit tests, OK (one expected unprivileged-symlink skip); 270 scenario checks including S11 and both validation modes; 33 targeted independent-review checks with no blocking/backlog defects; original fixture hashes 16/16 before/after and all 51 fixture files unchanged. [Ubuntu/Windows CI](https://github.com/snicolello/project_recovery/actions/runs/38801139358) passed. Capture tests substitute synthetic responses for live requests; these are retained implementation results, not live evidence or a new test run for the acceptance record.
