# Scoped evaluation evidence

Start with [the gap list](gap-list.md). The approved scope was one day, two tools, a small synthetic vault, and five hands-on scenarios. The 40-case benchmark remains unapproved.

## Evidence files

- `scenario-plan.json`: the five expectations written before scenario execution.
- `synthetic-vault/`: nine original Markdown notes across Atlas and Beacon. These are fictional. The authority link uses a reserved test domain and is not a real GitHub record.
- `initial-vault-hashes.json`: SHA-256 digests of the original note bytes.
- `basic-memory-results.json`: first run, including cold-index behavior, accepted-status filtering, the source edit, and missing evidence.
- `basic-memory-ready-recheck.json`: follow-up S1/S2 results from the populated index, plus the default-project configuration remedy. It supplements rather than replaces the original results.
- `qmd-results.json`: five scenarios, including reads before/after the file edit and after explicit refresh.
- `basic-memory-source-check.json` and `qmd-source-check.json`: source hashes before and after each run; only the intentional runbook mutation should differ.
- `versions.json`, package metadata, dependency manifests and tool schemas: the actual tested package versions and interfaces.
- `logs/`: MCP request/response records and setup diagnostics.

These records contain local workspace paths and synthetic content. They have not been published. Keep private-vault content out of any future public benchmark.

## Method

Search queries were `Atlas project`, `queue`, `restart`, and `rollout`; every search specified a project or collection. Search used Basic Memory `search_notes(search_type="text")` and QMD `query(searches=[{"type":"lex",...}],rerank=false)`. Reads used exact known note titles or paths. Basic Memory additionally exercised `build_context` and the accepted-status filter. No model was asked to generate a recovery answer.

S4 changed one runtime-copy file from local-r1 / 15 seconds / REVISION-OLD-15 to local-r2 / 45 seconds / REVISION-NEW-45. The original output vault stayed unchanged. The harness read immediately, waited three seconds, and read again. QMD then ran an explicit update and another read. Basic Memory's enabled watcher updated automatically. Cold-index rechecks did not recreate or alter the source corpus.

Durations in logs are single observed call timings, not benchmark statistics. Payload sizes and call counts are not directly comparable because response shapes and follow-up operations differ. No accuracy percentage or performance winner is claimed.

## Reproduction notes

The companion evidence ZIP preserves `work/scoped-evaluation/` scripts and `outputs/scoped-evaluation/` evidence paths under one extraction root. It excludes virtual environments, caches, indexes and third-party package source. Read scripts and installation requirements before replaying them; replay overwrites result files, so extract a separate copy if preserving the original run.

Requirements are Windows, Python 3.11+ for the small harness, Python 3.12+ for Basic Memory, Node 24.13.0 for the observed QMD environment, and package installers. Create a virtual environment at `work/scoped-evaluation/bm-venv`, install Basic Memory 0.23.2 with prereleases enabled and the recorded dependency versions, and restore QMD under `work/scoped-evaluation/qmd-runtime` using its package lock. QMD was installed with package scripts disabled; its packaged native SQLite support worked on this host without a rebuild. This is an observed configuration, not a cross-platform guarantee.

After installing the isolated runtimes, run `prepare.py` once from `work/scoped-evaluation/` to create fresh runtime vault copies/configuration. It refuses to overwrite existing runtime copies. The script resolves its own location, so it can also be invoked from the extraction root. It rewrites the original fixture files to their initial contents. Add QMD collections named `atlas` and `beacon` pointing at the corresponding `qmd-vault` subfolders using the `prepare.py qmd <log-label> collection add ... --name ...` helper, which applies the isolated environment. Then run `probe.py bm`, `probe.py qmd`, `run_qmd.py`, `run_bm.py`, and `recheck_bm.py`. All scripts live in the same folder.

The observed Basic Memory run needed local socket access outside the Codex restricted sandbox. Its launcher is invoked through the virtual environment's Python and the package's declared CLI entrypoint. No product source was patched. The diagnostic traceback timer was added to that invocation only to explain the initial startup stall.

Basic Memory starts indexing asynchronously: preserve first-run empty results, then use the ready-index recheck to inspect retrieval separately. Its default project changes from null to Atlas in the recheck. Because the two changes coincide, the recheck does not independently isolate every cause of the initial empty results; explicit project requests and the initial run's later successful reads support the indexing explanation.
