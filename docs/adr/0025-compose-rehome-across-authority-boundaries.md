---
status: accepted
---

# Compose rehome across authority boundaries

Rehome is one Skill-owned workflow, not one executable-owned transaction.

The executable establishes the same-id destination and proves rollout and
transport invariants. The destination Codex App proves product visibility. The
running source Codex App owns the one archive mutation. The executable then
proves that the archived identity and SHA-256 match the established snapshot.

Do not start a second local app-server to archive the source. A live task can
have an active writer in the running Codex App, so a second process is not the
state authority and can reject the valid mutation.

Expose only the two mechanical boundaries required around the App mutation:
`rehome establish` and read-only `rehome verify-archive`. Do not retain the old
executable-owned archive path, generic phase APIs, or mutation fallback.
