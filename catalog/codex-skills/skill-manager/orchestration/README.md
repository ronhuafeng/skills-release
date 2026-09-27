# skill-manager orchestration

This package provides evidence and guarded filesystem primitives for the
skill-manager Agent Contract. It does not decide placement policy, infer
ownership, classify semantic renames, order a fleet rollout, or persist a
workflow state machine.

## Public commands

- `inspect`: parse one profile and inspect selected registries and source roots.
- `enroll`: atomically bind the current host user to a published Fleet revision.
- `apply`: reconcile the current enrolled host from one exact published Fleet
  revision and emit a readback-bound receipt.
- `render-profile`: deterministically render one host profile from a Fleet Manifest.
- `fleet-audit`: collect stable local or SSH host evidence without mutation.
- `--identity`: identify the packaged audit runtime.

The `_link-*` and `_snapshot-*` commands are private mechanical interfaces.
They exist for explicit profile compatibility and tests, not as a Fleet
authority bypass.

`_host` is a private read-only transport endpoint used by fleet audit. Its only
operations are host audit and exact source-catalog inspection. It cannot alter
sources, profiles, registries, snapshots, runtimes, or repositories.

## Mutation primitive boundary

Plan commands accept explicit JSON evidence and write a private artifact to the
path selected by the Agent. The result exposes a digest, blockers, action
counts, and destructive scope. Apply commands require that exact artifact and
digest, revalidate profile, source, target, and provenance state, reject
unapproved destructive actions, perform the filesystem mutation, and verify
the postcondition. A non-JSON `AcceptedFleetRevision` capability is produced
only after published-revision, enrollment, fully clean pinned-source, catalog,
in-memory profile projection, and target-repository identity verification. The same capability is
required again at apply. It makes global placement and configured repository
names authoritative without a second approval. Public plan requests and plan
artifacts cannot create this capability; the one-host Fleet apply composition
owns its use.

These artifacts bind one deterministic filesystem mutation. They are not user
intent, durable desired state, portable approval, recovery state, or a product
review protocol. The Agent edits the owning Fleet Manifest or explicit profile,
shows the semantic diff, obtains needed approval, invokes the primitive, reads
back the result, and discards the temporary artifact.

The request shapes are the existing `core.plan_sync` and `core.plan_vendor`
contracts exercised by `tests/test_command.py`. Do not add wrappers that infer
desired state or hide semantic decisions.

## Fleet evidence

The Fleet Manifest remains private durable desired state for enrolled hosts.
Schema 5 can select a source default or per-Skill `implicit_invocation` policy
and can alias conflicting native names. `apply` materializes only the required
derived Skill copies under a manifest-digest cache; source checkouts remain
exact and clean. The same projection writes Codex and Claude invocation fields,
and its tree digest is bound into placement authority.
`enroll` validates a clean exact commit published on `origin/main`, selects the
current hostname and username, and writes the minimal private local identity.
`render-profile` validates it and derives canonical profile bytes. Neither
`apply` nor `fleet-audit` reads or writes a host-local profile file. `fleet-audit`
uses the configured host runtime only for read-only facts, including source Git
identity, exact skill tree identities, profile projection, registries, repository
identity, managed-snapshot provenance, ownership declarations, Git visibility,
and concurrency fingerprints.

The host runtime is a reproducible native executable built on each supported
host platform. It is useful for bounded SSH evidence, not for remote mutation.
Runtime installation is an explicit operator action outside this package.
`apply` materializes pinned sources only at the declared
`~/.cache/skill-manager/sources/<source_id>` paths. Invalid or dirty disposable
checkouts can be rebuilt; development worktrees are never changed.

## Verification

Run from the repository root:

```sh
uv run \
  --python 3.11.11 \
  --python-preference only-managed \
  --locked \
  --project catalog/codex-skills/skill-manager/orchestration \
  --group build \
  pytest catalog/codex-skills/skill-manager/orchestration/tests
```

For a runtime change, also build with `packaging/skill-manager.spec`, run
`--identity`, run `--help`, and execute one real `fleet-audit` path. A unit test
or successful exit code does not prove host convergence.
