# Vendor Git Visibility

This reference classifies whether converged Managed Skill Snapshots and their
vendor lock are represented by a repository's Git state. It does not authorize
ignore-rule edits, staging, commit, or publication.

Capture full untracked status before mutation. After apply, inspect index and
ignore evidence for `.agents/skills` and
`.agents/skill-manager/vendor-lock.json`.

Classify each required snapshot and the lock in this order:

- `tracked-content`: every required regular entry is represented in the index;
- `tracked-symlink-replacement`: the index still records mode `120000` while
  the worktree contains the new real snapshot directory;
- `partially-tracked`: only part of the required snapshot is indexed;
- `untracked-visible`: required content is unindexed and not ignored;
- `ignored`: an ignore rule hides at least one required unindexed entry;
- `not-a-git-worktree`: no Git owner exists for the target path.

An ignore rule that also matches an already tracked file does not downgrade
that file. Compare before and after status so unrelated user changes remain
distinct. If the user requested committable or portable state, `ignored`,
`partially-tracked`, and `tracked-symlink-replacement` remain blockers until a
separate repository-policy decision resolves them.
