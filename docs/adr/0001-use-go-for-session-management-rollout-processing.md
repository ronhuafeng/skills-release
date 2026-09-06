---
status: accepted
---

# Use Go for session-management rollout processing

`session-management` will use Go as its single implementation language for
rollout parsing, typed evidence, and orchestration commands. Although Codex
defines rollout data in Rust, its protocol and rollout crates are tightly
coupled to the larger Codex workspace; depending on them would add a second
toolchain and a large external runtime dependency. The installed Codex CLI's
generated `RolloutLine.json` and the upstream Rust definitions remain
development-time schema references, while the existing Go orchestration binary
owns the locally controlled reader and command behavior.
