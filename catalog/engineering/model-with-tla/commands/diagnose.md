# Diagnose a failure with TLA+

Use `diagnose` to reproduce and explain a verified failure without changing the
implementation.

## Establish the failure

Read the governing contract, failure evidence, existing models, adapter seams,
and relevant tests. Distinguish observed facts from suspected cause. Preserve
unknown event order or external behavior as unknown.

Read [model adequacy](../references/model-adequacy.md) and the identity or effect
reference when the trace crosses those boundaries. Read
[concurrency contracts](../references/concurrency-contracts.md) when the failure
depends on overlapping histories, consistency, faults, shared memory, or time.

**Completion condition:** the observed bad result, minimum known event history,
affected property, and evidence gaps are explicit. When a history property is
in scope, invocation, response, pending operations, and relevant precedence are
not replaced by the final state.

## Build the negative witness

Add or revise the smallest fault action, mutation, or negative model that can
represent the observed result. Keep the triggering state reachable. Do not copy
the current implementation as the requirements contract.

Read [TLC tool](../references/tlc-tool.md). Parse the model and run the negative
configuration with its exact expected violation. Inspect the counterexample and
require the intended property or fault signature; another nonzero result does
not reproduce the failure.

**Completion condition:** the failure is reproduced by a checked counterexample,
or the diagnosis is `blocked` with the missing state, event, or source of truth
identified.

## Report without fixing

Translate the counterexample into:

```text
initial state
→ actor and action
→ authority, evidence, or effect change
→ forbidden result
→ violated property
→ likely implementation seam
→ controlled test order
→ remaining external assumption
```

Report that trace, abstraction limits, and a precise close condition. Do not
change product code or claim that a proposed fix works while `diagnose` is
active. Preserve the smallest durable negative witness when the failure is
verified, the witness has regression value, and artifact changes are
authorized. Reuse an existing witness when it covers the same fault boundary.
