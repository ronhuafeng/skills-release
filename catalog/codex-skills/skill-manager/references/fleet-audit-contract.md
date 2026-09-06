# Fleet Audit Contract

This reference owns cross-host observation, drift classification, and
convergence evidence. Audit never grants mutation authority.

## Interface

```text
skill-manager fleet-audit \
  --manifest <absolute-path> \
  [--host-id <stable-host-id>]
```

Hosts are processed in stable ID order. Results contain manifest identity,
overall status, and independent host results with:

- runtime compatibility and availability;
- expected and observed enrollment ID, hostname, and username;
- rendered and observed profile digests;
- accepted and observed source origin, revision, clean-worktree state, metadata,
  and revision-derived Skill tree object IDs;
- repo path, canonical remote, worktree, and Git visibility evidence;
- desired and observed global and repository placements;
- link targets and managed-snapshot provenance;
- repo-owned declarations and observed real directories;
- drift codes, blockers, evidence gaps, and concurrency fingerprints.

Source qualification uses the portable Skill identity contract: readable YAML
frontmatter with valid `name` and `description`. Preserve additional OpenAI or
Claude frontmatter fields as source content. Validate `agents/openai.yaml`
separately when it exists; do not reject a Claude-compatible Skill only because
its frontmatter contains platform-specific fields.

## Runtime and Consistency

Every selected host uses its configured absolute runtime through Local or SSH
transport. The coordinator sends versioned host-scoped JSON. It does not expose
other hosts' inventory or substitute its own process for a missing target
runtime.

A missing, unknown, or mismatched enrollment identity makes the host result
`incomplete` with `identity_drift`. A missing or incompatible runtime reports `runtime_unavailable` or
`runtime_incompatible`. Audit does not install, copy, or upgrade it.

Do not hold a lock across network calls. Capture matching before and after
fingerprints for profile, sources, repositories, registries, ownership, and
provenance. Changed evidence reports `concurrent_change`, not convergence.
Preserve completed host evidence when another host is unavailable.

## Result States

- `converged`: all selected hosts match complete stable desired state;
- `drifted`: evidence is complete and stable, with deterministic differences;
- `incomplete`: transport, runtime, permission, identity, ownership, or
  concurrency gaps prevent a conclusion;
- `invalid`: manifest or host selection is invalid.

Exit codes are `0`, `3`, `4`, and `2` respectively. When drift and incomplete
evidence coexist, overall status is `incomplete`; host results retain both.

Drift codes include `profile_drift`, `source_identity_drift`,
`source_content_drift`, `source_metadata_invalid`, `repo_identity_mismatch`,
`registry_drift`, `vendor_provenance_drift`, `repo_ownership_unknown`,
`git_visibility_drift`, `identity_drift`, `runtime_unavailable`, `runtime_incompatible`,
`transport_unavailable`, and `concurrent_change`.

## Safety Rules

- Name equality does not prove content identity; compare accepted revision and
  its derived Skill tree object ID.
- Content equality does not prove managed ownership; require vendor provenance.
- A copied directory without a vendor lock remains unknown.
- A tracked real directory without a committed ownership declaration remains
  unknown.
- Snapshot drift requires an ownership decision before update.
- Host-global differences are valid only when the manifest explains them.
- A mismatched canonical repo remote blocks that Host Binding.
- Source refresh, destructive placement, ownership conversion, and Git
  publication require separate authority.

## Completion

Cross-host reconciliation completes only when final audit proves:

- accepted source origins, revisions, and derived Skill tree identities;
- byte-equal rendered Runtime Profiles;
- exact registry placements and valid Skill metadata;
- matching managed snapshots and vendor locks;
- committed ownership declarations for Owned Skills;
- requested Git visibility;
- no unknown directory, broken link, identity mismatch, evidence gap, or
  concurrent change; and
- every intentional host difference in the Fleet Manifest.
