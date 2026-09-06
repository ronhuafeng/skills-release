---
status: accepted
---

# Compose one-host Fleet apply

One supported `apply` command composes published-revision verification,
enrollment selection, disposable source materialization, in-memory profile
rendering, guarded placement, and final readback for the current host. It emits
one versioned receipt bound to the enrolled target, Fleet commit, manifest
digest, actions, and before/after fingerprints.

Source checkouts used for placement live only at the declared
`~/.cache/skill-manager/sources/<source_id>` paths. The manager may atomically
rebuild dirty or invalid checkouts there. It refuses paths outside that
namespace and linked development worktrees. This removes development checkout
state from deployment authority without creating a persistent source registry.
A Host Source Binding also owns its credential-free Git `fetch_url`; normalized
identity must equal the shared canonical source origin. The manager does not
guess HTTPS, SSH usernames, aliases, or ports.

The Runtime Profile is an in-memory deterministic projection. Apply and audit
do not read or write its compatibility path. Link and snapshot plans remain
digest-bound private mechanics and revalidate evidence at apply. Public JSON
cannot obtain Fleet authority.

Effects run serially on one host. An error stops later effects and triggers
readback; there is no blind retry or cross-host transaction. Receipts are
evidence and must not become desired state. Vendored Git publication remains a
separate repository-owned action.

Placement readback uses a fresh zero-action guarded re-plan. Fleet audit can
still report only Git visibility or committed-provenance drift after a
successful Vendored mutation. The receipt reports this as pending repository
publication, not a placement failure. An interrupted or ambiguous phase uses
an unknown applied-action count and always runs the available readback path.
