# Last-checked decision evidence

Owner-approved option 2 for [#17](https://github.com/snicolello/project_recovery/issues/17), recorded on [Epic #113](https://github.com/snicolello/stephen-project-hub/issues/113#issuecomment-6201195668). GitHub remains the acceptance authority. Historical evidence answers what was previously checked; it never establishes current acceptance offline.

## What recovery reports

Without historical inputs, packets behave as before. With a capture bundle and its independently retained SHA-256, an optional top-level `last_checked` block reports:

- `status`: `historical`, `unavailable` (missing bundle), or `invalid` (including malformed or altered evidence).
- `replayed_at`: when the local bundle was read. This is not a GitHub verification time.
- `bundle_sha256` and `trust_root`: the inspected evidence identity and its operator-supplied trust boundary.
- `entries`: the source locator, GitHub reference and revision, approver, original `last_checked_at`, approved note digest and acceptance-policy digest. `applicability` reports `matches`, `note_changed`, `reference_changed`, `missing_source`, or `policy_changed`. Policy changes take precedence over note/reference changes; reference changes take precedence over a general note change. A match covers the captured note bytes and policy, not current GitHub approval.
- `acceptance_effect: none`: history establishes no current acceptance. The ordinary verifier determines `accepted_decisions`; with `--verifier offline`, referenced decisions remain unverified candidates and accepted decisions remain unknown.

Historical entries are trimmed first when needed for the packet budget. `budget.omitted.last_checked` counts the omitted entries. Invalid or unavailable history retains its explicit status. Packet `status: complete` still describes generation health, not current acceptance or completeness of historical context.

## Retain evidence after an authorized online check

All live runs remain on hold for this project. The commands below describe the workflow for a future separately authorized run; they have been tested only with synthetic GitHub responses.

Use the separate governed utility `scripts/capture_last_checked.py` after selecting an approved manifest and source. It is outside the recovery tool surface. It uses the existing serial GitHub verifier, records only decision claims that pass the configured approver, reference, revision, exact-note-digest and one-record-per-note checks, and retains the response bodies needed to inspect and replay those checks. Claims that do not verify are omitted; they are not historical approvals. An empty bundle means no successfully verified claims were captured, not that all claims were checked successfully.

```powershell
python -I scripts/capture_last_checked.py --manifest manifest/fixture-vault.json --project atlas --out .qmd/history/atlas-check-001.json
```

The capture prints its SHA-256. Retain that digest in a trusted operator record independently of the bundle and any recovery packet. Select a new filename for each observation: the utility exclusively creates `.json` files under this clone's `.qmd/`, outside source roots, and refuses overwrites. Source bytes and policy are rechecked before capture completes. It cannot manufacture a new check from an already-used verifier or the snapshot transport. No capture is performed by `assemble`, `validate`, or any QMD read tool.

A bundle contains source locators and GitHub response bodies. Treat it as private project data when used with private records. Keep it in the Personal zone and outside source roots; do not publish it. Synthetic captures use only fictional fixture data.

## Read retained context offline

Supply both the bundle and the independently retained digest. Replace `RETAINED_SHA256` below with that digest; do not obtain a replacement digest from an untrusted packet or a modified bundle.

```powershell
python -I skills/project-recovery/scripts/recover.py assemble --manifest manifest/fixture-vault.json --project atlas --query queue --verifier offline --last-checked .qmd/history/atlas-check-001.json --last-checked-sha256 RETAINED_SHA256
python -I skills/project-recovery/scripts/recover.py validate --manifest manifest/fixture-vault.json --packet .scratch/packet.json --hits requery --verifier offline --last-checked .qmd/history/atlas-check-001.json --last-checked-sha256 RETAINED_SHA256
```

Validation uses its own supplied bundle and pin. It never takes a trust root from the submitted packet. It re-reads the file, checks the pinned bytes and original capture structure, replays the existing acceptance rules against the retained responses, and compares the historical output during deterministic rederivation. Deleting entries, changing the approver or changing `last_checked_at` is rejected. Only the local `replayed_at` is volatile; historical check times remain material. Both `packet` and `requery` validation modes support this, with their existing hit-selection limits unchanged.

Missing, invalid, wrong-project or altered bundles produce no historical entries. A changed note, reference or policy leaves the original metadata visible with its applicability warning. Capture dates must be valid UTC timestamps, cannot be in the future, and cannot precede a retained verification time. Old evidence is allowed without an expiry policy: it remains historical and establishes no current approval.

## Reconnect and limits

When separately authorized and connected, verify the acceptance record again through `gh`, and create a new capture if retention is wanted. A refused or unavailable current verification does not become accepted because an older capture exists. Actions requiring current approval wait for that approval.

The trust root is the operator-controlled bundle plus the independently retained digest and the approvers' GitHub accounts at capture. A matching hash proves integrity relative to that retained digest; it does not prove GitHub authenticity. A coherently forged bundle with a newly trusted pin is outside that integrity guarantee. A capture cannot reveal later edits, revocations or superseding decisions. The existing live verifier's documented acceptance/revocation limits still apply.

The `snapshot` transport remains a trusted-input mechanism for synthetic fixtures and explicit test reproduction. It is not this historical workflow: successful snapshot verification uses the replay time as `verified_at` and may establish fixture decisions under that separate trust model. Do not use it to describe a retained check as fresh GitHub verification. Ordinary offline context uses `--verifier offline` plus `--last-checked`.

## Synthetic verification

`tests/test_last_checked.py` replaces `GhTransport.get` with committed synthetic REST responses, and never calls GitHub. Scenario S11 does the same while exercising the real pinned QMD read tools. Their checks include original timestamps, missing/altered evidence, scope and policy changes, capture races, output safety, budget omissions, forged packet history and both validation modes. Original fixture hashes are checked before and after. No real source or live acceptance-evidence capture has been tested or authorized.
