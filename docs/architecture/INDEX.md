# Architecture decisions

This index is the status and routing authority for repository ADRs. Read
the relevant body only after checking its status here. Superseded decisions are
historical context, not implementation instructions.

| ID | Context | Decision | Status |
|----|---------|----------|--------|
| [0001](../adr/0001-use-go-for-session-management-rollout-processing.md) | Session Management | Use Go for rollout processing | accepted |
| [0002](../adr/0002-separate-rollout-coverage-from-runtime-views.md) | Session Management | Separate complete coverage from narrow typed views | accepted |
| [0003](../adr/0003-make-rollout-go-the-only-codex-rollout-semantic-package.md) | Session Management | Keep rollout semantics in `rollout-go` | accepted |
| [0004](../adr/0004-use-event-messages-for-the-visible-message-projection.md) | Session Management | Build visible messages from event records | accepted |
| [0005](../adr/0005-use-an-eager-full-fidelity-rollout-file-api.md) | Session Management | Use an eager full-fidelity rollout API | superseded by 0027 |
| [0007](../adr/0007-filter-rollout-records-with-partial-json-objects.md) | Session Management | Filter with partial JSON objects | accepted |
| [0009](../adr/0009-require-complete-decodability-for-filtered-rollout-output.md) | Session Management | Require complete decodability for filtered output | accepted |
| [0010](../adr/0010-retain-five-session-management-user-jobs.md) | Session Management | Retain five session jobs | superseded by 0012 |
| [0011](../adr/0011-use-a-minimal-cgo-free-go-sqlite-package-for-doctor.md) | Session Management | Use a minimal CGo-free SQLite primitive | superseded by 0026 |
| [0012](../adr/0012-share-session-snapshots-and-objective-segments.md) | Session Management | Retain seven jobs and share session segmentation | superseded by 0013 and 0015 |
| [0013](../adr/0013-sunset-session-management-learn.md) | Session Management | Remove `learn` and retain seven current jobs | superseded by 0026 |
| [0014](../adr/0014-separate-skill-links-from-managed-snapshots.md) | Skill Manager | Separate links from managed snapshots | superseded by 0030 |
| [0015](../adr/0015-separate-content-timeline-from-rollout-metadata.md) | Session Management | Separate semantic content from rollout metadata | superseded by 0027 |
| [0016](../adr/0016-route-agent-context-through-authoritative-documents.md) | Repository | Route agent context through authoritative documents | accepted |
| [0017](../adr/0017-make-repo-placement-host-specific.md) | Skill Manager | Make repo placement host-specific | accepted |
| [0018](../adr/0018-separate-source-checkout-from-profile-discovery.md) | Skill Manager | Separate source checkout from profile discovery | accepted |
| [0019](../adr/0019-separate-source-tree-identity-from-snapshot-digests.md) | Skill Manager | Separate source tree identity from snapshot digests | superseded by 0028 |
| [0024](../adr/0024-prefer-authoritative-interfaces-over-owned-mechanization.md) | Repository | Prefer authoritative interfaces over owned mechanization | accepted |
| [0025](../adr/0025-compose-rehome-across-authority-boundaries.md) | Session Management | Compose rehome across authority boundaries | accepted |
| [0026](../adr/0026-remove-session-management-doctor.md) | Session Management | Remove `doctor` and retain six current jobs | accepted |
| [0027](../adr/0027-stream-large-rollout-partitioning.md) | Session Management | Stream large rollout partitioning through bounded semantic windows | accepted |
| [0028](../adr/0028-derive-skill-catalog-from-pinned-source-revision.md) | Skill Manager | Derive the Skill catalog from the pinned source revision | accepted |
| [0029](../adr/0029-enroll-host-users-from-published-fleet-revisions.md) | Skill Manager | Enroll host users from published Fleet revisions | accepted |
| [0030](../adr/0030-make-published-fleet-placements-authoritative.md) | Skill Manager | Make published Fleet placements authoritative | accepted |
| [0031](../adr/0031-compose-one-host-fleet-apply.md) | Skill Manager | Compose one-host Fleet apply | accepted |
| [0032](../adr/0032-render-fleet-owned-skill-policy-projections.md) | Skill Manager | Render Fleet-owned Skill policy projections | accepted |
| [0033](../adr/0033-develop-in-the-public-repository.md) | Repository | Develop directly in the public repository | accepted |
| [0034](../adr/0034-build-portable-plugin-packages-from-canonical-skill-sources.md) | Repository | Build portable Plugin packages from canonical Skill sources | accepted |

Status changes must update both the ADR frontmatter and this index in the same
change.
