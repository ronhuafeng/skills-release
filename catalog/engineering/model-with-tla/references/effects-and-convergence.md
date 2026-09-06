# Effects and convergence

Effect modeling records what an operation changed, which authority owns the
change, and which terminal states remain truthful after cancellation or
failure.

## Effect ledger

An effect ledger describes:

| Field | Meaning |
|---|---|
| Point of no return | First point at which the environment can observe the effect |
| Cancelability | Whether execution can still stop or only its result can be ignored |
| Ownership evidence | Fact that proves responsibility for the effect |
| Compensation | Bounded action that can reduce or remove the effect |
| Residual effect | State that can remain after compensation or failure |
| Stable terminal | Truthful success, degraded, or responsibility-retaining state |
| Retry eligibility | Stage at which an attempt can be restored or repeated |

Compensation is not necessarily rollback. Some effects have no safe inverse,
and preserving a residual state can be safer than destructive restoration.

## Staged outcomes

An effectful adapter can expose stages such as:

```text
notStarted
effectStarted
ownedEffectCreated
cleanupConfirmed
cleanupUnknown
```

Names vary by domain. The stages distinguish whether a caller can retry, must
clean up, or must retain ownership. A single success/failure Boolean loses this
responsibility information.

Effect evidence must survive cancellation of ordinary result handling.
Cancellation records changed user or caller intent; it does not prove that an
adapter stopped, an effect disappeared, or ownership ended.

## Transaction phases

An external transaction can contain these observable phases:

```text
idle
→ executing
→ effectObserved
→ submittingResult
→ compensating
→ confirmingCleanup
→ cleanTerminal | responsibilityRetained
```

A phase is a distinct modeling boundary when it can block permanently or when
its intermediate state changes Safety, Liveness, authority, ownership,
deadline, cleanup, terminal meaning, or an observable interleaving. An immediate
failure with no decision-relevant intermediate state can remain a
nondeterministic result of one action. A promised transaction deadline covers
execution, result delivery, compensation, cleanup confirmation, and terminal
publication. Resetting a relative timeout at each phase does not establish one
end-to-end bound.

An unconfirmed cleanup preserves enough identity and ownership evidence for
supervision or an explicit responsibility-retaining failure. A command return
or expired deadline is not cleanup confirmation.

## Recovery meanings

- **Rollback** restores the prior state.
- **Compensation** performs a bounded corrective action.
- **Containment** prevents an uncertain or owned effect from creating more work.
- **Convergence** reaches a stable, explainable state.

These meanings are not interchangeable. A stable state can be degraded,
different from the prior state, or responsibility-retaining because cleanup is
uncertain.

Possible stable-terminal classes include:

```text
successful
safelyDeferred
policySuppressed
failedWithResponsibilityRetained
unknownAwaitingEvidence
```

The product contract determines which classes are acceptable.

## Invalidation cut-point template

The matrix records product decisions at effect boundaries:

| Invalidation source | Before effect | After effect, before result | After result, before commit | During cleanup |
|---|---|---|---|---|
| Identity or incarnation change | defer, invalidate, compensate, retain, or fail? | same decision set | same decision set | same decision set |
| Observation becomes unknown | defer, invalidate, compensate, retain, or fail? | same decision set | same decision set | same decision set |
| User intent changes | defer, invalidate, compensate, retain, or fail? | same decision set | same decision set | same decision set |
| Deadline expires | defer, invalidate, compensate, retain, or fail? | same decision set | same decision set | same decision set |
| Concurrent request arrives | defer, invalidate, compensate, retain, or fail? | same decision set | same decision set | same decision set |

Important cells correspond to TLA+ interleavings and controlled implementation
traces. The matrix supplies questions; the governing contract supplies answers.
