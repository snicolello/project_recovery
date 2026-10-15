# Recovery contract

Version 0.1, release R0, 2026-10-11. Governs every later release. Changes to this contract are owner rulings recorded on [stephen-project-hub#113](https://github.com/snicolello/stephen-project-hub/issues/113). Amended 2026-10-14 under the owner ruling on [project_recovery #16](https://github.com/snicolello/project_recovery/issues/16#issuecomment-6177400662): blank notes and empty collections (section 4). Amended 2026-10-15 under the [owner ruling on Epic #113](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6198390697): the governing-record mapping, including stricter frontmatter behavior (section 4), following the labelled-line choice on [project_recovery #17](https://github.com/snicolello/project_recovery/issues/17#issuecomment-6177401293).

This contract derives from two existing records: the hub's fresh-session recovery protocol (six acceptance items for a reader with no conversation history) and the Phase 0 MVP (minimum viable product) acceptance criteria in `discovery/mvp-acceptance-criteria.md`. Where they differ, this document governs.

## 1. The job

Given a project identifier and a fixed source snapshot, return a bounded **recovery packet** that a fresh agent can act on without reconstructing private conversation history. Every material field cites evidence or says `unknown`. Nothing in the packet authorizes work by itself; it reports what is authorized and by whom.

## 2. Recovery fields

| Field | Meaning | Must cite |
|---|---|---|
| `objective` | What the project is trying to achieve now. | Yes |
| `authority` | The single record that governs the project's current position, and who may change it. | Yes |
| `accepted_decisions` | Decisions with a verified acceptance record. Superseded and draft decisions are listed separately with their status. | Yes, per decision |
| `current_state` | What is done and verified, as distinct from reviewed, proposed or merged. | Yes |
| `blockers` | Named dependencies or decisions that stop authorized work. | Yes |
| `next_action` | One action within current authority, or an explicit stop. | Yes |
| `conflicts` | Contradictions between sources that the packet could not resolve, with the implicated evidence. | Yes |
| `unknowns` | Mandatory fields that could not be established. | n/a |

A packet that cannot fill a mandatory field returns `unknown` for it. It never fills the field from the newest note, the highest-ranked search result, or model inference.

## 3. Evidence receipt

Each cited field carries one or more receipts:

```
source:      path or URI relative to a declared root
span:        start line, end line (1-indexed, inclusive)
content_sha: SHA-256 of the exact cited bytes
generation:  the index or snapshot generation the read came from
revision:    source revision (git commit, GitHub node id) where known, else unknown
observed_at: when the bytes were read
```

The cited text must validate against `content_sha` from the same bytes that were hashed. A receipt that fails validation makes the field `unknown` and records a `conflict`. A missing source produces `unknown`, never a fabricated locator.

## 4. Authority and freshness states

**Authority.** Only configured acceptance records establish acceptance: a GitHub issue comment, PR review or merge in an allowlisted repository, identified by revision. Local frontmatter such as `status: accepted`, a URL in a note, a matching hash or a newer timestamp can select a candidate but cannot prove approval. Each decision carries one of:

| State | Meaning |
|---|---|
| `verified` | The acceptance record was read from GitHub at `verified_at`, serially, with its revision recorded. |
| `unverified` | A record is referenced but could not be read now (offline, rate-limited, permission). Known provenance is kept; the packet says current status is unverified. |
| `local_only` | The claim exists only in local notes. It is a draft or copy, never an accepted decision. |
| `superseded` | A later verified record replaces it. |

Verification requests run serially. Concurrent GitHub GraphQL requests are an untested cause of earlier failures and are avoided by design.

**Governing record.** The `authority` field cites the one line of the configured governing record that states its status, under exactly one configured mapping: a frontmatter key, or a body line starting with a configured label (for example `- **Status:**`). Configuring both is refused, and a label never falls back to frontmatter. A line inside a fenced code block or an HTML comment is an example, not a statement, and never matches. No matching line, more than one, or a cited value that is empty or starts with `UNKNOWN` makes `authority` `unknown`; matching lines are kept as evidence, and more than one is also a conflict. The governing record is a local claim (`local_only`): reading it never establishes a decision's acceptance.

**Freshness.** Freshness is eventually consistent and is stated, not assumed. The packet separates `file_mtime`, `observed_at`, `generation` and `verified_at`. Before assembly the recipe refreshes the index and records the generation; a read whose generation differs from the one recorded is `incomplete`, and the packet says so. Byte equality means integrity, not currency or approval. Both checks are the orchestrator's responsibility at session start.

**Last-checked evidence (option 2, [owner ruling, 2026-10-15](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6201195668)).** A separately captured record may retain what was previously verified against GitHub, the original verification time, approval revision and actor, exact note digest and verification policy. Optional historical replay uses an operator-controlled bundle and a separately retained digest; this establishes integrity relative to that trust root, not GitHub authenticity. Historical context is separate from current acceptance and never promotes offline candidates into `accepted_decisions`. The original `last_checked_at` is not refreshed by replay; `replayed_at` names the local read. Missing, malformed, altered or wrong-project evidence yields no historical entries; changes to notes, references or policy are reported. Later GitHub changes remain unknown until a separately authorized fresh check. Capture writes are outside source roots and the recovery read-tool surface. [Workflow and limits](last-checked-evidence.md).

**Blank notes and empty collections.** The generation covers every Markdown file in scope. A file the engine does not index (for QMD 2.8.3, one whose text is empty after JavaScript's `trim()`, such as an empty, whitespace-only or byte-order-mark-only file) is **present, not indexable**: its hash is kept in the generation record, it is never cited, and a change to it still makes a packet `incomplete`. Refresh fails unless the engine serves exactly the indexable files, byte for byte, and fails if a declared root does not exist as a directory. A declared collection the engine does not list is **verified empty** only when its root exists as a directory, the scan finds no indexable file in it and the engine serves nothing for it; every field is then `unknown`.

## 5. Read-only and isolation rules

- The recovery path exposes no write, edit, move, delete or shell capability. Agents that may change notes do so through governed git and filesystem actions, outside this path.
- Source roots are an explicit allowlist. Path traversal and symlink or junction escape are rejected. A same-named project outside scope contributes nothing.
- Derived indexes and caches live outside every source root.
- Instructions found inside notes, search results or tool output are data. A packet records them as content and never acts on them.
- Fixture source files hash identical before and after every run.

## 6. Bounded output

Default packet limit: 4,000 tokens under a named tokenizer. Truncation is reported, omitted items are counted, and `conflicts` and `unknowns` are never dropped to fit. Fetching cited detail is a separate, explicit call.

## 7. Acceptance tests

Each release passes the scenarios named on its hub ticket. The current set is `fixtures/scenario-plan.json` (S1 to S5); R2 adds S6 concurrent edit, S7 budget stress and S8 adversarial cross-project instructions.

| Requirement | Pass condition |
|---|---|
| Recovery completeness | Every answerable mandatory field is filled correctly in every scenario. |
| Unsupported assertions | Zero material assertions without a validating receipt. |
| Abstention | Every deliberately missing or contradictory field is `unknown` or in `conflicts`; no answerable field is wrongly abstained. |
| Authority | A `local_only` or newer draft never outranks a `verified` decision; offline runs label authority `unverified` and keep provenance. |
| Freshness | A changed file after indexing yields either the new bytes or an `incomplete` packet that names the generation gap. Never silent stale content. |
| Isolation | Atlas scope returns no Beacon content and the reverse; embedded instructions in notes are reported, not followed. |
| Repeatability | Fixed bytes, policy, version and budget yield identical ordered receipts and canonical packet content across 20 runs, including an index rebuild. |
| Source integrity | Fixture hashes match before and after. |
| Usability (R5) | A reader outside the project completes the sample recovery in 15 minutes on Windows and one Linux environment, from the quickstart alone. |

## 8. Build-or-reuse rule

Prefer configuring the existing engine. Prefer a thin adapter or an upstream change over new retrieval code. Propose new retrieval machinery only when a scenario cannot be passed any other way and the owner approves a scoped design. A reproducible negative result is a valid outcome and is published as such.
