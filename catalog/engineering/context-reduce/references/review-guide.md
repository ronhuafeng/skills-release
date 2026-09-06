# Engineering Context Review Guide

This guide identifies and reduces the context surface of an engineering system. It does not
prescribe a language, project structure, or test framework. Reducing the number of files or other
artifacts is not itself success.

## Context surface

The context surface of a behavior is everything a maintainer must understand at the same time to
change and verify that behavior safely:

- concepts and domain vocabulary;
- source, documentation, tests, schemas, configuration, and metadata;
- authorities, identities, states, and exceptional failure paths;
- abstraction layers, indirect dependencies, and implicit control flow;
- compatibility rules or historical facts that still affect current behavior.

The goal is to keep local decisions local without weakening correctness. The following relationship
describes direction only; it is not a scoring formula:

```text
engineering quality ~= correctness guarantees / required context
```

## Architecture and control flow

Every interface, registry, plugin system, factory, state machine, scheduler, taxonomy, wrapper, or
compatibility layer must answer:

> Which current problem becomes incorrect or materially harder if this is removed?

A current consumer, named invariant, or observed failure can justify it. Uniformity, testing
convenience, hypothetical consumers, and possible future extensions cannot justify it alone.

Keep the normal path directly readable:

```text
input -> execution -> result
```

Automatic discovery, reflection, global registration, implicit fallback, configuration inheritance,
environment-dependent branches, and hidden hooks obscure the real control flow. Prefer explicit
wiring unless a current requirement proves the indirection necessary. Explicit code may be longer
while requiring less implicit knowledge.

Compatibility is a product capability, not free insurance. Keep a redirect, alias, deprecated API,
fallback, or old format only when it has a current consumer, support period, owner, and verification
entrypoint.

## Code, schemas, and configuration

Test stable properties rather than today's instances. Test actual behavior rather than freezing text
or data snapshots.

Persisted fields and metadata can easily be mistaken for public contracts. For each item, ask whether
it affects:

1. behavior or matching;
2. interpretation of results;
3. identity, audit, or reproducibility.

Propose removal when it affects none of them. If a value can be derived reliably from a canonical
authority, persist only the authority by default. Keep a value that records an irreproducible
historical observation, and state its meaning.

Configuration is input data, not automatically architecture. A model, prompt, timeout, tool choice,
or deployment value that is allowed to vary should not be frozen because of its current value. Test
that the selected value takes effect, material differences enter identity, and necessary values are
recorded.

A CLI option or configuration field belongs in the public surface only when it represents an
independent user decision. Internal steps, current implementation choices, and test-only branches
should not become permanent options.

Several result artifacts may have distinct responsibilities, but their roles must be explicit:
canonical record, derived projection, or aggregate. Do not copy the same identity and state without
purpose. When duplication is necessary, identify the consistency owner.

Optional assurance is optional only when core correctness does not depend on it. Extra tracing,
provenance, validation, or isolation must not force every normal path to understand it.

## External effects

Only for a path that creates an external effect, check that:

- the writing interface binds the correct target and returns a verifiable observed result;
- an uncertain non-idempotent operation is not retried blindly and reports possible residual effects;
- completion is proven by a sufficiently fresh authoritative readback.

Do not add a mutation state machine, retry model, or cleanup workflow to a path with no external
effect.

## Tests and verification

Tests should protect current invariants, not preserve design history. Before deleting a test, ask:

> Which current defect could enter if this test were removed?

If there is no answer, tests that freeze counts, hashes, current service lists, directory snapshots,
or the continued absence of a removed feature should usually be deleted. Keep a negative regression
test when the behavior is security-sensitive or likely to recur with high cost.

Verify at the lowest useful layer:

```text
logic         cover the rules fully
integration   exercise representative boundaries
E2E           prove a few key outcomes
```

Pure logic can cover the complete rule set. Integration tests prove critical wiring and fail-closed
paths. E2E or live evidence proves a small number of consumer-visible outcomes; it should not repeat
every permutation from lower layers.

Fast verification is an architectural property. If a local change can be verified only through a
broad, slow E2E run, the system forces maintainers to understand a wider scope. Preserve a narrow
feedback loop, then use a small amount of higher-level evidence for critical boundaries.

## Documentation and history

Give each concept one canonical authority. A `README` or index routes to that authority instead of
copying its content. Comments, test literals, configuration, and supporting documents must not become
an implicit second contract.

Current artifacts describe the current system. Past designs belong in Git history, release records,
or historical Issues, not in production paths, compatibility stubs, dead schemas, deprecated
configuration, or tests that only prove an old path remains absent.

An external fact that still affects current behavior may remain, but state its system, scope,
evidence, or revalidation entrypoint. Do not present an external fact as local architecture or a
released capability.

Indexes route. When deletion has removed the ambiguity, do not fill the gap with another summary,
term, classification, template, or migration note.

## Five review questions

Ask these questions for each candidate:

1. Which current invariant does it protect?
2. Which concepts, files, states, exceptional paths, or indirect dependencies does it add?
3. Can a stable property be tested instead of enumerating today's instances?
4. Can the source of complexity be deleted instead of adding a validator, wrapper, document, or test?
5. Can a new maintainer find the correct path near the target and complete narrow verification?

A removal is not valid context reduction if it weakens a consumer-visible outcome, identity,
freshness, authority, effect ownership, failure semantics, a safety boundary, external compatibility,
or authoritative readback.

## Clean up experiments

After an experiment, identify:

- the current invariants it established;
- the canonical implementation that remains;
- helpers, temporary flags, taxonomies, fallbacks, fixtures, and temporary documents that can be
  removed.

Do not let the experimental process become architecture. Add the minimum capability when a future
need becomes current. Guessing future variations raises the context floor of every current change.
