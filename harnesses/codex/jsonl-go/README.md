# codex/jsonl-go

Syntax-only Go API for reading non-empty JSONL rows without interpreting JSON.

## API

`Scan(path, visit)` visits each non-empty source row with its path, 1-based line
number, and original bytes excluding only the trailing `\n` line terminator.
`ScanRange` resumes from one byte-and-line cursor through a fixed source byte
boundary, gives the visitor the current row cursor, and returns the exact
successor cursor. The caller can therefore defer one row without copying its
content into continuation state. Leading/trailing whitespace, CRLF `\r`,
malformed JSON, non-object JSON, and lines larger than `bufio.Scanner` defaults
remain unchanged.

This package owns no Codex record, session, message, turn, filtering, or
command semantics. `rollout-go` is the only Codex-specific consumer.

## Validation

```bash
GOWORK=off go test ./... -count=1
```
