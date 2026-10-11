# Markdown context gateway Phase 0 decision brief

As of October 10, 2026. Independent personal open-source portfolio discovery. Decision status: proposed; implementation awaits user approval.

Scope update: the user approved a smaller evaluation only: one day, Basic Memory and QMD, a small synthetic vault, five hands-on scenarios, and a written gap list. That evaluation is complete in [Scoped evaluation gap list](scoped-evaluation/gap-list.md). The broader benchmark proposal below is historical and remains unapproved pending review of that gap list.

**Recommendation: do not commit to a new general-purpose Obsidian MCP server. Approve a bounded comparative recovery benchmark first.** Markdown memory, read-only retrieval, shared search, provenance checks, and deterministic context selection already have substantial prior art. A useful portfolio outcome could be a benchmark and integration recipe, an upstream contribution, or a thin adapter. A standalone gateway needs evidence that these simpler options cannot satisfy the recovery contract.

The intended user resumes an interrupted project in a fresh agent session and needs its objective, accepted decisions, current state, blockers, and next authorized action, with inspectable evidence. General note search is only one part of that job.

**Evidence boundary.** This Phase 0 is a documentation and limited source-code comparison, including scenario-based contract checks below. No competitor was installed or executed; there are no measured comparative accuracy, latency, or usability results. Primary sources were reviewed on the date above, using available web snapshots of moving branches rather than pinned commits. Product claims are authored/sourced evidence; the explicitly identified code inspection is static/measured evidence of code structure only. Fit judgments are inferred. Undocumented behavior is unknown, not absent. Repository README and its documentation count as one source lineage. This is a bounded sample, not an exhaustive market census.

## Competitive evidence

| Solution | Documented overlap | Consequence for this project |
| --- | --- | --- |
| [MarkusPfundstein mcp-obsidian](https://github.com/MarkusPfundstein/mcp-obsidian) | Obsidian access through its REST API community plugin; note search and editing workflows. | Basic vault connectivity is established. Plugin/API dependency differs from direct local recovery. |
| [DalecB Obsidian Semantic MCP](https://github.com/DalecB/obsidian-semantic-mcp) | Direct filesystem reads, no note-write tools, hybrid search, headings and line ranges; local Ollama embeddings. | Read-only Obsidian retrieval and source locations are not differentiation. Explicit accepted-decision recovery remains unverified. |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | Markdown ownership, projects, graph-based `build_context`, search, recent activity, and Claude session briefings. | Strong reuse candidate for continuity. Test a configured project recovery workflow before replacing it. |
| [QMD](https://github.com/tobi/qmd) | Local document retrieval, collection/path context, metadata filters, line-addressable fetching, and a long-lived HTTP MCP server that shares loaded models. | Shared retrieval efficiency is established. It is a strong retrieval baseline or component, not evidence that accepted-state recovery is solved. |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | Git-backed Markdown wiki, derived index, shared memory, typed cross-agent handoffs, bounded brief injection; native Windows listed as experimental. | Direct overlap with project continuity. Test its import and authority fit; a Git-backed memory wiki does not automatically establish GitHub approval semantics. |
| [Graphiti](https://github.com/getzep/graphiti) | Temporal facts, source episodes, historical queries, hybrid retrieval, and an external graph database. | Provenance and temporal memory are established. Its operating model is broader than the proposed simple Markdown reader. |
| [MCP reference memory server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | Persistent entities, relations, and observations exposed through MCP. | Useful minimal memory comparator; its graph abstraction is not an ordinary Markdown vault recovery contract. |
| [contexts-mcp](https://github.com/mupersega/contexts-mcp) | Persistent context folders, Markdown metadata, filtered search, archival state, and performance benchmark commands. | Project grouping and performance measurement are not novel. Existing folder/naming conventions could impose migration work. |
| [Universal Research MCP](https://github.com/mp-juns/universal-research-mcp) | Evidence-fetch and eligibility workflow, source integrity checks, and published fault/activation studies. | Closest available evidence-verification comparator. Its canonical JSONL ledger differs from the requested authority model; reported results are not independently reproduced here. |
| [ContextNest paper v2](https://arxiv.org/html/2607.02116v2) | Typed Markdown, deterministic selectors, version history, context packs, publication governance, and controlled evaluation. | Strong conceptual overlap. Its linked [repository](https://github.com/PromptOwl/context-nest) returned 404 during this review; installability and current implementation are unknown. |

The ContextNest paper's small controlled experiments do not establish general superiority over semantic retrieval. Its determinism experiment also varies index construction conditions. Universal Research MCP explicitly describes residual semantic failures and dependence on agents invoking the evidence workflow. These limitations make both relevant benchmark references, not performance promises for this product. [ContextNest](https://arxiv.org/html/2607.02116v2), [Universal Research MCP](https://github.com/mp-juns/universal-research-mcp).

## Capability overlap checks

These are static scenario checks, not runtime passes. They test whether the proposed capability has a documented equivalent and identify what execution must resolve.

| Recovery scenario | Evidence and result | Remaining test |
| --- | --- | --- |
| Resume a named project after losing chat history | Basic Memory has project/context tools and briefings; ai-memory describes explicit handoffs. Substantial overlap. | Can each recover all required fields from an existing vault with minimal preparation? |
| Reject evidence changed since indexing | In Universal Research MCP's `memory_fetch_evidence`, inspection found registration checks, a single byte read, SHA-256 comparison, and content withheld on mismatch by default. Mechanism present in inspected source. | Run changed-file, preserved-mtime, deleted-file, and concurrent-edit fixtures. [Source](https://raw.githubusercontent.com/mp-juns/universal-research-mcp/main/universal_research_mcp/server.py). |
| Choose an older accepted GitHub decision over a newer contradictory note | ContextNest describes publication filtering; Universal's architecture makes a ledger canonical. Neither reviewed contract demonstrates this exact GitHub/local-copy policy. | Distinguish an accepted revision, a local draft, and an offline unverified copy. [Architecture](https://raw.githubusercontent.com/mp-juns/universal-research-mcp/main/docs/architecture-deep-dive.md). |
| Two clients recover the same snapshot efficiently | QMD documents a shared HTTP service; ai-memory documents shared server memory. Overlap. | Measure repeated reads, response bytes, consistency, and isolation with two concurrent clients. |
| Recover while a synced local file is changing | Direct local retrieval exists. Atomic multi-file recovery under this scenario is not established by reviewed contracts. | Require a stable snapshot or an explicit incomplete/conflict result; never silently mix revisions. |
| Measure whether the agent actually uses and correctly interprets recovery | Existing projects publish benchmarks; Universal reports activation limitations. Benchmarking alone is not novel. | Measure tool activation separately from tool correctness and final recovery accuracy on the same cases. |

## Candidate unmet needs

**Inferred opportunity, medium confidence:** a small, portable contract for recovering accepted project state from existing Markdown, with source authority, freshness uncertainty, and conflicts visible in one bounded result. This combination was not established across the sampled contracts. It is not a claim that no product implements it.

**Unknown demand:** whether people beyond the project owner repeatedly need this, will maintain a small project manifest, and find existing tools too difficult. Before a product build, ask three prospective users to demonstrate a failed project restart and attempt the same task with a baseline. Treat this as directional discovery, not market validation.

**Potential advantage to test:** lower setup effort and less context sent per correct recovery. Richer governance alone may reduce usability. An arbitrary unstructured vault cannot reliably yield deterministic accepted state without explicit conventions; missing structure must yield partial recovery rather than invented certainty.

## Authority and Obsidian Sync boundaries

GitHub remains authoritative for governed source decisions, through explicitly configured repositories and acceptance records. Local Markdown is readable recovery evidence. A copied decision, newer timestamp, or matching content hash cannot by itself prove current approval. Return the known source revision and verification time; when offline, report that current GitHub status is unverified. Conflicting local material remains visible as a conflict or draft and cannot authorize work.

For a future pilot, read a user-selected local folder already synchronized by Obsidian. Obsidian's documentation distinguishes encryption of remote data from the unencrypted local vault, making local file access a plausible integration route. This does not prove that the local copy is globally current. [Obsidian Sync security](https://help.obsidian.md/Obsidian%20Sync/Security%20and%20privacy).

Keep indexes outside the vault. Do not add a second sync engine or place a live database in Sync. Initial evaluation should use a synthetic vault; a later private pilot can use a selected personal project. No vault path or credentials are needed for this discovery. No GOM mandate changes, SWIM USA access, company corpus, or existing repository changes are part of this project.

## Decision and next approval

Proposed next scope: at most two working days to implement and run a public synthetic benchmark, with a direct Markdown baseline, Basic Memory, QMD, and Universal Research MCP. Screen ai-memory within the same timebox; record setup failure or exclusion transparently. Attempt ContextNest only if a verifiable implementation becomes accessible. Pin revisions and inspect setup behavior before execution; do not install global hooks or point competitors at the real vault.

Use equivalent source facts and disclose conversion/setup effort. First test off-the-shelf configurations, then allow a small documented configuration recipe. If a baseline meets the acceptance criteria, prefer a benchmark plus recipe. If a small upstream change or adapter closes the gap, prefer that. Consider a standalone gateway only after the best configured baseline fails material requirements and the user separately approves a scoped design.

The next scope authorizes evaluation tooling only if approved. Product implementation, repository publication, and real-vault integration remain separate decisions. This brief and the adjacent acceptance criteria are discovery deliverables, not new organizational mandates.
