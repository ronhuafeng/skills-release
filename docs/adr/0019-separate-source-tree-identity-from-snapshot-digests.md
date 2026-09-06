---
status: superseded by 0028
---

# Separate source tree identity from snapshot digests

A Git source alias is identified by its relative path and the Git tree object
ID at the source's pinned revision. Fleet audit reads that object ID from
`HEAD:<relative_path>` and compares it with the manifest's `tree_oid`. Source
origin, revision, clean tracked state, and metadata validation remain separate
evidence. Source cleanliness ignores untracked files; repository inspection
continues to report untracked state where visibility and ownership matter.

Managed snapshots continue to use the filesystem SHA-256 digest owned by
`skills_snapshot_plan`. Their source, target, and vendor-lock digests must agree
with each other, but they are not compared with a source alias Git tree object
ID.

The previous source-alias `tree_digest` reused snapshot identity for a different
domain. A live two-host audit proved that ignored build artifacts made clean
checkouts at the same commit report different source identities. Git tree
identity excludes those host-local artifacts without introducing another
hashing implementation. The old field and response shape are removed; no
compatibility reader remains.
