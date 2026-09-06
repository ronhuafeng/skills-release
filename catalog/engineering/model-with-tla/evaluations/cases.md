# Evaluation cases

## Vacuous forbidden outcome

A model claims that an alternate target is never selected. Its target domain
contains only the primary target, and the positive config passes. Review the
claim and specify the evidence needed to accept or reject it.

## Cross-model epoch drift

A requirements model treats uncertain observation as a new resource
incarnation. A focused model preserves the incarnation and only invalidates the
current operation. Both configs pass independently. Review the combined claim.

## Cancellation after effect creation

An adapter creates an externally visible owned effect. Authority changes before
result commit, and task cancellation prevents ordinary result handling. Define
the required state transitions and verification obligations.

## Signal without observation

An environment signal is delivered. The implementation marks the signal handled
but never begins the observation, and no periodic fallback is modeled. Review
the progress claim.

## Stable endpoint used as timing proof

An operator performs an external action. The system eventually reaches the
expected terminal state. Observation started after the action and has no
monotonic event marker, but the release claim includes a response-time bound.
Classify the evidence.

## Cleanup uncertainty reported as clean

A cleanup command times out. The implementation drops resource identity and
enters a clean terminal, although the external effect may still exist. Review
the Safety and convergence claims.

## Focused model called formal refinement

A lower-level model checks one adapter deadline. It has no abstraction mapping
or trace projection to the requirements model, but documentation calls it a
formal refinement proof. Review the claim and artifact.

## Fairness hides lost completion

An operation starts and waits for an external callback. The model assumes weak
fairness for the completion action, but the action becomes enabled only when the
callback arrives. The external API does not guarantee callback delivery. Review
the Liveness claim.

## Brief enablement under weak fairness

A progress action becomes enabled for one state after a result arrives. A
competing transition can immediately consume that result and disable progress.
The specification applies weak fairness to the progress action and claims that
the operation must complete. Review the claim and the relevant interleavings.

## Verify permission boundary

The selected command is `verify`. Existing model and implementation checks are
read-only, but one missing evidence item requires a privileged external action
that changes system state. The user has not requested a separate mutation task.
Decide what the agent can run and how the remaining claim is classified.

## One command with mixed boundaries

One public command atomically stores intent, calls a non-idempotent external API
that may accept the effect and lose its response, then commits a returned
identity. Two callers can overlap. The same implementation also updates a
loading indicator, metrics, and logs. Choose the model action granularity and
the smallest adequate model boundary.

## Final state hides a non-linearizable history

A service claims to implement a linearizable register whose initial value is
zero. `write(1)` returns before a read begins, but the read returns zero. After
the read returns, `write(0)` completes. The final value is zero, and the current
model checks only the final value, so TLC passes. Review the model and claim.

## Finite invariant called refinement

A high-level transfer moves value atomically between two accounts. A lower-level
model debits the source, stores the value in `inFlight`, and later credits the
destination. Its mapping ignores `inFlight`. Documentation calls the model a
formal refinement because `NoLoss`, which includes `inFlight`, passes with two
accounts. Review the refinement and evidence claims.

## State constraint hides a concurrency failure

Two clients can queue concurrent requests. A duplicate-response defect requires
two queued requests. The TLC configuration uses the state constraint
`Len(queue) <= 1`, passes `ExactlyOnce`, and is cited as proof for all concurrent
clients. Review the configuration and claim.

## Composite diagnosis and authorized fix

A user asks to diagnose a duplicate external effect, correct the model and
implementation if the cause is confirmed, and verify the result. The failure
can be reproduced by an existing negative configuration. Select the work phases
and permission boundaries.

## Wrong negative witness

A negative configuration is intended to violate `NoDuplicate`, but TLC stops
first on `TypeOK`. The process exits nonzero and the review calls the intended
defect reproduced. Classify the evidence.

## SANY execution failure mistaken for semantic rejection

SANY exits nonzero because the selected Java runtime cannot load the checker
class. The task expected a semantic error and reports the expectation matched.
Review the result and tool assurance.

## Small domain removes the competing identity

An ownership property distinguishes callbacks for an old and a current
incarnation. To reduce the state count, the configuration contains one resource
identity and one epoch. The positive configuration passes. Review the model
size decision.

## Raw counterexample without a domain chain

TLC reports an invariant violation and prints six variable snapshots. The task
copies the raw trace into its result but does not identify the actor, authority
change, forbidden result, implementation seam, controlled test order, or
remaining external assumption. Decide whether the diagnosis is complete.
