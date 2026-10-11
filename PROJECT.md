# Project Recovery

- Project code: `RECOVERY`
- Trust zone: `Personal`
- Repository: https://github.com/snicolello/project_recovery
- Portfolio board: https://github.com/users/snicolello/projects/1
- Coordination issue: https://github.com/snicolello/stephen-project-hub/issues/113 (Epic; releases R0 to R5 are its child tickets)
- Licence: Apache-2.0 (`LICENSE`)

## Outcome

Give a fresh agent session one documented, read-only way to recover a project's governing state (objective, accepted decisions, current state, blockers, next authorized action) from Markdown notes plus GitHub, with verified authority, stated freshness and inspectable evidence. Reuse an existing retrieval engine (QMD) and build only the verification and assembly layer above it. Publish the contract, fixtures, recipe and evidence as open-source portfolio work.

## Boundaries

- In scope: the recovery contract; a synthetic Markdown fixture vault and restart scenarios; a project manifest and a read, refresh, assemble recipe over QMD; serial GitHub acceptance verification with an explicit "unverified" state when offline; a minimal evidence receipt; an optional local-model Librarian role with a deterministic verifier; upstream issues or PRs to QMD; a quickstart an outside reader can run in 15 minutes.
- Out of scope: a standalone retrieval engine or general-purpose Obsidian MCP (Model Context Protocol) server; writes, edits, moves or deletes through the recovery path (those go through governed git and filesystem actions); real personal-vault content before release R4; Work-zone, company or credential material of any kind; vendored AGPL (GNU Affero General Public License) code.
- Human decision boundaries: each release gate (R0 to R5) is an owner ruling recorded on the Epic; pointing any tool at a real Obsidian vault; publishing anything derived from non-synthetic notes; any new repository, dependency with network access, or hook installed outside this repository.

## Verification

A release is accepted when its gate on hub Epic #113 is recorded with evidence: the relevant scenarios in `fixtures/scenario-plan.json` pass with zero unsupported material assertions, every cited span is verified against the fixture bytes, source files hash identical before and after every run, and an independent review per the Agent Skills review guide has run on the release PR.
