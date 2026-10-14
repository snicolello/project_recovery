# Release record

Every release of Project Recovery is gated by a ruling from the owner (Stephen). This page is the public summary of each gate: what was decided, when, what was accepted and the limits stated with it. Detailed coordination records, review threads and the rulings themselves live in the owner's private project hub; the summaries here are derived from [`STATE.md`](../STATE.md), the [recovery contract](recovery-contract.md), the evidence committed in this repository, and, for the 2026-10-14 rulings on #16 and #17, the owner-ruling comments recorded publicly on [#16](https://github.com/snicolello/project_recovery/issues/16) and [#17](https://github.com/snicolello/project_recovery/issues/17).

As of 2026-10-14.

| Release | State | Decision date |
|---|---|---|
| [R0](#r0-contract-fixtures-and-discovery) | Accepted | 2026-10-11 |
| [R1](#r1-manifest-and-read-only-recipe-over-qmd) | Accepted | 2026-10-11 |
| [R2](#r2-verified-authority-and-stated-freshness) | Accepted, bounded | 2026-10-12 |
| [Reliance gate #6](#reliance-gate-6-validate-re-derives-received-packets) | Accepted | 2026-10-12 |
| [R3](#r3-librarian-deferred) | Deferred, not accepted | 2026-10-13 |
| [R4](#r4-read-only-mechanics-pilot) | Accepted, bounded mechanics pilot | 2026-10-14 |
| [R5](#r5-public-v10-not-started) | Not started | — |

## R0: contract, fixtures and discovery

- **Gate:** owner ruling before any implementation.
- **Accepted:** the [recovery contract](recovery-contract.md) (recovery fields, evidence receipt, authority and freshness states, read-only rules); nine synthetic fixture notes with SHA-256 digests; five restart scenarios with expectations written before execution; the [discovery record](discovery/) and the [hand-trial evidence](../evidence/scoped-evaluation-2026-10-10/) comparing two existing tools.
- **Limits:** fixtures are fictional; no real notes are in scope.

## R1: manifest and read-only recipe over QMD

- **Gate:** the five R0 scenarios pass through the recipe; owner ruling; merged as [PR #1](https://github.com/snicolello/project_recovery/pull/1).
- **Accepted:** a project manifest and a read, refresh, assemble recipe over pinned [QMD](https://github.com/tobi/qmd) 2.8.3 (lexical search only), shipped as the agent skill in [`skills/project-recovery/`](../skills/project-recovery/), with a [quickstart](quickstart.md).
- **Limits:** every decision is `local_only`; GitHub verification arrives in R2.

## R2: verified authority and stated freshness

- **Gate:** scenarios S1 to S8 pass offline with zero unsupported assertions; repeated independent reviews and their remediations; owner ruling; merged as [PR #5](https://github.com/snicolello/project_recovery/pull/5).
- **Accepted:** a serial GitHub acceptance verifier with offline, snapshot and live transports. A note marked accepted is only a decision candidate; it reaches `accepted_decisions` only when an approver's acceptance record was read and binds to the SHA-256 of the note's exact bytes. Offline, decisions stay `unverified` and the packet says so. Every packet states its index generation. Three further scenarios: concurrent edit (S6), budget stress (S7) and adversarial cross-project content (S8).
- **Limits:** accepted for synthetic fixtures and for packets produced directly by the deterministic assembler. Packets modified after assembly or produced by a model were outside the trusted boundary until reliance gate #6.

## Reliance gate #6: validate re-derives received packets

- **Gate:** the R2 review exceptions resolved and independently re-reviewed; owner acceptance of [PR #8](https://github.com/snicolello/project_recovery/pull/8); [issue #6](https://github.com/snicolello/project_recovery/issues/6) closed.
- **Accepted:** `validate` checks a received packet against an exact structural allowlist, re-derives it from the vault bytes at the recorded generation, reads every acceptance record again and compares value by value. Only wall-clock times are exempt. Evidence: [`evidence/reliance-gate-2026-10-12/`](../evidence/reliance-gate-2026-10-12/).
- **Limits:** a pass means the packet is exactly what the deterministic assembler produces from those bytes. It does not mean the notes are true, or say who produced the packet. Packet mode (`--hits packet`) is not equivalent to requery: hit selection and order remain claims made by the packet. Vault bytes, snapshot files and approvers' GitHub accounts remain trust roots.

## R3: Librarian (deferred)

- **Planned:** a local language model (the Librarian) takes a bounded field list, runs retrieval, and returns a packet that a deterministic verifier checks span by span.
- **Decision:** deferred without acceptance. R3 was waived only as R4's predecessor.
- **Done before deferral:** Stage A, a predeclared measurement of how much query choice could reduce estimated token cost ([`evidence/r3-stage-a/`](../evidence/r3-stage-a/README.md), merged as [PR #12](https://github.com/snicolello/project_recovery/pull/12)). Its figure of record is an 8.629% best-in-hindsight estimated token reduction (packets plus fetches) against the R2 control queries, across 37 eligible synthetic comparisons. The recovered fields were identical in all 37 once timestamps were normalized; the savings came from smaller echoed search material. The 15% reference was not met and was never an acceptance threshold. A separate agent session audited the arithmetic and evidence.
- **Limits:** the figure holds only within the frozen query lists on synthetic fixtures; it does not bound other query strategies. The model trial (Stage B) was not run.
- **Re-entry:** only if pilot evidence shows recovered content depending on the query, or token cost becomes material.

## R4: read-only mechanics pilot

A mechanics pilot shows the read-only recipe working end to end on a live folder; it does not measure recovery quality.

- **Gate:** "read-only enforcement demonstrated; owner approval". Accepted 2026-10-14 as a bounded mechanics pilot.
- **Accepted:** one live run against a single owner-selected folder completed refresh, assembly and `validate --hits requery` with the result `equal_to_rederived` and zero validation failures. Exactly four read tools were advertised and all observed calls stayed within the allowlist. Source, synthetic fixtures and default tool home were unchanged before and after. Aggregate evidence only: [`evidence/r4-pilot/run-004/`](../evidence/r4-pilot/run-004/README.md). Advance preparation: the [synthetic transition rehearsal](transition-rehearsal.md), merged as [PR #11](https://github.com/snicolello/project_recovery/pull/11).
- **Limits:** the source was one agent-authored starter note, not the owner's own notes, so the run shows mechanics, not representative recovery. Authority and accepted decisions stayed `unknown`; recovery completeness is false. Read-only enforcement is client-side, backed by before/after hashes; there is no operating-system sandbox or network isolation. Acceptance is not readiness for real use. At acceptance, real use was blocked by two issues; each issue has its current status:
  - [#16](https://github.com/snicolello/project_recovery/issues/16): refresh failed under QMD 2.8.3 on a blank note or a collection with no indexable notes. The owner authorized a fix on 2026-10-14; see #16 for its status.
  - [#17](https://github.com/snicolello/project_recovery/issues/17): the authority mapping expects a YAML frontmatter field that ordinary notes may not carry. The owner chose a configurable labelled-line mapping on 2026-10-14; see #17 for its status.

## R5: public v1.0 (not started)

- **Planned gate:** owner ruling plus outside-reader usability evidence: a 15-minute quickstart on Windows and Linux, uninstall steps, stated limitations, and an upstream QMD issue or PR.
- **Current position:** not started. The prepared QMD upstream report has not been sent and needs separate owner approval.
