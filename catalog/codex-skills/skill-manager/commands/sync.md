# Sync Linked Placement

## Goal

Make one accepted global or repository Linked placement true through symlinks.
The Agent decides the desired diff; the runtime only plans and applies the
guarded filesystem change.

## Workflow

1. Establish the desired-state owner and inspect the exact host, source,
   profile, registry, conflicting entry, and bounded effective exposure defined
   by `inspect`.
2. Confirm that every selected alias resolves to one readable `SKILL.md` and
   valid optional `agents/openai.yaml`.
3. Edit the owning Fleet Manifest or explicit profile to express the accepted
   desired state. For Fleet authority, run the one-host `apply` command; it
   derives the profile in memory.
4. For Fleet authority, run `skill-manager apply --manifest ... --revision ...`
   and continue at readback. For an explicit host-local profile, build one
   link-plan request containing the candidate profile, profile path, selected
   registries, desired aliases, proven source paths, and managed aliases. Store
   the request and plan in a private temporary directory.
5. Run
   `skill-manager _link-plan --request <request.json> --artifact <plan.json>`.
   Show create, retarget, remove, overwrite, and preserved actions. Stop on
   unresolved sources, changed evidence, or paths outside the exact global
   registry or repository registry.
6. Run `skill-manager _link-apply --artifact <plan.json> --digest <digest>`.
   Add `--approve-destructive` for the shown remove or retarget scope. This
   private compatibility path cannot carry Fleet authority.
7. Inspect the profile and links again. For Fleet authority, rerun the selected
   host audit. Report remaining agent-native or plugin duplicates separately;
   this sync does not modify them.

Sync never changes source content and never publishes repository Git state.
Repo-local links are workspace wiring unless the user separately requests a
Git policy change.

## Completion

Report the authority, accepted revision, host, aliases, create, retarget,
remove, overwrite, and preserved actions, readback, remaining managed drift,
external exposure findings, and unrelated Git work.
