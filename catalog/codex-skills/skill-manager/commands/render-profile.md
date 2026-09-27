# Render Fleet Profile

## Goal

Derive one host's canonical runtime profile from a fleet manifest without
reading or modifying target-host state.

Read
[`fleet-model.md`](../references/fleet-model.md)
for the manifest model, identity, authority migration, and deterministic
rendering rules.

## Contract

- Require an explicit manifest path and stable `host_id`.
- Treat source, repo, and host IDs as logical identity. Use absolute paths only
  from the selected host binding.
- Validate the complete selected host input, including transport, profile,
  runtime, global registry, source, and repo bindings.
- Emit canonical profile TOML and the requested and effective Skill policies
  inside versioned JSON. Do not write the active profile, materialize a derived
  Skill projection, or inspect target filesystem state.
- Return the same manifest and profile digests for equivalent normalized
  logical data regardless of TOML table or set ordering.

## Command

```text
skill-manager render-profile \
  --manifest "/absolute/fleet.toml" \
  --host-id "<stable-host-id>"
```

Exit `0` returns `status = success`. Exit `2` returns `status = invalid` plus
`validation_blockers`. Stdout is one versioned JSON object.

## Workflow

1. Confirm the requested host identity and private manifest owner.
2. Run `render-profile` without creating a temporary target profile.
3. Show the manifest digest, profile digest, canonical profile diff, and any
   validation blockers.
4. Treat the result as a candidate projection. Report any required profile or
   placement change as a separate `sync`, `vendor`, or `refresh-source` action.
   Do not write the profile or reconcile placements. Renderer output is not
   approval or independent desired state.

## Completion

Finish when one valid canonical profile and its digests are reported, or when
invalid logical data is rejected without filesystem mutation.
