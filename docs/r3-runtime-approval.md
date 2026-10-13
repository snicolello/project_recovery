# R3 local-runtime approval proposal

Owner Attention: **Approval required before any download, installation or inference.** This is a prepared option, not an executed model trial or an R3 acceptance recommendation. Review the Stage A result first. No amount of deterministic-double testing proves model usefulness.

## Decision and recommendation

If the owner elects to test a local Librarian, authorize **one isolated CPU-only trial** of the exact pair below on the existing synthetic scenarios. Use one bounded adapter PR and evaluation session; retain R2 as the fallback. This is the smallest proposed experiment to test whether model-selected queries preserve recovery quality and reduce consumer reading. The choice is an inference from size, official provenance and existing QMD/validator compatibility, not a measured model-quality comparison.

The alternative of deferring Stage B costs no installation or inference time and retains the already accepted deterministic capability. A larger model or GPU runtime could improve speed or quality but adds downloads and compatibility questions without evidence that this query-selection task needs them. Neither is included in this request.

## Exact proposed artifacts

| Item | Pinned artifact | Licence | Download bytes |
|---|---|---|---:|
| Model | `Qwen/Qwen3-4B-GGUF`, revision `bc640142c66e1fdd12af0bd68f40445458f3869b`, file `Qwen3-4B-Q4_K_M.gguf` | Apache-2.0 | 2,497,280,256 |
| Runtime | `ggml-org/llama.cpp` build `b11435`, source `43fe9c64281ef735046adc025e9e7559a1f659a5`, `llama-b11435-bin-win-cpu-x64.zip` | MIT for llama.cpp; retain bundled third-party notices | 19,399,527 |
| **Total** | two artifacts only | | **2,516,679,783** |

Model SHA-256: `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.

Runtime ZIP SHA-256: `3ed50261147e260d80f5cdc7bdccfa13a94882be560a4438e7a69fa519c93fb7`.

The runtime is a pinned **pre-release build**, published 2026-10-06; it is not claimed to be the latest or locally verified. The model is 4.0B parameters and supports non-thinking operation, which suits the bounded query task. Digests and sizes are **sourced** from publisher APIs; they have not been verified against downloaded bytes. The JSON metadata in `evidence/r3-runtime-proposal/` records the observation. A mismatch after approval must stop setup rather than silently select another artifact.

Sources: [official model file details](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf), [model card](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/README.md), [model licence](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/LICENSE), [runtime release](https://github.com/ggml-org/llama.cpp/releases/tag/b11435), [runtime licence](https://github.com/ggml-org/llama.cpp/blob/43fe9c64281ef735046adc025e9e7559a1f659a5/LICENSE). Only public documentation and JSON metadata were read; no model/runtime bytes were retrieved.

## Resource envelope and unknowns

**Measured host metadata:** AMD Ryzen 7 9800X3D, 8 cores reported; physical memory 33,883,017,216 bytes (about 31.56 GiB), roughly 1.30 TB free on C: at inspection. An RTX 5070 Ti is present but is outside this CPU-only request. The Windows adapter-memory field was not used to infer usable VRAM.

**Proposed limits:** six CPU threads, one request at a time, 4,096-token context, 384 generated tokens maximum, at most 2,048 input tokens, no persisted prompt cache, 8 GiB process working-set stop limit, 6 GB retained runtime/model disk allowance plus 1 GB scratch. Expected memory below that cap is an **assumption**, not a measurement. Throughput, time-to-first-token, exact peak memory, Windows binary compatibility, and usefulness on this task are all **untested**. Missing DLLs or runtime prerequisites stop the trial; their installation is not covered.

## Bounded trial after approval

1. Use exactly `C:\dev\project_recovery\.scratch\r3-model-trial-2026-10-13\` for the two downloaded artifacts and extracted runtime, and `C:\dev\project_recovery\.scratch\r3-model-evaluation-2026-10-13\` for evaluation outputs/index/cache. Any generated synthetic source copy belongs separately at `C:\dev\project_recovery\runtime-vaults\r3-model-trial-2026-10-13\`. Before creation, resolve these absolute paths and every active manifest source root; refuse existing targets, reparse-point aliases, overlap, or a runtime/cache/output path within a source root. A different target requires a refreshed decision. Read setup code before execution; after the two approved downloads, verify byte size and SHA-256, then inspect archive contents before extraction or execution. No package manager, global PATH edit, hooks, services, additional models, GPU packages, or account/API keys.
2. Commit the adapter, prompt, parameters, scenario matrix and evaluation policy before inference. Read a reviewed local model path; never use an auto-download model selector. Keep inference in a local CLI child process with no listening server. No hosted inference or live GitHub verification. Offline flags are configuration, not proof of OS network isolation; if existing sandbox controls cannot provide the approved boundary, stop for a decision rather than changing firewall/access settings.
3. Model receives only the synthetic task question and required-field shopping list. It proposes one lexical query and raw claims/abstentions. It gets no filesystem, shell, write, edit, move or delete capability. Use non-thinking mode with the pinned chat template; inspect the binary's help after approval to confirm supported options before running. Fix sampling/seeds in the precommitted trial plan; two seeds (7 and 8), at most 16 proposals over S1-S8. No adaptive tuning or silent retries after viewing outcomes.
4. Apply 120 seconds per proposal and 2 hours total wall time, including failures. Count failed/timeout requests toward the 16-proposal cap. Read and validate through existing pinned QMD and `validate --hits requery`; only its re-derived packet may reach the consuming agent. Preserve the original synthetic bytes and record hashes before/after each trial run.
5. Evaluate the unchanged Stage A required evidence/fetch policy and R2 control for the same scenario conditions, including freshness/concurrency/budget cases. Report every case, rejection rate, raw-claim false assertion/false abstention, coverage/completeness, packet-plus-fetch estimated tokens, latency and measured resources. Product model work and consumer reading are separate costs. Do not hide rejected proposals by returning an unlabelled successful baseline; any fallback must be recorded and charged consistently.
6. Stop affected execution on fixture mutation, trust-boundary failure, unsupported trusted assertion, validator inconsistency, resource/time cap or unexpected dependency/network need. Retain failure evidence. A passing trial is evidence for an owner decision, not permission to merge, accept R3, use a real vault or transition.

## Consequence and recovery

Blast radius is this Personal synthetic evaluation branch and its isolated local runtime directory. A wrong choice produces poor queries, rejection, slow runs or an observable setup failure; it must not change governing packet content or accepted R2 behavior. Keep trial outputs as untrusted evidence. The proposed work is reversible by stopping the child process and returning to R2; removal of the trial-owned directory can be reviewed separately, with no blanket cleanup of existing scratch/worktrees.

**Approval wording:** “Authorize the pinned Qwen3-4B Q4_K_M / llama.cpp b11435 CPU trial in this proposal at its three exact named paths, including the two stated downloads, isolated setup and at most 16 synthetic proposals within the stated resource/time bounds. No merge, release acceptance, real-vault access or transition.” Approval of a PR alone does not grant this trial.
