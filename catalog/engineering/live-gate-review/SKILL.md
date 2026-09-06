---
name: live-gate-review
description: Review executable live acceptance gates against an accepted user-visible contract and bounded evidence. Use when auditing a live harness, CI oracle, validator, evidence manifest, or aggregate for false acceptance, false rejection, unsupported assertions, unsafe re-invocation, or unsupported failure attribution. Do not use to define the Story or diagnose an unproven product defect; live execution requires separate explicit authorization.
---

# Review Live Gates

Start the review read only. Do not run a live, paid, semantic, or externally
state-changing operation unless the user separately authorizes that exact
operation and its cost or side effect.

## Fix the proof authority

Obtain:

- for a new or changed Story or outcome-driving assertion, the latest
  `contract_status: accepted` Story review, the accepted Story or acceptance
  contract, and its required proof set;
- for an unchanged gate governed by another formal acceptance contract, that
  exact contract and its revision;
- the owning ticket or Issue when one exists, reconciled with that accepted
  Story;
- the exact source, artifact, environment, product path, and relevant time;
- the runner, workflow, validator, manifest builder, and aggregate policy when
  they exist; for a new gate, obtain the proposed assertion matrix, evidence
  mapping, operation budget, and aggregate policy before code is written;
- existing run evidence when the request concerns a recorded outcome.

If the user-visible claim, proof budget, or required proof set is missing or
ambiguous, stop and report the contract gap. Do not let executable gate code
define the missing product contract.

For new or changed Story assertions, if the accepted review is missing,
blocked, or superseded, stop and route Story work back to
`live-story-review`. If the accepted Story conflicts with the owning ticket or
Issue, identify which side conflicts with its authority: route Story defects to
`live-story-review` and Issue defects to the repository's owning Issue
workflow. Resume only after the exact Story and Issue revisions are reconciled.
Do not review or repair executable gate code against an inferred contract.

## Trace the proof outcome

Reduce the gate to:

```text
accepted claim
  -> real operation
  -> externally observable terminal result
  -> bounded evidence
  -> proof outcome
  -> aggregate decision
```

For each assertion that can change the proof outcome:

1. name its contract or protocol authority;
2. classify it as a hard contract, diagnostic observation, or unsupported
   constraint;
3. name the semantic fact it proves and explain why any exact event, field,
   item, path, filename, envelope, or other representation is necessary;
4. test both a false-acceptance counterexample and an equivalent, causally
   linked evidence representation that could be falsely rejected;
5. propose the smallest correction when the classification or implementation
   is wrong.

Do not assume that count, order, timing, retry, or implementation shape is
diagnostic. Treat it as a hard contract only when the accepted claim or an
authoritative protocol requires it. A diagnostic value must not decide the
proof outcome.

Check that:

- evidence identifies the exact source, artifact, environment, and operation;
- the runner does not re-invoke an incomplete top-level operation to create a
  successful proof;
- product-internal attempts remain separate from runner invocations;
- failure evidence retains the last proven stage without secrets, private
  content, raw traffic, or unnecessary stable identifiers;
- every required child proof remains required by the aggregate policy;
- an optional proof affects the aggregate only as the accepted policy states;
- a changed proof candidate invalidates evidence for the previous candidate.

## Separate outcome from attribution

Use these proof outcomes:

- `PROVEN`: all required user-visible semantics are supported by the evidence;
- `NOT_PROVEN`: at least one required semantic result is absent, invalid, or
  supported only by insufficient evidence.

When the outcome is `NOT_PROVEN`, classify its attribution separately:

- `repository`: evidence identifies a repository-owned defect;
- `external_environment`: evidence identifies an external system or execution
  environment failure;
- `inconclusive`: available evidence does not support either attribution.

A timeout, missing terminal event, or non-zero exit proves only
`NOT_PROVEN` until evidence identifies the responsible boundary. Do not modify
the product, integrate a candidate, or automatically re-run the live operation
from an `inconclusive` result.

## Report findings

Order findings by consequence:

- `P0`: the gate can report `PROVEN` without the required external result, use
  evidence from the wrong identity or boundary, expose secrets, or repeat an
  unsafe operation;
- `P1`: the gate can reject a valid result, lose material failure evidence,
  or misattribute failure;
- `Suggestion`: a supported improvement that does not change outcome validity;
- `No issue`: an important proof boundary that passed review.

For each finding, report the exact location, affected assertion, authority,
counterexample, and minimum correction. If a concrete run is in scope, report
its proof outcome, attribution when applicable, allowed next action, and stop
condition. If no run is in scope, report the outcome as `not evaluated`.

Root-cause diagnosis and implementation are separate tasks. This review does
not authorize either task.

## Complete the review

The review is complete when every outcome-driving assertion has one authority,
diagnostics cannot determine the outcome, proof identity is exact, operations
and re-invocations are bounded, failure evidence supports only its stated
attribution, equivalent sufficient evidence is not rejected without authority,
and the aggregate follows the accepted required-proof policy.

Bind the result to the exact Story or contract revision, owning Issue revision,
and either the proposed gate design revision or executable gate revision. An
outcome-driving gate change invalidates this result and its validation. A new
gate may receive a design review before implementation, but the exact
executable gate requires another review before remote execution or integration.

If a concrete run lacks sufficient evidence, return `NOT_PROVEN` with
`inconclusive`. Do not infer a run outcome from a static gate review.
