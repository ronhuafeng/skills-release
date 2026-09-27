# Fleet Model

This reference owns fleet identity, desired-state authority, host bindings, and
deterministic runtime-profile rendering.

## State and Identity

| Concept | Durable owner | Host representation |
| --- | --- | --- |
| Fleet manifest | Private version-controlled configuration owner | Read-only logical desired state |
| Host enrollment | Fleet manifest plus host-local identity | Manifest ID and host/user guards |
| Host binding | Fleet manifest | Absolute source, repo, profile, runtime, registry, and transport paths |
| Shared source | Fleet Manifest | Accepted origin and full revision; disposable checkout under `~/.cache/skill-manager/sources/` |
| Managed snapshot | Registered source and target repo lock | Provenance-bound real directory |
| Repo-owned Skill | Target repository | Tracked real directory and committed ownership declaration |
| Global or linked Skill | Registered source | Host-local symlink |
| Derived Skill projection | Fleet manifest, pinned source, and one host binding | Disposable copy under `~/.cache/skill-manager/rendered/<manifest-digest>/` |
| Runtime profile | Fleet manifest and one host binding | Canonical in-memory projection; configured path is compatibility metadata only |

`host_id`, `repo_id`, and `source_id` are stable logical identities. Each host
also has one unique canonical UUID `enrollment_id` and one unique
`hostname`/`username` selector. The enrollment ID selects an installation; it
is neither a secret nor a hardware fingerprint. Host paths and SSH endpoints
are bindings, not identity. Canonical Git identity is
`<host>[:port]/<repository-path>` without scheme, SSH username, or trailing
`.git`. Reject local or unnormalizable remotes.

Each Git source records its canonical origin and full accepted commit. The
catalog inspection primitive derives Skill names, paths, and lowercase
40-character tree object IDs from that revision, scoped to the Host Source
Binding's `discovery_path` when it is set. Managed snapshots retain
separate filesystem SHA-256 provenance. Duplicate native names can exist across
sources, but every desired Fleet alias must resolve unambiguously. Use an
explicit `[skills.<alias>]` record to select and, when needed, rename one.

## Desired-State Authority

The Fleet Manifest owns accepted sources, Skill aliases and invocation policy,
common global availability, host-specific additions and removals, host-specific
Linked or Vendored repo placement, logical identities, and Host Bindings.

Repo-owned aliases remain repository authority. Declare them at:

```text
<repo>/.agents/skill-manager/ownership.toml
```

```toml
schema_version = 1
owned = ["repo-local-skill"]
```

An undeclared real directory remains `unknown`, even when tracked. One repo
alias cannot be Linked, Vendored, and Owned at the same time.

Keep private host names, paths, and inventory in the private manifest owner.
Commands require an explicit manifest path. The reusable Skill source does not
own deployment inventory or credentials.

## Profile Migration

Before enrollment, the explicit host-local profile is desired-state authority.
Enrollment requires:

1. Encode current desired state, a unique enrollment ID, host/user guards, and
   Host Bindings.
2. Render the candidate profile and resolve every identity, ownership, and
   placement difference.
3. Publish the exact clean Fleet commit on `origin/main`.
4. Run `enroll` from that exact revision; it selects the current host/user
   without a caller-supplied `host_id`.
5. Prove the rendered bytes equal the accepted host profile and make the Fleet
   Manifest the authority for future Agent reconciliation.

After enrollment, never edit or require the Runtime Profile as independent
desired state. The Agent updates the Fleet Manifest and invokes one-host apply,
which renders in memory, applies guarded placement primitives, and verifies the
affected host.

The exact published Fleet revision is also the placement authorization. The
global user registry is exact for its accepted global set. A repository is
exact only for names declared as Linked or Vendored there. Source content,
target state, and provenance remain plan-bound; a change after planning blocks
apply. Repository-owned entries outside configured names remain repository
authority. System, plugin, bundled, and source-development paths are never
Fleet mutation targets.

Each Host Source Binding path must be the exact manager-owned
`~/.cache/skill-manager/sources/<source_id>` path for one-host apply. A dirty or
invalid checkout there is disposable. A path outside this namespace or a
linked development worktree blocks before target mutation.
The binding's credential-free `fetch_url` selects host-specific Git transport;
its normalized identity must equal the shared source `origin`.

Managed snapshot provenance remains in
`.agents/skill-manager/vendor-lock.json`; repo ownership declarations remain in
the repository. Temporary plan artifacts are disposable mutation evidence and
must not become a second runtime-state registry.

## Manifest Shape

Schema 5 adds source-level invocation defaults and explicit Skill records.
Schema 4 added enrollment ID, hostname, and username to every Host Binding.
Enrollment IDs and host/user selectors are unique across the manifest. Logical
source and repo identity remain stored once, while absolute paths remain only
inside Host Bindings. Repo placement exists only on hosts with an explicit
repo binding. A Host Source Binding owns the manager checkout `path`, its
credential-free `fetch_url`, and an optional relative `discovery_path`.

Source tables contain `kind`, canonical `origin`, full `revision`, and an
optional invocation default. They do not duplicate the catalog. A path move
keeps placement when the Skill name is stable. A removed referenced name is
removed from managed placements unless evidence and user approval support a
semantic replacement.

```toml
[sources.emil.defaults]
implicit_invocation = "deny"

[skills.emil-prototype]
source = "emil"
source_name = "prototype"
implicit_invocation = "default"
```

`implicit_invocation` accepts only `default`, `allow`, or `deny`. The effective
value is the explicit Skill override when it is not `default`, then the source
default, then unchanged upstream metadata when both are `default`.
`default` means inherit; it does not force an agent-specific value.

Host-global aliases are:

```text
(global.include ∪ host.global_add) − host.global_remove
```

`global_add` and `global_remove` must be disjoint. Each host repo binding owns
`path`, `include`, and `vendor`; `include` and `vendor` must be disjoint. The
shared repo record owns the canonical remote.

The manifest never contains credentials. The host-local identity file contains
only its schema version and enrollment ID. SSH configuration, agent forwarding,
tokens, and host-key policy remain in their normal owners.

## Deterministic Renderer

`skill-manager render-profile --manifest <absolute-path> --host-id <id>` is
read-only. It validates the complete selected Host input and returns canonical
profile TOML, manifest digest, profile digest, status, and blockers.

Rendering:

1. Validates schema, source identities, the catalog derived from each exact
   revision, name uniqueness, and disjoint placement sets.
2. Derives complete host-global availability.
3. Selects only repositories bound on that host.
4. Resolves every desired alias through one source and Host Source Binding.
5. Selects a digest-bound derived projection when an alias or invocation
   override changes upstream behavior. The projection rewrites Codex
   `policy.allow_implicit_invocation` and Claude
   `disable-model-invocation` consistently.
6. Rejects relative bindings, path traversal, missing bindings, and conflicts.
7. Emits `[source_roots]` only for required bindings with `discovery_path` and
   emits `[sources]` only for aliases required on that host.
8. Emits repo tables from Host Bindings; Owned aliases do not enter the profile.
9. Sorts keys, paths, and alias lists and uses one trailing newline.

The manifest digest covers canonical validated logical data. The profile digest
covers exact UTF-8 output bytes. Equivalent manifest and pinned Git revisions
produce byte-equal output without reading target registry state. Renderer and
Fleet audit output expose source defaults, Skill overrides, effective policy,
and whether a derived projection is required.
