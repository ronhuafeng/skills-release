# Snapshot Ownership Resolution

Snapshot content drift outside an accepted Fleet placement is an ownership
decision, not an automatic update. Show the alias, exact differences, target
digest, source digest, and vendor-lock evidence. Preserve the target until the
user selects one outcome:

- **Preserve and pause:** leave snapshot and provenance unchanged. Vendor
  remains blocked.
- **Discard drift:** bind approval to the selected aliases and observed target
  digests, move targets to a recoverable location, revalidate the lock, retire
  only their provenance, and prepare a new Vendor review.
- **Make a fork:** stop Vendor and transfer ownership through separate repo-owned
  Skill work. Remove the managed-snapshot claim only as part of that explicit
  ownership conversion.

A missing target with an unretired provenance record remains a conflict. Never
clear provenance while target ownership or disposition is unknown.

For a name configured as Vendored by an exact published Fleet revision, center
authority replaces drift from the pinned source. The plan must bind the
accepted revision and observed source, target, and provenance state. This rule
does not apply to unconfigured repository content.
