# Enroll a Host User

## Goal

Bind the current operating-system host and user to one Fleet host from an exact
configuration commit that is already published on `origin/main`.

Read [`fleet-model.md`](../references/fleet-model.md) for identity and authority.

## Command

```text
skill-manager enroll \
  --manifest "/absolute/fleet.toml" \
  --revision "<full-lowercase-commit>"
```

The checkout that contains the manifest must be clean. The requested revision
must equal `HEAD` and be an ancestor of the freshly fetched `origin/main`.
Enrollment selects one manifest host by exact current `hostname` and `username`;
the caller does not provide `host_id`.

## Result

Write only this private host-local identity:

```text
~/.config/skill-manager/identity.toml
```

```toml
schema_version = 1
enrollment_id = "<canonical-uuid>"
```

The directory mode is `0700` and the file mode is `0600`. The write is atomic
and idempotent for the same ID. An existing different ID stops the command.
The ID selects an installation; it is not a secret or a hardware identifier.

Completion requires a successful readback and a subsequent `fleet-audit` whose
identity evidence matches the manifest ID, hostname, and username. Enrollment
does not install a runtime or apply a profile, registry, source, or repository
placement.
