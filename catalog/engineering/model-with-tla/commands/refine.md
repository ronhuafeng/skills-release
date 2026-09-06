# Refine a modeled workflow

Use `refine` when the user authorizes alignment of a lower-level model, adapter,
test, or implementation seam to an existing requirements model. A change only
to the requirements model belongs to `design`.

## Establish the obligation

Read the governing requirements model, implementation seam, controlled tests,
current failure evidence, and repository instructions. Read
[model adequacy](../references/model-adequacy.md) and
[refinement claims](../references/refinement.md). Read the identity, effects,
[concurrency contracts](../references/concurrency-contracts.md), and evidence
references only when required by the boundary.

Classify the lower-level artifact as:

- proved refinement, only with a general proof for the declared assumptions;
- finite-checked refinement, with a mapping or trace projection checked for
  explicit finite configurations; or
- focused obligation model, which proves one named adapter or lifecycle
  requirement without claiming trace inclusion for the full system.

**Completion condition:** the higher-level requirement, lower-level boundary,
mapping status, authorized writes, and target property are explicit.

Carry forward the shared model contract. Do not silently change an identity,
epoch, assumption, expected witness, or terminal outcome while changing the
lower-level artifact.

## Refine model and controlled trace

Apply the action-granularity gate from model adequacy to decision-relevant cut
points in the in-scope implementation path. Do not infer model atomicity from
the public command count. Reject both a hidden decision-relevant cut point and
an added phase or variable that fails the gate.

Represent every blocking, completion, effect, commit, compensation, and cleanup
phase that can change responsibility. Preserve delayed, duplicate, cancelled,
no-response, and lost-completion behavior where relevant.

For a refinement claim, map every lower-level step to a higher-level step or
stuttering. Declare hidden and auxiliary variables, and check Safety separately
from Liveness assumptions. Do not promote a finite-checked relation to a proved
or unbounded claim.

Preserve the verified defect's negative witness. Check the corrected model
against the same exact expected property. Convert important counterexamples
into the domain trace defined by `diagnose`, then into controlled implementation
tests with `Given / When / Then` event order.

**Completion condition:** the split and merged boundaries are justified; the
refined model and controlled test preserve the same identity, reset, ownership,
effect, and terminal semantics.

## Implement and verify authorized changes

When implementation is in scope, change the smallest owning boundary, run
focused and full affected tests, and repeat positive and targeted negative model
checks. External mutation or privileged validation remains separately
authorized.

**Completion condition:** requested artifacts pass their declared checks;
effectful failure paths retain truthful ownership or confirmed cleanup; skipped
external evidence and remaining assumptions are classified.

Report the obligation, claim class, mapping, finite configurations or proof,
counterexample, implementation mapping, checks, changed state, and residual
risks.
