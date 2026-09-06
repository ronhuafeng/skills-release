---
status: accepted
---

# Make published Fleet placements authoritative

Linked placements and Managed Skill Snapshots remain separate mechanisms, but
an exact published Fleet revision authorizes both inside their declared scope.
The complete global user registry is authoritative. A repository is
authoritative only for names declared as Linked or Vendored there. A desired
name can replace a stale symlink, real entry, or drifted snapshot, and an
obsolete managed name can be removed without a second deployment approval.

Publication approval is valid only after enrollment and published-revision
verification. Public plan input cannot assert this authority. The internal
capability also binds the exact rendered profile and declared host scopes. The
same capability must be presented again at apply. Every bound source checkout
must be clean, including ignored content, at the pinned revision and expose the
accepted Git tree. Every repository target must retain its accepted Git root
and canonical origin. The guarded plan binds the accepted revision, source
content, profile projection, registry state, and valid provenance state. A
change after planning blocks apply. System, plugin, bundled,
source-development, and unrelated repository paths cannot enter the mutation
scope.

Repository-owned and unknown real entries outside configured names remain
repository authority and are preserved. This replaces the drift-blocking rule
in ADR 0014; it does not turn snapshots into bidirectional synchronization or
authorize changes outside the Fleet scope.
