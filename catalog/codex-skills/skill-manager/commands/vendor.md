# Vendor Managed Snapshots

## Goal

Materialize accepted source content into one repository while retaining enough
provenance to update or remove only content that skill-manager owns.

## Workflow

1. Establish desired-state authority, repository identity, source owner, alias
   set, vendor lock, target contents, and Git baseline.
2. For an explicit host-local profile, stop if a target is an unknown real
   directory, provenance is incomplete, or a managed snapshot diverged. Use
   [`snapshot-ownership-resolution.md`](../references/snapshot-ownership-resolution.md)
   for an explicit ownership decision. An accepted Fleet revision instead
   restores only its configured Vendored names.
3. Edit the owning Fleet Manifest or explicit profile to express the accepted
   Vendored placement.
4. For Fleet authority, run `skill-manager apply --manifest ... --revision ...`
   and continue at readback. For an explicit host-local profile, build one
   snapshot-plan request with the target repository, candidate profile, source
   paths, vendor-lock path, desired aliases, and managed aliases. Keep request
   and plan files private and temporary.
5. Run
   `skill-manager _snapshot-plan --request <request.json> --artifact <plan.json>`.
   Show create, update, overwrite, remove, symlink-replacement, and preserved
   actions with their exact scope.
6. Run `skill-manager _snapshot-apply --artifact <plan.json> --digest <digest>`.
   Add `--approve-destructive` only for the shown destructive scope. This
   private compatibility path cannot carry Fleet authority.
7. Verify target and source digests, `agents/openai.yaml`, vendor-lock
   provenance, desired state, and Git visibility. Read
   [`vendor-git-visibility.md`](../references/vendor-git-visibility.md) for a
   Git worktree.

Vendor never adopts, overwrites, or deletes repository content outside its
configured names. Commit and push remain separate user-authorized work.

## Completion

Report authority, accepted revision, repository, aliases, source identity,
create, update, overwrite, remove, and preserved actions, provenance readback,
Git visibility, unrelated changes, and blockers.
