# Vendor Skills

## Goal

Deliver complete, accepted Skill files in a repository without requiring
developers to install Skill Manager.

## Repository-owned copies

Use the repository's Git workflow for team distribution. Read its existing
source record and local changes before updating. Reuse one existing source
record, or add a concise `.agents/README.md` when none exists. Record the
accepted upstream repository, revision and source paths. Do not add a parallel
catalog or host profile. If the original revision cannot be verified, record
that limit and preserve repository ownership.

Copy each selected Skill with its required resources, client metadata and
licenses. Preserve local customizations. A customized copy belongs to the
repository; replacing it requires an explicit decision, not an automatic
upstream refresh. Remove replaced files only within the accepted update scope.

Verify the committed file tree, metadata and resource paths without personal
absolute links or caches. Report the source revision, diff, validation and Git
publication state. Normal clone and pull distribute accepted changes; do not
deploy the same repository update to each host separately.

Before taking over a Fleet-managed path, explicitly withdraw its Fleet binding.
Removing that binding relinquishes management; it does not delete project files.
An existing managed snapshot remains under its declared authority until that
transfer is complete.

## Explicitly managed snapshots

Use this path only when the user selects profile- or Fleet-owned placement.
Retain enough provenance to update or remove only content the manager owns.

### Workflow

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

### Completion

Report authority, accepted revision, repository, aliases, source identity,
create, update, overwrite, remove, and preserved actions, provenance readback,
Git visibility, unrelated changes, and blockers.
