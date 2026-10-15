# QMD 2.8.3 blank-note probe (project_recovery #16), 2026-10-14

Synthetic only. `probe.py` generates throwaway vaults under the git-ignored
`.scratch/qmd-blank-probe/` and indexes them under the git-ignored `.qmd/`; it never reads
or writes `fixtures/`. It drives QMD only through the recovery client's allowlisted
surface: `collection add`, `update` and the read tools `status`, `multi_get`, `get` and
`query`. It also runs one inline Node script, with the Node that runs QMD, to list the code
points `String.prototype.trim()` removes. `versions.json` records the existing runtimes
used; nothing was installed or downloaded.

The probe was run before the rule was written. `observed-before-rule.json` is that first
run: observations only, so every `predicate_*` value is null. Its harness was the same
apart from the later `trim` section. `results.json` is the run after the rule
(`recipe.indexable`) existed. Its observations are identical, and the rule agrees with
every probe (`predicate_disagreements: []`).

```powershell
python -I evidence/qmd-blank-notes-2026-10-14/probe.py
```

## Source

QMD's indexer (`dist/cli/qmd.js`, `indexFiles`) reads each file with
`readFileSync(path, "utf-8")` and skips it when `!content.trim()`. Its `getStatus`
(`dist/store.js`) groups active documents by collection, so a collection with no active
document is not listed. The probes below confirm both behaviours.

## Observed

| Probe file (alone in its collection) | Bytes | Indexed and served | Collection in `status` |
|---|---|---|---|
| empty | (none) | no | no |
| spaces; tabs and spaces | `20 20 20`; `20 09 20 09 20` | no | no |
| newline only (LF); newlines (CRLF) | `0a`; `0d 0a 0d 0a` | no | no |
| mixed whitespace | `20 09 0d 0a 20 0a 09` | no | no |
| byte-order mark only; BOM and CRLF | `ef bb bf`; `ef bb bf 0d 0a` | no | no |
| vertical tab and form feed | `0b 0c` | no | no |
| U+00A0; U+3000 U+2028 U+2029 | UTF-8 | no | no |
| frontmatter only; empty frontmatter | `---\ntitle: Probe\n---\n`; `---\n---\n` | **yes** | yes |
| U+0085; U+001C | UTF-8 | **yes** | yes |
| U+200B; U+180E | UTF-8 | **yes** | yes |

- **Mixed:** one collection held a real note and all 17 probe files. QMD served exactly
  the real note plus the six non-blank probes, and `status` counted 7 documents.
- **No Markdown at all:** the collection was not in `status`. `multi_get` and `get`
  served nothing, and a lexical `query` scoped to it returned no results and no error.
  The same was true for every collection holding only blank files.
- **`trim()` set:** Node v24.13.0 removes exactly 25 code points: U+0009 to U+000D,
  U+0020, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029, U+202F, U+205F, U+3000 and
  U+FEFF. `recipe.JS_WHITESPACE` equals this set (`rule_equals_node: true`). Python's
  `str.isspace()` differs: it also accepts U+001C to U+001F and U+0085, which QMD indexes,
  and does not accept U+FEFF, which QMD skips. The rule therefore does not use it.
- **Transitions** (`transitions`):
  1. Index a note with content, then empty it and run `update`. QMD **keeps serving the
     earlier content**, and `status` still counts the note. A collection whose only note
     was emptied stays listed, with that content. The indexer records the path as seen
     before it skips the blank file, so the document is never deactivated.
  2. Refill the note and run `update`. The new content is served.
  3. Delete the note and run `update`. It is removed, and a collection left with no
     documents drops out of `status`.
  4. Build a fresh index of the same blank files. They are not served, and the
     all-blank collection is not listed.

## Consequences for the recipe

- Refresh hashes every Markdown file and compares QMD's served set with the files the
  rule calls indexable. Blank files are recorded as present, not indexable, with their
  hashes kept in the generation record.
- A collection missing from `status` is verified empty only when the scan finds no
  indexable file and QMD serves nothing for it.
- Transition 1 makes refresh fail closed, because QMD serves content the disk no longer
  has. The error names the note and `--rebuild`, and a rebuild then passes. Scenario S9
  exercises this against QMD.
