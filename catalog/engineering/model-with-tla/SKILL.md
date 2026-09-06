---
name: model-with-tla
description: Model, diagnose, refine, review, and verify concurrent and high-risk stateful systems with TLA+. Use when correctness depends on overlapping operations, consistency histories, event ordering, delayed results, retries, lifecycle, authority, ownership, cleanup, recovery, freshness, or eventual progress; when creating or updating .tla or .cfg files; when converting a failure into a counterexample; or when checking whether models, adapters, tests, and scoped live evidence support one contract.
---

# Model concurrent and stateful systems with TLA+

Use TLA+ to define requirements, expose counterexamples, and connect formal
results to implementation evidence:

```text
requirements model
  → proved or finite-checked refinement, or focused obligation
  → controlled implementation trace
  → scoped external evidence
```

A finite TLC run establishes only the checked abstraction, configuration, and
properties. It does not prove a parameterized refinement, or that code or an
external environment implements the model.

## Route the request

Read the command for the requested result:

- [design](commands/design.md): create or revise the requirements model itself;
- [diagnose](commands/diagnose.md): turn a verified failure into a reproducible
  counterexample without fixing code;
- [refine](commands/refine.md): align a lower-level model, adapter, test, or
  implementation seam to an existing requirements model;
- [review](commands/review.md): perform a read-only adequacy and conformance
  review;
- [verify](commands/verify.md): run existing checks and report drift without
  changing repository or external state.

Select the narrowest command that produces the requested result. A composite
request may run several commands in its authorized order; apply the next
command's write and evidence boundary before continuing. `review` and `verify`
are read-only. `diagnose` does not change product code.

Skip this Skill for presentation-only UI, static content, or deterministic
single-step behavior without a meaningful state lifecycle.

## Route domain references

Read only references needed by the selected command:

- [model adequacy](references/model-adequacy.md) before accepting any model
  result or changing an abstraction;
- [identity and epochs](references/identity-and-epochs.md) when identity,
  replacement, delayed results, retry budgets, or policy scope matter;
- [effects and convergence](references/effects-and-convergence.md) when work can
  create an external effect, time out, be cancelled, or require cleanup;
- [concurrency contracts](references/concurrency-contracts.md) when overlapping
  operations, transactions, shared memory, faults, time, or progress semantics
  determine correctness;
- [refinement claims](references/refinement.md) when relating abstraction levels
  or making a refinement claim;
- [evidence closure](references/evidence-closure.md) when relating a property to
  tests, external validation, or a completion claim;
- [visualization](references/visualization.md) only for a requested state graph,
  statechart, or counterexample visualization;
- [TLC tool](references/tlc-tool.md) before every SANY or TLC invocation.

## Keep the evidence boundary

Keep required behavior, current implementation, external observations,
environment assumptions, and unknown claims distinct. The model-adequacy
reference owns the model contract; the active command applies only relevant
fields. Model only distinctions that can change a checked property or evidence
claim.

Use the canonical checker and evidence limits from the TLC reference. It owns
deterministic tool execution, not abstraction, fairness, cardinality, claim
class, or implementation mapping.

Repository writes follow the selected command and the user's authorization.
External mutations, privileged actions, destructive operations, and live
workflow changes require explicit scope and authorization. Keep generated TLC
state and sensitive local evidence outside the target repository.

## Surface reusable Skill improvements

If execution exposes a reusable mismatch between this Skill's contract and
observed behavior, report one concise improvement candidate with its evidence,
impact, and minimal change. Do not edit this Skill or record the candidate
unless the user asks. Omit this section when no evidence-backed candidate
exists.
