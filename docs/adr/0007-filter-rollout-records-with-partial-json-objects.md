---
status: accepted
---

# Filter rollout records with partial JSON objects

The `session-management rollout` command accepts repeated `--filter` arguments,
each containing a partial JSON object. Object fields match recursively with AND
semantics, repeated filters use OR semantics, and non-object values use exact
JSON equality. With no filters all non-empty records are selected. Matching
records are emitted in source order using their original JSON bytes. This uses
the rollout's persisted field names and values directly instead of semantic
aliases, dotted-path syntax, or an expression language.
