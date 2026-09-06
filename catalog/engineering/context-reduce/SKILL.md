---
name: context-reduce
description: Reduce the context needed to make safe engineering changes without weakening current behavior or essential correctness boundaries. Use when the user asks for just enough context, Radical KISS, an over-design review, the shortest correct path, or lower maintenance overhead. Do not use for ordinary code review, copy editing, or UI-only design.
---

# Reduce Engineering Context

Minimize what a maintainer must understand to make and verify a local change, without weakening
correctness. Context includes concepts, files, layers, state, historical rules, exceptional paths,
and indirect dependencies.

Every persistent concept must justify the extra context it forces future maintainers to carry.
Fewer lines, files, or abstractions do not by themselves make a system simpler.

For a repository-wide or cross-artifact review, read the
[review guide](references/review-guide.md). For a local task, use this contract directly and do not
expand the reading scope for completeness.

## Choose the operating mode

- No confirmed finding IDs: perform a read-only review, report findings, and stop.
- Confirmed finding IDs with an apply request: apply only those findings.
- Apply request without confirmed finding IDs: perform the read-only review first.

Review findings are not write authorization. Do not commit, push, create a PR, release, or deploy
unless the user authorizes that action separately.

## Bound the current context

Read the applicable repository instructions first. Then identify:

- the consumer-visible result and the invariants that protect it;
- the canonical authority for current behavior;
- the files and verification entrypoints on a common local change path;
- which context is necessary for current correctness and which is historical burden;
- which artifacts this request allows you to review or change.

By default, read the relevant source, tests, current documentation index and directly linked active
documents, plus the schemas, configuration, and metadata the target actually uses. Read product
direction, Stories, Issues, or external-system authorities only when the target depends on them.

Do not read Git history, old branches, historical designs from closed Issues, journals, superseded
decisions, migration records, old implementation notes, or previous agent traces by default. Read
the minimum necessary portion only when a current authority links to it and current evidence is
otherwise insufficient. Do not infer legacy from age, name, location, or apparent complexity.

## Choose the shortest correct path

- Prefer the highest-level supported interface that owns the target state and can prove the result
  through readback.
- Add or retain a layer, stage, tool, or gate only when it prevents a concrete current failure.
- Examine commit, retry, residual effects, and readback only for external effects. When a new path
  replaces an old one, remove the old path and verify the result with minimum sufficient evidence.

## Identify unnecessary context

Report a finding only when direct evidence shows that a design forces maintainers to understand
unrelated context. Look for:

- facts defined in more than one place, or historical paths with no current consumer;
- layers, stages, tools, or gates that prevent no concrete failure or hide the real control flow;
- tests that freeze current instances or repeat the same behavior across several layers;
- fields, metadata, or configuration that are duplicated, reliably derived, or expose only internals;
- unclear boundaries between canonical records and projections, or optional capabilities that leak
  into every normal path.

Complexity, age, or inconsistency alone is not evidence. Possible future use does not prove current
value.

## Preserve correctness

Do not change current consumer-visible behavior, confirmed external compatibility, or safety,
privacy, and destructive-operation boundaries. Do not remove evidence needed to interpret or verify
current results. A historical observation that cannot be re-derived from the current authority is
not duplicate state.

Test current invariants, not today's data or configuration. Prefer positive contracts and stable
properties over growing blacklists and lists of current instances.

## Phase A: Read-only review

Report only evidence-backed findings, ordered by impact. Give each finding a stable ID such as
`CR-01` or `CR-02`, and include:

- artifact and current owner;
- the invariant it should protect;
- the extra context it imposes and the supporting evidence;
- the minimum action: delete, merge, shorten, rewrite, or keep;
- the resulting canonical authority or local change path;
- the correctness boundary and verification that must remain;
- risk level.

Do not add opportunistic improvements or invent a context score. Stop after the findings and wait
for confirmation.

## Phase B: Apply changes

Apply only confirmed finding IDs, using the smallest complete change:

- remove the source of complexity instead of adding an explanation layer, compatibility layer, or
  second authority;
- replace instance enumeration with stable properties, and do not persist reliably derived data;
- verify behavior at the lowest useful layer, with only a few E2E checks for key external outcomes;
- remove superseded implementation, tests, configuration, documentation, and references together,
  then update direct consumers and verification entrypoints.

Stop and request a decision if the change would alter product intent, consumer-visible behavior,
external compatibility, a public schema, or acceptance criteria that the user has not confirmed.

## Report applied changes

Report:

1. applied finding IDs;
2. removed concepts, states, indirect paths, or duplicate authorities;
3. the current canonical authority and shortest local change path;
4. preserved invariants and verification evidence;
5. unresolved fact conflicts and unverified items;
6. changes to reusable evidence.

If no reusable fact changed, state:

> No reusable fact changed; this change only removed stale or duplicate authority.

## Determine completion

Before completion, answer:

1. Can a common local change be made by reading only directly relevant material?
2. Does every persistent concept, field, layer, and exceptional path protect a current invariant?
3. Does each fact have one canonical authority?
4. Can anything else be removed without weakening correctness, observability, or verification?
5. Is local verification fast while key boundaries retain proportionate evidence?

The task is complete when correctness guarantees remain intact and a local change no longer requires
unrelated state. Do not keep expanding or generalizing for completeness.
