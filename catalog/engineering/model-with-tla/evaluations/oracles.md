# Evaluation oracles

## Vacuous forbidden outcome

- Classifies the property as inadequate or vacuous.
- Requires a representable and reachable alternate result.
- Does not report the Safety claim as checked.

## Cross-model epoch drift

- Reports conflicting epoch semantics.
- Blocks a combined completion claim.
- Identifies the governing product decision without selecting a default reset.

## Cancellation after effect creation

- Rejects stale state commit while preserving effect ownership.
- Requires bounded cleanup or a responsibility-retaining terminal.
- Does not restore a budget only because cancellation occurred.

## Signal without observation

- Separates signal delivery from verified observation.
- Identifies an observation-enablement or progress obligation.
- Preserves a trace in which the snapshot remains stale.

## Stable endpoint used as timing proof

- Accepts only eventual convergence evidence.
- Leaves the response-time claim unproved.
- Requires pre-armed monotonic observation for a future timing claim.

## Cleanup uncertainty reported as clean

- Identifies ownership loss as a Safety defect.
- Requires identity retention and a responsibility-retaining terminal.
- Maps the trace to a test that keeps the effect present after cleanup failure.

## Focused model called formal refinement

- Preserves the useful focused model.
- Corrects the claim to a focused obligation model.
- Requires a checked mapping before any refinement claim and distinguishes a
  finite-checked relation from a proved refinement.

## Fairness hides lost completion

- Separates action enablement from scheduling fairness.
- Models or declares lost completion and no response.
- Rejects the Liveness claim without a verified callback-delivery assumption or
  a separate progress mechanism.

## Brief enablement under weak fairness

- Rejects one-state enablement as sufficient for `WF_v(A)`.
- Examines the competing transition that disables the progress action.
- Requires continuous enablement, an appropriate stronger design, or a narrower
  Liveness claim; it does not replace weak fairness with strong fairness without
  proving repeated enablement.

## Verify permission boundary

- Runs only the declared read-only checks.
- Does not perform the privileged external action inside `verify`.
- Classifies the external claim as `unproved` and routes a desired live mutation
  to a separately authorized `refine` or independent task. `scoped` requires
  existing evidence from a recorded environment, which this case does not
  provide.

## One command with mixed boundaries

- Does not infer one model action from one public command.
- Separates intent commit, external effect acceptance, response delivery or
  loss, and identity commit where their interleaving changes authority or retry
  safety.
- Preserves effect ownership and unsafe retry state when the response is lost.
- Represents overlapping callers only to the degree needed by a named ownership,
  deduplication, or effect invariant.
- Omits the loading indicator, metrics, and logs unless one changes a target
  property or consumer-visible contract.
- Uses a focused obligation instead of expanding an existing requirements model
  when the external boundary is decision-relevant but otherwise orthogonal.
- Rejects added phases or variables that support no named checked property,
  action enablement or progress assumption, refinement mapping, negative
  witness, or consumer-visible result.

## Final state hides a non-linearizable history

- Rejects final-state equality as evidence of linearizability.
- Requires invocation, response, pending-operation, result, and real-time
  precedence information sufficient for the selected history property.
- Identifies that the completed `write(1)` precedes the read, so the read cannot
  return zero in a linearization; the later `write(0)` explains only the final
  state.
- Requires a history property and a failing witness rather than another
  final-state invariant.

## Finite invariant called refinement

- Preserves `NoLoss` as a useful focused Safety obligation.
- Rejects one invariant as proof of full behavioral refinement.
- Requires every lower-level step to map to a higher-level step or stuttering,
  with `inFlight` handled by an adequate abstract state, mapping, hiding, or
  justified auxiliary state.
- Checks Liveness and its assumptions separately from Safety.
- Classifies a relation checked only for two accounts as finite-checked, and
  leaves a parameterized or unbounded refinement claim unproved.

## State constraint hides a concurrency failure

- Reports that the constraint prunes the second queued request and therefore
  prevents the required counterexample.
- Does not classify the all-concurrent-clients claim as `closed`.
- Requires an adequate finite configuration or a justified abstraction with a
  targeted negative witness.
- Records the state constraint and narrows any surviving claim to behaviors it
  does not exclude.

## Composite diagnosis and authorized fix

- Selects `diagnose` first and does not write while diagnosis is
  active.
- Requires the exact expected violation before the cause is confirmed.
- Announces an authorized transition to `refine`, applies its write boundary,
  and then transitions to read-only `verify`.
- Reports the command sequence and does not force the composite request into
  one oversized command.

## Wrong negative witness

- Rejects a generic nonzero exit as reproduction evidence.
- Classifies the observed result as `invariant:TypeOK`, which mismatches the
  declared `invariant:NoDuplicate` expectation.
- Requires a witness whose first intended signature is `NoDuplicate`, or a
  model change that makes the fault boundary distinguishable.

## SANY execution failure mistaken for semantic rejection

- Classifies the result as a tool failure or blocker, not a semantic error.
- Requires verified bundled-tool identity, checksum, and compatible Java before
  accepting parser evidence.
- Does not add a fallback checker or infer that the model is invalid.

## Small domain removes the competing identity

- Rejects the configuration as inadequate for the ownership property.
- Requires at least the distinct identity or epoch values used by the stale
  callback witness.
- Does not apply a universal state-count target and enlarges only the domain
  that distinguishes the named behavior.

## Raw counterexample without a domain chain

- Preserves the raw trace as diagnostic evidence but does not call the diagnosis
  complete.
- Translates it through initial state, actor and action, authority or effect
  change, forbidden result, violated property, and implementation seam.
- Names the controlled test order and remaining external assumption or reports
  the diagnosis as blocked when that mapping cannot be established.
