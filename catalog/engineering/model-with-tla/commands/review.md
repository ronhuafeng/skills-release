# Review a modeled workflow

Use `review` for a read-only assessment of contracts, models, implementation,
tests, and evidence. Do not edit files, external systems, or product state.

## Inspect the evidence chain

Read the nearest repository instructions and only artifacts needed to trace:

```text
product requirement
→ requirements model
→ focused obligation, finite-checked refinement, or proved refinement
→ implementation seam and controlled test
→ external assumption or evidence
```

Read [model adequacy](../references/model-adequacy.md). Read the identity,
effects, and evidence references when those concerns appear in the workflow.
Read [concurrency contracts](../references/concurrency-contracts.md) for
overlapping operations or concurrency claims, and
[refinement claims](../references/refinement.md) for any refinement claim.
Existing SANY, TLC, or test commands may run only when they are non-mutating and
write generated data outside the repository.

## Review for actionable defects

Check for:

- requirements copied from implementation or contradicted across evidence
  layers;
- an abstraction, domain, constraint, or action boundary that removes the
  trigger, forbidden outcome, history, fault, or progress behavior required by
  the claim;
- a Safety witness that fails for another reason, or a Liveness claim whose
  environment never enables the fair action as required;
- identity, observation, effect, ownership, cleanup, or terminal semantics
  collapsed across boundaries that authorize different actions;
- a focused obligation or finite check reported as a broader refinement or
  proof;
- tool identity, configuration, or expected-result evidence that does not
  support the reported TLC outcome;
- implementation tests or external evidence that do not preserve the modeled
  event order and shared semantics;
- a counterexample reported without a domain event chain, implementation seam,
  and close condition.

## Report findings

Rank findings by user impact and correctness risk. Each finding contains the
artifact and location, violated contract or property, reproducible trace or
evidence chain, consequence, and close condition.

Missing models, tests, or external evidence are review results, not a failure to
complete the review. If no actionable defect is found, state `no findings` and
list the evidence boundary and checks that were not available.

**Completion condition:** every reported conclusion is traceable to inspected
evidence; the repository and external environment remain unchanged.
