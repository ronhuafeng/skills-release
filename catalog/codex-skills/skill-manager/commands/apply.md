# Apply One Fleet Revision

## Goal

Make the current enrolled host match one exact Fleet Manifest commit and emit
one readback-bound receipt.

## Contract

Run:

```sh
skill-manager apply \
  --manifest /absolute/path/to/fleet.toml \
  --revision <full-origin-main-commit>
```

The command selects the current host by enrollment identity plus hostname and
username. It requires an exact clean configuration checkout at the requested
commit and proves that commit is published on `origin/main`.

For each source bound on the selected host, the declared path must be exactly:

```text
~/.cache/skill-manager/sources/<source_id>
```

The command creates or rebuilds that disposable checkout at the pinned commit.
The same Host Source Binding supplies a credential-free `fetch_url`. Its
canonical Git identity must equal the source `origin`; this preserves the
host's chosen HTTPS, SSH alias, and port without putting credentials in Fleet.
It never resets, checks out, or removes a development worktree. It derives the
profile in memory, plans all target changes before target mutation, applies
links and snapshots serially through digest-bound primitives, and reads the
host again after the last attempted effect.

The receipt is versioned and contains the enrolled target, exact Fleet commit,
manifest digest, source and placement actions, before and after fingerprints,
placement readback, Fleet audit status, pending repository publication, and any
partial-failure error. A failed effect reports its applied action count as
unknown; it never guesses zero. It is deployment evidence, not
desired state. Do not commit receipts, generated profiles, or plan artifacts to
the Fleet repository.

An ambiguous or interrupted effect is not retried automatically. Inspect the
receipt readback, then run the same command again. A successful repeated apply
of the same revision must report zero placement actions.

Vendored repository changes remain uncommitted. A zero-action placement
readback can succeed while Fleet audit reports only Git visibility/provenance
publication drift. The receipt lists those repositories separately. Publish
them only under each repository's own explicit Git workflow.

## Completion

Complete placement only when the receipt names the exact target and revision
and placement readback is `converged`. Report partial completion and pending
repository publication separately; do not claim the repository or full Fleet
is converged before that publication is verified.
