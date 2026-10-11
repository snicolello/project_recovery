# Markdown project recovery acceptance criteria

Proposed on October 10, 2026. These criteria are a decision instrument for existing tools and any later adapter or MVP. They are targets, not achieved results or authorization to build.

Scope update: only the smaller two-tool, five-scenario evaluation was approved and executed. Its [gap list](scoped-evaluation/gap-list.md) must be reviewed before deciding whether to authorize the 40-case design below.

**Minimum outcome:** from a project identifier and a fixed source snapshot, return a bounded recovery packet containing objective, current state, accepted decisions, blockers, and next authorized action. Every material field must cite evidence or explicitly say unknown. Determinism applies to retrieval and structured assembly; it does not promise identical model prose or automatic understanding of arbitrary notes.

## Smallest proposed product boundary

Support existing UTF-8 Markdown with optional frontmatter and wikilinks. Permit an external project manifest naming project roots, the baseline note, decision sources, and authority policy; do not require vault-wide rewriting. Without a manifest, provide search and partial recovery only. Start with local MCP access and lexical retrieval. Treat embeddings, automatic capture, note editing, graph databases, cloud hosting, mobile access, and multi-user collaboration as deferred until evidence justifies them.

Suggested interface, subject to design approval: recover a project, fetch cited evidence, and inspect source/index status. Existing retrieval implementations may supply these capabilities. Shared retrieval means reuse of a derived index and content cache across local client sessions; it does not require a network service in the first version.

## Observable acceptance tests

| Requirement | Pass condition |
| --- | --- |
| Read-only recovery | Full before/after hashes of fixture source files match for every operation; no write, delete, shell, or note-edit tool is exposed. Derived files remain outside source roots. |
| Vault compatibility | Handle plain Markdown, optional frontmatter, relative links, wikilinks, duplicate basenames, Unicode, spaces, and Windows paths. Report broken/ambiguous links and malformed metadata without silently dropping material evidence. |
| Project isolation | Explicit root allowlist; reject traversal and symlink/junction escape. A same-named project outside scope contributes zero content. Test malicious instructions embedded in notes as data, not authority. |
| Deterministic recovery | With fixed source bytes, policy, tool version, budget, and supplied as-of time, ordered evidence IDs and canonical packet content match across 20 runs, including index rebuilds. Exclude request IDs and wall-clock diagnostics from comparison. |
| Evidence traceability | Every factual packet field has source path/URI, exact line span, content hash, and source revision where known. Validate cited text against the same bytes hashed. Missing evidence produces unknown, not a fabricated locator. |
| Freshness honesty | Separate file modification time, observation time, index generation, and last authority verification. Detect changed/deleted content even when mtime is preserved. A byte match means integrity, not semantic currency or approval. |
| GitHub authority | Configured acceptance records and revisions outrank local drafts regardless of mtime or search rank. Offline recovery preserves known provenance and labels current authority unverified. A URL or frontmatter claim alone cannot establish acceptance. |
| Conflicts and incomplete input | A superseded decision, unresolved contradiction, missing baseline, or sync-in-progress fixture yields an explicit status with implicated evidence. Never silently choose the newest note. |
| Stable reads | Edits during assembly yield either one consistent captured generation or a bounded retry followed by incomplete status. Cache keys include project scope, content generation, policy/version, and budget. |
| Bounded output | Default packet limit: 4,000 tokens under a named tokenizer. Report omitted items and truncation; retain conflict/unknown status. Fetching details is explicit and separately metered. |
| Shared efficiency | Two concurrent clients see the same generation. Instrumented repeated unchanged reads reuse the index/cache; report cold/warm latency, bytes, and repeated work. No cross-project cache leakage. |
| Open-source usability | No paid service, Obsidian subscription, hosted account, or model download required for lexical recovery. Document one local quickstart and uninstall procedure; verify native Windows and one Linux environment. A fresh user completes the sample recovery in 15 minutes after stated prerequisites. |
| Portfolio reproducibility | Publish license choice, synthetic corpus, scoring rules, exact versions, commands, raw results, failure cases, and limitations. Do not publish private vault content. |

## Benchmark design before implementation

Create 40 synthetic restart cases: five each for clean recovery, superseded decisions, source drift, cross-project ambiguity, missing evidence, authority conflicts, concurrent/sync-like edits, and budget stress. Use at least four unrelated project themes. Split 24 development cases and 16 held-out cases, with two held-out cases per category. Freeze fixtures and gold answers before comparing systems. A second human review of the gold labels is desirable before public performance claims; disclose if unavailable.

Each case specifies required facts, allowed evidence spans, forbidden assertions, expected authority/freshness states, and the acceptable next action. Use synthetic GitHub acceptance snapshots with fixed revisions for reproducible offline authority tests. Evaluate any live GitHub adapter separately; fixtures cannot establish live integration correctness.

Compare direct Markdown reading with a clear recovery prompt, then the same agent with each shortlisted tool. Include a direct-reader-plus-manifest baseline so a favorable result cannot be attributed only to giving the candidate better metadata. Provide all systems the same facts and allowed setup information. Disclose schema transformations, tool-specific prompts, and preprocessing cost. A tool that cannot represent a requirement is an unsupported case, not a secretly modified competitor.

Score structured recovery without an LLM first. Then run fresh agent sessions three times per case using the same pinned model, settings, prompt, and token ceiling across conditions. Record model identity and date if a provider cannot guarantee an immutable revision. Log whether the agent invoked recovery at all. If the model stage would require paid calls, establish a separate cost ceiling before running it.

| Metric | Definition and proposed gate |
| --- | --- |
| Recovery completeness | Correct required fields / all required fields on answerable cases, macro-averaged by case. At least 90% on held-out cases. |
| Unsupported assertions | Unsupported material assertions / all material assertions. Zero authority-violating or unsupported material assertions in the held-out run; report counts and denominator. |
| Citation correctness | Correct supporting locators / all claimed supporting locators. 100% structurally valid; at least 95% semantically supporting under gold labels. |
| Appropriate abstention | Report abstention precision and recall separately. All deliberately missing/contradictory mandatory fields must be flagged; answerable-field false abstention at most 10%. |
| Repeatability | Exact packet equality under fixed inputs in 20/20 runs. Score model outcome variability separately. |
| Efficiency | Total input tokens, tool response bytes, tool calls, cold/warm p50 and p95 latency, indexing time, and peak memory. Report hardware and corpus size; make no universal speed claim. |
| Agent activation | Sessions invoking the recovery/evidence workflow / eligible sessions. Report natural prompting and explicit-use prompting separately. |

Report numerator/denominator, per-category failures, repeated-run spread, and 95% intervals where meaningful; do not treat repeats of one case as independent users. This small benchmark is a regression and decision tool, not evidence of universal reliability.

## Build or reuse gate

Adopt or document an existing solution if it meets the hard authority, isolation, evidence, and read-only requirements and clears the quality gates. Prefer a thin adapter if it can meet those requirements without replacing retrieval or introducing a competing source of authority.

A standalone proposal must show a concrete unmet requirement and either at least a 10 percentage-point held-out completeness gain at comparable token cost, or at least 30% fewer total input tokens with completeness within 2 percentage points and no safety regression, against the strongest configured baseline. These are proposed practical decision thresholds, not statistically validated effect sizes. Require user review of raw failures and uncertainty before drawing a build conclusion.

If the benchmark cannot distinguish approaches, or better recovery requires heavy manual annotation, stop the gateway proposal and publish the limitation honestly. A reproducible negative result and useful integration recipe remain valid portfolio outcomes.
