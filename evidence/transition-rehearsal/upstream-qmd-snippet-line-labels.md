# UNSENT upstream QMD report: MCP snippet labels do not match source lines

Status: draft only; not submitted. Prepared under Project Recovery hub issue 126 for owner review.

## Proposed title

MCP lexical query snippet labels count the diff header as source lines (QMD 2.8.3, CRLF Markdown)

## Proposed body

With QMD 2.8.3 on Windows, the MCP `query` tool's lexical result has a correct separate `line` field for the matching source line, but the rendered `snippet` labels do not match the file. This reproduced with a CRLF Markdown file.

Environment: QMD 2.8.3 (`facd35e`), Node 24.13.0, Windows 11 host, lexical query, reranking disabled, embeddings disabled.

The source contains:

```text
8: # Queue Archive
9: Atlas queue originally used Redis in an abandoned prototype.
10: This decision is superseded by [[Queue Decision]] and must not govern current work.
```

The MCP structured result for query `Atlas queue` contains:

```json
{
  "file": "atlas/Queue Archive.md",
  "line": 9,
  "snippet": "9: @@ -8,4 @@ (7 before, 0 after)\n10: # Queue Archive\r\n11: Atlas queue originally used Redis in an abandoned prototype.\r\n12: This decision is superseded by [[Queue Decision]] and must not govern current work.\r\n13: "
}
```

The separate `line: 9` correctly identifies the matching source line. Within `snippet`, however, the source heading at line 8 is labelled 10, and the match at line 9 is labelled 11. It appears that the rendered unified-diff header is assigned a source label and then counted while labelling the following content.

Expected: content lines in the rendered snippet use their actual source line numbers, or the snippet omits line labels if they cannot be made source-accurate. The unified-diff header should not advance the source-line counter.

Impact is bounded: a consumer that treats rendered labels as citation coordinates can cite the wrong lines. The separate `line` field remains correct in this case. Project Recovery avoids the issue by fetching the selected source and validating exact spans against the source bytes.

Reproduction is current on the environment above and the hash-pinned synthetic fixture at Project Recovery revision `513457d0a10a2111e6d7dbda348f633da99e9ad2`. I did not test another operating system, LF-only input, another QMD version, vector search or reranking.
