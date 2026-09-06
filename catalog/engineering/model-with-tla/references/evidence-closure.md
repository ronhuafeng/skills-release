# Evidence closure

Evidence closure describes when a modeled property has enough engineering
support for a scoped completion claim.

## Evidence layers

1. **Requirements model:** abstract behaviors and event interleavings.
2. **Refinement or focused obligation:** a mapped lower-level behavior relation,
   or one adapter, effect, deadline, identity, or observation boundary.
3. **Controlled implementation trace:** forced event order at an implementation
   seam.
4. **External validation:** facts and effects supplied by the environment.
5. **Convergence observation:** a representative workflow reaching a stable
   terminal state.

Finite model checking is not implementation proof. A controlled test is not an
external-platform guarantee. A stable endpoint does not prove that no Safety
violation occurred during the transition.

## Evidence matrix

For a high-risk claim, the matrix records semantic alignment:

| Property | Model and witness | Implementation seam and test | External fact | Convergence | Status and remaining assumption |
|---|---|---|---|---|---|
| `<property>` | `<model/property/fault>` | `<controlled trace>` | `<scoped observation>` | `<stable terminal>` | `closed/scoped/unproved` |

Names alone do not establish alignment. Each cited artifact must use compatible
identity, reset, ownership, effect, and terminal semantics.

## Closure classes

- `closed`: every layer required by the scoped claim is present and
  semantically aligned;
- `scoped`: internal behavior is supported, while a platform, compatibility,
  identity, or timing claim is limited to a recorded environment;
- `drifted`: evidence was once aligned, but the current model contract,
  implementation, toolchain, or external environment no longer matches it;
- `blocked`: a prerequisite prevents the declared evidence from being
  collected, without establishing that the property passes or fails;
- `unproved`: a critical layer is missing, contradictory, vacuous, or based on
  an unjustified assumption.

Checked models, controlled traces, and scoped adapter facts can jointly cover an
internal scheduling boundary. An external operator does not need to reproduce
every scheduling instant when all three preserve the same transition semantics.

External evidence remains necessary for claims about:

- whether a platform emits or exposes a required fact;
- authorization and revocation lifecycle;
- identity stability and alias reuse;
- process, storage, network, or service behavior outside the implementation;
- version, hardware, topology, or deployment compatibility;
- latency and response-time bounds.

## Interactive-observation evidence

Reliable interactive evidence has a pre-armed observer, a stable baseline, a
defined cut point, a monotonic action marker when available, effect and cleanup
observations, and a declared stability window. Retained artifacts are scoped and
anonymized.

The timestamp of a user's confirmation message is not the timestamp of an
external event. Without a pre-armed monotonic observation, the evidence can
support eventual convergence but not a response-time bound.

## Counterexample-to-test relation

An important counterexample maps through this semantic chain:

```text
initial state
→ actor and action
→ authority, evidence, or effect change
→ forbidden result and violated property
→ implementation adapter or state transition
→ controlled test order
→ remaining external assumption
```

Adjacent happy-path tests do not cover a counterexample. A timeout test whose
adapter normally completes does not cover lost completion. A stale-result test
without distinct revisions or incarnations does not cover alias reuse. A
cleanup test in which the effect disappears normally does not cover retained
ownership.
