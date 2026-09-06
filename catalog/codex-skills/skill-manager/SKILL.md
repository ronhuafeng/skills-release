---
name: skill-manager
description: Manual-only Agent Skill for inspecting, recommending, and applying authority-safe Agent Skills placement and source reconciliation. Use only when the user explicitly invokes skill-manager or asks it to inspect, sync, vendor, refresh, audit, or clean managed skills.
user-invocable: true
disable-model-invocation: true
---

# Skill Manager

Choose one primary command from the request and read its command document.

The Agent owns intent, evidence interpretation, ownership decisions, source
change classification, ordering, and recovery. Tools may parse configuration,
inspect Git or hosts, calculate identity, plan guarded filesystem changes, apply
an approved plan, and verify postconditions. Do not turn those observations
into an automatic policy or a durable workflow state machine.

Before `sync`, `vendor`, or `refresh-source`, read
[`references/cross-host-reconciliation.md`](references/cross-host-reconciliation.md).
Establish the current desired-state owner:

- an explicit Fleet Manifest for an enrolled host; or
- one explicit host-local profile when no Fleet Manifest owns that host.

Do not infer authority from a missing local path. An accepted published Fleet
revision controls the complete global user registry and the configured names
in each repository. Outside that scope, preserve unknown real directories
until ownership is known.

## Commands

- `inspect`: explain registry, source, ownership, provenance, and drift. Read
  `commands/inspect.md`.
- `recommend`: make a semantic placement or cleanup recommendation. Read
  `commands/recommend.md`.
- `render-profile`: render one host profile from a Fleet Manifest. Read
  `commands/render-profile.md`.
- `fleet-audit`: collect stable local or SSH fleet evidence. Read
  `commands/fleet-audit.md`.
- `enroll`: bind the current host user to a published Fleet revision. Read
  `commands/enroll.md`.
- `apply`: reconcile the current enrolled host from one published Fleet
  revision. Read `commands/apply.md`.
- `refresh-source`: reconcile an accepted source revision and its managed
  placements. Read `commands/refresh-source.md`.
- `sync`: manage global or Linked symlink exposure. Read `commands/sync.md` and
  `commands/sync-cross-host.md` when another host is involved.
- `vendor`: manage provenance-bound repository snapshots. Read
  `commands/vendor.md` and `commands/vendor-cross-host.md` when another host is
  involved.

Route source additions, deletions, renames, or changed skill contracts to
`refresh-source`. Route ordinary link exposure to `sync`, materialized copies
to `vendor`, and read-only questions to `inspect`, `recommend`,
`render-profile`, or `fleet-audit`. A read-only command may name the required
mutation command, but it does not run that command or grant mutation authority.
When an enrolled Fleet Manifest owns the requested mutation, route execution
through `apply`; do not manually assemble public mutation requests.

## Safety and completion

- Show the semantic diff and destructive scope before mutation. An explicit
  execution request is approval only for the scope it clearly names.
- Use guarded link or snapshot plan/apply primitives for filesystem placement.
  Accepted Fleet authority can restore names inside its exact scope; otherwise
  never overwrite an unknown directory or a divergent managed snapshot.
- Treat `agents/openai.yaml` as source content. Invocation policy comes only
  from `policy.allow_implicit_invocation`.
- Before claiming that a work environment has complete or equivalent skill
  visibility, inspect bounded agent-native and agent-reported exposure outside
  the managed registry. Discovery supplies evidence; it does not grant
  management authority.
- Preserve repo-owned and user-created skills. For a proven orphan from an
  accepted source, recommend adoption or deletion; do not silently preserve
  stale managed content.
- After mutation, read back the owning configuration and affected registries or
  repositories. For a Fleet Manifest, rerun the affected host audit. A command
  exit code alone does not prove completion.
