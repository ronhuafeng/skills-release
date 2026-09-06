---
name: plan-issue-roadmap
description: Turn a product goal, accepted decision, or gap analysis into a verified, ordered set of non-overlapping issues. Use when the user asks to check current repository and issue-tracker state, draft an implementation roadmap, decide how candidate work should merge or split, or publish the resulting issues.
---

# Plan an issue roadmap

Convert a governing product goal into the smallest set of evidence-backed,
independently verifiable issues. Treat prior analysis as candidate input, not
current truth. Do not convert every gap into a ticket mechanically.

## Establish the task

Identify:

- the target repository and issue tracker;
- the governing goal, contract, or accepted decision;
- the requested scope and any candidate gaps;
- the repository revision and tracker state used as evidence;
- whether the requested result is a draft or published issues.

Read the nearest repository instructions and the authority that owns the goal.
Inspect the current working-tree state before drawing conclusions. When the
request depends on the latest default branch, inspect that branch through a
supported read-only interface and name the observed revision. Do not change the
checkout, branch, or product files.

If the target repository or governing goal cannot be determined, stop and ask
for the missing input. Do not invent a North Star from the current
implementation.

## Verify current gaps

Inspect only the implementation, tests, schemas, interfaces, and documentation
needed to evaluate the candidate gaps. Check open issues and pull requests for
the same outcome or root cause.

For each surviving candidate, establish:

```text
goal requirement
→ observed current behavior
→ verified gap or unknown
→ desired observable outcome
→ evidence and dependency
```

Remove candidates already resolved by current code. Reuse or propose an update
to an existing issue when it owns the outcome. Keep unsupported claims as
`unknown`; do not publish them as implementation facts. If authoritative code
or tracker state cannot be inspected, do not publish the affected issue.

## Shape the roadmap

Each issue owns one outcome that can be accepted independently. Merge
candidates when they share one missing contract and no part creates useful
value alone. Split them when they have independent outcomes, owners, release
boundaries, or acceptance evidence. A dependency exists only when one outcome
cannot be completed or accepted before another.

Use the project's priority system when one exists. Otherwise order issues by
real dependency and user impact; do not invent labels or a universal P0/P1/P2
taxonomy.

Each issue contains only what its implementer needs:

- an outcome-based title;
- the observed behavior, evidence, and user or system consequence;
- in-scope work;
- objective acceptance criteria;
- real blockers or related existing work, when present;
- non-goals or migration requirements only when they prevent likely scope
  confusion.

State required semantics before suggesting an implementation. Include an
implementation candidate only when it clarifies a known seam or invariant; do
not make it the contract when several correct designs remain. Do not create an
umbrella issue unless it has a real tracking consumer.

If a material product decision is unresolved, present that decision instead of
encoding one arbitrary answer into implementation tickets.

## Draft or publish

For a planning, review, or roadmap request, return the candidate issues and do
not mutate the tracker.

Publish only when the user explicitly requested issue creation. Before the
first write, finalize the complete issue set and recheck repository identity,
open duplicates, and dependency assumptions. Use the repository's owning issue
tracker interface.

Treat each issue creation as one external effect. Do not repeat a creation when
its result is unknown; use tracker readback to determine whether it exists.
After each confirmed creation, record its tracker identity. Create supported
dependency links only after both issue identities are known. Report partial
completion and remaining effects truthfully.

Issue publication does not authorize code changes, branches, commits, pushes,
or pull requests.

## Report the result

A draft reports the evidence scope, proposed issue titles, outcomes, ordering,
real dependencies, reused existing work, corrections to prior analysis, and
remaining unknowns.

A published result reports the evidence scope, created and reused issue
identities, the resulting dependency order, readback status, partial failures,
and unverified items.

Completion requires that every proposed issue is supported by inspected
evidence, has a distinct acceptance boundary, does not duplicate known work,
and has only necessary dependencies. A published issue is complete only after
authoritative tracker readback.
