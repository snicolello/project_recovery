# UNSENT upstream QMD report: MCP snippet labels do not match source lines

Status: draft only; not submitted. Prepared under Project Recovery hub issue 126 for owner review.

## Proposed title

MCP lexical query snippet labels count the diff header as source lines (QMD 2.8.3, CRLF Markdown)

## Proposed body

With QMD 2.8.3 on Windows, the MCP `query` tool's lexical result has a correct separate `line` field for the matching source line, but the rendered `snippet` labels are two lines ahead of the file. This reproduces with a standalone CRLF Markdown file.

Environment: QMD 2.8.3 (`facd35e`), Node 24.13.0, Windows 11 host, lexical query, reranking disabled, embeddings disabled. The Project Recovery implementation revision used for the retained reproduction will be inserted after the one authorized fresh run; this draft remains unsent.

From an empty temporary directory, create `Queue Archive.md` with explicit CRLF bytes:

```powershell
$lines = @('---','title: Queue Archive','project: atlas','---','','Historical only.','','# Queue Archive','Atlas queue originally used Redis in an abandoned prototype.','This decision is superseded and must not govern current work.')
[IO.File]::WriteAllBytes((Join-Path (Get-Location) 'Queue Archive.md'), [Text.Encoding]::UTF8.GetBytes(($lines -join "`r`n") + "`r`n"))
qmd collection add (Get-Location).Path --name snippet-repro
qmd update
qmd mcp
```

Initialize the MCP session, send `notifications/initialized`, and then send this request. The material query arguments are fully included:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "query",
    "arguments": {
      "searches": [{"type": "lex", "query": "Atlas queue"}],
      "collections": ["snippet-repro"],
      "limit": 10,
      "rerank": false
    }
  }
}
```

The relevant source lines are:

```text
8: # Queue Archive
9: Atlas queue originally used Redis in an abandoned prototype.
10: This decision is superseded and must not govern current work.
```

The retained QMD result has a separate `line: 9`, which correctly identifies the matching source line. Its rendered snippet begins like this:

```text
9: @@ -8,4 @@ (7 before, 0 after)
10: # Queue Archive
11: Atlas queue originally used Redis in an abandoned prototype.
12: This decision is superseded and must not govern current work.
```

The rendered diff header is itself labelled `9`, the correct match-line coordinate. Content labels then continue from that synthetic header: the actual line 8 heading is labelled 10, and the actual line 9 match is labelled 11. Thus the content labels are two lines ahead; the issue is not that only the header advances the source counter by one.

Expected: content lines in the rendered snippet use their actual source line numbers, or the snippet omits line labels if they cannot be made source-accurate. A unified-diff header should not be presented as a source line.

Impact is bounded: a consumer that treats rendered labels as citation coordinates can cite the wrong lines. The separate `line` field remains correct in this case. Project Recovery avoids the issue by fetching the selected source and validating exact spans against the source bytes.

I did not test another operating system, LF-only input, another QMD version, vector search or reranking.
