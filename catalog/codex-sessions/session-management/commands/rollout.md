# rollout

## Goal

Read or structurally filter Raw Rollout Lines without adding command-specific
semantics.

## Command

```text
session-management rollout <session-id-or-path> [--include-archived] [--filter <partial-json-object>]...
```

A rollout path must be absolute and clean. A session id is resolved only when
`CODEX_HOME` is explicitly set to an absolute clean path; the command does not
discover a home directory. ID lookup searches active sessions first. Add
`--include-archived` to search archived sessions second.

Filters use persisted JSON field names. Fields within one object are recursive
AND conditions; repeated filters are alternatives. Arrays, scalars, and null
use exact JSON equality.

With no filter, every non-empty source line is emitted unchanged, including
malformed JSON. With filters, every line must first be a JSON object; otherwise
stdout remains empty and exit `3` reports only the path and line. Invalid
filters or selectors exit `2` with no records.

The command returns selected raw lines in source order and leaves storage
unchanged. Higher-level Go commands import `rollout-go` directly.

## Done

Selected original lines were written in source order, or the command failed
before writing partial filtered output.
