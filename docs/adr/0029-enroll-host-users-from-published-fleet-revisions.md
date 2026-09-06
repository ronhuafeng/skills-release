---
status: accepted
---

# Enroll host users from published Fleet revisions

Fleet Manifest schema 4 gives every Host Binding a unique canonical UUID
`enrollment_id`, an expected hostname, and an expected username. The local
installation stores only schema version 1 and that ID in
`~/.config/skill-manager/identity.toml`. The ID is an installation selector,
not a credential or a hardware fingerprint.

Enrollment accepts an explicit manifest and full lowercase commit. The
containing worktree must be clean, the commit must equal `HEAD`, and it must be
an ancestor of a freshly fetched `origin/main`. The command selects exactly one
Host Binding from the current hostname and username. It atomically writes a
private identity file and refuses to replace a different existing ID.

Fleet audit sends the expected enrollment ID and host/user guards through the
same versioned local or SSH host protocol. Missing, unknown, or mismatched
identity is incomplete evidence and blocks a convergence claim before later
placement work. Normal SSH configuration remains the authority for endpoint
and host-key trust.

This separates three identities: `host_id` is the stable human-facing logical
name, `enrollment_id` binds one installation, and hostname/username prevent an
ID copied to the wrong operating-system account from selecting a Host Binding.
The manifest remains the only shared desired-state authority; the local file is
only a selector.
