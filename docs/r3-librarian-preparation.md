# R3 Librarian preparation

Status: deterministic preparation only. The owner ruling for package B authorizes this
seam and its synthetic evaluation. It does **not** authorize a model call, model download,
runtime installation, live-vault use, or selection of a model/runtime. Those remain a
separate owner decision.

## Purpose

The optional Librarian may eventually help formulate retrieval queries and decide when
to abstain. It is not allowed to author recovery facts. The recovery contract still
requires every material field to come from the deterministic assembler with verified
receipts or to be `unknown`.

`skills/project-recovery/scripts/librarian.py` is the smallest seam needed to test that
boundary. It accepts a raw proposal, assembles through the existing QMD recipe, and then
validates the candidate through a fresh `hits=requery` re-derivation. A caller receives a
packet only when the fresh validator returns `equal_to_rederived` and the returned packet
is complete. The packet exposed to the caller is the validator's re-derived packet, never
the candidate object and never model-written recovery content.

## Raw proposal envelope

The input is UTF-8 JSON with exactly two keys:

```json
{
  "queries": ["bounded retrieval query"],
  "claims": {
    "objective": "raw proposed wording or null",
    "authority": null,
    "accepted_decisions": null,
    "current_state": "raw proposed wording or null",
    "blockers": null,
    "next_action": null
  }
}
```

A string means the proposer claims the field is answerable. `null` is an explicit
abstention. Claim strings are never used as packet values, citations, locators, or
instructions, and the result does not echo them. The adapter measures only whether the
proposer chose claim versus abstain; it does not establish that any raw wording is true.

The parser rejects duplicate keys, non-finite JSON, malformed UTF-8/JSON, controls and
lone surrogates, missing or extra keys, duplicate queries, and non-string values. The
proposal is limited to 32,768 bytes, one to four queries, 512 characters per query, and
2,048 characters per non-null claim. Claim keys are the six mandatory recovery fields;
packet-shaped input, tool instructions, credentials, Work fields, and other out-of-scope
claims have no accepted location in the envelope.

## Deterministic flow

For each query, the adapter:

1. creates a new read-only session and calls `recipe.assemble` with the existing manifest,
   project, token estimator, authority verifier, and QMD retrieval path;
2. serializes that candidate and calls `rederive.validate` in `requery` mode using a
   second new read-only session;
3. rejects the attempt with `packet: null` unless validation returns
   `equal_to_rederived` and its own packet is fresh and complete;
4. scores the raw claim/abstain posture against that re-derived packet's field status,
   `unknowns`, and `conflicts`; and
5. returns only the fresh re-derived packet for a successful attempt.

The proposed query remains untrusted selection input. Its presence in the validated
packet does not prove that it was a good question or grant authority; this is already an
explicit limit of `rederive.validate`. Text found in notes and tool output remains data.

## Abstention score

Each raw field posture receives one of four outcomes:

- `claim_on_answerable`: the deterministic packet established the field and the proposal
  supplied a string;
- `correct_abstention`: the deterministic packet said unknown/conflict and the proposal
  supplied `null`;
- `false_abstention`: the deterministic packet established the field but the proposal
  supplied `null`; or
- `claim_on_unknown_or_conflict`: the deterministic packet required abstention but the
  proposal supplied a string.

The result reports per-field outcomes, counts, and a posture rate. It always states
`claim_text_correctness_established: false`. This score can evaluate a deterministic test
double without treating the double's prose as evidence.

## Failure behavior and boundaries

A malformed or out-of-scope proposal is rejected before any retrieval session starts.
An assembly failure, validator mismatch, freshness gap, or incomplete packet is an
explicit rejected result with no packet. One query's rejection does not turn another
query's result into trusted content; every returned packet has its own fresh validation.

The module adds no model/runtime transport, retrieval engine, dependency, command-line
entry point, write tool, or filesystem mutation. Tests use deterministic proposal bytes,
temporary synthetic vault copies, and the existing vault-backed session double. The
opt-in integration check uses pinned QMD 2.8.3 against the committed synthetic fixture,
with its index and cache under the worktree's ignored `.qmd/` directory.

Before any real-model evaluation, the owner must separately approve the exact model,
runtime, acquisition/install actions, data handling, prompt protocol, and evaluation
gate. This preparation provides no default approval for any of them.
