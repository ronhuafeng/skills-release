# Model adequacy

Model adequacy describes whether an abstraction can express the behaviors that
its properties are intended to distinguish. A passing finite model is useful
only within an adequate, declared boundary.

## Model contract

Before a check can support a claim, bind the governing requirement, claim
class, system and environment boundaries, authority, identity, epoch,
externally visible effect, Safety and Liveness obligations, assumptions,
deliberate omissions, finite configurations, and expected outcomes. Add the
implementation or external-evidence mapping only when it is in scope.

This is a semantic contract, not a template artifact. Keep it in the task result
unless the user authorizes a durable project document. A changed assumption,
identity, epoch, witness, or terminal outcome creates a new contract and must
not inherit the prior evidence silently.

## Requirements and implementation

The requirements transition system is derived from the governing contract,
accepted decisions, user intentions, and verified failures. The implementation
transition system is derived from code, adapters, persistence, callbacks,
retries, and cleanup paths.

These systems serve different purposes. Copying implementation transitions into
the requirements model can preserve the implementation's omissions while still
producing a passing TLC result.

## Abstraction inventory

An abstraction inventory records:

- controlled state;
- user, system, and environment actions;
- external adapters and sources of truth;
- observation quality and freshness;
- identity, incarnation, revision, and operation scope;
- externally visible effects and ownership;
- deliberately omitted details;
- assumptions required for progress.

A fact belongs in the abstraction when changing it can alter authority,
ownership, eligibility, effect commitment, cleanup responsibility, or
user-visible correctness. Raw values can be omitted after the decision-relevant
distinctions are preserved.

## Action granularity

One user command or API call does not imply one atomic model action. Split a
candidate action at a cut point only when delay, failure, or interleaving there
can change a checked property, authority, ownership, effect commitment, retry
eligibility, cleanup responsibility, observation quality, or consumer-visible
result.

Keep steps in one action when they share one atomic authority boundary, contain
no independently relevant external effect or observation, and every
interleaving has the same abstract result. Every added phase or variable must
support a named checked property, action enablement or progress assumption,
refinement mapping, negative witness, or consumer-visible result; otherwise omit
it. Use a focused obligation for a decision-relevant but orthogonal boundary
instead of multiplying unrelated state into the requirements model. State count
alone justifies neither merging a real boundary nor splitting an irrelevant
detail.

## State-space growth

Start with the smallest domains that preserve every identity, competing actor,
operation, history element, and forbidden value needed by the target property.
First make the negative witness reachable, then run the smallest positive
configuration. Enlarge one domain only when its new value distinguishes a named
behavior. A global state-count target is not an adequacy rule, and a symmetry or
constraint that removes the witness cannot support the claim.

## Epistemic states

Observation is not identical to reality. Relevant epistemic states can include:

- confirmed presence;
- confirmed absence;
- multiple eligible identities;
- unknown because observation failed;
- stale because a newer revision exists;
- mismatch because evidence names another identity.

States that authorize different actions are not interchangeable. A notification
or callback normally establishes only that observation should begin; it does
not establish the state that observation may later discover.

## Safety discriminability

A discriminating Safety check has all of these characteristics:

1. the triggering condition is reachable;
2. the forbidden result exists in the model domain;
3. a faulty action, mutation, or negative witness can reach that result;
4. the property fails on the faulty behavior;
5. the corrected behavior blocks the same fault.

This model does not meaningfully check alternate-target selection:

```tla
Targets == {"primary"}
NoAlternateTarget == target # "alternate"
```

The forbidden value cannot occur. A meaningful fault boundary includes the
alternate value and a faulty choice that can select it.

Discriminability does not require one negative config per property. A shared
fault model, controlled mutation, or reachability witness can cover several
properties when the intended signatures remain distinguishable. A durable
negative witness is valuable when a verified defect has regression value. It
can be a shared fault action, config, mutation, or reachability witness and need
not be a separate model.

Other invalid Safety evidence includes an unreachable implication antecedent,
a history-sensitive claim without corresponding history, and a negative config
whose first violation is unrelated to the claimed defect.

## Liveness adequacy

Liveness across an external boundary contains two separate obligations:

```text
environment or adapter supplies the required enablement pattern
→ the selected fairness condition schedules the action under that pattern
```

`WF_v(A)` guarantees an `A` step when `A` remains continuously enabled long
enough. `SF_v(A)` guarantees an `A` step when `A` is enabled infinitely often.
Neither weak nor strong fairness guarantees an action that is enabled in only
one state. A competing action can disable `A` before it occurs, so the model's
other transitions are part of the Liveness analysis.

Fairness does not prove that a callback arrives, I/O returns, authorization
completes, a process exits, or a remote system supplies a response. Those facts
determine whether the required enablement pattern exists.

An adequate model represents relevant non-enablement behaviors such as:

- no response;
- lost completion delivery;
- completion that enables progress only briefly;
- competing work that disables the progress action;
- callback delivered without the required observation;
- an operation that remains blocked;
- cleanup whose confirmation never arrives.

If the property excludes these behaviors, the exclusion is an explicit
environment assumption backed by a contract or scoped evidence. A critical
adapter boundary benefits from negative witnesses in which completion never
becomes enabled and in which it is enabled only briefly or intermittently. These
witnesses detect fairness assumptions that hide missing progress mechanisms or
an incorrect choice between weak and strong fairness.

## Cross-model semantics

Shared terms keep compatible meanings across product contracts, requirements
models, focused models, implementation state, and tests. Relevant comparison
dimensions include:

- identity and resource incarnation;
- epoch creation and reset;
- observation quality;
- operation eligibility;
- attempt-budget consumption;
- ownership acquisition and release;
- clean, degraded, and responsibility-retaining terminal states.

A focused model can omit unrelated variables. It cannot silently assign a
different meaning to a shared event or state. Different representations require
an explicit projection.

A lower-level model supports a refinement claim only when an abstraction mapping
or trace projection connects its behaviors to the higher-level specification.
Use the claim classes and mapping rules in
[refinement claims](refinement.md); otherwise classify the artifact as a focused
obligation model.

## Adequacy classification

- `adequate`: critical distinctions, triggers, faults, and progress boundaries
  are representable;
- `scoped`: named properties are adequate while declared external or
  compatibility facts remain outside the abstraction;
- `blocked`: a critical property is vacuous, an essential source of truth is
  absent, a progress assumption hides non-enablement, or shared models disagree
  about the claimed behavior.

A `blocked` model cannot support the affected completion claim until the model
or claim boundary changes.
