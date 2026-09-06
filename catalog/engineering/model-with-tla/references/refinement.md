# Refinement claims

Refinement connects behaviors at two abstraction levels. A lower-level model is
not a refinement merely because it preserves one invariant or reaches the same
final state.

## Claim classes

- **Focused obligation:** checks one named property without claiming that all
  lower-level behaviors implement the higher-level specification.
- **Finite-checked refinement:** checks a mapping or trace projection for named
  finite TLC configurations. The claim does not extend beyond those
  configurations.
- **Proved refinement:** establishes the declared refinement relation for the
  stated parameterized assumptions by proof, not only by finite model checking.

Use the weakest class supported by the evidence. A parameterized or unbounded
claim without a proof remains `unproved`, even when representative finite
configurations pass.

## Mapping lower-level behavior

A refinement mapping projects each lower-level state to a higher-level state.
Every lower-level step must project to an allowed higher-level step or to
stuttering, where the higher-level visible state does not change. Hide
lower-level variables that are not observable at the higher-level boundary.

A direct mapping can be insufficient when the higher-level state depends on
information distributed across several lower-level steps. Add an auxiliary
variable only when it is required by the declared relation:

- a **history variable** records relevant past behavior;
- a **prophecy variable** represents a future-dependent choice needed by the
  mapping;
- a **stuttering variable** aligns different step structures.

An auxiliary variable must not change the visible behaviors of the specification
it extends. Do not add one to make a model look more formal.

## Safety and progress

A Safety refinement does not automatically preserve Liveness. Check progress
separately, including the mapping of fairness assumptions, environment
enablement, and actions that may stutter or remain disabled.

For each refinement claim, record:

- the higher- and lower-level specifications;
- the mapping or trace projection;
- hidden and auxiliary variables;
- the treatment of each lower-level action;
- the Safety and Liveness obligations;
- the exact finite configurations checked or the proof performed;
- assumptions and behaviors outside the claim.

## Further reading

- [Hiding and refinement](https://lamport.azurewebsites.net/tla/hiding-and-refinement.pdf)
- [Auxiliary variables in TLA+](https://lamport.azurewebsites.net/pubs/auxiliary.pdf)
