# Identity and epochs

Identity and epoch modeling distinguishes a logical target, one lifetime of a
resource, an observation, and an asynchronous operation. These distinctions
prevent delayed work or replacement resources from inheriting stale authority.

## Identity dimensions

- **Stable identity** names the logical target across observations.
- **Resource incarnation** identifies one lifetime of that target.
- **Observation revision** orders snapshots or query results.
- **Operation identity** binds one asynchronous transaction.
- **Attempt budget** records whether an eligible attempt was consumed.
- **Policy scope** identifies which target lifetime or operation a user
  intention controls.
- **Effect ownership** records responsibility for a resource created by an
  operation.

One integer or Boolean cannot safely represent several dimensions when they
have different reset or authority semantics.

## Reset-semantics template

Each event class requires product-specific answers. The table is a decision
template, not a default policy.

| Event class | Stable identity | Incarnation | Operation | Budget | Policy scope | Ownership |
|---|---|---|---|---|---|---|
| Fresh observation | preserve, replace, or unknown? | preserve, replace, or unknown? | preserve, invalidate, or replace? | preserve, consume, or restore? | preserve, replace, or clear? | preserve, acquire, release, or unknown? |
| Observation failure | preserve, replace, or unknown? | preserve, replace, or unknown? | preserve, invalidate, or replace? | preserve, consume, or restore? | preserve, replace, or clear? | preserve, acquire, release, or unknown? |
| Confirmed replacement | preserve, replace, or unknown? | preserve, replace, or unknown? | preserve, invalidate, or replace? | preserve, consume, or restore? | preserve, replace, or clear? | preserve, acquire, release, or unknown? |
| User policy change | preserve, replace, or unknown? | preserve, replace, or unknown? | preserve, invalidate, or replace? | preserve, consume, or restore? | preserve, replace, or clear? | preserve, acquire, release, or unknown? |
| Adapter completion | preserve, replace, or unknown? | preserve, replace, or unknown? | preserve, invalidate, or replace? | preserve, consume, or restore? | preserve, replace, or clear? | preserve, acquire, release, or unknown? |

The governing product contract supplies each answer and its evidence. An
uncertain, multiple, or stale observation does not by itself prove either
continuity or replacement.

## Delayed-result authority

An asynchronous result that can mutate product state carries enough authority
for a commit decision. Depending on the workflow, relevant fields include:

```text
result stable identity
result resource incarnation
result observation revision
result operation identity
current policy eligibility
current effect ownership
```

Failure of the commit gate rejects a state transition. It does not erase an
external effect that may already exist, so cleanup authority can outlive commit
authority.

## Aliases and reuse

Short names, numeric IDs, slots, paths, handles, and addresses can be reused by
external systems. They are aliases unless their lifecycle guarantee is verified.

A replacement action can preserve an alias while changing the resource
incarnation. Finite checks need enough values to distinguish an old resource,
the current resource, and a replacement when stale-result correctness depends
on reuse.

## Attempt-consumption boundary

Possible consumption boundaries include scheduling, starting an adapter call,
crossing an external point of no return, creating an owned effect, and
committing product state. The product contract selects one boundary.

Restoring a budget is safe only when the selected boundary was not crossed or
when the contract defines a compensating reset. Staged results preserve this
information better than a single success/failure Boolean.
