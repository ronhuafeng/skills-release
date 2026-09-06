# Verify declared TLA+ evidence

Use `verify` to run existing evidence and report closure or drift. This command
is always read-only for repository files and external systems.

## Establish the declared suite

Read repository instructions, existing models and configs, declared test
commands, evidence matrices, and current working-tree state. Read
[model adequacy](../references/model-adequacy.md),
[evidence closure](../references/evidence-closure.md), and
[TLC tool](../references/tlc-tool.md).
Read [concurrency contracts](../references/concurrency-contracts.md) for a
declared concurrency contract and
[refinement claims](../references/refinement.md) for a declared refinement
claim.

Do not add, rewrite, or weaken properties to make current behavior pass. Do not
perform privileged, destructive, or externally effectful validation in this
command. Route a separately authorized live mutation to `refine` or a new task
with its own target, side effects, preconditions, and convergence evidence.

## Run checks without changing state

Verify the pinned tool through the deterministic checker, run declared positive
and negative configs against explicit expectations, inspect expected fault
signatures, and run the affected non-mutating implementation suites. The
checker places generated metadata outside the repository and reports its
cleanup.

Check whether each TLC configuration is adequate for its declared claim,
including constants and cardinalities, constraints, symmetry, overrides,
deadlock settings, and whether the run is exhaustive model checking or sampled
simulation.

Compare property names, identity and epoch semantics, adapter phases, ownership,
and terminal states across each cited evidence layer. A matching name alone is
not evidence closure.

## Classify the result

Use the `closed`, `scoped`, `drifted`, `blocked`, and `unproved` classes from
evidence closure. Report `closed` only when required checks pass, configurations
are adequate for the declared scope, and cited layers have matching semantics.

**Completion condition:** all requested existing checks have a result or an
explicit prerequisite blocker; model, repository, and external state remain
unchanged.

Report tool assurance, TLC configuration boundaries, expected and observed
outcomes, checked properties, state counts, depth, duration, fault signatures,
skipped checks, drift, and remaining assumptions. New live mutation remains a
separately authorized effect rather than an implicit part of `verify`.
