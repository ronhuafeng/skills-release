---
status: superseded
superseded_by: 0026
supersedes: 0012
---

# Sunset session-management learn

Remove `learn` as a session-management user job. Session-management retains
`rollout`, `rename`, `delete`, `journal`, `split`, `rehome`, and `doctor`.

Raw session selection and filtering belong to `rollout`. Detecting reusable
workflow patterns and evidence-backed skill improvements belongs to
`skill-detect`. A separate `learn` projection duplicated that responsibility
and added a command-specific output contract without representing a distinct
user job.

Do not keep a compatibility alias or deprecated command. Existing historical
ADRs remain the record of the superseded design.
