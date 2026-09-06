---
status: accepted
supersedes: 0011, 0013
---

# Remove session-management doctor

Session Management retains six user jobs: `rollout`, `rename`, `delete`,
`journal`, `split`, and `rehome`. The earlier removal of `learn` remains in
effect.

Remove `doctor`, its SQLite inventory implementation, and the dedicated
`harnesses/codex/sqlite-go` module. Doctor compared the complete Codex home with
derived SQLite state, but current Session Management is bounded to tasks on
registered hosts and matching saved projects. No retained workflow consumes
the inventory result or owns storage repair.

Do not keep a hidden command, compatibility alias, or SQLite fallback. A rare
internal-storage investigation is an explicit one-off read-only diagnosis, not
a permanent Skill capability.
