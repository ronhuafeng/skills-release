---
status: accepted
---

# Separate source checkout from profile discovery

A host source binding is a table with an absolute `path` to the accepted Git
worktree root and an optional non-traversing `discovery_path` relative to that
root. Source origin, revision, cleanliness, and alias content are audited from
`path`. Profile rendering emits a `[source_roots]` entry only when
`discovery_path` is present, while every required `[sources]` alias remains
resolved from the Git root plus its declared alias path.

Enrollment evidence showed that these paths are not the same concept. The
Cloudflare checkout is audited at its repository root, but its accepted profile
discovers reusable skills from the nested `skills/` directory. Other accepted
sources provide explicit aliases without enabling profile discovery at all.
Using the Git root as every profile source root silently changed discovery
scope and prevented lossless profile migration.

The schema-2 host source table directly replaces the undeployed bare-string
binding. The parser rejects the old shape; no compatibility reader remains.
