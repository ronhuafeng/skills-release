---
status: accepted
---

# Make rollout-go the only Codex rollout semantic package

`jsonl-go` remains a syntax-only reader that preserves raw rows and source
locations. `rollout-go` becomes the sole owner of Codex rollout decoding and
metadata, message, Goal, and coverage views. Commands consume the shared raw
records or typed views directly and do not decode rollout maps locally. This
two-layer boundary keeps raw input handling reusable without allowing Codex
semantics to spread across packages.
