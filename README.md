# Project Recovery

Recover a project's governing state from Markdown notes and GitHub, read-only, with verified authority and inspectable evidence.

A fresh agent session that resumes an interrupted project needs five things: the objective, the accepted decisions, the current state, the blockers, and the next authorized action. Searching notes is only part of that job. This project defines the recovery contract, ships synthetic fixtures and scenarios to test it, and builds a thin verification and assembly layer over an existing retrieval engine ([QMD](https://github.com/tobi/qmd)) rather than a new one.

## Status

Release R1 is merged: a manifest and a read-only read, refresh, assemble recipe over pinned QMD 2.8.3 (lexical only), shipped as the agent skill in `skills/project-recovery/`. Release R2 (authority and freshness) is in review under [stephen-project-hub#119](https://github.com/snicolello/stephen-project-hub/issues/119): frontmatter-accepted notes are decision candidates, `accepted_decisions` holds only decisions whose GitHub acceptance record was read and verified serially (offline they stay unverified, and the packet says so), every packet states its index generation, and scenarios S1 to S8 pass offline with zero unsupported assertions. Try it: [`docs/quickstart.md`](docs/quickstart.md). The release roadmap and owner rulings live on the coordination Epic, [stephen-project-hub#113](https://github.com/snicolello/stephen-project-hub/issues/113). Current baseline: [`STATE.md`](STATE.md).

## Why not a new tool

A one-day hand trial (2026-10-10) ran two existing tools, Basic Memory 0.23.2 and QMD 2.8.3, against nine synthetic notes and five restart scenarios. Both retrieved a prepared recovery note, respected explicit project scope, and did not invent missing content. Neither verified GitHub authority, both served stale content without saying so, and neither produced a uniform evidence receipt. The gap is a workflow above retrieval, not retrieval itself. Details: [`docs/discovery/gap-list-2026-10-10.md`](docs/discovery/gap-list-2026-10-10.md).

## Layout

| Path | Contents |
|---|---|
| `docs/recovery-contract.md` | The product contract: recovery fields, evidence receipt, authority and freshness states, read-only rules, acceptance tests. |
| `docs/discovery/` | Phase 0 decision brief, MVP (minimum viable product) acceptance criteria, and the hand-trial gap list. |
| `fixtures/synthetic-vault/` | Sixteen fictional Markdown notes across three projects (Atlas, Beacon, and Cobalt for R2's adversarial scenario). SHA-256 digests in `fixtures/synthetic-vault-hashes.json`. |
| `fixtures/github-snapshots/` | Fictional GitHub REST responses on the reserved `github.example.test` domain, read by the offline snapshot verifier. |
| `fixtures/borrow-notes/` | Five fictional decision notes, not indexed, which S8 copies into a throwaway vault to show that quoted, negated, fenced or non-approver approval text never binds. |
| `fixtures/scenario-plan.json` | Eight restart scenarios with expectations written before execution. |
| `manifest/` | Manifest schema, the fixture and scenario manifests (with their authority policies), and pinned tool versions. |
| `skills/project-recovery/` | The recipe as an agent skill: `SKILL.md`, the pinned QMD lockfile, and stdlib Python scripts. |
| `scripts/run_scenarios.py` | Runs S1 to S8 offline and scores every gate; exits non-zero on any failure. `scripts/live_gh_smoke.py` is an optional live check of the GitHub verifier. |
| `evidence/scoped-evaluation-2026-10-10/` | Executed tool responses, source-integrity checks, versions, tool schemas, MCP (Model Context Protocol) request logs, and the harness scripts. Workspace paths are replaced with `<workspace>`. |

## Roadmap

| Release | Deliverable |
|---|---|
| R0 | Contract, fixtures, discovery record (this commit). |
| R1 | Project manifest and a read, refresh, assemble recipe over QMD, shipped as an agent skill; passes the five scenarios. |
| R2 | Serial GitHub acceptance verification with an explicit "unverified" state offline; index generation in every result; three more scenarios (concurrent edit, budget stress, adversarial cross-project). |
| R3 | Librarian: a local model takes a bounded field list, runs retrieval, and returns a packet that a deterministic verifier checks span by span. |
| R4 | Pilot against a user-selected Obsidian-synced folder, indexes outside the vault. |
| R5 | Public v1.0 with a 15-minute quickstart on Windows and Linux, uninstall steps, stated limitations, and an upstream QMD issue or PR. |

Each release is gated by an owner ruling on the Epic.

## Security posture

Read-only recovery surface. Synthetic fixtures only until R4. Third-party tools pinned to exact versions and installed in isolated environments. Instructions found inside notes are treated as data. No personal vault, work or credential material anywhere in this repository.

## Licence

Apache-2.0. Tools evaluated here keep their own licences; Basic Memory is AGPL-3.0 and none of its code is included.
