# Reconcile an Accepted Source

## Goal

Move one accepted Git source to reviewed current content and reconcile every
placement managed from that source. The source is authority for managed skill
existence and content; the Agent owns semantic classification and ordering.

## Workflow

1. Inspect canonical origin, pinned revision, remote candidate, checkout
   cleanliness, metadata, and every host binding. Do not mutate during this
   evidence pass.
2. Compare the exact old and candidate catalogs and contracts. Classify:
   additions, deletions, path moves, content changes, and possible semantic
   replacements. Do not infer a rename from name similarity alone.
3. Build the proposed fleet diff:
   - remove a deleted source skill from every managed global, Linked, and
     Vendored placement;
   - preserve those placements under a replacement name only when evidence and
     user intent support semantic continuity;
   - propagate changed content to every managed placement;
   - recommend new skills from source policy and actual fleet needs; do not
     place them automatically;
   - preserve repo-owned and user-created skills;
   - recommend adoption or deletion for a proven non-owned orphan.
4. Show revisions, catalog changes, affected hosts and repositories,
   destructive scope, recommendations, and unknown ownership. Obtain approval
   for deletions, replacements, or overwrite scope.
5. Update clean source checkouts to the exact accepted revision and edit the
   owning Fleet Manifest or profile. Apply hosts serially. Use `sync` and
   `vendor` guarded primitives for managed placements.
6. If a step has an ambiguous result, inspect current authority and target
   state, then continue forward from observed facts. Do not reuse a stale plan
   or automatically retry.
7. Run the affected fleet audit and inspect repository Git visibility.

Source reconciliation does not edit skill source, guess replacements, or
commit and publish target repositories.

## Completion

Report origin, before and after revisions, catalog diff, replacements,
affected placements, applied actions, cleanup and new-skill recommendations,
final audit, Git visibility, and unresolved evidence.
