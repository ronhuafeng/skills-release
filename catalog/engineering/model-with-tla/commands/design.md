# Design a requirements model

Use `design` to establish or revise the required state-machine contract before
implementation work.

## Discover the contract

Read the nearest repository instructions, product contract, accepted decisions,
existing models, relevant failures, and current working-tree state. Separate
required behavior from implementation behavior and environment assumptions.

Read [model adequacy](../references/model-adequacy.md). Read
[concurrency contracts](../references/concurrency-contracts.md) when overlapping
operations, transactions, shared memory, faults, time, or progress semantics
matter. Read [refinement claims](../references/refinement.md) when the design
relates two abstraction levels. Read the identity, effects, or evidence
reference only when that boundary affects the model.

**Completion condition:** the controlling contract, modeled system boundary,
environment boundary, modification authority, and unresolved semantic conflicts
are explicit. When applicable, the consistency contract, fault envelope, memory
or time model, and progress requirement are selected rather than assumed.

Establish the model contract defined by model adequacy. A Safety obligation
names its reachable trigger, forbidden outcome, witness, and corrected
behavior. A Liveness obligation names external enablement, local scheduling,
and allowed terminal outcomes.

## Define the abstraction

Apply the abstraction inventory, action-granularity, and state-space growth
rules from model adequacy. For a history property, preserve the smallest event
projection that can distinguish valid from invalid histories.

Use a requirements transition table only when it exposes missing actions,
environment boundaries, or contract ambiguity. Do not create one as a required
artifact when `Init`, `Next`, and the properties express the contract directly.
Compare an implementation transition table only when that comparison matters.

**Completion condition:** each omission has a stated reason, and every critical
property has a reachable trigger and representable forbidden outcome.

## Build and check the model

Define `Init`, `Next`, Safety invariants, required Liveness properties, and only
justified fairness assumptions. Model external non-response or lost completion
at each critical adapter boundary unless a verified contract excludes it.

Read [TLC tool](../references/tlc-tool.md). Check configuration adequacy and use
the deterministic checker for positive configs and the smallest
discriminability witnesses. Declare `success` or the exact expected violation;
a nonzero TLC exit alone is not evidence. For a verified defect in scope with
regression value, preserve a durable negative witness. One witness may cover
multiple properties that share a fault boundary.

**Completion condition:** changed models parse; declared positive checks pass;
negative witnesses fail for the intended signature; the TLC configuration,
checked scope, state counts, depth, exclusions, and unproved assumptions are
recorded.

## Deliver the design

Update only authorized model and owning contract artifacts. Implementation and
external validation may remain planned evidence; their absence does not fail a
design-only task when the boundary is explicit.

Report the abstraction, properties, counterexamples, assumptions, tool results,
changed files, and implementation obligations created by the design.
