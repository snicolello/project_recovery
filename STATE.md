# Project State

- Project: Project Recovery (`RECOVERY`), Personal trust zone.
- Status: R2 and reliance gate #6 accepted. R3 Stage A and synthetic advance preparation authorized; all overnight PRs remain proposed and unmerged.
- As of: 2026-10-12 evening, America/New_York; prepared for the 2026-10-13 morning review. Accepted `main`: `7e73ca4b77fe68bfdafda5c5a53ef5a0e2032a28` (PRs #8 and #9 merged).
- Authority: Stephen's [overnight ruling](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6136264847), recorded before execution, supersedes the former "R3 not authorized" position only within its preparation scope.
- Execution record: [hub #126](https://github.com/snicolello/stephen-project-hub/issues/126), open for owner review. [Epic #113](https://github.com/snicolello/stephen-project-hub/issues/113) remains the release authority.
- Objective: reach a usable transition when the evidence and explicit owner gates support it.
- Next action: owner review of the [overnight approval package](docs/overnight-approval-2026-10-13.md); no merge, release acceptance, model trial, real-vault access or transition follows automatically.

## Accepted baseline

R0, R1, R2 and the #6 reliance fix are accepted on `main`. [PR #8](https://github.com/snicolello/project_recovery/pull/8) merged the reliance fix; [#6's final closeout](https://github.com/snicolello/project_recovery/issues/6#issuecomment-6136067672) records acceptance and closure. [PR #9](https://github.com/snicolello/project_recovery/pull/9) reconciled that baseline. No overnight branch changes this accepted status until the owner rules.

The recovery path is read-only. A consumer uses only the validator's returned re-derived packet after successful `validate --hits requery`. Exact structural checks and fresh re-derivation address the earlier F1-F3 reliance exceptions. Packet mode retains narrower guarantees: hit selection, order, titles and omitted-hit count are packet claims; deleted omitted-hit traces are not detected; queries that dropped out-of-scope results require requery. Wall-clock fields are format checked. Vault bytes, snapshot files and approvers' GitHub accounts remain trust roots; validation does not prove submitter provenance.

Accepted #6 evidence remains in `evidence/reliance-gate-2026-10-12/` and its closeout: 126 unit tests run (125 passed, one platform-permission skip), 184/184 actual-QMD checks including 20 repeatability iterations and rebuild, unchanged fixtures and an independently reviewed allocation fix. These historical results are not evidence of a model trial.

## Proposed overnight work

| Package | Review location | Boundary |
|---|---|---|
| Stage A fixed-query measurement and reproducible evidence | [PR #12](https://github.com/snicolello/project_recovery/pull/12) | Offline synthetic measurement; 15% is a reference, not an acceptance threshold |
| Deterministic Librarian proposal validation, rejection and abstention scoring; runtime approval proposal | [PR #10](https://github.com/snicolello/project_recovery/pull/10) | Test doubles and actual QMD; no product model run or download |
| Synthetic transition rehearsal, isolation/read-only checks, recovery procedure and unsent QMD report | [PR #11](https://github.com/snicolello/project_recovery/pull/11) | Advance R4/R5 preparation; no real-vault pilot or release acceptance |

The approval package records exact tested and published revisions, failed attempts, independent reviews and remaining validation. Each code branch starts from accepted `7e73ca4`; none assumes another branch has passed its owner gate. This state reconciliation is itself a proposed documentation change.

## Remaining gates and limits

- Owner review and merge decisions for every proposed PR, then an explicit R3 disposition. Stage A alone does not accept the full Librarian release.
- Any local-model trial needs its own ruling naming the pinned model/runtime and bounded trial. The prepared proposal grants no download, installation or inference authority.
- R4 requires its release gate and explicit approval of a named Personal vault/source scope. No real vault has been accessed or selected.
- R5 still requires a reader outside the project to complete the sample recovery from the quickstart alone within 15 minutes on Windows and one Linux environment. Maintained-install and dependency-free WSL checks do not satisfy that criterion.
- No later release ticket was opened. No deployment, upstream submission, access change, spending or actual transition is authorized by preparation evidence.

## Read first

- `PROJECT.md`: project identity and boundaries.
- `docs/recovery-contract.md`: unchanged product contract and acceptance criteria.
- `docs/overnight-approval-2026-10-13.md`: current review package and resumable checkpoint.
- `skills/project-recovery/SKILL.md` and `docs/quickstart.md`: accepted recovery procedure and limitations.
- `fixtures/scenario-plan.json`, `fixtures/synthetic-vault-hashes.json`: synthetic scenarios and byte-integrity checks.

The cancelled comparative 40-case benchmark remains deferred; re-entry requires a later release decision that cannot be made without it.
