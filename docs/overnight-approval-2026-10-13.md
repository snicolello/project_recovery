# Overnight approval package — 2026-10-13

## Owner Attention

**Ready for owner review; final independent audit passed.** Stage A measured **8.63%** estimated read-token saving from the best non-control queries, or **9.26%** when retaining R2 in the three scenarios where candidates cost more. The independent auditor verified the exact retained packets, source receipts, coverage and arithmetic with no actionable findings. My recommendation is to proceed toward a bounded R4 pilot after owner review and defer the optional model trial for now. This is an **inferred** investment recommendation from the measured headroom and the owner's priority of reaching a usable transition quickly, not a claim that other Librarian strategies lack value.

The [owner ruling](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6136264847) authorized synthetic implementation, measurement and preparation. Merges, release acceptance, downloads, model trials, real-vault access and actual transition still require explicit approval. The single execution record is [hub #126](https://github.com/snicolello/stephen-project-hub/issues/126), which remains open.

**Smallest next approval:** review #12 and #11, approve their merges if satisfied, and explicitly waive the R3 predecessor for R4 while deferring the optional R3 Librarian without accepting R3. To execute the pilot, also name an exact Personal source folder and external index/cache location and approve that bounded read-only scope. No real source folder has been inspected or selected. R4 acceptance and actual transition follow only after pilot evidence and a further owner ruling. Alternatively, approve the fully specified local-model trial below; that adds an experiment before transition evidence and has no demonstrated model benefit yet.

## Outcome and proposed review order

Accepted `main` remains **`7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28`**, with R2 and reliance gate #6 accepted. All work below is proposed on separate branches from that baseline. The recovery contract, acceptance criteria and fixtures are unchanged. Independent reviewers were separate Codex agents, not outside human readers. Labels: **measured** means observed in this session; **sourced** means read from authoritative evidence; **inferred** means a recommendation drawn from those facts.

| Review order | Proposed work | Published revision | Result |
|---|---|---|---|
| 1 — [PR #12](https://github.com/snicolello/project_recovery/pull/12) | Stage A fixed-query headroom | `10849760e6eb380eb8b55308cfffa594276a1a3f` | Implemented, measured and independently audited |
| 2 — [PR #11](https://github.com/snicolello/project_recovery/pull/11) | Synthetic transition rehearsal and recovery procedure | `f31c231d77e1d4f2789b893aa3ec6b6b7ec4556b` | Implemented, tested and independently reviewed |
| Optional — [PR #10](https://github.com/snicolello/project_recovery/pull/10) | Deterministic Librarian interface/scoring and approval-only trial proposal | `504d51b4f892437ad4a531f59f3a170fe1ec1098` | Implemented, tested and independently reviewed; no model trial |
| Last — [PR #13](https://github.com/snicolello/project_recovery/pull/13) | Current STATE and consolidated approval evidence | Identified by its PR head | Records proposed versus accepted state |

There is no code dependency between #10, #11 and #12: each adds its own files above the accepted core. Review #12 first for the investment decision. #10 is unnecessary for an R4 path that explicitly defers the Librarian. Keep each release decision separate from merge approval. No integrated release or deployment is claimed.

## Stage A — results and limitations

**Measured at `541ea4397574d2a3ed8874085be4aaf5e37ef704`; independent raw-evidence audit passed at `f63a2781bd5effe5b805aef09138a84bf705187f`.** Final publication `10849760e6eb380eb8b55308cfffa594276a1a3f` only records that review in the README and summary; measurement inputs and results are unchanged. The fixed candidate queries, required coverage, fetch policy, byte estimator and calculation were committed before the first run. Independent review passed the original method at `53b388d17d0838a80cb741fe5f4f4d2051962326`, its infrastructure correction at `9fa99e743ae7d40d79164876946e408e7a57f673`, and packet-retention amendment at `541ea4397574d2a3ed8874085be4aaf5e37ef704`. Final predeclaration SHA-256: `11c071e9260c34dca3e3d601a94177a380e2a8db971ec21ae5ca01265d2b55ba`. Fixed measurement fields across all versions have identical canonical SHA-256 `e63b5514a235f956474cd540765f72d3ba8eeef5ed08c43beb860286b4312fc1`; no query or calculation was tuned after observing results.

| Scenario | R2 estimated tokens | Best non-control estimated tokens | Saving | Best non-control query | Explicit fetches / zero-fetch consuming cases |
|---|---:|---:|---:|---|---|
| S1 | 3,923 | 3,138 | 20.01% | `ATLAS-42` | 0 / 1 of 1 |
| S2 | 7,600 | 5,713 | 24.83% | `SQLite PostgreSQL Redis` | 0 / 2 of 2 |
| S3 | 4,853 | 4,574 | 5.75% | `retry-window` | 0 / 2 of 2 |
| S4 | 6,640 | 6,078 | 8.46% | `retry-window` | 0 / 2 of 2 |
| S5 | 3,142 | 3,145 | -0.10% | `UNKNOWN approval` | 0 / 1 of 1 |
| S6 | 3,923 | 3,138 | 20.01% | `ATLAS-42` | 0 / 1 of 1 |
| S7 | 9,170 | 9,178 | -0.09% | `load option` | 8 / 0 of 4 |
| S8 | 7,183 | 7,463 | -3.90% | `Recovery marker` | 2 / 0 of 2 |
| **Total** | **46,434** | **42,427** | **8.63%** | Best per scenario within fixed list | **10 / 9 of 15** |

Keeping the control in S5, S7 and S8 yields **42,136 tokens, 9.26% saving**. The total sums the predeclared 15 consuming cases; it is not an equally weighted scenario average or a measured real-workload distribution. Negative results remain visible. Two other S7 query plans (`project`, `report`) were excluded because their semantic projections differed from the control even though individual row checks passed.

All 88 rows met their per-row expectations: 64 successful re-derivations (including four unbounded diagnostic references), 20 expected `not_rederivable` and four expected `rejected`. The 24 expected refusals exposed no trusted packet, matched the specified cause and contributed no saving. Coverage was 460/460 spans across the full grid, including diagnostic references. Across the 60 charged grid rows, 36 needed no explicit fetch; the four references and expected refusals are not consuming cases. No fetch failed. The independent audit verified all 64 canonical packets (692,470 bytes), 1,328 source receipts, 42 full-grid fetches (19,870 bytes), exact refusal causes, row costs, plan exclusions and both aggregates. The raw attempt-3 result SHA-256 is `522cb351f402e316055f74c3546735de53a9218d440d2e78db1e0aced47eef6d`; its parsed-identical LF audit export is `9c1bfb832ff2948100f5de1bcfab3e097fca2301328b813ba145cd9c6401e597`.

The final worker took **348.297 seconds**, 351.508 seconds from recorded start to finish, under the 600-second cap. Fixture hashes were 16/16 before and after, with the entire fixture tree unchanged. The cumulative Stage A lane held 40,569,165 bytes at finish, below 250 MiB. No product model call or network authority lookup ran.

The final 21 focused method/retention tests passed, including canonical packet round-trip checks, path refusals and process-tree termination when a resource monitor fails. Independent review also passed these focused checks. Exact commands and runtime pins are retained in Stage A evidence.

Earlier attempts remain retained. The first produced 27 state-directory refusals and 61 dependent setup errors, leaving all 88 rows ineligible before a valid packet or saving was observed. Null saving was not treated as zero saving. The second executed successfully in 346.843 seconds but saved only packet byte counts/digests, so its cost inputs were not independently auditable. The final run retains exact compact packets and reproduced the same costs. Infrastructure and retention corrections preserved the fixed measurement rules. Four initially ignored raw logs were explicitly committed after review caught their absence; all hashes were checked. Every attempt left fixtures unchanged.

Consumer cost includes the validated packet plus every explicit fetch envelope/span the consumer reads, estimated from UTF-8 bytes divided by 2.9 and rounded up. Candidate exploration and validation traffic are separately reported. The 15% reference is not a pass/fail threshold. Eight synthetic scenarios, a fixed candidate list and a byte-based estimator cannot establish all possible Librarian strategies, real-vault performance, model quality or realized provider savings.

## Implemented and verified preparation

**Librarian interface (measured).** At implementation `4351301dbb9a51bbaa3c3c96cf6498c40b403045`, the unit suite ran 137 tests: 134 passed, three skipped (one existing platform-permission test and two opt-in integration tests). The two actual-QMD integration checks separately passed. Independent review repeated nine focused tests and both actual-QMD tests with no blocking finding. Fixture hashes passed 16/16 around executions. [Committed evidence](https://github.com/snicolello/project_recovery/tree/504d51b4f892437ad4a531f59f3a170fe1ec1098/evidence/r3-preparation) records the commands and versions.

The parser accepts a bounded query/claim envelope, rejects malformed or out-of-scope input, never uses raw claim text as trusted content, and exposes only a fresh re-derived packet after `validate --hits requery`. Claim-versus-abstention scoring explicitly does not establish correctness of claim wording. Deterministic doubles are labelled; no model behavior is claimed.

**Transition rehearsal (measured).** At implementation `0fad9f3109189bc366eaf6054a43106da73f8752`, 133 unit tests ran: 132 passed and one existing permission test skipped. Windows actual-QMD rehearsal passed in 1.621 s. Independent review passed seven focused checks and a fresh rehearsal in 2.625 s. The orchestrator followed the documented procedure at evidence revision `012c683d70cc7610414cc0136890b4931712bf08`: it passed in 1.691 s, including a real Windows junction escape refusal. [Normalized result](../evidence/overnight-2026-10-13/root-transition-result.json) preserves that replay and the hash of its retained raw report.

The live tool surface advertised only `get`, `multi_get`, `query` and `status`; all seven tested mutating calls were refused. Traversal, junction escape, source-contained state, update hooks and poisoned tool advertisements were rejected. Indexes/caches were outside the copied source; copied and fixture bytes remained unchanged; requery returned zero validation failures.

**Quickstart and portability (measured, incomplete for R5).** The existing Windows installation completed the five documented recovery operations in 4.403 s. Seven dependency-free tests passed on existing WSL Ubuntu/Python 3.12.3. No installation ran. Native Linux QMD was unavailable; existing Linux Node was 22.21.0 versus the documented Node 24 prerequisite. These checks do not satisfy the outside-reader, quickstart-only, Windows-and-Linux 15-minute criterion.

**Accepted seam regression (measured).** At `53b388d17d0838a80cb741fe5f4f4d2051962326`, `python -I scripts/run_scenarios.py` passed 184/184 checks in 133.850 s under a 600-s process-tree bound. Fixtures matched before and after. This is one global full-harness run, despite its internal 20 repeatability iterations. Later harness-only corrections do not change the tested accepted seam.

## Optional runtime/model approval — no download or trial performed

The complete [trial proposal](https://github.com/snicolello/project_recovery/blob/504d51b4f892437ad4a531f59f3a170fe1ec1098/docs/r3-runtime-approval.md) contains exact destinations, digest checks, isolation, rejection/scoring plan and stop conditions. Public metadata is saved beside it and independently reviewed. All artifact digests and sizes below are **sourced**, not locally verified downloads.

| Item | Exact proposed artifact | Licence / size / SHA-256 |
|---|---|---|
| Model | Official Qwen3-4B Q4_K_M GGUF, repository revision `bc640142c66e1fdd12af0bd68f40445458f3869b` | Apache-2.0; 2,497,280,256 bytes; `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Runtime | llama.cpp `b11435` Windows CPU x64 pre-release archive, source `43fe9c64281ef735046adc025e9e7559a1f659a5` | MIT core plus bundled notices; 19,399,527 bytes; `3ed50261147e260d80f5cdc7bdccfa13a94882be560a4438e7a69fa519c93fb7` |

Download total: **2,516,679,783 bytes**. Proposed CPU-only trial: six threads, one process, 4,096-token context, input at most 2,048 tokens, output at most 384 tokens, 16 proposals (two fixed seeds across S1-S8), 120 s per proposal and two hours total; stop above 8 GiB working set. Retain at most 6 GB artifacts plus 1 GB scratch. These are trial limits, not measured performance promises. No hosted service or GPU setup is requested. The existing workstation has approximately 31.56 GiB RAM; achievable speed and model benefit remain unknown.

Owner approval must name this proposal explicitly. Merging #10 alone approves neither the download/installation nor inference. An actual trial would still not accept R3.

## Unresolved items and dispositions

- Stage A setup failure, missing committed logs and absent packet evidence: fixed and retained. Each amendment passed focused review before its next run; final raw-evidence audit passed without actionable findings. No acceptance gate was weakened.
- Existing subprocess-pipe `ResourceWarning`: observation/no action because processes exited and no functional impact was measured. Re-enter on measured handle growth or failure during a longer trial; accepted core was not reopened speculatively.
- Reviewer sandbox junction/full-suite restrictions: the denied junction and interrupted broad suite are retained as unavailable/incomplete, not passes. Worker and orchestrator authorized Windows runs cover the junction boundary. No fixture change resulted.
- QMD 2.8.3 snippet line labels: reproduced and documented in the [unsent upstream report](https://github.com/snicolello/project_recovery/blob/f31c231d77e1d4f2789b893aa3ec6b6b7ec4556b/evidence/transition-rehearsal/upstream-qmd-snippet-line-labels.md). The recovery path verifies fetched source bytes, so this did not compromise evidence receipts. External submission requires approval.
- Native Linux installation, outside-reader trials, real-vault pilot, model trial and actual transition remain unexecuted. R4 acceptance and R5 release criteria remain owner gates.

## Resumable checkpoint and workspace

Resume from [issue #126](https://github.com/snicolello/stephen-project-hub/issues/126), then this file and the exact PR heads. Preserve the difference between the accepted baseline and proposed branches. Do not repeat successful checks unless code changes or a concrete unresolved concern justifies it. Check fixture hashes before and after every execution. Do not infer any unrecorded approval.

Useful authorized implementation and execution are complete early, before the 08:00 America/New_York deadline. Final publication and approval-package review are the closeout work. Further transition progress depends on the owner decisions above; no idle waiting or additional speculative implementation is warranted.

Session-created worktrees under `C:\dev\project_recovery\.scratch\` are `overnight-stage-a`, `overnight-librarian`, `overnight-transition` and `overnight-handoff`; branches are respectively `codex/126-stage-a`, `codex/126-librarian-prep`, `codex/126-transition-prep` and `codex/126-approval-package`. Retain all for review. Stage A attempt logs/ledger, generated synthetic sources and QMD state are retained in their worktree; B/C keep their focused/integration/rehearsal evidence. Each reuses the existing runtime through a junction; no new runtime was installed. Root drafts/public-metadata intermediates remain in `.scratch/overnight-control/`.

Older worktrees, unrelated `.review-pr17-portable/` and `.review-pr17-retry/`, branches and mixed-provenance caches were preserved. No cleanup or source deletion was performed. Public evidence normalizes machine-local path prefixes and separators where stated. **Global full-harness use: 4/20** — failed Stage A setup, passing 184-check regression, successful but incompletely retained Stage A, and final packet-retaining Stage A. No further full run is planned. The [03:05:12 UTC inventory](../evidence/overnight-2026-10-13/scratch-inventory.json) measured **44,554,902 bytes** in generated roots. A conservative count of all four new worktrees plus root control scratch, including tracked source/evidence and bytecode but excluding existing runtime junction targets, was **61,282,629 bytes**, well below 1 GB. Only small evidence/documentation edits follow this inventory.

## What cost time, and what remains unknown

Method review found real issues in failure oracles, S7 budget checks, timing independence and resource-limit failure handling; they were fixed before meaningful results. Pure methodology checks missed the integration placement constraint, so the first attempt failed. The first successful execution omitted exact packet inputs from saved evidence. Corrections added path-compatibility checks, tracked-log verification and lossless packet-retention checks before the final run. All failures remain visible. Future measurements should prove the complete saved-input audit on a small deterministic example before launching the full matrix; this is a project lesson, not a change to accepted product behavior.

GitHub DNS failures in one execution context were resolved through a working authorized publisher context, with ordinary fast-forward pushes and independent remote SHA checks. No alternative branch history or force push was used. Automatic approval review rejected a research command containing a raw model-file URL; no model bytes were downloaded. Public metadata APIs supplied the approved research instead.

[Usage checkpoint](../evidence/overnight-2026-10-13/usage-observation.json): the shared weekly Codex counter moved from **5%** at start to **26%** in the 03:14:39 UTC checkpoint (21 percentage points); unrelated account activity cannot be separated. At that checkpoint, the goal tool reported 2,990,517 tokens used and 5,467 elapsed seconds; its token accounting composition is not established here. These are observations, not a provider bill, output-token total or reliable task cost. Final documentation/publication follows this checkpoint. No product inference or model/runtime download occurred. No ticket was closed as accepted, so no outcome-ledger closure entry is due.
