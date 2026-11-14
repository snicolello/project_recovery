# Project Recovery

[![CI](https://github.com/snicolello/project_recovery/actions/workflows/ci.yml/badge.svg)](https://github.com/snicolello/project_recovery/actions/workflows/ci.yml)

Recover a project's governing state from Markdown notes and GitHub, read-only, with verified authority and inspectable evidence.

A fresh agent session that resumes an interrupted project needs five things: the objective, the accepted decisions, the current state, the blockers, and the next authorized action. Searching notes is only part of that job. This project defines the recovery contract, ships synthetic fixtures and scenarios to test it, and builds a thin verification and assembly layer over an existing retrieval engine ([QMD](https://github.com/tobi/qmd)) rather than a new one.

## Example

Given a folder of ordinary project notes, the recipe returns one JSON packet. Every recovered line carries a receipt (source file, line span, content hash), and anything the notes do not establish is reported as `unknown` instead of being guessed. Abridged from the packet's `fields` for the synthetic Atlas project (hashes shortened):

```json
{
  "objective": {
    "status": "established",
    "items": [{
      "text": "Objective: Build an offline field-report queue for one laptop.",
      "receipt": { "source": "atlas/Project.md", "span": [9, 9], "content_sha": "480098ea...", "generation": "qmd-2.8.3:d3096a01a1830271" }
    }]
  },
  "accepted_decisions": {
    "status": "unknown",
    "basis": "verified acceptance records only",
    "reason": "no decision has verified acceptance evidence; 2 candidate(s): not_referenced 1, unavailable 1"
  },
  "decision_candidates": {
    "decisions": [{
      "title": "Queue Decision",
      "local_status": "accepted",
      "authority_state": "unverified",
      "verification": { "transport": "offline", "result": "unavailable" }
    }]
  }
}
```

The note says the decision is accepted, but offline that is only a claim, so it stays a candidate. Run the same command with the acceptance record available and the decision moves to `accepted_decisions` as `verified`, bound to the SHA-256 of the note's exact bytes. [`docs/quickstart.md`](docs/quickstart.md) walks through both runs in about ten minutes.

## What this demonstrates

- **A read-only recovery path.** The recipe exposes read tools only: no write, edit, move, delete or shell capability. Changes to notes happen outside it, through ordinary governed git and filesystem actions. The scenario suite checks that every fixture note hashes identically before and after it runs.
- **Verified authority, with an explicit unverified state.** A note that calls itself accepted is only a decision candidate. A decision reaches `accepted_decisions` only when an approver's GitHub acceptance record is read, serially, and binds to the SHA-256 of the note's exact bytes. Offline, the decision stays `unverified` and the packet says so, rather than guessing.
- **Deterministic requery validation.** `validate` re-derives a received packet from the source bytes at its recorded index generation, re-reads every acceptance record and compares value by value; edited, deleted or added content is rejected. A pass shows the packet is what the deterministic assembler produces from those bytes, not that the notes are true.
- **Adversarial scenarios.** The offline restart scenarios scored by `scripts/run_scenarios.py` include instructions planted in a note, cross-project bleed, and approval text that is quoted, negated, fenced, in a merge or commit message, or written by a non-approver. None of these binds.
- **Measured before building more.** The predeclared Stage A measurement asked how much choosing a better search query could save. Its figure of record is an 8.629% best-in-hindsight estimated token reduction (packets plus fetches) against the control queries, across 37 eligible synthetic comparisons. Once timestamps were normalized, the recovered fields were identical in every eligible comparison; the savings came from smaller echoed search results. The figure is limited to frozen query lists on synthetic fixtures. It did not reach the 15% reference, which was never an acceptance threshold. The planned Librarian (R3: a local language model that would run retrieval and return a packet for deterministic checking) is deferred, to be reopened only if live evidence shows recovered content depending on the query or token cost becomes material. Details: [`evidence/r3-stage-a/README.md`](evidence/r3-stage-a/README.md).

## Status

As of 2026-10-21. In short: the recipe works end to end and passes every gate on synthetic fixtures, and it has had one bounded live run. It is not yet established as ready for real use.

- **Accepted:** releases R0, R1 and R2, and reliance gate [#6](https://github.com/snicolello/project_recovery/issues/6) (the check that makes `validate` strong enough to rely on a packet received from elsewhere).
- **Accepted as a bounded pilot:** R4. One live, read-only run on one owner-selected folder showed that refresh, assembly and validation work outside the fixtures. It does not show that recovery is complete.
- **Deferred without acceptance:** R3, the Librarian.
- **Fixed since the pilot, on synthetic evidence only:** the pilot found two blockers to real use, and both are now closed as completed at synthetic scope. Neither fix has been run against a live folder.
  - [#16](https://github.com/snicolello/project_recovery/issues/16): refresh failed under QMD 2.8.3 on a blank note or a collection with no indexable notes.
  - [#17](https://github.com/snicolello/project_recovery/issues/17): the authority mapping expected a YAML frontmatter field that ordinary notes may not carry. A manifest can now name a labelled line instead.
- **Open:** [#23](https://github.com/snicolello/project_recovery/issues/23) holds the remaining pilot and real-use readiness decisions, and [#26](https://github.com/snicolello/project_recovery/issues/26) tracks a difference between the folders QMD skips and the folders refresh scans. All live capture and recovery runs are on hold.
- **Not started:** R5 (public v1.0).

Try the recipe on the synthetic fixtures: [`docs/quickstart.md`](docs/quickstart.md). Optional [last-checked evidence](docs/last-checked-evidence.md) retains historical approval context without establishing current acceptance offline. Current baseline: [`STATE.md`](STATE.md).

## Why not a new tool

A one-day hand trial (2026-10-10) ran two existing tools, Basic Memory 0.23.2 and QMD 2.8.3, against nine synthetic notes and five restart scenarios. Both retrieved a prepared recovery note, respected explicit project scope, and did not invent missing content. Neither verified GitHub authority, both served stale content without saying so, and neither produced a uniform evidence receipt. The gap is a workflow above retrieval, not retrieval itself. Details: [`docs/discovery/gap-list-2026-10-10.md`](docs/discovery/gap-list-2026-10-10.md).

## Layout

| Path | Contents |
|---|---|
| `docs/recovery-contract.md` | The product contract: recovery fields, evidence receipt, authority and freshness states, read-only rules, acceptance tests. |
| `docs/releases.md` | Public record of each release gate: decision date, what was accepted, stated limits. |
| `docs/discovery/` | Phase 0 decision brief, MVP (minimum viable product) acceptance criteria, and the hand-trial gap list. |
| `fixtures/synthetic-vault/` | Sixteen fictional Markdown notes across three projects (Atlas, Beacon, and Cobalt for R2's adversarial scenario). SHA-256 digests in `fixtures/synthetic-vault-hashes.json`. |
| `fixtures/github-snapshots/` | Fictional GitHub REST responses on the reserved `github.example.test` domain, read by the offline snapshot verifier. |
| `fixtures/borrow-notes/` | Seven fictional decision notes, not indexed. S8 copies them into a throwaway vault to show that approval text which is quoted, negated, fenced, in a merge or commit message, or written by a non-approver never binds. |
| `fixtures/scenario-plan.json` | Eight restart scenarios with expectations written before execution. |
| `manifest/` | Manifest schema, the fixture and scenario manifests (with their authority policies), and pinned tool versions. |
| `skills/project-recovery/` | The recipe as an agent skill: `SKILL.md`, the pinned QMD lockfile, and stdlib Python scripts. |
| `scripts/run_scenarios.py` | Runs the restart scenarios offline and scores every gate; exits non-zero on any failure. `scripts/live_gh_smoke.py` is an optional live check of the GitHub verifier. |
| `evidence/scoped-evaluation-2026-10-10/` | Executed tool responses, source-integrity checks, versions, tool schemas, MCP (Model Context Protocol) request logs, and the harness scripts. Workspace paths are replaced with `<workspace>`. |
| `evidence/` (other folders) | Reliance gate #6, Stage A measurement, synthetic transition rehearsal, and R4 pilot aggregates. |
| `.github/workflows/ci.yml` | CI: fixture hashes, pinned QMD install, all scenarios and unit tests on Ubuntu and Windows. |

## Roadmap

| Release | Deliverable | State |
|---|---|---|
| R0 | Contract, fixtures, discovery record. | Accepted |
| R1 | Project manifest and a read, refresh, assemble recipe over QMD, shipped as an agent skill; passes the five scenarios. | Accepted |
| R2 | Serial GitHub acceptance verification with an explicit "unverified" state offline; index generation in every result; three more scenarios (concurrent edit, budget stress, adversarial cross-project). | Accepted (bounded); reliance gate #6 accepted |
| R3 | Librarian: a local model takes a bounded field list, runs retrieval, and returns a packet that a deterministic verifier checks span by span. | Deferred, not accepted |
| R4 | Pilot against a user-selected Obsidian-synced folder, indexes outside the vault. | Accepted as a bounded mechanics pilot; at acceptance, real use blocked by [#16](https://github.com/snicolello/project_recovery/issues/16) and [#17](https://github.com/snicolello/project_recovery/issues/17), both since closed at synthetic scope |
| R5 | Public v1.0 with a 15-minute quickstart on Windows and Linux, uninstall steps, stated limitations, and an upstream QMD issue or PR. | Not started |

Each release is gated by an owner ruling. The public summary of every gate, with its date, what was accepted and its stated limits, is in [`docs/releases.md`](docs/releases.md). Detailed coordination records live in the owner's private project hub: links to `stephen-project-hub` in this repository open only for the owner, and everything an outside reader needs is in the public records above.

## How this was built

The code and documents were written with AI coding agents under the owner's direction, and the commits carry the agents' co-author trailers. The owner sets scope, rules on every release gate and merges every pull request. Changes land through pull requests, with review rounds before merge and CI on Ubuntu and Windows. [`docs/usage/outcomes.jsonl`](docs/usage/outcomes.jsonl) records, per ticket, the model used, the review rounds and the findings.

## Security posture

Read-only recovery surface. Synthetic fixtures only in this repository; the R4 pilot's real-folder evidence is published as aggregates only. Third-party tools pinned to exact versions and installed in isolated environments. Instructions found inside notes are treated as data. No personal vault, work or credential material anywhere in this repository.

## Licence

Apache-2.0. Tools evaluated here keep their own licences; Basic Memory is AGPL-3.0 and none of its code is included.
