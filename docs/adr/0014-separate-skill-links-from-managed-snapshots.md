---
status: superseded by 0030
---

# Separate skill links from managed snapshots

`skill-manager sync` remains the desired-state operation for global and repo
symlink exposure. A separate repo-only `vendor` operation owns one-way Managed
Skill Snapshots, with desired aliases in the profile and content identity in a
repo lock. Snapshot drift blocks updates rather than being overwritten or
silently reclassified as a Repo-Owned Skill Fork. This preserves one content
owner for reusable skills while supporting portable, committable repo copies
without turning link sync into a bidirectional content synchronization system.
