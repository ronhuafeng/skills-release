---
status: superseded
superseded_by: 0013, 0015
supersedes: 0010
---

# Retain seven session jobs and share objective segmentation internally

The `session-management` user jobs are `rollout`, `rename`, `learn`, `journal`,
`split`, `rehome`, and `doctor`. They remain separate subcommand contracts.

`journal` and `split` share a mechanically revalidated `SessionSnapshot` and a
Codex-authored `ObjectiveSegments` contract. Journal projects segments into
evidence-backed claims; split projects them into lifecycle-safe physical record
ranges. There is no additional user command, persisted segmentation state,
automatic objective classifier, journal-specific evidence copy, or independent
split range plan.
