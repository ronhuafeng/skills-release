---
status: accepted
---

# Separate complete rollout coverage from runtime typed views

`session-management` will not maintain a universal Go mirror of Codex's full
Rust rollout type tree. The shared reader preserves each raw JSONL line and
decodes a small common envelope; commands and shared derivations own narrow Go
views for the fields they consume. Complete structural coverage is checked in
development against real local rollouts and a temporarily generated
`RolloutLine.json` from the installed Codex CLI. The generated upstream schema
is not committed and is not a runtime validator. This keeps raw evidence
lossless and schema drift observable without coupling every command to fields
it does not need.
