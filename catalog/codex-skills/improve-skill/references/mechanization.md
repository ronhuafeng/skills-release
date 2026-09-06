# Mechanization Boundary

Mechanization fixes behavior in a program, interface, state machine, command sequence, or automatic
decision. Use it only to protect a repeated, deterministic, high-value invariant.

Using a tool to obtain evidence is not mechanization. Reading files, querying state, calling an API,
or running a validator does not require a fixed tool or sequence.

## Default to semantic judgment

Keep user intent, scope, evidence, ownership, ambiguity, and tradeoffs as semantic judgments. Use a
mechanism only for deterministic parsing, validation, identity binding, approved mutation, or
post-condition checks.

Prefer the highest-level supported interface that owns the target state and can prove the result. Do
not create another interface for uniform naming, test convenience, a hypothetical consumer, future
reuse, or a one-time command sequence.

## Decide whether to mechanize

Adopt or retain a mechanism only when all of these conditions hold:

1. Valid input has one correct result or a defined finite result set.
2. A repeated error or a concrete high-cost failure justifies reduced freedom.
3. The interface can own the path from intent-level input through effects and result verification.
4. The capability has a current recurring consumer and a long-term owner.

If removing the mechanism does not materially increase risk, delete it.

Structured parsing, schema validation, identity calculation, state binding, and approved
deterministic mutation can fit this boundary. User intent, artifact ownership, design tradeoffs, and
conflicting evidence remain semantic decisions.

## Require a complete interface

A stable interface must:

- accept intent-level input with domain-level output and errors;
- state the invariant it owns and verify the post-condition;
- for a mutation, bind the target identity and own side effects, partial failures, retry semantics,
  and readback;
- for a stateful operation, return the observed state, blockers, target identity, and verification;
- keep source paths, working directories, environments, package managers, and temporary artifacts
  out of the public contract;
- leave no critical safety or orchestration step for the caller to reconstruct.

A renamed wrapper, temporary script, or command that exposes low-level sequencing is not a stable
interface. If one entrypoint replaces another, remove the old entrypoint.

## Review an existing mechanism

Choose one result:

- **Delete:** The mechanism protects no independent invariant.
- **Deepen:** The capability is necessary, but the caller still owns internal sequencing or safety.
- **Keep:** The mechanism satisfies the adoption conditions and the complete interface contract.
- **Unknown:** The evidence is insufficient. Do not invent certainty or a replacement.

After changing the boundary, remove superseded commands, wrappers, references, and tests that
support only the old path.

## Verify responsibility

Verify that valid and invalid inputs follow the contract. For a mutation, verify that failed
preconditions do not write and that repeated or partial operations follow the public semantics. Do
not report success when the post-condition is false.

If behavior still requires judgment, use a realistic task without the design answer. Confirm that
the mechanism does not replace the required judgment.
